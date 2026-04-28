from celery import Celery


def make_celery_app(*, broker_url: str, result_backend: str) -> Celery:
    app = Celery("golf", broker=broker_url, backend=result_backend)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_routes={
            "golf_worker.tasks.process_video": {"queue": "video"},
            "golf_worker.tasks.generate_export_zip": {"queue": "export"},
        },
    )
    return app


PROCESS_VIDEO_TASK = "golf_worker.tasks.process_video"
GENERATE_EXPORT_ZIP_TASK = "golf_worker.tasks.generate_export_zip"
