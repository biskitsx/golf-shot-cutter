from pydantic import BaseModel

from golf_domain.events import SessionProcessingStarted
from golf_domain.ids import SessionId
from golf_domain.session import SessionStatus

from ..ports import Clock, EventPublisher, JobQueue, ProcessVideoJob, SessionRepository


class StartProcessingInput(BaseModel):
    session_id: SessionId


class StartProcessingUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        queue: JobQueue,
        events: EventPublisher,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._events = events
        self._clock = clock

    async def execute(self, input: StartProcessingInput) -> None:
        session = await self._sessions.get(input.session_id)
        now = self._clock.now()

        if session.status is SessionStatus.UPLOADING:
            session = session.model_copy(update={"status": SessionStatus.QUEUED, "updated_at": now})

        moved = session.mark_processing(now=now)
        await self._sessions.update(moved)
        await self._queue.enqueue_process_video(ProcessVideoJob(session_id=moved.id))
        await self._events.publish(SessionProcessingStarted(session_id=moved.id, occurred_at=now))
