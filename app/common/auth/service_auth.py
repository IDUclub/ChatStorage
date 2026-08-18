from __future__ import annotations

import os

import httpx
from idu_service_auth import KeycloakTokenClient, KeycloakTokenConfig

USER_ID_HEADER = "X-User-Id"


def build_service_auth() -> KeycloakTokenClient:
    values = {
        name: (os.getenv(name) or "").strip()
        for name in (
            "SERVICE_AUTH_SERVER_URL",
            "SERVICE_AUTH_REALM",
            "SERVICE_AUTH_CLIENT_ID",
            "SERVICE_AUTH_CLIENT_SECRET",
        )
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(
            "Missing mandatory service-auth variables: " + ", ".join(missing)
        )
    return KeycloakTokenClient(
        KeycloakTokenConfig(
            auth_server_url=values["SERVICE_AUTH_SERVER_URL"],
            realm=values["SERVICE_AUTH_REALM"],
            client_id=values["SERVICE_AUTH_CLIENT_ID"],
            client_secret=values["SERVICE_AUTH_CLIENT_SECRET"],
            background_refresh=True,
        )
    )


class ServiceTokenAuth(httpx.Auth):
    def __init__(self, auth: KeycloakTokenClient, user_id: str) -> None:
        self.auth = auth
        self.user_id = user_id

    async def async_auth_flow(self, request: httpx.Request):
        request.headers.update(await self.auth.get_authorization_headers())
        request.headers[USER_ID_HEADER] = self.user_id
        yield request
