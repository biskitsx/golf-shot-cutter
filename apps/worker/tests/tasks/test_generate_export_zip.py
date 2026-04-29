def test_export_zip_task_is_registered():
    from app.infrastructure.queue.celery_app import GENERATE_EXPORT_ZIP_TASK
    from worker_app.main import celery_app
    import worker_app.tasks.generate_export_zip  # noqa: F401

    assert GENERATE_EXPORT_ZIP_TASK in celery_app.tasks
