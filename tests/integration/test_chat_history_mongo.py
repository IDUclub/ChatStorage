"""Integration tests for ChatHistoryService against a live MongoDB.

Skipped automatically unless ``TEST_MONGO_URL`` points at a reachable server
(see tests/conftest.py).
"""

from uuid import uuid4

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.dto.message_dto import (
    ChatCreateDTO,
    MessageCreateDTO,
    MessagePartCreateDTO,
)
from app.services.chat_history_service import ChatHistoryService

pytestmark = pytest.mark.integration

FILE_PAYLOAD = {
    "url": "https://files.example.org/reports/effects.docx",
    "filename": "effects.docx",
    "mime_type": "application/octet-stream",
    "size_bytes": 1024,
    "source_service": "ObjectEffectsAPI",
}


def _user_id() -> str:
    return str(uuid4())


@pytest.fixture
def service(mongo_database: AsyncDatabase) -> ChatHistoryService:
    return ChatHistoryService(mongo_database)


async def test_create_and_get_chat(service: ChatHistoryService) -> None:
    user_id = _user_id()
    created = await service.create_chat(
        user_id, ChatCreateDTO(title="My chat", scenario_id="772", project_id=42)
    )

    fetched = await service.get_chat(user_id, created.chat_id)

    assert fetched.chat_id == created.chat_id
    assert fetched.title == "My chat"
    assert fetched.messages == []


async def test_get_chat_unknown_id_raises_404(service: ChatHistoryService) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.get_chat(_user_id(), str(uuid4()))

    assert exc_info.value.status_code == 404


async def test_get_chat_pages_backwards_from_latest(
    service: ChatHistoryService,
) -> None:
    user_id = _user_id()
    chat = await service.create_chat(user_id)
    for index in range(1, 6):
        await service.add_message(
            user_id,
            chat.chat_id,
            MessageCreateDTO(role="user", content=f"message-{index}"),
        )

    latest = await service.get_chat(user_id, chat.chat_id, message_limit=2)
    previous = await service.get_chat(
        user_id,
        chat.chat_id,
        message_limit=2,
        before_seq=latest.next_before_seq,
    )
    oldest = await service.get_chat(
        user_id,
        chat.chat_id,
        message_limit=2,
        before_seq=previous.next_before_seq,
    )

    assert [message.seq for message in latest.messages] == [4, 5]
    assert latest.has_more is True
    assert latest.next_before_seq == 4
    assert [message.seq for message in previous.messages] == [2, 3]
    assert previous.has_more is True
    assert previous.next_before_seq == 2
    assert [message.seq for message in oldest.messages] == [1]
    assert oldest.has_more is False
    assert oldest.next_before_seq is None


async def test_add_text_message_increments_seq(service: ChatHistoryService) -> None:
    user_id = _user_id()
    chat = await service.create_chat(user_id)

    first = await service.add_message(
        user_id, chat.chat_id, MessageCreateDTO(role="user", content="hi")
    )
    second = await service.add_message(
        user_id, chat.chat_id, MessageCreateDTO(role="assistant", content="hello")
    )

    assert first.seq == 1
    assert second.seq == 2
    assert first.parts[0].kind == "text"
    assert first.parts[0].payload == {"text": "hi"}


async def test_add_file_message_persists(service: ChatHistoryService) -> None:
    """A file part round-trips through the strict Mongo validator and back."""

    user_id = _user_id()
    chat = await service.create_chat(user_id)

    message = await service.add_message(
        user_id,
        chat.chat_id,
        MessageCreateDTO(
            role="assistant",
            parts=[
                MessagePartCreateDTO(kind="text", payload={"text": "Report ready."}),
                MessagePartCreateDTO(kind="file", payload=FILE_PAYLOAD),
            ],
        ),
    )

    fetched = await service.get_chat(user_id, chat.chat_id)
    stored_part = fetched.messages[0].parts[1]

    assert message.parts[1].kind == "file"
    assert stored_part.kind == "file"
    assert stored_part.payload["url"] == FILE_PAYLOAD["url"]
    assert stored_part.payload["filename"] == "effects.docx"


