"""Chat space registry.

A chat space is the environment (provider) a chat belongs to. Every user-facing
chat query carries a space, so chats of one environment are never visible from
another. ``main`` is the default space and holds every chat created before
spaces were introduced.

Adding a space means adding one entry here, extending the ``ChatSpace`` literal
in app/schema/chat_history_schema.py and adding a migration that extends the
``space`` enum in the chats validator (mirrored in mongo/init/01-init.js).
"""

from dataclasses import dataclass

from app.schema.chat_history_schema import DEFAULT_CHAT_SPACE, ChatSpace


@dataclass(frozen=True)
class ChatSpaceDefinition:
    """One selectable chat space with its human-readable labels."""

    slug: ChatSpace
    title: str
    description: str

    @property
    def is_default(self) -> bool:
        """Whether this space is used when a request omits the filter."""

        return self.slug == DEFAULT_CHAT_SPACE


CHAT_SPACES: tuple[ChatSpaceDefinition, ...] = (
    ChatSpaceDefinition(
        slug="main",
        title="Помощник Проектировщика",
        description="Основное пространство помощника проектировщика.",
    ),
    ChatSpaceDefinition(
        slug="synapse",
        title="Synapse",
        description="Пространство чатов Synapse.",
    ),
)

CHAT_SPACE_SLUGS: tuple[ChatSpace, ...] = tuple(space.slug for space in CHAT_SPACES)


def get_chat_space(slug: ChatSpace) -> ChatSpaceDefinition:
    """
    Return the space definition for a slug.
    Args:
        slug (ChatSpace): Space slug.
    Returns:
        ChatSpaceDefinition: Matching space definition.
    """

    for space in CHAT_SPACES:
        if space.slug == slug:
            return space
    raise KeyError(f"Unknown chat space: {slug}")
