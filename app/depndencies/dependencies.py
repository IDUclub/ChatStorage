from pathlib import Path

from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig
from app.common.config.config_loader import load_config
from app.common.db.migrations import run_migrations
from app.common.db.mongo import create_mongo_client, get_database
from app.depndencies.init_dependencies import init_dependencies
from app.services.chat_history_service import ChatHistoryService
from app.services.tool_call_execution_service import ToolCallExecutionService

app_deps = init_dependencies()

MONGO_ENV_VARS = {"MONGO_URL", "MONGO_USER", "MONGO_PASSWORD", "MONGO_DB"}


async def get_app_configuration() -> AppConfig:
    """
    Function returns AppConfiguration instance for current app.
    Returns:
        AppConfig: App configuration instance.
    """

    return app_deps["app_config"]


async def get_logs_path() -> Path:
    """
    Function returns logs path as Path object for current app.
    Returns:
        Path: Path to logs instance.
    """

    return app_deps["app_config"].PATH_TO_LOG


async def get_auth_configuration() -> AuthConfig:
    """
    Function returns AuthConfiguration instance for current app.
    Returns:
        AuthConfig: Authentication configuration instance.
    """

    return app_deps["auth_config"]


async def get_auth_client() -> AuthenticationClient:
    """
    Function returns AuthenticationClient instance for current app.
    Returns:
        AuthenticationClient: Auth client for app.
    """
    return app_deps["auth_client"]


async def get_chat_history_service() -> ChatHistoryService:
    """
    Function returns ChatHistoryService instance for current app.
    Returns:
        ChatHistoryService: Chat history service.
    """

    return app_deps["chat_history_service"]


async def get_tool_call_execution_service() -> ToolCallExecutionService:
    """
    Function returns ToolCallExecutionService instance for current app.
    Returns:
        ToolCallExecutionService: tool call execution service.
    """

    return app_deps["tool_call_execution_service"]


async def reinitialize_db_service() -> None:
    """Reinitialize MongoDB client and update ChatHistoryService in-place using current env vars."""

    await app_deps["mongo_client"].close()

    new_config = load_config()
    new_client = create_mongo_client(new_config)
    new_db = get_database(new_client, new_config)

    app_deps["app_config"] = new_config
    app_deps["mongo_client"] = new_client
    app_deps["mongo_db"] = new_db

    service: ChatHistoryService = app_deps["chat_history_service"]
    service._db = new_db
    service._chats = new_db["chats"]
    service._messages = new_db["messages"]


async def run_startup_migrations() -> None:
    """Apply pending MongoDB migrations using the current database connection."""

    await run_migrations(app_deps["mongo_db"])


async def close_mongo_client() -> None:
    """Close MongoDB client on application shutdown."""

    await app_deps["mongo_client"].close()
