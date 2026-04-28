from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import SessionProcessingStarted
from golf_domain.ids import SessionId
from golf_domain.session import SessionStatus

from ..ports import EventPublisher, JobQueue, ProcessVideoJob, SessionRepository


class StartProcessingInput(BaseModel):
    session_id: SessionId


class StartProcessingUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        queue: JobQueue,
        events: EventPublisher,
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._events = events

    async def execute(self, input: StartProcessingInput) -> None:
        session = await self._sessions.get(input.session_id)

        if session.status is SessionStatus.UPLOADING:
            session = session.model_copy(update={"status": SessionStatus.QUEUED})

        moved = session.mark_processing()
        await self._sessions.update(moved)
        await self._queue.enqueue_process_video(ProcessVideoJob(session_id=moved.id))
        await self._events.publish(
            SessionProcessingStarted(session_id=moved.id, occurred_at=datetime.now())
        )
