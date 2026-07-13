"""FastAPI authentication client with Keycloak JWT verification."""

import asyncio
from typing import Any

import aiohttp
from aiohttp import ClientConnectorError
from cachetools import TTLCache
from jose import JWTError, jwt
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.common.config.auth_config import AuthConfig
from app.common.exceptions.auth import (
    ChatStorageAuthDecodeError,
    InvalidAudienceError,
    InvalidTokenSignatureError,
    ServiceTokenUserIdRequiredError,
    TokenExpiredError,
)

JWKS_CACHE_KEY = "jwks"

# Keycloak client-credentials (service) tokens carry a service-account
# preferred_username of the form "service-account-<client-id>".
SERVICE_ACCOUNT_PREFIX = "service-account-"


class AuthenticationClient:
    """Authentication client for validating jwt tokens and extract users from payload."""

    RETRIES = 3

    def __init__(self, config: AuthConfig):
        self.config: AuthConfig = config

        self._jwks_cache = TTLCache(maxsize=1, ttl=config.jwks_cache_ttl)
        self._user_cache = TTLCache(
            maxsize=config.user_cache_size,
            ttl=config.user_cache_ttl,
        )

        self._lock = asyncio.Lock()

    # ------------------------
    # CONFIG UPDATE
    # ------------------------

    def update(self, config: AuthConfig) -> None:
        """Hot-reload configuration."""
        self.config = config
        self.config.jwks_url = f"{config.server_url}/protocol/openid-connect/certs"

        self._jwks_cache = TTLCache(maxsize=1, ttl=config.jwks_cache_ttl)
        self._user_cache = TTLCache(
            maxsize=config.user_cache_size,
            ttl=config.user_cache_ttl,
        )

    # ------------------------
    # JWKS FETCHING
    # ------------------------

    @retry(
        stop=stop_after_attempt(RETRIES),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(ClientConnectorError),
    )
    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS (public keys) from Keycloak."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.config.jwks_url,
                timeout=self.config.timeout,
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_jwks(self) -> dict[str, Any]:
        """Return cached JWKS document.

        Cache stores the whole JWKS JSON document under JWKS_CACHE_KEY.
        Expected JWKS shape: {"keys": [JWK, ...]}.
        """

        if JWKS_CACHE_KEY in self._jwks_cache:
            return self._jwks_cache[JWKS_CACHE_KEY]

        async with self._lock:
            if JWKS_CACHE_KEY in self._jwks_cache:
                return self._jwks_cache[JWKS_CACHE_KEY]

            jwks_document = await self._fetch_jwks()
            self._jwks_cache[JWKS_CACHE_KEY] = jwks_document
            return jwks_document

    # ------------------------
    # JWT PROCESSING
    # ------------------------

    async def _verify_jwt(self, token: str) -> dict[str, Any]:
        """Full JWT verification (signature + claims)."""
        try:  # pylint: disable=too-many-try-statements
            jwks_document = await self.get_jwks()

            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise InvalidTokenSignatureError()

            key = next(
                (jwk for jwk in jwks_document.get("keys", []) if jwk.get("kid") == kid),
                None,
            )
            if not key:
                raise InvalidTokenSignatureError()

            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.config.server_url,
                options={"verify_aud": False},
            )

            if self.config.verify_aud:
                audiences = payload.get("aud", [])
                if isinstance(audiences, str):
                    audiences = [audiences]
                elif audiences is None:
                    audiences = []
                if not any(aud in self.config.valid_audiences for aud in audiences):
                    raise InvalidAudienceError()

            return payload

        except JWTError as exc:
            if "expired" in str(exc).lower():
                raise TokenExpiredError() from exc
            raise InvalidTokenSignatureError() from exc
        except Exception as exc:
            logger.exception(exc)
            raise ChatStorageAuthDecodeError() from exc

    async def process_token(self, token: str) -> dict[str, Any]:
        """Process token depending on verify flag."""
        if self.config.verify:
            return await self._verify_jwt(token)
        try:
            return jwt.get_unverified_claims(token)
        except Exception as exc:
            raise ChatStorageAuthDecodeError() from exc

    # ------------------------
    # MAIN METHOD
    # ------------------------

    async def get_user_from_token(self, token: str) -> int | str:
        """Validate token and return UserDTO."""

        cached_user = self._user_cache.get(token)
        if cached_user:
            return cached_user
        payload = await self.process_token(token)
        user_id = payload.get("sub")
        self._user_cache[token] = user_id
        return user_id

    @staticmethod
    def is_service_token(payload: dict[str, Any]) -> bool:
        """Return True if the token payload belongs to a Keycloak service account.

        Args:
            payload (dict[str, Any]): Decoded JWT claims.
        Returns:
            bool: True for client-credentials (service) tokens.
        """

        preferred_username = payload.get("preferred_username") or ""
        return isinstance(preferred_username, str) and preferred_username.startswith(
            SERVICE_ACCOUNT_PREFIX
        )

    async def resolve_user_id(
        self,
        token: str,
        service_user_id: str | None = None,
    ) -> int | str | None:
        """Resolve the effective user id, honoring service tokens.

        For service tokens (Keycloak client-credentials) the effective user id
        is taken from ``service_user_id`` (the ``X-User-Id`` header), since the
        token ``sub`` is the service account rather than an end user. For regular
        user tokens the id is the token ``sub`` claim and ``service_user_id`` is
        ignored to prevent one user acting on behalf of another.

        Args:
            token (str): Raw bearer token.
            service_user_id (str | None): User id supplied via ``X-User-Id``,
                only honored for service tokens.
        Returns:
            int | str | None: Effective user id, or None if the token has no sub.
        Raises:
            ServiceTokenUserIdRequiredError: Service token used without X-User-Id.
        """

        payload = await self.process_token(token)
        if self.is_service_token(payload):
            if not service_user_id:
                raise ServiceTokenUserIdRequiredError()
            return service_user_id
        return payload.get("sub")