async def test_validator_rejects_unknown_kind(
    mongo_database: AsyncDatabase,
) -> None:
    """The schema only allows the documented part kinds."""

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with pytest.raises(PyMongoError):
        await mongo_database["messages"].insert_one(
            {
                "user_id": _user_id(),
                "chat_id": str(uuid4()),
                "message_id": str(uuid4()),
                "seq": 1,
                "role": "assistant",
                "parts": [
                    {
                        "part_seq": 1,
                        "kind": "bogus",
                        "payload": {"x": 1},
                        "created_at": now,
                    }
                ],
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            }
        )


async def test_get_chats_filters_by_scenario(service: ChatHistoryService) -> None:
    user_id = _user_id()
    await service.create_chat(user_id, ChatCreateDTO(scenario_id="772"))
    await service.create_chat(user_id, ChatCreateDTO(scenario_id="999"))

    result = await service.get_chats(user_id, scenario_id="772")

    assert len(result.items) == 1
    assert result.items[0].scenario_id == "772"


async def test_get_message_part(service: ChatHistoryService) -> None:
    user_id = _user_id()
    chat = await service.create_chat(user_id)
    message = await service.add_message(
        user_id,
        chat.chat_id,
        MessageCreateDTO(
            role="assistant",
            parts=[MessagePartCreateDTO(kind="file", payload=FILE_PAYLOAD)],
        ),
    )

    part = await service.get_message_part(
        user_id, chat.chat_id, message.message_id, part_seq=1
    )

    assert part.kind == "file"
    assert part.payload["url"] == FILE_PAYLOAD["url"]


async def test_delete_chat_removes_messages(service: ChatHistoryService) -> None:
    user_id = _user_id()
    chat = await service.create_chat(user_id)
    await service.add_message(
        user_id, chat.chat_id, MessageCreateDTO(role="user", content="hi")
    )

    result = await service.delete_chat(user_id, chat.chat_id)

    assert result.deleted_messages == 1
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await service.get_chat(user_id, chat.chat_id)


async def test_build_tool_call_extract_payload(service: ChatHistoryService) -> None:
    user_id = _user_id()
    chat = await service.create_chat(user_id, ChatCreateDTO(scenario_id="772"))
    message = await service.add_message(
        user_id,
        chat.chat_id,
        MessageCreateDTO(
            role="assistant",
            parts=[
                MessagePartCreateDTO(
                    kind="tool_call",
                    payload={
                        "calls": [
                            {
                                "step": 1,
                                "tool_name": "GetServices",
                                "arguments": {"services_names": ["school"]},
                            }
                        ]
                    },
                )
            ],
        ),
    )

    payload = await service.build_tool_call_extract_payload(
        user_id=user_id,
        message_id=message.message_id,
        part_seq=1,
        tool_call_step=1,
    )

    assert payload.tool_call.tool_name == "GetServices"
    assert payload.tool_call.arguments == {"services_names": ["school"]}
    # scenario_id resolved from the chat when not passed explicitly.
    assert payload.scenario_id == 772


async def test_chats_are_isolated_per_space(service: ChatHistoryService) -> None:
    user_id = _user_id()
    main_chat = await service.create_chat(user_id, ChatCreateDTO(title="Main chat"))
    synapse_chat = await service.create_chat(
        user_id, ChatCreateDTO(title="Synapse chat", space="synapse")
    )

    main = await service.get_chats(user_id)
    synapse = await service.get_chats(user_id, space="synapse")

    assert [item.chat_id for item in main.items] == [main_chat.chat_id]
    assert main.items[0].space == "main"
    assert [item.chat_id for item in synapse.items] == [synapse_chat.chat_id]
    assert synapse.items[0].space == "synapse"


async def test_source_event_id_makes_message_creation_idempotent(
    service: ChatHistoryService,
) -> None:
    user_id = str(uuid4())
    chat = await service.create_chat(
        user_id, ChatCreateDTO(title="Synapse chat", space="synapse")
    )
    payload = MessageCreateDTO(
        role="system",
        content="delegation completed",
        source_event_id="01991d22-7a04-7d93-9900-cc95d8db4f47",
    )

    first = await service.add_message(user_id, chat.chat_id, payload, space="synapse")
    repeated = await service.add_message(
        user_id, chat.chat_id, payload, space="synapse"
    )

    assert repeated.message_id == first.message_id
    assert repeated.seq == first.seq
    assert repeated.source_event_id == payload.source_event_id


