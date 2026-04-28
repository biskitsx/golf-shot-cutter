from typing import Protocol

from pydantic import BaseModel

from golf_domain.ids import SessionId


class ProcessVideoJob(BaseModel):
    session_id: SessionId


class JobQueue(Protocol):
    async def enqueue_process_video(self, job: ProcessVideoJob) -> None: ...
