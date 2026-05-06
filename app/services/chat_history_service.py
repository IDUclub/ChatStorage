"""Chat history persistence service."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.common.db.chat_history_document import (
    ChatDocument,
    MessageDocument,
    MessagePartDocument,
)
from app.dto.message_dto import (
    ChatCreateDTO,
    MessageCreateDTO,
)
from app.schema.chat_history_schema import (
    ChatListSchema,
    ChatSchema,
    ChatSummarySchema,
    ChatTitleListSchema,
    DeleteChatSchema,
    MessagePartSchema,
    MessageSchema,
)


class ChatHistoryService:
    """Service for loading and storing assistant chat history."""

    def __init__(self, database: AsyncDatabase):
        self._db = database
        self._chats = database["chats"]
        self._messages = database["messages"]

    async def create_chat(
        self,
        user_id: str,
        payload: ChatCreateDTO | None = None,
    ) -> ChatSummarySchema:
        """
        Create chat in MongoDB for user_id.
        Args:
            user_id (str): String repr of user uuid.
            payload (ChatCreateDTO | None): Chat creation data.
        Returns:
            ChatSummarySchema: Created chat.
        """

        payload = payload or ChatCreateDTO()
        now = self._now()
        document: ChatDocument = {
            "user_id": user_id,
            "chat_id": str(uuid4()),
            "title": payload.title,
            "scenario_id": payload.scenario_id,
            "metadata": payload.metadata,
            "next_seq": 1,
            "created_at": now,
            "updated_at": now,
        }

        try:
            await self._chats.insert_one(document)

        # TODO rewrite to internal exceptions
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chat id collision, please retry",
            ) from exc

        return self._chat_summary_from_document(document)

    async def add_message(
        self,
        user_id: str,
        chat_id: str,
        message: MessageCreateDTO,
    ) -> MessageSchema:
        """Add message to a user chat."""

        now = self._now()
        chat = await self._chats.find_one_and_update(
            {"user_id": user_id, "chat_id": chat_id},
            {"$inc": {"next_seq": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.BEFORE,
        )
        if not chat:
            raise self._not_found(chat_id)

        document: MessageDocument = {
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": str(uuid4()),
            "seq": chat["next_seq"],
            "role": message.role,
            "parts": self._build_parts(message, now),
            "metadata": message.metadata,
            "created_at": now,
            "updated_at": now,
        }

        try:
            await self._messages.insert_one(document)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Message sequence collision, please retry",
            ) from exc

        return self._message_from_document(document)

    async def get_chats(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> ChatListSchema:
        """Get user chats ordered by recent activity."""

        cursor = (
            self._chats.find({"user_id": user_id})
            .sort("updated_at", -1)
            .skip(offset)
            .limit(limit)
        )
        items = [
            self._chat_summary_from_document(document) async for document in cursor
        ]
        return ChatListSchema(items=items, limit=limit, offset=offset)

    async def get_unique_chat_titles(self, user_id: str) -> ChatTitleListSchema:
        """Get all unique non-empty chat titles for a user."""

        titles = await self._chats.distinct(
            "title",
            {
                "user_id": user_id,
                "title": {"$type": "string", "$ne": ""},
            },
        )
        return ChatTitleListSchema(items=sorted(titles))

    async def get_chat(self, user_id: str, chat_id: str) -> ChatSchema:
        """Get user chat with ordered messages."""

        chat = await self._chats.find_one({"user_id": user_id, "chat_id": chat_id})
        if not chat:
            raise self._not_found(chat_id)

        cursor = self._messages.find({"user_id": user_id, "chat_id": chat_id}).sort(
            "seq",
            1,
        )
        messages = [self._message_from_document(document) async for document in cursor]

        summary = self._chat_summary_from_document(chat)
        return ChatSchema(**summary.model_dump(), messages=messages)

    async def delete_chat(self, user_id: str, chat_id: str) -> DeleteChatSchema:
        """Delete user chat and all its messages."""

        result = await self._chats.delete_one({"user_id": user_id, "chat_id": chat_id})
        if result.deleted_count == 0:
            raise self._not_found(chat_id)

        message_result = await self._messages.delete_many(
            {"user_id": user_id, "chat_id": chat_id}
        )
        return DeleteChatSchema(
            chat_id=chat_id,
            deleted_messages=message_result.deleted_count,
        )

    async def get_message_part(
        self,
        user_id: str,
        chat_id: str,
        message_id: str,
        part_seq: int,
    ) -> MessagePartSchema:
        """Get one message part by id and sequence."""

        document = await self._messages.find_one(
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "parts.part_seq": part_seq,
            },
            {"parts.$": 1},
        )
        if not document or not document.get("parts"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message part not found",
            )
        return MessagePartSchema(**document["parts"][0])

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _not_found(chat_id: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found",
        )

    @staticmethod
    def _build_parts(
        message: MessageCreateDTO,
        created_at: datetime,
    ) -> list[MessagePartDocument]:
        if message.parts:
            return [
                {
                    "part_seq": index,
                    "kind": part.kind,
                    "payload": part.payload,
                    "created_at": created_at,
                }
                for index, part in enumerate(message.parts, start=1)
            ]

        return [
            {
                "part_seq": 1,
                "kind": "text",
                "payload": {"text": message.content},
                "created_at": created_at,
            }
        ]

    @staticmethod
    def _chat_summary_from_document(document: dict[str, Any]) -> ChatSummarySchema:
        return ChatSummarySchema(
            chat_id=document["chat_id"],
            title=document.get("title"),
            scenario_id=document.get("scenario_id"),
            metadata=document.get("metadata", {}),
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )

    @staticmethod
    def _message_from_document(document: dict[str, Any]) -> MessageSchema:
        return MessageSchema(
            message_id=document["message_id"],
            chat_id=document["chat_id"],
            seq=document["seq"],
            role=document["role"],
            parts=[MessagePartSchema(**part) for part in document["parts"]],
            metadata=document.get("metadata", {}),
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )
