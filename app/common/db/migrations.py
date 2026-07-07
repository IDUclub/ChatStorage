"""Startup MongoDB migrations.

Migrations run from the service itself on startup (see app.main.lifespan).
Each migration runs once; applied ids are recorded in the `_migrations`
collection. Keep migrations idempotent where possible.

Note: schema-validator migrations use `collMod`, which requires the connected
Mongo user to have the `dbAdmin` role on the database. A plain `readWrite`
user is not enough.

The canonical schema for a fresh database lives in mongo/init/01-init.js.
When you change a collection validator there, mirror the change here as a new
migration so existing deployments are updated too.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from loguru import logger
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

# MongoDB error code for "collection/namespace not found".
_NAMESPACE_NOT_FOUND = 26

# chats validator, kept in sync with mongo/init/01-init.js.
UUID_PATTERN = (
    "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}"
    "-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)

CHATS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "chat_id", "next_seq", "created_at", "updated_at"],
        "additionalProperties": False,
        "properties": {
            "_id": {},
            "user_id": {
                "bsonType": "string",
                "pattern": UUID_PATTERN,
                "description": "Required user UUID from auth token",
            },
            "chat_id": {
                "bsonType": "string",
                "pattern": UUID_PATTERN,
                "description": "Required service-generated chat UUID",
            },
            "scenario_id": {
                "bsonType": ["string", "int", "null"],
                "description": "Optional scenario identifier",
            },
            "project_id": {
                "bsonType": ["string", "int", "null"],
                "description": "Optional project identifier",
            },
            "title": {
                "bsonType": ["string", "null"],
                "description": "Optional chat title",
            },
            "metadata": {
                "bsonType": "object",
                "description": "Optional client or assistant metadata",
            },
            "next_seq": {
                "bsonType": "int",
                "minimum": 1,
                "description": "Next message sequence number in this chat",
            },
            "created_at": {"bsonType": "date", "description": "Creation date"},
            "updated_at": {"bsonType": "date", "description": "Last update date"},
        },
    }
}


# messages validator, kept in sync with mongo/init/01-init.js.
MESSAGES_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id",
            "chat_id",
            "message_id",
            "seq",
            "role",
            "parts",
            "created_at",
            "updated_at",
        ],
        "additionalProperties": False,
        "properties": {
            "_id": {},
            "user_id": {
                "bsonType": "string",
                "pattern": UUID_PATTERN,
                "description": "Required user UUID from auth token",
            },
            "chat_id": {
                "bsonType": "string",
                "pattern": UUID_PATTERN,
                "description": "Required service-generated chat UUID",
            },
            "message_id": {
                "bsonType": "string",
                "pattern": UUID_PATTERN,
                "description": "Required service-generated message UUID",
            },
            "seq": {
                "bsonType": "int",
                "minimum": 1,
                "description": "Message sequence number inside one chat",
            },
            "role": {
                "enum": ["user", "assistant", "system", "tool"],
                "description": "Message role",
            },
            "parts": {
                "bsonType": "array",
                "minItems": 1,
                "description": "Ordered message parts",
                "items": {
                    "bsonType": "object",
                    "required": ["part_seq", "kind", "payload", "created_at"],
                    "additionalProperties": False,
                    "properties": {
                        "part_seq": {"bsonType": "int", "minimum": 1},
                        "kind": {
                            "enum": [
                                "text",
                                "tool_call",
                                "tool_result",
                                "status",
                                "data",
                                "table",
                                "file",
                            ]
                        },
                        "payload": {"bsonType": "object"},
                        "mcp_source": {
                            "bsonType": ["string", "null"],
                            "description": "Optional MCP server name that executed this tool",
                        },
                        "created_at": {"bsonType": "date"},
                    },
                },
            },
            "metadata": {
                "bsonType": "object",
                "description": "Optional model, token, trace, or client metadata",
            },
            "created_at": {"bsonType": "date", "description": "Creation date"},
            "updated_at": {"bsonType": "date", "description": "Last update date"},
        },
    }
}


async def _migration_001_add_project_id(database: AsyncDatabase) -> None:
    """Add optional project_id to the chats collection validator."""

    try:
        await database.command(
            {
                "collMod": "chats",
                "validator": CHATS_VALIDATOR,
                "validationAction": "error",
                "validationLevel": "strict",
            }
        )
    except OperationFailure as exc:
        if exc.code == _NAMESPACE_NOT_FOUND:
            # Fresh database: chats is created by 01-init.js with the current
            # schema, so there is nothing to migrate.
            logger.info(
                "Migration 001: chats collection does not exist yet, skipping collMod"
            )
            return
        raise


async def _migration_002_scenario_project_indexes(database: AsyncDatabase) -> None:
    """Add compound indexes to filter chats by scenario_id/project_id with sorting."""

    await database["chats"].create_index(
        [("user_id", ASCENDING), ("scenario_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await database["chats"].create_index(
        [("user_id", ASCENDING), ("project_id", ASCENDING), ("updated_at", DESCENDING)]
    )


async def _migration_003_add_file_part_kind(database: AsyncDatabase) -> None:
    """Allow the "file" part kind in the messages collection validator."""

    try:
        await database.command(
            {
                "collMod": "messages",
                "validator": MESSAGES_VALIDATOR,
                "validationAction": "error",
                "validationLevel": "strict",
            }
        )
    except OperationFailure as exc:
        if exc.code == _NAMESPACE_NOT_FOUND:
            # Fresh database: messages is created by 01-init.js with the current
            # schema, so there is nothing to migrate.
            logger.info(
                "Migration 003: messages collection does not exist yet, "
                "skipping collMod"
            )
            return
        raise


async def _migration_004_add_table_part_kind(database: AsyncDatabase) -> None:
    """Allow the "table" part kind in the messages collection validator."""

    try:
        await database.command(
            {
                "collMod": "messages",
                "validator": MESSAGES_VALIDATOR,
                "validationAction": "error",
                "validationLevel": "strict",
            }
        )
    except OperationFailure as exc:
        if exc.code == _NAMESPACE_NOT_FOUND:
            # Fresh database: messages is created by 01-init.js with the current
            # schema, so there is nothing to migrate.
            logger.info(
                "Migration 004: messages collection does not exist yet, "
                "skipping collMod"
            )
            return
        raise


# Ordered list of migrations. Append new ones; never reorder or rewrite applied ids.
MIGRATIONS: list[tuple[str, Callable[[AsyncDatabase], Awaitable[None]]]] = [
    ("001-add-project-id", _migration_001_add_project_id),
    ("002-scenario-project-indexes", _migration_002_scenario_project_indexes),
    ("003-add-file-part-kind", _migration_003_add_file_part_kind),
    ("004-add-table-part-kind", _migration_004_add_table_part_kind),
]


async def run_migrations(database: AsyncDatabase) -> None:
    """Apply pending migrations recorded in the `_migrations` collection."""

    migrations_collection = database["_migrations"]
    applied: set[str] = set()
    async for document in migrations_collection.find({}, {"_id": 1}):
        applied.add(document["_id"])

    for migration_id, migration in MIGRATIONS:
        if migration_id in applied:
            continue

        logger.info(f"Applying migration {migration_id}")
        await migration(database)
        await migrations_collection.insert_one(
            {"_id": migration_id, "applied_at": datetime.now(UTC)}
        )
        logger.info(f"Migration {migration_id} applied")
