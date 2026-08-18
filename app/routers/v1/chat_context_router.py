"""Public context reads/enqueue and internal context-worker endpoints."""

from fastapi import APIRouter, Body, Depends, Path, Query, Response, status

from app.depndencies.auth_dependencies import (
    get_current_user_id,
    verify_service_token,
)
from app.depndencies.dependencies import get_chat_context_service
from app.schema.chat_context_schema import (
    ChatContextSchema,
    ContextJobClaimSchema,
    ContextJobCompletionSchema,
    ContextJobCreateSchema,
    ContextJobFailureSchema,
    ContextJobSchema,
)
from app.services.chat_context_service import ChatContextService

chat_context_router = APIRouter(prefix="/api/v1/chat_context", tags=["chat_context"])
internal_context_router = APIRouter(
    prefix="/api/v1/internal/chat_context",
    tags=["chat_context_internal"],
    dependencies=[Depends(verify_service_token)],
)


@chat_context_router.get("/{chat_id}", response_model=ChatContextSchema)
async def get_chat_context(
    chat_id: str = Path(..., min_length=36, max_length=36),
    tail_limit: int = Query(default=100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    service: ChatContextService = Depends(get_chat_context_service),
) -> ChatContextSchema:
    return await service.get_context(user_id, chat_id, tail_limit=tail_limit)


@chat_context_router.post(
    "/{chat_id}/jobs",
    response_model=ContextJobSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_chat_context(
    payload: ContextJobCreateSchema = Body(default_factory=ContextJobCreateSchema),
    chat_id: str = Path(..., min_length=36, max_length=36),
    user_id: str = Depends(get_current_user_id),
    service: ChatContextService = Depends(get_chat_context_service),
) -> ContextJobSchema:
    return await service.enqueue(
        user_id,
        chat_id,
        target_seq=payload.target_seq,
        model=payload.model,
        prompt_version=payload.prompt_version,
    )


@internal_context_router.post("/jobs/claim", response_model=ContextJobSchema | None)
async def claim_context_job(
    payload: ContextJobClaimSchema,
    response: Response,
    service: ChatContextService = Depends(get_chat_context_service),
) -> ContextJobSchema | None:
    job = await service.claim(payload.worker_id, payload.lease_seconds)
    if job is None:
        response.status_code = status.HTTP_204_NO_CONTENT
    return job


@internal_context_router.get("/jobs/{job_id}/source", response_model=ChatContextSchema)
async def get_context_job_source(
    job_id: str,
    worker_id: str = Query(..., min_length=1, max_length=128),
    after_seq: int | None = Query(default=None, ge=0),
    tail_limit: int = Query(default=100, ge=1, le=200),
    service: ChatContextService = Depends(get_chat_context_service),
) -> ChatContextSchema:
    return await service.get_job_source(
        job_id,
        worker_id,
        after_seq=after_seq,
        tail_limit=tail_limit,
    )


@internal_context_router.post(
    "/jobs/{job_id}/complete", response_model=ChatContextSchema
)
async def complete_context_job(
    job_id: str,
    payload: ContextJobCompletionSchema,
    service: ChatContextService = Depends(get_chat_context_service),
) -> ChatContextSchema:
    return await service.complete(job_id, payload.worker_id, payload.content)


@internal_context_router.post("/jobs/{job_id}/fail", response_model=ContextJobSchema)
async def fail_context_job(
    job_id: str,
    payload: ContextJobFailureSchema,
    service: ChatContextService = Depends(get_chat_context_service),
) -> ContextJobSchema:
    return await service.fail(job_id, payload.worker_id, payload.error)
