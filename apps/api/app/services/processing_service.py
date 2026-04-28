from pydantic import BaseModel, Field

from app.core.models.ids import SessionId
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.core.models.events import SessionReady, ShotDetected
from app.infrastructure.clock import SystemClock
from app.infrastructure.id_generator import UlidIdGenerator
from app.infrastructure.queue.redis_event_publisher import RedisEventPublisher
from app.persistence.mongo.session_repository import MongoSessionRepository
from app.persistence.mongo.shot_repository import MongoShotRepository


class ShotCandidate(BaseModel):
    t_impact: float
    confidence: float = Field(ge=0.0, le=1.0)
    clip_key: str


class ProcessVideoInput(BaseModel):
    session_id: SessionId
    candidates: list[ShotCandidate]


class ProcessingService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        events: RedisEventPublisher,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._events = events
        self._clock = clock
        self._ids = ids

    async def process(self, input: ProcessVideoInput) -> None:
        session = await self._sessions.get(input.session_id)
        now = self._clock.now()

        new_shots: list[Shot] = []
        for index, c in enumerate(input.candidates, start=1):
            t_start = max(0.0, c.t_impact - session.pre_roll_seconds)
            t_end = c.t_impact + session.post_roll_seconds
            shot = Shot(
                id=self._ids.shot_id(),  # type: ignore[arg-type]
                session_id=session.id,
                index=index,
                t_impact=c.t_impact,
                t_start=t_start,
                t_end=t_end,
                confidence=Confidence(value=c.confidence),
                source=ShotSource.AUTO,
                clip_key=c.clip_key,
                created_at=now,
                updated_at=now,
            )
            new_shots.append(shot)

        await self._shots.add_many(new_shots)
        for s in new_shots:
            await self._events.publish(
                ShotDetected(
                    session_id=session.id,
                    shot_id=s.id,
                    confidence=s.confidence.value,
                    occurred_at=now,
                )
            )

        ready = session.mark_ready(shot_count=len(new_shots), now=now)
        await self._sessions.update(ready)
        await self._events.publish(
            SessionReady(
                session_id=session.id,
                shot_count=len(new_shots),
                occurred_at=now,
            )
        )
