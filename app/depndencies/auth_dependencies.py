from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.auth.auth_client import AuthenticationClient
from app.depndencies.dependencies import get_auth_client

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    auth_client: AuthenticationClient = Depends(get_auth_client),
) -> str:
    """
    Function retrieves current user id from token.
    Args:
        credentials (HTTPAuthorizationCredentials): Request credentials from bearer schema.
        auth_client (AuthenticationClient): Auth client for app.
    Returns:
        str: User id in string format.
    """

    token = credentials.credentials
    user_id = await auth_client.get_user_from_token(token)

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
