"""Celery worker entry point. Container + tasks are wired in Task 3."""

from celery import Celery


celery_app = Celery("golf_worker", broker="redis://localhost:6379/0")
