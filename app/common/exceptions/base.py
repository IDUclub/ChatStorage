"""Base ChatStorage error is defined here."""


class ChatStorageError(Exception):
    """
    Base ChatStorage exception to inherit from.
    """

    def __str__(self) -> str:
        return f"Unexpected error happened in ChatStorage ({type(self).__qualname__})"
