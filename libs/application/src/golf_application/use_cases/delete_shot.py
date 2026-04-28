from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import ShotDeleted
from golf_domain.ids import SessionId, ShotId

from ..ports import EventPublisher, SessionRepository, ShotRepository


class DeleteShotInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId


class DeleteShotUseCase:
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

    async def execute(self, input: DeleteShotInput) -> None:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        await self._shots.delete(input.shot_id)
        await self._events.publish(
            ShotDeleted(
                session_id=session.id,
                shot_id=input.shot_id,
                occurred_at=datetime.now(),
            )
        )