async def test_chat_titles_are_isolated_per_space(service: ChatHistoryService) -> None:
    user_id = _user_id()
    await service.create_chat(user_id, ChatCreateDTO(title="Main chat"))
    await service.create_chat(
        user_id, ChatCreateDTO(title="Synapse chat", space="synapse")
    )

    main = await service.get_unique_chat_titles(user_id)
    synapse = await service.get_unique_chat_titles(user_id, space="synapse")

    assert main.items == ["Main chat"]
    assert synapse.items == ["Synapse chat"]


async def test_chat_reads_from_another_space_raise_404(
    service: ChatHistoryService,
) -> None:
    from fastapi import HTTPException

    user_id = _user_id()
    chat = await service.create_chat(user_id, ChatCreateDTO(space="synapse"))
    message = await service.add_message(
        user_id,
        chat.chat_id,
        MessageCreateDTO(role="user", content="hi"),
        space="synapse",
    )

    with pytest.raises(HTTPException) as chat_error:
        await service.get_chat(user_id, chat.chat_id)
    with pytest.raises(HTTPException) as part_error:
        await service.get_message_part(
            user_id, chat.chat_id, message.message_id, part_seq=1
        )

    assert chat_error.value.status_code == 404
    assert part_error.value.status_code == 404


async def test_chat_writes_from_another_space_raise_404(
    service: ChatHistoryService,
) -> None:
    from fastapi import HTTPException

    user_id = _user_id()
    chat = await service.create_chat(user_id, ChatCreateDTO(space="synapse"))

    with pytest.raises(HTTPException) as message_error:
        await service.add_message(
            user_id, chat.chat_id, MessageCreateDTO(role="user", content="hi")
        )
    with pytest.raises(HTTPException) as delete_error:
        await service.delete_chat(user_id, chat.chat_id)

    assert message_error.value.status_code == 404
    assert delete_error.value.status_code == 404
    # The chat survived both rejected calls inside its own space.
    assert (await service.get_chat(user_id, chat.chat_id, space="synapse")).chat_id


async def test_tool_call_payload_rejects_another_space(
    service: ChatHistoryService,
) -> None:
    from fastapi import HTTPException

    user_id = _user_id()
    chat = await service.create_chat(user_id, ChatCreateDTO(space="synapse"))
    message = await service.add_message(
        user_id,
        chat.chat_id,
        MessageCreateDTO(
            role="assistant",
            parts=[
                MessagePartCreateDTO(
                    kind="tool_call",
                    payload={
                        "calls": [
                            {
                                "step": 1,
                                "tool_name": "GetServices",
                                "arguments": {"services_names": ["school"]},
                            }
                        ]
                    },
                )
            ],
        ),
        space="synapse",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.build_tool_call_extract_payload(
            user_id=user_id,
            message_id=message.message_id,
            part_seq=1,
            tool_call_step=1,
        )

    assert exc_info.value.status_code == 404
    payload = await service.build_tool_call_extract_payload(
        user_id=user_id,
        message_id=message.message_id,
        part_seq=1,
        tool_call_step=1,
        space="synapse",
    )
    assert payload.tool_call.tool_name == "GetServices"


async def test_count_chats_by_space(service: ChatHistoryService) -> None:
    user_id = _user_id()
    await service.create_chat(user_id)
    await service.create_chat(user_id)
    await service.create_chat(user_id, ChatCreateDTO(space="synapse"))

    assert await service.count_chats_by_space(user_id) == {"main": 2, "synapse": 1}


async def test_validator_rejects_unknown_space(mongo_database: AsyncDatabase) -> None:
    """The chats schema only allows the registered spaces."""

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with pytest.raises(PyMongoError):
        await mongo_database["chats"].insert_one(
            {
                "user_id": _user_id(),
                "chat_id": str(uuid4()),
                "space": "matrix",
                "next_seq": 1,
                "created_at": now,
                "updated_at": now,
            }
        )
