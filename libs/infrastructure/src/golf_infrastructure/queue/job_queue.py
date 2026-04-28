import asyncio

from celery import Celery

from golf_application.ports import ProcessVideoJob

from .celery_app import PROCESS_VIDEO_TASK


class CeleryJobQueue:
    def __init__(self, app: Celery) -> None:
        self._app = app

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        payload = {"sessionId": job.session_id}
        task = self._app.tasks.get(PROCESS_VIDEO_TASK)
        if task is not None:
            await asyncio.to_thread(task.apply, args=[payload])
        else:
            await asyncio.to_thread(self._app.send_task, PROCESS_VIDEO_TASK, args=[payload])
