"""Internal MongoDB document types."""

from datetime import datetime
from typing import Any, NotRequired, TypedDict

from app.schema.chat_history_schema import ChatSpace, MessagePartKind, MessageRole


class MessagePartDocument(TypedDict):
    """Message part document stored in MongoDB."""

    part_seq: int
    kind: MessagePartKind
    payload: dict[str, Any]
    mcp_source: NotRequired[str | None]
    created_at: datetime


class ChatDocument(TypedDict):
    """Chat document stored in MongoDB."""

    user_id: str
    chat_id: str
    space: ChatSpace
    next_seq: int
    created_at: datetime
    updated_at: datetime
    title: NotRequired[str | None]
    scenario_id: NotRequired[str | int | None]
    project_id: NotRequired[str | int | None]
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


class ChatContextDocument(TypedDict):
    """Latest published context for one chat."""

    user_id: str
    chat_id: str
    revision: int
    content: dict[str, Any]
    updated_through_seq: int
    target_seq: int
    model: str
    prompt_version: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_error: NotRequired[str | None]


class ContextJobDocument(TypedDict):
    """Durable worker queue item."""

    job_id: str
    user_id: str
    chat_id: str
    target_seq: int
    model: str
    prompt_version: str
    status: str
    attempts: int
    lease_owner: NotRequired[str | None]
    lease_until: NotRequired[datetime | None]
    created_at: datetime
    updated_at: datetime
    last_error: NotRequired[str | None]
