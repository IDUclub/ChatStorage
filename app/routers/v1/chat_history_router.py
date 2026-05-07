from fastapi import APIRouter, Body, Depends, Path, Query, status

from app.depndencies.auth_dependencies import (
    get_current_access_token,
    get_current_user_id,
)
from app.depndencies.dependencies import (
    get_chat_history_service,
    get_tool_call_execution_service,
)
from app.dto.message_dto import (
    ChatCreateDTO,
    MessageCreateDTO,
    ToolCallExtractDTO,
)
from app.schema.chat_history_schema import (
    ChatListSchema,
    ChatSchema,
    ChatSummarySchema,
    ChatTitleListSchema,
    DeleteChatSchema,
    MessagePartSchema,
    MessageSchema,
    ToolCallExecutionResultSchema,
)
from app.services.chat_history_service import ChatHistoryService
from app.services.tool_call_execution_service import ToolCallExecutionService

chat_history_router = APIRouter(prefix="/api/v1/chat_history", tags=["chat_history"])


CHAT_ID_EXAMPLE = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
MESSAGE_ID_EXAMPLE = "8ec7f7b8-ec3f-4bb9-a6c4-89f7a930bda1"


@chat_history_router.get("/chats", response_model=ChatListSchema)
async def get_user_chats(
    limit: int = Query(default=50, ge=1, le=100, examples=[20]),
    offset: int = Query(default=0, ge=0, examples=[0]),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> ChatListSchema:
    """
    Example:
    GET /api/v1/chat_history/chats?limit=20&offset=0
    Authorization: Bearer <token>
    """

    return await service.get_chats(user_id=user_id, limit=limit, offset=offset)


@chat_history_router.get("/chats/titles", response_model=ChatTitleListSchema)
async def get_user_unique_chat_titles(
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> ChatTitleListSchema:
    """
    Example:
    GET /api/v1/chat_history/chats/titles
    Authorization: Bearer <token>
    """

    return await service.get_unique_chat_titles(user_id=user_id)


@chat_history_router.post(
    "/create_chat",
    response_model=ChatSummarySchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_empty_user_chat(
    payload: ChatCreateDTO | None = Body(
        default=None,
        openapi_examples={
            "create_chat": {
                "summary": "Create chat",
                "value": {
                    "title": "New assistant chat",
                    "scenario_id": "default",
                    "metadata": {"source": "web"},
                },
            }
        },
    ),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> ChatSummarySchema:
    """
    Example:
    POST /api/v1/chat_history/create_chat
    Authorization: Bearer <token>
    Content-Type: application/json

    {"title": "New assistant chat", "scenario_id": "default", "metadata": {"source": "web"}}
    """

    return await service.create_chat(user_id=user_id, payload=payload)


@chat_history_router.get("/{chat_id}", response_model=ChatSchema)
async def get_user_chat_by_id(
    chat_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        examples=[CHAT_ID_EXAMPLE],
    ),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> ChatSchema:
    """
    Example:
    GET /api/v1/chat_history/f47ac10b-58cc-4372-a567-0e02b2c3d479
    Authorization: Bearer <token>
    """

    return await service.get_chat(user_id=user_id, chat_id=chat_id)


@chat_history_router.post(
    "/{chat_id}/message",
    response_model=MessageSchema,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    message: MessageCreateDTO = Body(
        ...,
        openapi_examples={
            "text_message": {
                "summary": "Create text message",
                "value": {
                    "role": "user",
                    "content": "What can you tell me about this project?",
                    "metadata": {"client_message_id": "local-1"},
                },
            },
            "multipart_message": {
                "summary": "Create message with explicit parts",
                "value": {
                    "role": "assistant",
                    "parts": [
                        {
                            "kind": "text",
                            "payload": {
                                "text": "I can help with the chat history API."
                            },
                        },
                        {
                            "kind": "status",
                            "payload": {"status": "done", "text": "Completed"},
                        },
                    ],
                    "metadata": {"model": "assistant"},
                },
            },
        },
    ),
    chat_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        examples=[CHAT_ID_EXAMPLE],
    ),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> MessageSchema:
    """
    Example:
    POST /api/v1/chat_history/f47ac10b-58cc-4372-a567-0e02b2c3d479/message
    Authorization: Bearer <token>
    Content-Type: application/json

    {"role": "user", "content": "What can you tell me about this project?", "metadata": {"client_message_id": "local-1"}}
    """

    return await service.add_message(user_id=user_id, chat_id=chat_id, message=message)


@chat_history_router.get(
    "/{chat_id}/messages/{message_id}/parts/{part_seq}",
    response_model=MessagePartSchema,
)
async def get_message_part(
    chat_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        examples=[CHAT_ID_EXAMPLE],
    ),
    message_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        examples=[MESSAGE_ID_EXAMPLE],
    ),
    part_seq: int = Path(..., ge=1, examples=[1]),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> MessagePartSchema:
    """
    Example:
    GET /api/v1/chat_history/f47ac10b-58cc-4372-a567-0e02b2c3d479/messages/8ec7f7b8-ec3f-4bb9-a6c4-89f7a930bda1/parts/1
    Authorization: Bearer <token>
    """

    return await service.get_message_part(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        part_seq=part_seq,
    )


@chat_history_router.post(
    "/tool_call/execute",
    response_model=ToolCallExecutionResultSchema,
)
async def execute_tool_call(
    payload: ToolCallExtractDTO = Body(
        ...,
        openapi_examples={
            "restriction_chain": {
                "summary": "Execute tool call with previous calls",
                "value": {
                    "scenario_id": 772,
                    "previous_tool_calls": [
                        {
                            "step": 1,
                            "tool_name": "GetPhysicalObjects",
                            "arguments": {"physical_objects_names": ["водный объект"]},
                        },
                        {
                            "step": 2,
                            "tool_name": "GetPhysicalObjects",
                            "arguments": {"physical_objects_names": ["жилой дом"]},
                        },
                        {
                            "step": 3,
                            "tool_name": "CreateBuffers",
                            "arguments": {
                                "buffer_info": {
                                    "водный объект": {
                                        "buffer_size": 200,
                                        "buffer_type": "round",
                                        "title": "Зоны возможного подтопления",
                                    }
                                }
                            },
                        },
                    ],
                    "tool_call": {
                        "step": 4,
                        "tool_name": "CreateRestrictions",
                        "arguments": {
                            "generators": ["Зоны возможного подтопления"],
                            "objects": ["жилой дом"],
                            "restrictions": {
                                "Зоны возможного подтопления": {
                                    "title": "Запрет размещения жилой застройки",
                                    "description": "Жилые дома не могут размещаться в пределах 200 м от зон возможного подтопления",
                                    "to": ["жилой дом"],
                                }
                            },
                        },
                    },
                },
            }
        },
    ),
    token: str = Depends(get_current_access_token),
    service: ToolCallExecutionService = Depends(get_tool_call_execution_service),
) -> ToolCallExecutionResultSchema:
    """
    Example:
    POST /api/v1/chat_history/tool_call/execute
    Authorization: Bearer <token>
    Content-Type: application/json
    """

    return await service.execute_tool_call(token, payload)


@chat_history_router.delete("/{chat_id}", response_model=DeleteChatSchema)
async def delete_chat(
    chat_id: str = Path(
        ...,
        min_length=36,
        max_length=36,
        examples=[CHAT_ID_EXAMPLE],
    ),
    user_id: str = Depends(get_current_user_id),
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> DeleteChatSchema:
    """
    Example:
    DELETE /api/v1/chat_history/f47ac10b-58cc-4372-a567-0e02b2c3d479
    Authorization: Bearer <token>
    """

    return await service.delete_chat(user_id=user_id, chat_id=chat_id)
