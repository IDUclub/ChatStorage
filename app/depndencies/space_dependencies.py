"""Chat space request dependency."""

from fastapi import Query

from app.schema.chat_history_schema import DEFAULT_CHAT_SPACE, ChatSpace

SPACE_DESCRIPTION = (
    "Chat space the request is scoped to. Chats of other spaces are invisible; "
    f"defaults to '{DEFAULT_CHAT_SPACE}'."
)


async def get_current_space(
    space: ChatSpace = Query(
        default=DEFAULT_CHAT_SPACE,
        description=SPACE_DESCRIPTION,
        examples=["synapse"],
    ),
) -> ChatSpace:
    """
    Function returns the chat space the request is scoped to.
    Args:
        space (ChatSpace): Space slug from the query string.
    Returns:
        ChatSpace: Requested space, defaulting to the main space.
    """

    return space
