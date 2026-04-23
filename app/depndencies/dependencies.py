from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig
from app.depndencies.init_dependencies import init_dependencies

app_deps: dict[str, AppConfig | AuthenticationClient | AuthConfig] = init_dependencies()


async def get_app_configuration() -> AppConfig:
    """
    Function returns AppConfiguration instance for current app.
    Returns:
        AppConfig: App configuration instance.
    """

    return app_deps["app_config"]


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
