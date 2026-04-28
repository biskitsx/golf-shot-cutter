from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import ShotBoundaryUpdated
from golf_domain.ids import SessionId, ShotId
from golf_domain.shot import Shot

from ..ports import EventPublisher, SessionRepository, ShotRepository


class UpdateShotBoundaryInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId
    t_start: float
    t_end: float


class UpdateShotBoundaryUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events

    async def execute(self, input: UpdateShotBoundaryInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()

        shot = await self._shots.get(input.shot_id)
        adjusted = shot.adjust_boundary(t_start=input.t_start, t_end=input.t_end)
        await self._shots.update(adjusted)
        await self._events.publish(
            ShotBoundaryUpdated(
                session_id=session.id,
                shot_id=adjusted.id,
                t_start=adjusted.t_start,
                t_end=adjusted.t_end,
                occurred_at=datetime.now(),
            )
        )
        return adjusted
