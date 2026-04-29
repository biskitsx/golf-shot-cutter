import asyncio

from celery import Celery
from pydantic import BaseModel

from app.core.models.ids import SessionId, ShotId
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.core.models.events import ShotBoundaryUpdated, ShotDeleted, ShotDetected
from app.infrastructure.clock import SystemClock
from app.infrastructure.id_generator import UlidIdGenerator
from app.infrastructure.queue.celery_app import GENERATE_POSE_CLIP_TASK
from app.infrastructure.queue.redis_event_publisher import RedisEventPublisher
from app.infrastructure.storage.r2_storage import R2Storage, SignedUrl
from app.persistence.mongo.session_repository import MongoSessionRepository
from app.persistence.mongo.shot_repository import MongoShotRepository
from app.services.errors import ShotNotFoundError


class UpdateShotBoundaryInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId
    t_start: float
    t_end: float


class AddManualShotInput(BaseModel):
    session_id: SessionId
    t_impact: float
    t_start: float
    t_end: float


class DeleteShotInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId


class GetPoseClipInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId


class ShotService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        events: RedisEventPublisher,
        storage: R2Storage,
        celery: Celery,
        clock: SystemClock,
        ids: UlidIdGenerator,
        pose_clip_timeout_seconds: int = 120,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._events = events
        self._storage = storage
        self._celery = celery
        self._clock = clock
        self._ids = ids
        self._pose_timeout = pose_clip_timeout_seconds

    async def update_boundary(self, input: UpdateShotBoundaryInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        shot = await self._shots.get(input.shot_id)
        now = self._clock.now()
        adjusted = shot.adjust_boundary(t_start=input.t_start, t_end=input.t_end, now=now)
        await self._shots.update(adjusted)
        await self._events.publish(
            ShotBoundaryUpdated(
                session_id=session.id,
                shot_id=adjusted.id,
                t_start=adjusted.t_start,
                t_end=adjusted.t_end,
                occurred_at=now,
            )
        )
        return adjusted

    async def add_manual(self, input: AddManualShotInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        existing = await self._shots.list_by_session(session.id)
        next_index = (max(s.index for s in existing) + 1) if existing else 1
        now = self._clock.now()
        shot = Shot(
            id=self._ids.shot_id(),  # type: ignore[arg-type]
            session_id=session.id,
            index=next_index,
            t_impact=input.t_impact,
            t_start=input.t_start,
            t_end=input.t_end,
            confidence=Confidence(value=1.0),
            source=ShotSource.MANUAL,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
        await self._shots.add(shot)
        updated_session = session.model_copy(
            update={"shot_count": session.shot_count + 1, "updated_at": now}
        )
        await self._sessions.update(updated_session)
        await self._events.publish(
            ShotDetected(
                session_id=session.id,
                shot_id=shot.id,
                confidence=1.0,
                occurred_at=now,
            )
        )
        return shot

    async def get_pose_clip(self, input: GetPoseClipInput) -> SignedUrl:
        """Return a signed URL for the pose-overlay version of a shot's clip.

        Generates the overlay synchronously on first request (via a Celery
        task) and caches the result in object storage. Subsequent calls hit
        the cache and return immediately.
        """
        shot = await self._shots.get(input.shot_id)
        if shot.session_id != input.session_id:
            raise ShotNotFoundError(input.shot_id)
        if not shot.clip_key:
            raise ValueError("shot has no source clip yet")

        output_key = _pose_clip_key(shot.clip_key)
        if not await self._storage.object_exists(output_key):
            await asyncio.to_thread(
                self._dispatch_and_wait, shot.clip_key, output_key
            )
        return await self._storage.signed_get_url(output_key)

    def _dispatch_and_wait(self, source_key: str, output_key: str) -> None:
        async_result = self._celery.send_task(
            GENERATE_POSE_CLIP_TASK,
            args=[{"sourceKey": source_key, "outputKey": output_key}],
        )
        async_result.get(timeout=self._pose_timeout, propagate=True)

    async def delete(self, input: DeleteShotInput) -> None:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        await self._shots.delete(input.shot_id)
        now = self._clock.now()
        new_count = max(0, session.shot_count - 1)
        updated_session = session.model_copy(update={"shot_count": new_count, "updated_at": now})
        await self._sessions.update(updated_session)
        await self._events.publish(
            ShotDeleted(
                session_id=session.id,
                shot_id=input.shot_id,
                occurred_at=now,
            )
        )


def _pose_clip_key(clip_key: str) -> str:
    """Map `clips/<sid>/shot_NNN.mp4` → `clips-pose/<sid>/shot_NNN.mp4`.

    Falls back to a `pose-` prefix if the input doesn't start with `clips/`.
    """
    if clip_key.startswith("clips/"):
        return "clips-pose/" + clip_key[len("clips/") :]
    return f"clips-pose/{clip_key}"
