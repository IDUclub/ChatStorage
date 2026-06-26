"""Integration tests for startup migrations against a live MongoDB.

Skipped unless ``TEST_MONGO_URL`` points at a reachable server.
"""

import copy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.common.db.migrations import MESSAGES_VALIDATOR, MIGRATIONS, run_migrations

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
