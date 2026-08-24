"""Chat history output schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant", "system", "tool"]
ChatSpace = Literal["main", "synapse"]
DEFAULT_CHAT_SPACE: ChatSpace = "main"

MessagePartKind = Literal[
    "text",
    "tool_call",
    "tool_result",
    "status",
    "data",
    "table",
    "file",
    "plan",
    "plan_revision",
    "artifact_ref",
    "validation",
    "failure",
    "check_plan",
    "requirement_resolution",
    "compliance_result",
    "compliance_summary",
]


class MessagePartSchema(BaseModel):
    """Message part returned to client."""

    part_seq: int
    kind: MessagePartKind
    payload: dict[str, Any]
    mcp_source: str | None = None
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
    space: ChatSpace = DEFAULT_CHAT_SPACE
    title: str | None = None
    scenario_id: str | int | None = None
    project_id: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChatSchema(ChatSummarySchema):
    """Full chat with messages."""

    messages: list[MessageSchema] = Field(default_factory=list)
    has_more: bool = False
    next_before_seq: int | None = None


class ChatListSchema(BaseModel):
    """Paginated chat list."""

    items: list[ChatSummarySchema]
    limit: int
    offset: int


class ChatTitleListSchema(BaseModel):
    """Unique chat titles for a user."""

    items: list[str]


class DeleteChatSchema(BaseModel):
    """Delete chat result."""

    chat_id: str
    deleted_messages: int


class ToolCallSchema(BaseModel):
    """Tool call returned to clients."""

    step: int | None = None
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallExecutionStepSchema(BaseModel):
    """Executable tool call with dependency metadata."""

    order: int
    tool_call: ToolCallSchema
    depends_on: list[int] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)


class ToolCallExtractSchema(BaseModel):
    """Prepared tool call execution chain."""

    target: ToolCallSchema
    execution_chain: list[ToolCallExecutionStepSchema]
    missing_dependencies: list[str] = Field(default_factory=list)


class ToolCallResultStepSchema(BaseModel):
    """Result of one executed tool call."""

    order: int
    tool_call: ToolCallSchema
    meta: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any]


class ToolCallExecutionResultSchema(ToolCallExtractSchema):
    """Executed tool call chain with final result."""

    steps: list[ToolCallResultStepSchema] = Field(default_factory=list)
    result: dict[str, Any] | None = None
