from dataclasses import dataclass, field


@dataclass
class AuthConfig:
    """Authentication and token validation settings."""

    verify: bool  # проверять ли токен вообще
    server_url: str  # https://.../realms/<realm>
    client_id: str
    verify_aud: bool = True
    valid_audiences: list[str] = field(default_factory=list)
    user_cache_ttl: int = 300  # TTL кеша пользователей (сек)
    user_cache_size: int = 10_000  # размер кеша пользователей
    jwks_cache_ttl: int = 600  # TTL кеша JWKS (сек)

    timeout: int = 5

    def __post_init__(self):
        """Ensure server URL has a valid scheme."""

        if not self.server_url.startswith("http"):
            self.server_url = "http://" + self.server_url

    @property
    def authorization_url(self) -> str:
        """Keycloak /auth URL."""

        return f"{self.server_url}/protocol/openid-connect/auth"

    @property
    def token_url(self) -> str:
        """Keycloak /token URL."""

        return f"{self.server_url}/protocol/openid-connect/token"

    @property
    def jwks_url(self) -> str:
        """Keycloak /certs URL."""

        return f"{self.server_url}/protocol/openid-connect/certs"
