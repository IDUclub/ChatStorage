"""Unit tests for the chat space registry."""

from typing import get_args

import pytest

from app.common.db.migrations import CHAT_SPACE_ENUM, CHATS_VALIDATOR
from app.common.spaces import CHAT_SPACE_SLUGS, CHAT_SPACES, get_chat_space
from app.dto.message_dto import ChatCreateDTO
from app.schema.chat_history_schema import DEFAULT_CHAT_SPACE, ChatSpace


def test_default_space_is_main() -> None:
    assert DEFAULT_CHAT_SPACE == "main"
    assert [space.slug for space in CHAT_SPACES if space.is_default] == ["main"]


def test_registry_matches_the_chat_space_literal() -> None:
    """The registry, the type and the Mongo enum must not drift apart."""

    literal_slugs = set(get_args(ChatSpace))

    assert set(CHAT_SPACE_SLUGS) == literal_slugs
    assert set(CHAT_SPACE_ENUM) == literal_slugs
    assert set(CHATS_VALIDATOR["$jsonSchema"]["properties"]["space"]["enum"]) == (
        literal_slugs
    )


def test_space_is_required_by_the_chats_validator() -> None:
    assert "space" in CHATS_VALIDATOR["$jsonSchema"]["required"]


def test_slugs_are_unique() -> None:
    assert len(CHAT_SPACE_SLUGS) == len(set(CHAT_SPACE_SLUGS))


def test_get_chat_space_returns_labels() -> None:
    assert get_chat_space("synapse").title == "Synapse"

    with pytest.raises(KeyError):
        get_chat_space("unknown")


def test_chat_create_dto_defaults_to_the_main_space() -> None:
    assert ChatCreateDTO().space == DEFAULT_CHAT_SPACE
    assert ChatCreateDTO(space="synapse").space == "synapse"


def test_chat_create_dto_rejects_unknown_space() -> None:
    with pytest.raises(ValueError):
        ChatCreateDTO(space="matrix")
