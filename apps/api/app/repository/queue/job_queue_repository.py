import asyncio

from celery import Celery
from pydantic import BaseModel

from app.core.models.ids import SessionId
from .celery_app import PROCESS_VIDEO_TASK


class ProcessVideoJob(BaseModel):
    session_id: SessionId


class CeleryJobQueueRepository:
    def __init__(self, app: Celery, *, eager: bool = False) -> None:
        self._app = app
        self._eager = eager

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        payload = {"sessionId": job.session_id}
        if self._eager:
            task = self._app.tasks[PROCESS_VIDEO_TASK]
            await asyncio.to_thread(task.apply, args=[payload])
        else:
            await asyncio.to_thread(self._app.send_task, PROCESS_VIDEO_TASK, args=[payload])
