"""Durable chat-context snapshots and a Mongo-backed worker queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.schema.chat_context_schema import (
    ChatContextContentSchema,
    ChatContextSchema,
    ContextJobSchema,
)
from app.schema.chat_history_schema import DEFAULT_CHAT_SPACE, ChatSpace
from app.services.chat_history_service import ChatHistoryService

MAX_CONTEXT_ATTEMPTS = 3
CONTEXT_REVISION_RETENTION = 10


class ChatContextService:
    """Own context snapshots and coordinate external summarization workers."""

    def __init__(
        self, database: AsyncDatabase, history_service: ChatHistoryService
    ) -> None:
        self._db = database
        self._history = history_service
        self._chats = database["chats"]
        self._messages = database["messages"]
        self._contexts = database["chat_contexts"]
        self._revisions = database["chat_context_revisions"]
        self._jobs = database["context_jobs"]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    async def get_context(
        self,
        user_id: str,
        chat_id: str,
        *,
        tail_limit: int = 100,
        target_seq: int | None = None,
        after_seq: int | None = None,
        space: ChatSpace | None = None,
    ) -> ChatContextSchema:
        """Return the latest snapshot and a bounded unsummarized message tail.

        ``space=None`` skips the space check and is used by the internal worker
        endpoints, which resolve the chat from an already authorized job.
        """

        query = {"user_id": user_id, "chat_id": chat_id}
        if space is not None:
            query["space"] = space
        chat = await self._chats.find_one(query)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )

        context = await self._contexts.find_one(
            {"user_id": user_id, "chat_id": chat_id}
        )
        through = int((context or {}).get("updated_through_seq", 0))
        tail_after = max(through, after_seq or through)
        upper = target_seq if target_seq is not None else int(chat["next_seq"]) - 1
        cursor = (
            self._messages.find(
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "seq": {"$gt": tail_after, "$lte": upper},
                }
            )
            .sort("seq", ASCENDING)
            .limit(tail_limit + 1)
        )
        fetched = [self._history._message_from_document(item) async for item in cursor]
        tail_has_more = len(fetched) > tail_limit
        tail = fetched[:tail_limit]
        tail_next_after_seq = tail[-1].seq if tail_has_more and tail else None
        if context is None:
            return ChatContextSchema(
                chat_id=chat_id,
                target_seq=upper,
                tail=tail,
                tail_has_more=tail_has_more,
                tail_next_after_seq=tail_next_after_seq,
            )
        return self._context_from_document(
            context,
            tail=tail,
            tail_has_more=tail_has_more,
            tail_next_after_seq=tail_next_after_seq,
        )

    async def enqueue(
        self,
        user_id: str,
        chat_id: str,
        *,
        target_seq: int | None,
        model: str,
        prompt_version: str,
        space: ChatSpace = DEFAULT_CHAT_SPACE,
    ) -> ContextJobSchema:
        """Create one idempotent job for a context target revision."""

        chat = await self._chats.find_one(
            {"user_id": user_id, "chat_id": chat_id, "space": space}
        )
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        latest_seq = int(chat["next_seq"]) - 1
        target = min(target_seq or latest_seq, latest_seq)
        if target < 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chat has no messages to summarize",
            )

        now = self._now()
        document = {
            "job_id": str(uuid4()),
            "user_id": user_id,
            "chat_id": chat_id,
            "target_seq": target,
            "model": model,
            "prompt_version": prompt_version,
            "status": "pending",
            "attempts": 0,
            "lease_owner": None,
            "lease_until": None,
            "created_at": now,
            "updated_at": now,
            "last_error": None,
        }
        try:
            await self._jobs.insert_one(document)
        except DuplicateKeyError:
            existing = await self._jobs.find_one(
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "target_seq": target,
                    "prompt_version": prompt_version,
                }
            )
            if existing is None:
                raise
            document = existing
        return self._job_from_document(document)

    async def claim(
        self, worker_id: str, lease_seconds: int
    ) -> ContextJobSchema | None:
        """Lease the oldest pending/retryable job atomically."""

        now = self._now()
        document = await self._jobs.find_one_and_update(
            {
                "attempts": {"$lt": MAX_CONTEXT_ATTEMPTS},
                "$or": [
                    {"status": "pending"},
                    {"status": "leased", "lease_until": {"$lte": now}},
                ],
            },
            {
                "$set": {
                    "status": "leased",
                    "lease_owner": worker_id,
                    "lease_until": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        return self._job_from_document(document) if document else None

    async def get_job_source(
        self,
        job_id: str,
        worker_id: str,
        *,
        tail_limit: int = 100,
        after_seq: int | None = None,
    ) -> ChatContextSchema:
        """Return the prior snapshot and only the messages needed for this job."""

        job = await self._leased_job(job_id, worker_id)
        return await self.get_context(
            job["user_id"],
            job["chat_id"],
            tail_limit=tail_limit,
            target_seq=int(job["target_seq"]),
            after_seq=after_seq,
        )

    async def complete(
        self,
        job_id: str,
        worker_id: str,
        content: ChatContextContentSchema,
    ) -> ChatContextSchema:
        """Publish only if this job is newer than the current context (CAS by seq)."""

        job = await self._leased_job(job_id, worker_id)
        now = self._now()
        published = await self._publish_context_cas(job, content, now)

        await self._jobs.update_one(
            {"job_id": job_id, "lease_owner": worker_id},
            {
                "$set": {
                    "status": "completed",
                    "lease_owner": None,
                    "lease_until": None,
                    "updated_at": now,
                    "last_error": None,
                }
            },
        )
        return self._context_from_document(published)

    async def _publish_context_cas(
        self, job: dict, content: ChatContextContentSchema, now: datetime
    ) -> dict:
        identity = {"user_id": job["user_id"], "chat_id": job["chat_id"]}
        target = int(job["target_seq"])
        for _ in range(4):
            current = await self._contexts.find_one(identity)
            if current is not None and int(current["updated_through_seq"]) >= target:
                return current
            published = {
                **identity,
                "revision": int((current or {}).get("revision", 0)) + 1,
                "content": content.model_dump(mode="json"),
                "updated_through_seq": target,
                "target_seq": target,
                "model": job["model"],
                "prompt_version": job["prompt_version"],
                "status": "ready",
                "created_at": (current or {}).get("created_at", now),
                "updated_at": now,
                "last_error": None,
            }
            if current is None:
                try:
                    await self._contexts.insert_one(published)
                    await self._trim_revisions(job["user_id"], job["chat_id"])
                    return published
                except DuplicateKeyError:
                    continue
            result = await self._contexts.replace_one(
                {**identity, "revision": current["revision"]}, published
            )
            if result.modified_count == 1:
                archived = dict(current)
                archived.pop("_id", None)
                archived["archived_at"] = now
                await self._revisions.insert_one(archived)
                await self._trim_revisions(job["user_id"], job["chat_id"])
                return published
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Context changed while publishing; retry the job",
        )

    async def fail(self, job_id: str, worker_id: str, error: str) -> ContextJobSchema:
        """Release a job for retry, or mark it terminal after three attempts."""

        job = await self._leased_job(job_id, worker_id)
        terminal = int(job["attempts"]) >= MAX_CONTEXT_ATTEMPTS
        document = await self._jobs.find_one_and_update(
            {"job_id": job_id, "lease_owner": worker_id},
            {
                "$set": {
                    "status": "failed" if terminal else "pending",
                    "lease_owner": None,
                    "lease_until": None,
                    "last_error": error,
                    "updated_at": self._now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._job_from_document(document)

    async def _leased_job(self, job_id: str, worker_id: str) -> dict:
        job = await self._jobs.find_one(
            {"job_id": job_id, "status": "leased", "lease_owner": worker_id}
        )
        if not job:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Context job is not leased by this worker",
            )
        return job

    async def _trim_revisions(self, user_id: str, chat_id: str) -> None:
        cursor = (
            self._revisions.find({"user_id": user_id, "chat_id": chat_id}, {"_id": 1})
            .sort("revision", -1)
            .skip(CONTEXT_REVISION_RETENTION)
        )
        stale = [item["_id"] async for item in cursor]
        if stale:
            await self._revisions.delete_many({"_id": {"$in": stale}})

    @staticmethod
    def _job_from_document(document: dict) -> ContextJobSchema:
        return ContextJobSchema.model_validate(
            {key: value for key, value in document.items() if key != "_id"}
        )

    @staticmethod
    def _context_from_document(
        document: dict,
        *,
        tail: list | None = None,
        tail_has_more: bool = False,
        tail_next_after_seq: int | None = None,
    ) -> ChatContextSchema:
        payload = {key: value for key, value in document.items() if key != "_id"}
        payload["tail"] = tail or []
        payload["tail_has_more"] = tail_has_more
        payload["tail_next_after_seq"] = tail_next_after_seq
        return ChatContextSchema.model_validate(payload)
