"""Chat history output schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant", "system", "tool"]
MessagePartKind = Literal["text", "tool_call", "tool_result", "status", "data"]


class MessagePartSchema(BaseModel):
    """Message part returned to client."""

    part_seq: int
    kind: MessagePartKind
    payload: dict[str, Any]
    created_at: datetime


class MessageSchema(BaseModel):
    """Message returned to client."""

    message_id: str
    chat_id: str
    seq: int
    role: MessageRole
    parts: list[MessagePartSchema]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChatSummarySchema(BaseModel):
    """Chat summary returned in chat lists."""

    chat_id: str
    title: str | None = None
    scenario_id: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChatSchema(ChatSummarySchema):
    """Full chat with messages."""

    messages: list[MessageSchema] = Field(default_factory=list)


class ChatListSchema(BaseModel):
    """Paginated chat list."""

    items: list[ChatSummarySchema]
    limit: int
    offset: int


class DeleteChatSchema(BaseModel):
    """Delete chat result."""

    chat_id: str
    deleted_messages: int
