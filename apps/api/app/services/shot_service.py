from pydantic import BaseModel

from app.core.models.ids import SessionId, ShotId
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.core.models.events import ShotBoundaryUpdated, ShotDeleted, ShotDetected
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.event_publisher_repository import RedisEventPublisherRepository


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


class ShotService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        events: RedisEventPublisherRepository,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._events = events
        self._clock = clock
        self._ids = ids

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
