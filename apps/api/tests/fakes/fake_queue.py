from app.repository.queue.job_queue_repository import (
    GenerateExportZipJob,
    ProcessVideoJob,
)


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[ProcessVideoJob] = []
        self.export_jobs: list[GenerateExportZipJob] = []

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        self.enqueued.append(job)

    async def enqueue_generate_export_zip(self, job: GenerateExportZipJob) -> None:
        self.export_jobs.append(job)
