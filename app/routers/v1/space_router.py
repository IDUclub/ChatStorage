"""Chat space catalogue for the client space switcher."""

from fastapi import APIRouter, Depends

from app.common.spaces import CHAT_SPACES
from app.depndencies.auth_dependencies import get_current_user_id
from app.depndencies.dependencies import get_chat_history_service
from app.schema.chat_history_schema import DEFAULT_CHAT_SPACE
from app.schema.space_schema import SpaceListSchema, SpaceSchema
from app.services.chat_history_service import ChatHistoryService

space_router = APIRouter(prefix="/api/v1/spaces", tags=["spaces"])


@space_router.get("", response_model=SpaceListSchema)
async def get_spaces(
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> SpaceListSchema:
    """
    Example:
    GET /api/v1/spaces
    Authorization: Bearer <token>
    """

    counts = await service.count_chats_by_space(user_id=user_id)
    return SpaceListSchema(
        items=[
            SpaceSchema(
                slug=space.slug,
                title=space.title,
                description=space.description,
                is_default=space.is_default,
                chat_count=counts.get(space.slug, 0),
            )
            for space in CHAT_SPACES
        ],
        default_space=DEFAULT_CHAT_SPACE,
    )
