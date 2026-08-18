"""Unit coverage for backwards chat-message pagination."""

from datetime import UTC, datetime

import pytest

from app.services.chat_history_service import ChatHistoryService


class FakeCursor:
    def __init__(self, documents: list[dict]):
        self.documents = list(documents)
        self.index = 0

    def sort(self, field: str, direction: int):
        self.documents.sort(key=lambda document: document[field], reverse=direction < 0)
        return self

    def limit(self, value: int):
        self.documents = self.documents[:value]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.documents):
            raise StopAsyncIteration
        document = self.documents[self.index]
        self.index += 1
        return document


class FakeCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    async def find_one(self, query: dict):
        return next(
            (
                document
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )

    def find(self, query: dict):
        def matches(document: dict) -> bool:
            for key, value in query.items():
                if isinstance(value, dict) and "$lt" in value:
                    if document.get(key, 0) >= value["$lt"]:
                        return False
                elif document.get(key) != value:
                    return False
            return True

        return FakeCursor(
            [document for document in self.documents if matches(document)]
        )


class FakeDatabase:
    def __init__(self, chats: list[dict], messages: list[dict]):
        self.collections = {
            "chats": FakeCollection(chats),
            "messages": FakeCollection(messages),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


@pytest.mark.asyncio
async def test_get_chat_returns_latest_page_and_backwards_cursor() -> None:
    now = datetime.now(UTC)
    chat = {
        "user_id": "user",
        "chat_id": "chat",
        "title": "Paged",
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    messages = [
        {
            "user_id": "user",
            "chat_id": "chat",
            "message_id": f"message-{seq}",
            "seq": seq,
            "role": "user",
            "parts": [
                {
                    "part_seq": 1,
                    "kind": "text",
                    "payload": {"text": str(seq)},
                    "created_at": now,
                }
            ],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
        for seq in range(1, 6)
    ]
    service = ChatHistoryService(FakeDatabase([chat], messages))  # type: ignore[arg-type]

    latest = await service.get_chat("user", "chat", message_limit=2)
    previous = await service.get_chat(
        "user", "chat", message_limit=2, before_seq=latest.next_before_seq
    )

    assert [message.seq for message in latest.messages] == [4, 5]
    assert latest.has_more is True
    assert latest.next_before_seq == 4
    assert [message.seq for message in previous.messages] == [2, 3]
    assert previous.has_more is True
    assert previous.next_before_seq == 2
