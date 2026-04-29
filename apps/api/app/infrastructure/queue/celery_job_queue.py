import asyncio

from celery import Celery
from pydantic import BaseModel

from app.core.models.ids import ExportId, SessionId

from app.infrastructure.queue.celery_app import GENERATE_EXPORT_ZIP_TASK, PROCESS_VIDEO_TASK


class ProcessVideoJob(BaseModel):
    session_id: SessionId


class GenerateExportZipJob(BaseModel):
    session_id: SessionId
    export_id: ExportId


class CeleryJobQueue:
    def __init__(self, app: Celery, *, eager: bool = False) -> None:
        self._app = app
        self._eager = eager

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        payload = {"sessionId": job.session_id}
        await self._send(PROCESS_VIDEO_TASK, payload)

    async def enqueue_generate_export_zip(self, job: GenerateExportZipJob) -> None:
        payload = {"sessionId": job.session_id, "exportId": job.export_id}
        await self._send(GENERATE_EXPORT_ZIP_TASK, payload)

    async def _send(self, task_name: str, payload: dict) -> None:
        if self._eager:
            task = self._app.tasks[task_name]
            await asyncio.to_thread(task.apply, args=[payload])
        else:
            await asyncio.to_thread(self._app.send_task, task_name, args=[payload])
