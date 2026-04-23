from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig
from app.common.config.config_loader import load_auth_config, load_config


def init_dependencies() -> dict:

    app_config: AppConfig = load_config()
    auth_config: AuthConfig = load_auth_config()
    auth_client = AuthenticationClient(auth_config)
    return {
        "app_config": app_config,
        "auth_config": auth_config,
        "auth_client": auth_client,
    }
