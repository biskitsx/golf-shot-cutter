from pydantic import BaseModel, Field

from golf_domain.events import SessionReady, ShotDetected
from golf_domain.ids import SessionId
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..ports import (
    Clock,
    EventPublisher,
    IdGenerator,
    SessionRepository,
    ShotRepository,
)


class ShotCandidate(BaseModel):
    t_impact: float
    confidence: float = Field(ge=0.0, le=1.0)
    clip_key: str


class ProcessVideoInput(BaseModel):
    session_id: SessionId
    candidates: list[ShotCandidate]


class ProcessVideoUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events
        self._clock = clock
        self._ids = ids

    async def execute(self, input: ProcessVideoInput) -> None:
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

        ready = session.mark_ready(shot_count=len(new_shots))
        await self._sessions.update(ready)
        await self._events.publish(
            SessionReady(
                session_id=session.id,
                shot_count=len(new_shots),
                occurred_at=now,
            )
        )
