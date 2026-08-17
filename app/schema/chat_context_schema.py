"""Schemas for durable, asynchronously refreshed chat context."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schema.chat_history_schema import MessageSchema

ContextJobStatus = Literal["pending", "leased", "completed", "failed"]


class ChatContextContentSchema(BaseModel):
    """Both representations consumed by scenario-data agents."""

    summary: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)


class ChatContextSchema(BaseModel):
    """Published context plus the messages not covered by it yet."""

    chat_id: str
    revision: int = 0
    content: ChatContextContentSchema = Field(default_factory=ChatContextContentSchema)
    updated_through_seq: int = 0
    target_seq: int = 0
    model: str | None = None
    prompt_version: str | None = None
    status: str = "empty"
    updated_at: datetime | None = None
    tail: list[MessageSchema] = Field(default_factory=list)
    tail_has_more: bool = False
    tail_next_after_seq: int | None = None


class ContextJobCreateSchema(BaseModel):
    """Request to refresh context through a stable message sequence."""

    target_seq: int | None = Field(default=None, ge=1)
    model: str = Field(default="gpt-oss-20b", min_length=1)
    prompt_version: str = Field(default="scenario-data-v1", min_length=1)


class ContextJobSchema(BaseModel):
    """Durable context job returned to producers and workers."""

    job_id: str
    user_id: str
    chat_id: str
    target_seq: int
    model: str
    prompt_version: str
    status: ContextJobStatus
    attempts: int = 0
    lease_owner: str | None = None
    lease_until: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None


class ContextJobClaimSchema(BaseModel):
    """Worker lease request."""

    worker_id: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=120, ge=30, le=600)


class ContextJobCompletionSchema(BaseModel):
    """CAS-protected context publication request."""

    worker_id: str = Field(min_length=1, max_length=128)
    content: ChatContextContentSchema


class ContextJobFailureSchema(BaseModel):
    """Worker failure report; retry remains bounded by the service."""

    worker_id: str = Field(min_length=1, max_length=128)
    error: str = Field(min_length=1, max_length=2000)
