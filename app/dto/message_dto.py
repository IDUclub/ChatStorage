"""Chat history input DTOs."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schema.chat_history_schema import MessagePartKind, MessageRole


class MessagePartCreateDTO(BaseModel):
    """Message part payload received from client."""

    kind: MessagePartKind = "text"
    payload: dict[str, Any]
    mcp_source: str | None = None


class MessageCreateDTO(BaseModel):
    """Message creation payload."""

    role: MessageRole
    content: str | None = Field(default=None, min_length=1)
    parts: list[MessagePartCreateDTO] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_message_body(self) -> "MessageCreateDTO":
        """Require either simple content or explicit parts."""

        if self.content is None and not self.parts:
            raise ValueError("Either content or parts must be provided")
        return self


class ChatCreateDTO(BaseModel):
    """Chat creation payload."""

    title: str | None = Field(default=None, max_length=256)
    scenario_id: str | int | None = None
    project_id: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallDTO(BaseModel):
    """Tool call received from clients or restored from history."""

    step: int | None = Field(default=None, ge=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallExtractDTO(BaseModel):
    """Payload for preparing an executable tool call chain."""

    tool_call: ToolCallDTO
    previous_tool_calls: list[ToolCallDTO] = Field(default_factory=list)
    scenario_id: int | None = None
    project_id: int | None = None
    mcp_source: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
