from hmac import compare_digest

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.auth.auth_client import AuthenticationClient
from app.common.config.app_config import AppConfig
from app.depndencies.dependencies import get_app_configuration, get_auth_client

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    x_user_id: str | None = Header(
        default=None,
        alias="X-User-Id",
        description=(
            "Target user id. Required when authenticating with a service token; "
            "ignored for user tokens (the token subject is used instead)."
        ),
    ),
    auth_client: AuthenticationClient = Depends(get_auth_client),
) -> str:
    """
    Function retrieves current user id from token.

    For user tokens the id is taken from the token subject and any X-User-Id
    header is ignored. For service tokens the X-User-Id header supplies the
    user the chat is recorded against.
    Args:
        credentials (HTTPAuthorizationCredentials): Request credentials from bearer schema.
        x_user_id (str | None): Target user id for service tokens (X-User-Id header).
        auth_client (AuthenticationClient): Auth client for app.
    Returns:
        str: User id in string format.
    """

    token = credentials.credentials
    user_id = await auth_client.resolve_user_id(token, service_user_id=x_user_id)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain user id",
        )

    return str(user_id)


async def get_current_access_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    auth_client: AuthenticationClient = Depends(get_auth_client),
) -> str:
    """
    Function retrieves current user id from token.
    Args:
        credentials (HTTPAuthorizationCredentials): Request credentials from bearer schema.
        auth_client (AuthenticationClient): Auth client for app.
    Returns:
        str: User bearer token from request.
    """

    token = credentials.credentials
    user_id = await auth_client.get_user_from_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain user id",
        )

    return token


async def verify_context_internal_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    config: AppConfig = Depends(get_app_configuration),
) -> None:
    """Protect context-worker endpoints without retaining a user JWT."""

    expected = config.CONTEXT_INTERNAL_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Context worker API is disabled",
        )
    if not x_internal_api_key or not compare_digest(x_internal_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
