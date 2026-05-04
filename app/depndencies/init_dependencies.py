from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig
from app.common.config.config_loader import load_auth_config, load_config
from app.common.db.mongo import create_mongo_client, get_database
from app.common.logging.init_logs import init_logger
from app.services.chat_history_service import ChatHistoryService


def init_dependencies() -> dict:

    app_config: AppConfig = load_config()
    logs_path = app_config.PROJECT_ROOT / "logs" / ".log"
    init_logger(logs_path)
    auth_config: AuthConfig = load_auth_config()
    auth_client = AuthenticationClient(auth_config)
    mongo_client = create_mongo_client(app_config)
    mongo_db = get_database(mongo_client, app_config)
    chat_history_service = ChatHistoryService(mongo_db)
    return {
        "app_config": app_config,
        "logs_path": logs_path,
        "auth_config": auth_config,
        "auth_client": auth_client,
        "mongo_client": mongo_client,
        "mongo_db": mongo_db,
        "chat_history_service": chat_history_service,
    }
