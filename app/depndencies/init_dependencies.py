from app.common.config.app_config import AppConfig
from app.common.config.config_loader import load_config


def init_dependencies() -> dict[str, AppConfig]:

    app_config: AppConfig = load_config()
    return {
        "app_config": app_config,
    }
