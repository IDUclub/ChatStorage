"""
Module aimed to load app configuration.
"""

import os

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from app.common.config.app_config import AppConfig

ENV_EXTENSIONS = [
    "",
    ".dev",
    ".develop",
    ".development",
    ".prod",
    ".production",
    ".docker",
    ".example",
]


def try_load(env_file_extension: str) -> dict[str, tuple[str | None, str | None]]:
    """
    Function loads env variables from file.
    Args:
        env_file_extension (str): Env file extension name.
    Returns:
        dict[str, tuple[str | None, str | None]]: Dict with updated variables.
    """
    if "." not in env_file_extension:
        env_file_extension = "." + env_file_extension
    before = dict(os.environ)
    find_res = find_dotenv(f".env{env_file_extension}")
    load_dotenv(find_res, override=True)
    return {
        k: (before.get(k), os.environ.get(k))
        for k in os.environ
        if before.get(k) != os.environ.get(k)
    }


def load_config() -> AppConfig:
    """
    Function loads app configuration from env. Firstly tries to load configurations from file.
    Returns:
        AppConfig: Instance of app configuration.
    Raises:
        ValueError: Value error in case no configuration loaded.
    """

    try:
        # load from existing envs
        return AppConfig(
            mongo_url=os.environ.get("MONGO_URL"),
            mongo_user=os.getenv("MONGO_USER"),
            mongo_password=os.getenv("MONGO_PASSWORD"),
            mongo_db=os.getenv("MONGO_DB"),
        )
    except ValueError:
        logger.warning(
            "Couldn't load config from app variables. trying to load from env file."
        )
        # load from APP_ENV variable
        if app_env := os.getenv("APP_ENV"):
            logger.info(
                "Found APP_ENV variable with value {} in environment variables. Loading app config from APP_ENV".format(
                    app_env
                )
            )
            if try_load(app_env):
                return AppConfig(
                    mongo_url=os.environ.get("MONGO_URL"),
                    mongo_user=os.environ.get("MONGO_USER"),
                    mongo_password=os.environ.get("MONGO_PASSWORD"),
                    mongo_db=os.environ.get("MONGO_DB"),
                )
            else:
                logger.warning(
                    "Couldn't find app configurations from APP_ENV. APP_ENV={}".format(
                        app_env
                    )
                )
        try:
            for extension in ENV_EXTENSIONS:
                if try_load(extension):
                    logger.info("Trying to load config from .env.{}".format(extension))
                    return AppConfig(
                        mongo_url=os.environ.get("MONGO_URL"),
                        mongo_user=os.environ.get("MONGO_USER"),
                        mongo_password=os.environ.get("MONGO_PASSWORD"),
                        mongo_db=os.environ.get("MONGO_DB"),
                    )
            logger.warning(
                "No config file found or no new variables where found from: {}".format(
                    ", ".join(ENV_EXTENSIONS)
                )
            )
            return AppConfig(
                mongo_url=os.getenv("MONGO_URL"),
                mongo_user=os.getenv("MONGO_USER"),
                mongo_password=os.getenv("MONGO_PASSWORD"),
                mongo_db=os.getenv("MONGO_DB"),
            )
        except ValueError:
            raise
        except Exception as e:
            logger.exception(e)
            raise ValueError("No configuration found in environment variables") from e
