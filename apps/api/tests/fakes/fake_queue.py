from app.repository.queue.job_queue_repository import ProcessVideoJob


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[ProcessVideoJob] = []

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        self.enqueued.append(job)
