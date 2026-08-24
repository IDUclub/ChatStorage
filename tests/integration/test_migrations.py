"""Integration tests for startup migrations against a live MongoDB.

Skipped unless ``TEST_MONGO_URL`` points at a reachable server.
"""

import copy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.common.db.migrations import (
    CHATS_VALIDATOR,
    MESSAGES_VALIDATOR,
    MIGRATIONS,
    run_migrations,
)

pytestmark = pytest.mark.integration


def _messages_validator_without_file() -> dict:
    """A pre-migration messages validator that does not allow the file kind."""

    validator = copy.deepcopy(MESSAGES_VALIDATOR)
    kinds = validator["$jsonSchema"]["properties"]["parts"]["items"]["properties"][
        "kind"
    ]["enum"]
    kinds.remove("file")
    return validator


def _file_message_document() -> dict:
    now = datetime.now(UTC)
    return {
        "user_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "message_id": str(uuid4()),
        "seq": 1,
        "role": "assistant",
        "parts": [
            {
                "part_seq": 1,
                "kind": "file",
                "payload": {"url": "https://x/y.docx"},
                "created_at": now,
            }
        ],
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }


async def test_migrations_enable_file_kind(mongo_client: AsyncMongoClient) -> None:
    """003 upgrades an existing deployment's validator to allow file parts."""

    db_name = f"chatstorage_mig_{uuid4().hex}"
    database = mongo_client[db_name]
    try:
        # Simulate an existing deployment whose validator predates the file kind.
        await database.create_collection(
            "messages",
            validator=_messages_validator_without_file(),
            validationAction="error",
            validationLevel="strict",
        )

        # Before migrating, a file part is rejected by the old validator.
        with pytest.raises(PyMongoError):
            await database["messages"].insert_one(_file_message_document())

        await run_migrations(database)

        # All migrations recorded exactly once.
        applied = {doc["_id"] async for doc in database["_migrations"].find({})}
        assert applied == {migration_id for migration_id, _ in MIGRATIONS}

        # After migrating, the same file part inserts successfully.
        await database["messages"].insert_one(_file_message_document())
        assert await database["messages"].count_documents({}) == 1
    finally:
        await mongo_client.drop_database(db_name)


async def test_migrations_are_idempotent(mongo_client: AsyncMongoClient) -> None:
    """Running migrations twice neither errors nor re-applies anything."""

    db_name = f"chatstorage_mig_{uuid4().hex}"
    database = mongo_client[db_name]
    try:
        await run_migrations(database)
        first = await database["_migrations"].count_documents({})

        await run_migrations(database)
        second = await database["_migrations"].count_documents({})

        assert first == second == len(MIGRATIONS)
    finally:
        await mongo_client.drop_database(db_name)


def _chats_validator_without_space() -> dict:
    """A pre-migration chats validator that predates the space field."""

    validator = copy.deepcopy(CHATS_VALIDATOR)
    schema = validator["$jsonSchema"]
    schema["required"] = [field for field in schema["required"] if field != "space"]
    schema["properties"].pop("space")
    return validator


def _legacy_chat_document() -> dict:
    now = datetime.now(UTC)
    return {
        "user_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "next_seq": 1,
        "created_at": now,
        "updated_at": now,
    }


async def test_migrations_backfill_chat_space(mongo_client: AsyncMongoClient) -> None:
    """007 moves existing chats into the default space and requires the field."""

    db_name = f"chatstorage_mig_{uuid4().hex}"
    database = mongo_client[db_name]
    try:
        # Simulate an existing deployment whose chats predate spaces.
        await database.create_collection(
            "chats",
            validator=_chats_validator_without_space(),
            validationAction="error",
            validationLevel="strict",
        )
        legacy = _legacy_chat_document()
        await database["chats"].insert_one(legacy)

        await run_migrations(database)

        stored = await database["chats"].find_one({"chat_id": legacy["chat_id"]})
        assert stored["space"] == "main"

        # After migrating, a chat without a space is rejected.
        with pytest.raises(PyMongoError):
            await database["chats"].insert_one(_legacy_chat_document())
    finally:
        await mongo_client.drop_database(db_name)


async def test_migrations_backfill_chat_space_on_migrated_deployment(
    mongo_client: AsyncMongoClient,
) -> None:
    """007 works on a deployment that already recorded every earlier migration.

    Regression test for a production startup failure: 001 re-applies the current
    chats validator, so a database migrating from scratch had `space` allowed
    before 007 backfilled it. A deployment that had already applied 001..006 kept
    the pre-space validator, and the backfill died with "Document failed
    validation (additionalProperties: space)".
    """

    db_name = f"chatstorage_mig_{uuid4().hex}"
    database = mongo_client[db_name]
    try:
        await database.create_collection(
            "chats",
            validator=_chats_validator_without_space(),
            validationAction="error",
            validationLevel="strict",
        )
        legacy = _legacy_chat_document()
        await database["chats"].insert_one(legacy)

        # Every migration before the space one is already recorded, so only 007 runs.
        now = datetime.now(UTC)
        for migration_id, _ in MIGRATIONS[:-1]:
            await database["_migrations"].insert_one(
                {"_id": migration_id, "applied_at": now}
            )

        await run_migrations(database)

        stored = await database["chats"].find_one({"chat_id": legacy["chat_id"]})
        assert stored["space"] == "main"

        # The final validator is in place: a chat without a space is rejected.
        with pytest.raises(PyMongoError):
            await database["chats"].insert_one(_legacy_chat_document())
    finally:
        await mongo_client.drop_database(db_name)
