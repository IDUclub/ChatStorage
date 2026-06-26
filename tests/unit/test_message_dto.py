"""Unit tests for chat history input DTOs."""

import pytest
from pydantic import ValidationError

from app.dto.message_dto import (
    ChatCreateDTO,
    MessageCreateDTO,
    MessagePartCreateDTO,
    ToolCallDTO,
    ToolCallExtractDTO,
)


class TestMessageCreateDTO:
    """Body validation: either ``content`` or ``parts`` must be provided."""

    def test_content_only_is_valid(self) -> None:
        message = MessageCreateDTO(role="user", content="hello")

        assert message.content == "hello"
        assert message.parts is None
        assert message.metadata == {}

    def test_parts_only_is_valid(self) -> None:
        message = MessageCreateDTO(
            role="assistant",
            parts=[MessagePartCreateDTO(kind="text", payload={"text": "hi"})],
        )

        assert message.content is None
        assert len(message.parts) == 1

    def test_neither_content_nor_parts_raises(self) -> None:
        with pytest.raises(ValidationError):
            MessageCreateDTO(role="user")

    def test_empty_content_is_rejected(self) -> None:
        # content has min_length=1.
        with pytest.raises(ValidationError):
            MessageCreateDTO(role="user", content="")

    def test_invalid_role_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageCreateDTO(role="robot", content="hello")


class TestChatCreateDTO:
    """Optional chat creation payload."""

    def test_defaults(self) -> None:
        chat = ChatCreateDTO()

        assert chat.title is None
        assert chat.scenario_id is None
        assert chat.project_id is None
        assert chat.metadata == {}

    def test_title_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ChatCreateDTO(title="x" * 257)

    def test_scenario_id_accepts_str_and_int(self) -> None:
        assert ChatCreateDTO(scenario_id="default").scenario_id == "default"
        assert ChatCreateDTO(scenario_id=772).scenario_id == 772


class TestToolCallDTO:
    """Tool call DTO validation."""

    def test_minimal_tool_call(self) -> None:
        tool_call = ToolCallDTO(tool_name="GetServices")

        assert tool_call.tool_name == "GetServices"
        assert tool_call.step is None
        assert tool_call.arguments == {}

    def test_blank_tool_name_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolCallDTO(tool_name="")

    def test_step_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ToolCallDTO(tool_name="GetServices", step=0)


class TestToolCallExtractDTO:
    """Payload for preparing an executable tool call chain."""

    def test_defaults(self) -> None:
        payload = ToolCallExtractDTO(tool_call=ToolCallDTO(tool_name="GetServices"))

        assert payload.previous_tool_calls == []
        assert payload.scenario_id is None
        assert payload.project_id is None
        assert payload.mcp_source is None
        assert payload.meta == {}
