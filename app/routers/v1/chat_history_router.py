from fastapi import APIRouter

from app.dto.message_dto import MessageDTO

chat_history_router = APIRouter(prefix="api/v1/chat_history", tags=["chat_history"])


@chat_history_router.get("/{user_id}/chats")
async def get_user_chats(user_id: str):
    pass


@chat_history_router.post("/{user_id}/create_chat")
async def create_empty_user_chat(
    user_id: str,
):
    pass


@chat_history_router.get("/{user_id}/{chat_id}")
async def get_user_chat_by_id(user_id: str, chat_id: int):
    pass


@chat_history_router.post("/{user_id}/{chat_id}/message")
async def post_message(user_id: str, chat_id: int, message: MessageDTO):
    pass


@chat_history_router.get("/{user_id}/{chat_id/{message_id}/{chunk_id}")
async def get_tool_call_result():
    pass
