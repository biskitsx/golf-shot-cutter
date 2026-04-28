def test_process_video_celery_task_is_registered():
    """Confirm the task is registered with Celery under the expected name."""
    from app.infrastructure.queue.celery_app import PROCESS_VIDEO_TASK
    from worker_app.main import celery_app
    import worker_app.tasks.process_video  # noqa: F401 — registers the task

    assert PROCESS_VIDEO_TASK in celery_app.tasks
