"""Unit tests for service-token identity resolution in AuthenticationClient.

These cover ``is_service_token`` and ``resolve_user_id`` without a live Keycloak:
the client is configured with ``verify=False`` so tokens are read via unverified
claims (``jwt.get_unverified_claims``), letting us craft arbitrary payloads.
"""

import pytest
from jose import jwt

from app.common.auth.auth_client import AuthenticationClient
from app.common.config.auth_config import AuthConfig
from app.common.exceptions.auth import ServiceTokenUserIdRequiredError


def _client() -> AuthenticationClient:
    config = AuthConfig(
        verify=False,
        server_url="http://keycloak.local/realms/test",
        client_id="chat-storage",
        verify_aud=False,
    )
    return AuthenticationClient(config)


def _token(claims: dict) -> str:
    # Signature is irrelevant here: verify=False -> get_unverified_claims.
    return jwt.encode(claims, "secret", algorithm="HS256")


class TestIsServiceToken:
    def test_service_account_username_is_service(self):
        payload = {"preferred_username": "service-account-gmart", "sub": "svc-1"}
        assert AuthenticationClient.is_service_token(payload) is True

    def test_regular_user_is_not_service(self):
        payload = {"preferred_username": "ivan.ivanov", "sub": "user-42"}
        assert AuthenticationClient.is_service_token(payload) is False

    def test_missing_username_is_not_service(self):
        assert AuthenticationClient.is_service_token({"sub": "user-42"}) is False


class TestResolveUserId:
    @pytest.mark.asyncio
    async def test_user_token_uses_sub_and_ignores_header(self):
        client = _client()
        token = _token({"preferred_username": "ivan", "sub": "user-42"})

        user_id = await client.resolve_user_id(token, service_user_id="user-999")

        assert user_id == "user-42"

    @pytest.mark.asyncio
    async def test_service_token_uses_header_user_id(self):
        client = _client()
        token = _token({"preferred_username": "service-account-gmart", "sub": "svc-1"})

        user_id = await client.resolve_user_id(token, service_user_id="user-42")

        assert user_id == "user-42"

    @pytest.mark.asyncio
    async def test_service_token_without_header_raises(self):
        client = _client()
        token = _token({"preferred_username": "service-account-gmart", "sub": "svc-1"})

        with pytest.raises(ServiceTokenUserIdRequiredError):
            await client.resolve_user_id(token, service_user_id=None)
