from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.models.events import SessionProcessingStarted
from app.core.models.ids import SessionId, UserId
from app.core.models.session import Session, SessionStatus
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.event_publisher_repository import RedisEventPublisherRepository
from app.repository.queue.job_queue_repository import CeleryJobQueueRepository, ProcessVideoJob
from app.repository.r2.storage_repository import R2StorageRepository, SignedUrl


class CreateSessionInput(BaseModel):
    user_id: UserId | None
    original_filename: str = Field(min_length=1)
    pre_roll_seconds: float = Field(ge=0, default=2.0)
    post_roll_seconds: float = Field(ge=0, default=5.0)


class CreateSessionOutput(BaseModel):
    session_id: str
    signed_upload_url: str
    expires_at: datetime


class StartProcessingInput(BaseModel):
    session_id: SessionId


class ListSessionsInput(BaseModel):
    user_id: UserId | None


class GetSessionWithShotsInput(BaseModel):
    session_id: SessionId


class GetSessionWithShotsOutput(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    session: Session
    shots: list


class RequestSignedUploadUrlInput(BaseModel):
    session_id: SessionId


class SessionService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        storage: R2StorageRepository,
        queue: CeleryJobQueueRepository,
        events: RedisEventPublisherRepository,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._storage = storage
        self._queue = queue
        self._events = events
        self._clock = clock
        self._ids = ids

    async def create(self, input: CreateSessionInput) -> CreateSessionOutput:
        session_id = self._ids.session_id()
        raw_key = f"raw/{session_id}/{input.original_filename}"
        now = self._clock.now()
        signed = await self._storage.signed_put_url(raw_key, content_type="video/mp4")

        session = Session(
            id=session_id,  # type: ignore[arg-type]
            user_id=input.user_id,
            raw_video_key=raw_key,
            status=SessionStatus.UPLOADING,
            pre_roll_seconds=input.pre_roll_seconds,
            post_roll_seconds=input.post_roll_seconds,
            shot_count=0,
            duration_seconds=0.0,
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self._sessions.add(session)
        return CreateSessionOutput(
            session_id=session_id,
            signed_upload_url=signed.url,
            expires_at=signed.expires_at,
        )

    async def request_upload_url(self, input: RequestSignedUploadUrlInput) -> SignedUrl:
        session = await self._sessions.get(input.session_id)
        return await self._storage.signed_put_url(session.raw_video_key, content_type="video/mp4")

    async def start_processing(self, input: StartProcessingInput) -> None:
        session = await self._sessions.get(input.session_id)
        now = self._clock.now()

        if session.status is SessionStatus.UPLOADING:
            session = session.model_copy(update={"status": SessionStatus.QUEUED, "updated_at": now})

        moved = session.mark_processing(now=now)
        await self._sessions.update(moved)
        await self._queue.enqueue_process_video(ProcessVideoJob(session_id=moved.id))
        await self._events.publish(SessionProcessingStarted(session_id=moved.id, occurred_at=now))

    async def list(self, input: ListSessionsInput) -> list[Session]:
        return await self._sessions.list_for_user(input.user_id)

    async def get_with_shots(self, input: GetSessionWithShotsInput) -> GetSessionWithShotsOutput:
        session = await self._sessions.get(input.session_id)
        shots = await self._shots.list_by_session(session.id)
        return GetSessionWithShotsOutput(session=session, shots=shots)
