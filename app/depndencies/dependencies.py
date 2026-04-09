from app.common.config.app_config import AppConfig
from app.depndencies.init_dependencies import init_dependencies

app_deps: dict[str, AppConfig] = init_dependencies()


async def get_app_configuration() -> AppConfig:
    """
    Function returns AppConfiguration instance for current app.
    Returns:
        AppConfig: App configuration instance.
    """

    return app_deps["app_config"]
