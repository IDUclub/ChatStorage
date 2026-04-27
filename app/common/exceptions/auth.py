"""Exceptions connected with authentication client are defined here."""

from app.common.exceptions.base import ChatStorageError


class AuthError(ChatStorageError):
    """
    Exception to raise when auth error hast to be raised.
    Attributes:
        status_code (int): HTTP status code to raise.
        message (str): Message sent to user.
    """

    status_code: int
    message: str


class TokenExpiredError(AuthError):
    """
    Exception to raise when token has expired.
    Attributes:
        status_code (int): HTTP status code to raise. Default to 401.
        message (str): Message sent to user. Default to "Token expired".
    """

    status_code: int = 401
    message: str = "Token expired."


class ChatStorageAuthDecodeError(AuthError):
    """
    Exception to raise when token decoding has failed.
    Attributes:
        status_code (int): HTTP status code to raise. Default to 401.
        message (str): Message sent to user. Default to "Invalid token."
    """

    status_code: int = 401
    message: str = "Invalid token."


class InvalidTokenSignatureError(AuthError):
    """
    Exception to raise when validating token by external service has failed.
    Attributes:
        status_code (int): HTTP status code to raise. Equal to 401.
        message (str): Message sent to user. Default to "Invalid token signature."
    """

    status_code: int = 401
    message: str = "Invalid token signature."


class InvalidAudienceError(AuthError):
    """
    Exception for handling audience.
    Attributes:
        status_code (int): HTTP status code to raise. Equal to 403.
        message (str): Message sent to user. Default to ""Invalid token audience."
    """

    status_code: int = 403
    message: str = "Invalid token audience."
