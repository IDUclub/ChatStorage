"""Unit tests for the ``file`` message part kind and its payload validation.

Pure-Python: exercises DTO/schema validation and the service's part builder
without touching MongoDB.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.dto.message_dto import (
    FilePartPayload,
    MessageCreateDTO,
    MessagePartCreateDTO,
)
from app.schema.chat_history_schema import MessagePartKind
from app.services.chat_history_service import ChatHistoryService

VALID_FILE_PAYLOAD = {
    "url": "https://files.example.org/reports/effects.docx",
    "filename": "effects.docx",
    "mime_type": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "size_bytes": 184320,
    "source_service": "ObjectEffectsAPI",
}


def test_message_part_kind_includes_file() -> None:
    """The ``file`` kind is part of the public contract."""

    assert "file" in MessagePartKind.__args__


class TestFilePartPayload:
    """Direct validation of the recommended file payload shape."""

    def test_full_payload_is_valid(self) -> None:
        payload = FilePartPayload.model_validate(VALID_FILE_PAYLOAD)

        assert payload.url == VALID_FILE_PAYLOAD["url"]
        assert payload.filename == "effects.docx"
        assert payload.size_bytes == 184320
        assert payload.source_service == "ObjectEffectsAPI"

    def test_url_only_is_valid(self) -> None:
        payload = FilePartPayload.model_validate({"url": "https://x/y.docx"})

        assert payload.url == "https://x/y.docx"
        assert payload.filename is None
        assert payload.mime_type is None
        assert payload.size_bytes is None

    def test_missing_url_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilePartPayload.model_validate({"filename": "y.docx"})

    def test_empty_url_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilePartPayload.model_validate({"url": ""})

    def test_negative_size_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilePartPayload.model_validate({"url": "https://x/y", "size_bytes": -1})

    def test_extra_service_fields_are_preserved(self) -> None:
        payload = FilePartPayload.model_validate(
            {"url": "https://x/y", "scenario_id": 772}
        )

        assert payload.model_dump()["scenario_id"] == 772


class TestMessagePartFileValidation:
    """``kind="file"`` parts must carry a valid file reference."""

    def test_valid_file_part(self) -> None:
        part = MessagePartCreateDTO(kind="file", payload=VALID_FILE_PAYLOAD)

        assert part.kind == "file"
        assert part.payload["url"] == VALID_FILE_PAYLOAD["url"]

    def test_payload_is_stored_as_plain_dict(self) -> None:
        """Validation must not mutate payload into a model instance."""

        part = MessagePartCreateDTO(kind="file", payload=dict(VALID_FILE_PAYLOAD))

        assert isinstance(part.payload, dict)
        # Extra/service-specific keys survive untouched.
        assert part.payload["source_service"] == "ObjectEffectsAPI"

    def test_missing_url_raises(self) -> None:
        with pytest.raises(ValidationError):
            MessagePartCreateDTO(kind="file", payload={"filename": "y.docx"})

    def test_empty_url_raises(self) -> None:
        with pytest.raises(ValidationError):
            MessagePartCreateDTO(kind="file", payload={"url": ""})

    @pytest.mark.parametrize("kind", ["text", "data", "status"])
    def test_non_file_kinds_skip_file_validation(self, kind: str) -> None:
        """Other kinds keep their free-form payload (no ``url`` required)."""

        part = MessagePartCreateDTO(kind=kind, payload={"text": "anything"})

        assert part.kind == kind
        assert "url" not in part.payload


class TestMessageWithFileParts:
    """End-to-end DTO/service behaviour for messages carrying file parts."""

    def test_message_create_accepts_file_part(self) -> None:
        message = MessageCreateDTO(
            role="assistant",
            parts=[
                MessagePartCreateDTO(kind="text", payload={"text": "Report ready."}),
                MessagePartCreateDTO(kind="file", payload=VALID_FILE_PAYLOAD),
            ],
        )

        assert len(message.parts) == 2
        assert message.parts[1].kind == "file"

    def test_message_create_rejects_invalid_file_part(self) -> None:
        with pytest.raises(ValidationError):
            MessageCreateDTO(
                role="assistant",
                parts=[MessagePartCreateDTO(kind="file", payload={"size_bytes": 10})],
            )

    def test_build_parts_sequences_file_part(self) -> None:
        """The service stores the file part with its sequence and payload intact."""

        now = datetime.now(UTC)
        message = MessageCreateDTO(
            role="assistant",
            parts=[
                MessagePartCreateDTO(kind="text", payload={"text": "Report ready."}),
                MessagePartCreateDTO(kind="file", payload=VALID_FILE_PAYLOAD),
            ],
        )

        parts = ChatHistoryService._build_parts(message, now)

        assert [part["part_seq"] for part in parts] == [1, 2]
        file_part = parts[1]
        assert file_part["kind"] == "file"
        assert file_part["payload"]["url"] == VALID_FILE_PAYLOAD["url"]
        assert file_part["created_at"] == now
