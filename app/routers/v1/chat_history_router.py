from fastapi import APIRouter

chat_history_router = APIRouter(prefix="api/v1/chat_history", tags=["chat_history"])
