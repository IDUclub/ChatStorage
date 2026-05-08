"""Internal MongoDB document types."""

from datetime import datetime
from typing import Any, NotRequired, TypedDict

from app.schema.chat_history_schema import MessagePartKind, MessageRole


class MessagePartDocument(TypedDict):
    """Message part document stored in MongoDB."""

    part_seq: int
    kind: MessagePartKind
    payload: dict[str, Any]
    created_at: datetime


class ChatDocument(TypedDict):
    """Chat document stored in MongoDB."""

    user_id: str
    chat_id: str
    next_seq: int
    created_at: datetime
    updated_at: datetime
    title: NotRequired[str | None]
    scenario_id: NotRequired[str | int | None]
    metadata: NotRequired[dict[str, Any]]


class MessageDocument(TypedDict):
    """Message document stored in MongoDB."""

    user_id: str
    chat_id: str
    message_id: str
    seq: int
    role: MessageRole
    parts: list[MessagePartDocument]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
