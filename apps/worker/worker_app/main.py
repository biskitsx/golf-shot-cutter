"""Celery worker bootstrap. Container is wired before tasks are discovered."""

from celery import Celery

from worker_app.container import TASK_MODULES, WorkerContainer


def make_celery() -> Celery:
    container = WorkerContainer()
    try:
        celery = container.celery_app()
        # Wire DI into task modules now that Settings is available.
        container.wire(modules=TASK_MODULES)
    except Exception:
        # Settings unavailable at import (e.g., in tests without env vars). Fall back to stub.
        celery = Celery(
            "golf_worker",
            broker="redis://localhost:6379/0",
            backend="redis://localhost:6379/0",
        )
    celery.autodiscover_tasks(["worker_app.tasks"], related_name=None, force=True)
    celery.conf.update(worker_container=container)
    return celery


celery_app = make_celery()
