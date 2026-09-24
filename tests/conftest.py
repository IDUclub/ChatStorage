"""Shared test fixtures.

Integration tests need a live MongoDB. Point them at one with the
``TEST_MONGO_URL`` env var, e.g. against the docker-compose Mongo::

    TEST_MONGO_URL="mongodb://admin:admin@localhost:27017/?authSource=admin" \
        uv run pytest -m integration

If the variable is unset or the server is unreachable, the integration tests
are skipped (never failed), so the unit suite stays runnable everywhere.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.common.db.migrations import CHATS_VALIDATOR, MESSAGES_VALIDATOR

TEST_MONGO_URL = os.getenv("TEST_MONGO_URL")


@pytest_asyncio.fixture
async def mongo_client() -> AsyncIterator[AsyncMongoClient]:
    """Connected async Mongo client, or skip if no reachable server."""

    if not TEST_MONGO_URL:
        pytest.skip("TEST_MONGO_URL is not set; skipping MongoDB integration test")

    client: AsyncMongoClient = AsyncMongoClient(
        TEST_MONGO_URL, serverSelectionTimeoutMS=2000
    )
    try:
        await client.admin.command("ping")
    except PyMongoError:
        await client.close()
        pytest.skip("MongoDB at TEST_MONGO_URL is not reachable")

    try:
        yield client
    finally:
        await client.close()


async def create_schema_collections(database: AsyncDatabase) -> None:
    """Create chats/messages with the production validators and key indexes."""

    await database.create_collection(
        "chats",
        validator=CHATS_VALIDATOR,
        validationAction="error",
        validationLevel="strict",
    )
    await database.create_collection(
        "messages",
        validator=MESSAGES_VALIDATOR,
        validationAction="error",
        validationLevel="strict",
    )
    await database["chats"].create_index(
        [("user_id", ASCENDING), ("chat_id", ASCENDING)], unique=True
    )
    await database["messages"].create_index(
        [("user_id", ASCENDING), ("chat_id", ASCENDING), ("seq", ASCENDING)],
        unique=True,
    )
    await database["messages"].create_index(
        [
            ("user_id", ASCENDING),
            ("chat_id", ASCENDING),
            ("source_event_id", ASCENDING),
        ],
        unique=True,
        partialFilterExpression={"source_event_id": {"$type": "string"}},
    )


@pytest_asyncio.fixture
async def mongo_database(
    mongo_client: AsyncMongoClient,
) -> AsyncIterator[AsyncDatabase]:
    """A throwaway database seeded with the production schema, dropped on teardown."""

    db_name = f"chatstorage_test_{uuid.uuid4().hex}"
    database = mongo_client[db_name]
    await create_schema_collections(database)
    try:
        yield database
    finally:
        await mongo_client.drop_database(db_name)
