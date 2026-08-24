"""Chat history input DTOs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schema.chat_history_schema import (
    DEFAULT_CHAT_SPACE,
    ChatSpace,
    MessagePartKind,
    MessageRole,
)


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


class TableColumnPayload(BaseModel):
    """Column contract of a strict table part: stable key + human label."""

    model_config = ConfigDict(extra="allow")

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)


class TablePartPayload(BaseModel):
    """Recommended payload shape for a table message part (``kind="table"``).

    Tables are produced by services (not by the LLM) with a fixed column
    contract: ``columns`` defines machine-readable keys and human-readable
    labels, ``rows`` hold values keyed by column key. Extra keys are preserved
    as-is, so producers may attach service-specific fields.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    title: str | None = None
    columns: list[TableColumnPayload] = Field(min_length=1)
    rows: list[dict[str, Any]]


class CheckPlanPartPayload(BaseModel):
    """Versioned executable-norm plan persisted without executable expressions."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(pattern=r"^1\.0$")
    template: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    params: dict[str, Any]
    source: dict[str, Any]
    planner_status: str


class RequirementResolutionPartPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    restriction_id: str = Field(min_length=1)
    effective_requirements: dict[str, Any]
    resolved_requirements: list[dict[str, Any]]
    missing_requirements: list[str]


class ComplianceResultPartPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    restriction_id: str = Field(min_length=1)
    template: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    verification_status: str
    compliance_status: str
    coverage: dict[str, Any]
    summary: dict[str, Any]
    evidence_schema_version: str = Field(pattern=r"^1\.0$")


class ComplianceSummaryPartPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str = Field(min_length=1)
    total_norms: int = Field(ge=0)
    violated_norms: int = Field(ge=0)
    passed_norms: int = Field(ge=0)
    unverifiable_norms: int = Field(ge=0)
    unsupported_norms: int = Field(ge=0)
    not_applicable_norms: int = Field(ge=0)
    partial_norms: int = Field(ge=0)
    results: list[dict[str, Any]]


class MessagePartCreateDTO(BaseModel):
    """Message part payload received from client."""

    kind: MessagePartKind = "text"
    payload: dict[str, Any]
    mcp_source: str | None = None

    @model_validator(mode="after")
    def validate_typed_payload(self) -> "MessagePartCreateDTO":
        """Require valid payload shapes for typed part kinds."""

        if self.kind == "file":
            # Validates url presence/metadata types without mutating payload,
            # so storage stays a plain dict like every other part kind.
            FilePartPayload.model_validate(self.payload)
        if self.kind == "table":
            TablePartPayload.model_validate(self.payload)
        if self.kind == "check_plan":
            CheckPlanPartPayload.model_validate(self.payload)
        if self.kind == "requirement_resolution":
            RequirementResolutionPartPayload.model_validate(self.payload)
        if self.kind == "compliance_result":
            ComplianceResultPartPayload.model_validate(self.payload)
        if self.kind == "compliance_summary":
            ComplianceSummaryPartPayload.model_validate(self.payload)
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

    space: ChatSpace = DEFAULT_CHAT_SPACE
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
