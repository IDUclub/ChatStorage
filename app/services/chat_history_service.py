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
    ToolCallDTO,
    ToolCallExtractDTO,
)
from app.schema.chat_history_schema import (
    ChatListSchema,
    ChatSchema,
    ChatSummarySchema,
    ChatTitleListSchema,
    DeleteChatSchema,
    MessagePartSchema,
    MessageSchema,
    ToolCallExecutionStepSchema,
    ToolCallExtractSchema,
    ToolCallSchema,
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
            "project_id": payload.project_id,
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
        scenario_id: str | None = None,
        project_id: str | None = None,
    ) -> ChatListSchema:
        """Get user chats ordered by recent activity, newest first."""

        query: dict[str, Any] = {"user_id": user_id}
        if scenario_id is not None:
            query["scenario_id"] = {"$in": self._filter_candidates(scenario_id)}
        if project_id is not None:
            query["project_id"] = {"$in": self._filter_candidates(project_id)}

        cursor = (
            self._chats.find(query).sort("updated_at", -1).skip(offset).limit(limit)
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

    async def get_chat(
        self,
        user_id: str,
        chat_id: str,
        message_limit: int | None = None,
        before_seq: int | None = None,
    ) -> ChatSchema:
        """Get a user chat with an optional backwards page of ordered messages."""

        chat = await self._chats.find_one({"user_id": user_id, "chat_id": chat_id})
        if not chat:
            raise self._not_found(chat_id)

        message_filter: dict[str, Any] = {"user_id": user_id, "chat_id": chat_id}
        if before_seq is not None:
            message_filter["seq"] = {"$lt": before_seq}

        if message_limit is None:
            cursor = self._messages.find(message_filter).sort("seq", 1)
            documents = [document async for document in cursor]
            has_more = False
        else:
            cursor = (
                self._messages.find(message_filter)
                .sort("seq", -1)
                .limit(message_limit + 1)
            )
            documents = [document async for document in cursor]
            has_more = len(documents) > message_limit
            documents = documents[:message_limit]
            documents.reverse()

        messages = [self._message_from_document(document) for document in documents]
        next_before_seq = messages[0].seq if has_more and messages else None

        summary = self._chat_summary_from_document(chat)
        return ChatSchema(
            **summary.model_dump(),
            messages=messages,
            has_more=has_more,
            next_before_seq=next_before_seq,
        )

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

    async def extract_tool_call_chain(
        self,
        payload: ToolCallExtractDTO,
    ) -> ToolCallExtractSchema:
        """Prepare previous tool calls required to execute the target tool call."""

        previous_steps = [
            self._tool_call_step_from_dto(tool_call)
            for tool_call in payload.previous_tool_calls
        ]
        target_step = self._tool_call_step_from_dto(payload.tool_call)
        all_steps = [*previous_steps, target_step]

        providers: dict[str, int] = {}
        provides_by_step: dict[int, list[str]] = {}
        for index, step in enumerate(all_steps):
            provided_refs = self._provided_refs(step.tool_call)
            provides_by_step[index] = provided_refs
            for provided_ref in provided_refs:
                providers.setdefault(self._normalize_ref(provided_ref), index)

        dependencies_by_step: dict[int, list[int]] = {}
        for index, step in enumerate(all_steps):
            required_refs = self._required_refs(step.tool_call)
            dependencies: list[int] = []
            for required_ref in required_refs:
                provider_index = providers.get(self._normalize_ref(required_ref))
                if provider_index is not None and provider_index < index:
                    self._append_unique_int(dependencies, provider_index)
            dependencies_by_step[index] = dependencies

        chain_indexes = self._collect_required_step_indexes(
            len(all_steps) - 1,
            dependencies_by_step,
        )
        missing_dependencies: set[str] = set()
        for index in chain_indexes:
            for required_ref in self._required_refs(all_steps[index].tool_call):
                provider_index = providers.get(self._normalize_ref(required_ref))
                if provider_index is None or provider_index >= index:
                    missing_dependencies.add(required_ref)

        execution_chain = [
            ToolCallExecutionStepSchema(
                order=order,
                tool_call=all_steps[index].tool_call,
                depends_on=[
                    chain_indexes.index(dependency) + 1
                    for dependency in dependencies_by_step[index]
                    if dependency in chain_indexes
                ],
                requires=self._required_refs(all_steps[index].tool_call),
                provides=provides_by_step[index],
            )
            for order, index in enumerate(chain_indexes, start=1)
        ]

        return ToolCallExtractSchema(
            target=target_step.tool_call,
            execution_chain=execution_chain,
            missing_dependencies=sorted(missing_dependencies),
        )

    async def build_tool_call_extract_payload(
        self,
        user_id: str,
        message_id: str,
        part_seq: int,
        tool_call_step: int,
        scenario_id: int | None = None,
        project_id: int | None = None,
    ) -> ToolCallExtractDTO:
        """Build executable tool call payload from a stored message."""

        target_message = await self._messages.find_one(
            {"user_id": user_id, "message_id": message_id}
        )
        if not target_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        previous_tool_calls: list[ToolCallDTO] = []
        cursor = self._messages.find(
            {
                "user_id": user_id,
                "chat_id": target_message["chat_id"],
                "seq": {"$lt": target_message["seq"]},
                "parts.kind": "tool_call",
            }
        ).sort("seq", 1)
        async for message in cursor:
            previous_tool_calls.extend(self._tool_calls_from_message(message))

        previous_tool_calls.extend(
            self._tool_calls_from_message(
                target_message,
                before_part_seq=part_seq,
            )
        )

        target_part = self._tool_call_part_from_message(target_message, part_seq)
        if target_part is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool call part {part_seq} not found",
            )

        target_tool_call: ToolCallDTO | None = None
        for tool_call in self._tool_calls_from_part(target_part):
            if tool_call.step == tool_call_step:
                target_tool_call = tool_call
                break

        if target_tool_call is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool call step {tool_call_step} not found in part {part_seq}",
            )

        return ToolCallExtractDTO(
            tool_call=target_tool_call,
            previous_tool_calls=previous_tool_calls,
            scenario_id=await self._resolve_int_field(
                target_message, scenario_id, "scenario_id"
            ),
            project_id=await self._resolve_int_field(
                target_message, project_id, "project_id"
            ),
            mcp_source=target_part.get("mcp_source"),
        )

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
            parts: list[MessagePartDocument] = []
            for index, part in enumerate(message.parts, start=1):
                doc: MessagePartDocument = {
                    "part_seq": index,
                    "kind": part.kind,
                    "payload": part.payload,
                    "created_at": created_at,
                }
                if part.mcp_source is not None:
                    doc["mcp_source"] = part.mcp_source
                parts.append(doc)
            return parts

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
            project_id=document.get("project_id"),
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

    async def _resolve_int_field(
        self,
        message: dict[str, Any],
        explicit_value: int | None,
        field: str,
    ) -> int | None:
        """Resolve an int field from explicit value, message metadata, then chat."""

        if explicit_value is not None:
            return explicit_value

        metadata = message.get("metadata", {})
        resolved_value = metadata.get(field)
        if resolved_value is None:
            chat = await self._chats.find_one(
                {
                    "user_id": message["user_id"],
                    "chat_id": message["chat_id"],
                },
                {field: 1},
            )
            resolved_value = chat.get(field) if chat else None

        try:
            return int(resolved_value) if resolved_value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _tool_calls_from_message(
        cls,
        message: dict[str, Any],
        before_part_seq: int | None = None,
    ) -> list[ToolCallDTO]:
        tool_calls: list[ToolCallDTO] = []
        for part in message.get("parts", []):
            if part.get("kind") != "tool_call":
                continue
            if before_part_seq is not None and part.get("part_seq") >= before_part_seq:
                continue
            tool_calls.extend(cls._tool_calls_from_part(part))
        return sorted(tool_calls, key=lambda tool_call: tool_call.step or 0)

    @staticmethod
    def _tool_call_part_from_message(
        message: dict[str, Any],
        part_seq: int,
    ) -> dict[str, Any] | None:
        for part in message.get("parts", []):
            if part.get("kind") == "tool_call" and part.get("part_seq") == part_seq:
                return part
        return None

    @classmethod
    def _tool_calls_from_part(cls, part: dict[str, Any]) -> list[ToolCallDTO]:
        payload = part.get("payload") or {}
        calls = payload.get("calls") or payload.get("tool_calls") or []
        return [
            cls._tool_call_from_payload(call, index)
            for index, call in enumerate(calls, start=1)
        ]

    @staticmethod
    def _tool_call_from_payload(
        payload: dict[str, Any],
        fallback_step: int,
    ) -> ToolCallDTO:
        function_call = payload.get("function") or {}
        tool_name = (
            payload.get("tool_name") or payload.get("name") or function_call.get("name")
        )
        arguments = payload.get("arguments") or function_call.get("arguments") or {}
        if not tool_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Tool call without tool name: {payload}",
            )
        return ToolCallDTO(
            step=payload.get("step") or fallback_step,
            tool_name=tool_name,
            arguments=arguments,
        )

    @staticmethod
    def _tool_call_step_from_dto(tool_call: ToolCallDTO) -> ToolCallExecutionStepSchema:
        return ToolCallExecutionStepSchema(
            order=tool_call.step or 0,
            tool_call=ToolCallSchema(
                step=tool_call.step,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
            ),
        )

    @classmethod
    def _provided_refs(cls, tool_call: ToolCallSchema) -> list[str]:
        arguments = tool_call.arguments
        if tool_call.tool_name == "GetServices":
            return cls._string_list(arguments.get("services_names"))

        if tool_call.tool_name == "GetPhysicalObjects":
            return cls._string_list(arguments.get("physical_objects_names"))

        if tool_call.tool_name == "CreateBuffers":
            buffer_info = arguments.get("buffer_info")
            if not isinstance(buffer_info, dict):
                return []
            refs: list[str] = []
            for source_name, info in buffer_info.items():
                cls._append_unique_str(refs, str(source_name))
                if isinstance(info, dict) and info.get("title"):
                    cls._append_unique_str(refs, str(info["title"]))
            return refs

        return cls._collect_string_refs(arguments)

    @classmethod
    def _required_refs(cls, tool_call: ToolCallSchema) -> list[str]:
        arguments = tool_call.arguments
        if tool_call.tool_name == "CreateBuffers":
            buffer_info = arguments.get("buffer_info")
            if isinstance(buffer_info, dict):
                return [str(name) for name in buffer_info]
            return []

        if tool_call.tool_name == "CreateRestrictions":
            refs: list[str] = []
            for ref in cls._string_list(arguments.get("generators")):
                cls._append_unique_str(refs, ref)
            for ref in cls._string_list(arguments.get("objects")):
                cls._append_unique_str(refs, ref)

            restrictions = arguments.get("restrictions")
            if isinstance(restrictions, dict):
                for generator_name, restriction in restrictions.items():
                    cls._append_unique_str(refs, str(generator_name))
                    if isinstance(restriction, dict):
                        for ref in cls._string_list(restriction.get("to")):
                            cls._append_unique_str(refs, ref)
            return refs

        explicit_dependencies = arguments.get("depends_on") or arguments.get("requires")
        return cls._string_list(explicit_dependencies)

    @classmethod
    def _collect_required_step_indexes(
        cls,
        target_index: int,
        dependencies_by_step: dict[int, list[int]],
    ) -> list[int]:
        result: list[int] = []
        visited: set[int] = set()

        def visit(index: int) -> None:
            if index in visited:
                return
            visited.add(index)
            for dependency_index in dependencies_by_step.get(index, []):
                visit(dependency_index)
            result.append(index)

        visit(target_index)
        return result

    @classmethod
    def _collect_string_refs(cls, value: Any) -> list[str]:
        refs: list[str] = []
        if isinstance(value, str):
            cls._append_unique_str(refs, value)
            return refs
        if isinstance(value, dict):
            for item_key, item_value in value.items():
                cls._append_unique_str(refs, str(item_key))
                for ref in cls._collect_string_refs(item_value):
                    cls._append_unique_str(refs, ref)
        if isinstance(value, list):
            for item in value:
                for ref in cls._collect_string_refs(item):
                    cls._append_unique_str(refs, ref)
        return refs

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    @staticmethod
    def _filter_candidates(value: str) -> list[str | int]:
        """Match a stored id filter against both string and int representations."""

        candidates: list[str | int] = [value]
        try:
            candidates.append(int(value))
        except (TypeError, ValueError):
            pass
        return candidates

    @staticmethod
    def _normalize_ref(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _append_unique_str(items: list[str], item: str) -> None:
        if item not in items:
            items.append(item)

    @staticmethod
    def _append_unique_int(items: list[int], item: int) -> None:
        if item not in items:
            items.append(item)
