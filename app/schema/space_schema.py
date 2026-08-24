"""Chat space output schemas."""

from pydantic import BaseModel, Field

from app.schema.chat_history_schema import ChatSpace


class SpaceSchema(BaseModel):
    """One chat space available to the user."""

    slug: ChatSpace
    title: str
    description: str
    is_default: bool = False
    chat_count: int = 0


class SpaceListSchema(BaseModel):
    """All chat spaces with the user's chat counts."""

    items: list[SpaceSchema] = Field(default_factory=list)
    default_space: ChatSpace
