from fastapi import APIRouter, Depends

from app.depndencies.auth_dependencies import get_current_user_id
from app.dto.message_dto import MessageDTO

chat_history_router = APIRouter(prefix="/api/v1/chat_history", tags=["chat_history"])


@chat_history_router.get("/user_id")
async def check_auth(user_id=Depends(get_current_user_id)):
    return {"user_id": user_id}


@chat_history_router.get("/chats")
async def get_user_chats(user_id=Depends(get_current_user_id)):
    pass


@chat_history_router.post("/create_chat")
async def create_empty_user_chat(user_id=Depends(get_current_user_id)):
    pass


@chat_history_router.get("/{chat_id}")
async def get_user_chat_by_id(chat_id: int, user_id=Depends(get_current_user_id)):
    pass


@chat_history_router.post("/{chat_id}/message")
async def post_message(
    chat_id: int, message: MessageDTO, user_id=Depends(get_current_user_id)
):
    pass


@chat_history_router.get("/{chat_id/{message_id}/{chunk_id}")
async def get_tool_call_result(user_id=Depends(get_current_user_id)):
    pass
