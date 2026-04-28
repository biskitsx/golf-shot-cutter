from pydantic import BaseModel

from golf_domain.events import ShotDeleted
from golf_domain.ids import SessionId, ShotId

from ..ports import Clock, EventPublisher, SessionRepository, ShotRepository


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
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events
        self._clock = clock

    async def execute(self, input: DeleteShotInput) -> None:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        now = self._clock.now()
        await self._shots.delete(input.shot_id)
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
