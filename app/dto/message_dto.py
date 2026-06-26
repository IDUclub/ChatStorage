"""Chat history input DTOs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schema.chat_history_schema import MessagePartKind, MessageRole


class FilePartPayload(BaseModel):
    """Recommended payload shape for a file message part (``kind="file"``).

    ChatStorage stores only a reference to the file, never the bytes. ``url`` is
    required; the remaining fields are optional metadata that let the UI render
    the attachment (name, icon, size) without downloading it. Extra keys are
    preserved as-is, so producers may attach service-specific fields.
    """

    model_config = ConfigDict(extra="allow")

    url: str = Field(min_length=1)
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    source_service: str | None = None


class MessagePartCreateDTO(BaseModel):
    """Message part payload received from client."""

    kind: MessagePartKind = "text"
    payload: dict[str, Any]
    mcp_source: str | None = None

    @model_validator(mode="after")
    def validate_file_payload(self) -> "MessagePartCreateDTO":
        """Require a valid file reference for ``kind="file"`` parts."""

        if self.kind == "file":
            # Validates url presence/metadata types without mutating payload,
            # so storage stays a plain dict like every other part kind.
            FilePartPayload.model_validate(self.payload)
        return self


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
