"""MongoDB client helpers."""

from urllib.parse import quote_plus

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.common.config.app_config import AppConfig


def build_mongo_uri(config: AppConfig) -> str:
    """Build MongoDB URI from app configuration."""

    if config.MONGO_URL.startswith(("mongodb://", "mongodb+srv://")):
        return config.MONGO_URL

    user = quote_plus(config.MONGO_USER)
    password = quote_plus(config.MONGO_PASSWORD)
    return (
        f"mongodb://{user}:{password}@{config.MONGO_URL}/"
        f"{config.MONGO_DB}?authSource=admin"
    )


def create_mongo_client(config: AppConfig) -> AsyncMongoClient:
    """Create async MongoDB client."""

    return AsyncMongoClient(build_mongo_uri(config))


def get_database(
    client: AsyncMongoClient,
    config: AppConfig,
) -> AsyncDatabase:
    """Return configured database."""

    return client[config.MONGO_DB]
