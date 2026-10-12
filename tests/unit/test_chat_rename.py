"""Renaming a chat: payload validation and the PATCH route."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.depndencies.auth_dependencies import get_current_user_id
from app.depndencies.dependencies import get_chat_history_service
from app.dto.message_dto import ChatUpdateDTO
from app.main import app
from app.schema.chat_history_schema import ChatSummarySchema

CHAT_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"


def test_title_is_stripped() -> None:
    assert ChatUpdateDTO(title="  Нормы озеленения  ").title == "Нормы озеленения"


@pytest.mark.parametrize("title", ["", "   ", "x" * 257])
def test_blank_or_long_title_is_rejected(title: str) -> None:
    with pytest.raises(ValueError):
        ChatUpdateDTO(title=title)


class _Service:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def rename_chat(self, **kwargs) -> ChatSummarySchema:
        self.calls.append(kwargs)
        now = datetime.now(UTC)
        return ChatSummarySchema(
            chat_id=kwargs["chat_id"],
            space=kwargs["space"],
            title=kwargs["payload"].title,
            created_at=now,
            updated_at=now,
        )


def test_patch_renames_the_callers_chat() -> None:
    service = _Service()
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_chat_history_service] = lambda: service
    try:
        response = TestClient(app).patch(
            f"/api/v1/chat_history/{CHAT_ID}?space=main",
            json={"title": "Нормы озеленения"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_chat_history_service, None)
    assert response.status_code == 200
    assert response.json()["title"] == "Нормы озеленения"
    (call,) = service.calls
    assert call["user_id"] == "user-1" and call["chat_id"] == CHAT_ID
    assert call["space"] == "main"
