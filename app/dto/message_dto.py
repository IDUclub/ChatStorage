"""Chat history input DTOs."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schema.chat_history_schema import MessagePartKind, MessageRole


class MessagePartCreateDTO(BaseModel):
    """Message part payload received from client."""

    kind: MessagePartKind = "text"
    payload: dict[str, Any]


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
    metadata: dict[str, Any] = Field(default_factory=dict)
