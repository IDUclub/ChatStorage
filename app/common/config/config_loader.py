"""
Module aimed to load app configuration.
"""

import os

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from app.common.config.app_config import AppConfig
from app.common.config.auth_config import AuthConfig

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


def _get_bool(name: str, default: bool | None = None) -> bool:
    """
    Function returns bool value from env as python object.
    Available values can be equal to "1", "true", "yes", "y", "on", "0", "false", "no", "n", "off".
    Args:
        name (str): Variable name in str format.
        default (bool | None): Default value for env variable. Default to None.
    Returns:
        bool: Bool value for env from config.
    Raises:
        ValueError: Value error if no env received.
    """

    value = os.getenv(name)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"Environment variable '{name}' is required")
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(
        f"Environment variable '{name}' must be a boolean value, got: {value}"
    )


def _get_int(name: str, default: int | None = None) -> int:
    """
    Function returns int value from env as python object.
    Args:
        name (str): Variable name in str format.
        default (bool | None): Default value for env variable. Default to None.
    Returns:
        bool: Bool value for env from config.
    Raises:
        ValueError: Value error if no env received.
    """

    value = os.getenv(name)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"Environment variable '{name}' is required")
    try:
        if float(value).is_integer():
            return int(float(value))
        else:
            raise ValueError(
                f"Environment variable '{name}' is not an integer or float with zero part, got {value}"
            )
    except ValueError as exc:

        raise ValueError(
            f"Environment variable '{name}' must be an integer or float with zero part, got: {value}"
        ) from exc


def _get_str(name: str, default: str | None = None) -> str:
    """
    Function returns string value from env as python object.
    Args:
        name (str): Variable name in str format.
        default (bool | None): Default value for env variable. Default to None.
    Returns:
        bool: Bool value for env from config.
    Raises:
        ValueError: Value error if no env received.
    """

    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ValueError(f"Environment variable '{name}' is required")
    return value.strip()


def _get_list(name: str, default: list[str] | None = None) -> list[str]:
    """
    Function returns list value from env as python object.
    Args:
        name (str): Variable name in str format.
        Env value should be presented as str, where values of list are separated by comma: "valuer_1, value_2, etc.".
        default (bool | None): Default value for env variable. Default to None.
    Returns:
        bool: Bool value for env from config.
    Raises:
        ValueError: Value error if no env received.
    """

    value = os.getenv(name)
    if value is None or not value.strip():
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def _get_mcp_sources() -> dict[str, str]:
    """Build MCP server name→URL mapping from env vars ending with '_MCP_URL'.

    ``<NAME>_MCP_URL`` is registered under the lowercased ``<name>`` key,
    e.g. ``IDU_MCP_URL`` → ``{"idu": "<value>"}``.
    """
    return {
        key[: -len("_MCP_URL")].lower(): value
        for key, value in os.environ.items()
        if key.endswith("_MCP_URL") and value and key != "_MCP_URL"
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
            idu_mcp_url=os.getenv("IDU_MCP_URL"),
            mcp_sources=_get_mcp_sources(),
            context_internal_api_key=os.getenv("CONTEXT_INTERNAL_API_KEY"),
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
                    idu_mcp_url=os.getenv("IDU_MCP_URL"),
                    mcp_sources=_get_mcp_sources(),
                    context_internal_api_key=os.getenv("CONTEXT_INTERNAL_API_KEY"),
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
                        idu_mcp_url=os.getenv("IDU_MCP_URL"),
                        mcp_sources=_get_mcp_sources(),
                        context_internal_api_key=os.getenv("CONTEXT_INTERNAL_API_KEY"),
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
                idu_mcp_url=os.getenv("IDU_MCP_URL"),
                mcp_sources=_get_mcp_sources(),
                context_internal_api_key=os.getenv("CONTEXT_INTERNAL_API_KEY"),
            )
        except ValueError:
            raise
        except Exception as e:
            logger.exception(e)
            raise ValueError("No configuration found in environment variables") from e


def load_auth_config() -> AuthConfig:
    """
    Function loads auth config from env or .env files.
    Returns:
        AuthConfig: Authentication config for app.
    """

    return AuthConfig(
        verify=_get_bool("AUTH_VERIFY", default=True),
        server_url=_get_str("AUTH_SERVER_URL"),
        client_id=_get_str("AUTH_CLIENT_ID"),
        verify_aud=_get_bool("AUTH_VERIFY_AUD", default=True),
        valid_audiences=_get_list("AUTH_VALID_AUDIENCES", default=[]),
        user_cache_ttl=_get_int("AUTH_USER_CACHE_TTL", default=300),
        user_cache_size=_get_int("AUTH_USER_CACHE_SIZE", default=10_000),
        jwks_cache_ttl=_get_int("AUTH_JWKS_CACHE_TTL", default=600),
        timeout=_get_int("AUTH_TIMEOUT", default=5),
    )
