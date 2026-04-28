from app.repository.queue.job_queue_repository import ProcessVideoJob
from app.repository.queue.celery_app import make_celery_app
from app.repository.queue.job_queue_repository import CeleryJobQueueRepository


async def test_enqueue_records_send_call():
    app = make_celery_app(broker_url="memory://", result_backend="cache+memory://")
    app.conf.task_always_eager = True  # don't actually transmit; just verify shape
    captured: list[dict] = []

    @app.task(name="golf_worker.tasks.process_video")
    def _capture(payload: dict) -> None:
        captured.append(payload)

    queue = CeleryJobQueueRepository(app, eager=True)
    await queue.enqueue_process_video(ProcessVideoJob(session_id="ses_1"))
    assert captured == [{"sessionId": "ses_1"}]
