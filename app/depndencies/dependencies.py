from pathlib import Path

from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig
from app.depndencies.init_dependencies import init_dependencies
from app.services.chat_history_service import ChatHistoryService

app_deps = init_dependencies()


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

    return app_deps["logs_path"]


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


async def close_mongo_client() -> None:
    """Close MongoDB client on application shutdown."""

    await app_deps["mongo_client"].close()
