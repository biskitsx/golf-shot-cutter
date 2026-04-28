"""Celery worker bootstrap. Container is wired before tasks are discovered."""

import os
import sys
from pathlib import Path

# macOS prefork-safety: cv2 + mediapipe pull in Apple Obj-C / Metal / OpenGL
# code. Celery's default `prefork` pool calls fork() to spawn workers, which
# crashes (SIGABRT) when an Obj-C class's `+initialize` was mid-flight in a
# parent thread. Setting this env var BEFORE any module that triggers Obj-C
# initialization is loaded is the documented Apple workaround. This is a
# dev-on-macOS concern only — Linux fork is unaffected.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

# Load apps/worker/.env into the process environment so tunables read via
# `os.environ.get(...)` inside task code (e.g. AUDIO_DELTA, POSE_PEAK_RATIO)
# pick up values from the .env file without needing to be `export`-ed in the
# shell. Pydantic-Settings already pulls in python-dotenv as a transitive dep.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

from celery import Celery  # noqa: E402

from worker_app.container import TASK_MODULES, WorkerContainer  # noqa: E402


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
