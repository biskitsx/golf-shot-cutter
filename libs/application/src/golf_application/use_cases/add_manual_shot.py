from pydantic import BaseModel

from golf_domain.events import ShotDetected
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


class AddManualShotInput(BaseModel):
    session_id: SessionId
    t_impact: float
    t_start: float
    t_end: float


class AddManualShotUseCase:
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

    async def execute(self, input: AddManualShotInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()

        existing = await self._shots.list_by_session(session.id)
        next_index = len(existing) + 1
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
        await self._events.publish(
            ShotDetected(
                session_id=session.id,
                shot_id=shot.id,
                confidence=1.0,
                occurred_at=now,
            )
        )
        return shot
