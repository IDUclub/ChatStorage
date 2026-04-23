"""Exceptions connected with authentication client are defined here."""

from app.common.exceptions.base import ChatStorageError


class AuthTokenExpiredError(ChatStorageError):
    """Exception to raise when token has expired."""


class JWTDecodeError(ChatStorageError):
    """Exception to raise when token decoding has failed."""


class InvalidTokenSignature(ChatStorageError):
    """Exception to raise when validating token by external service has failed."""
