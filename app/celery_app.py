"""Celery application instance for where2now.

Start a worker (Linux / macOS):
    celery -A app.celery_app worker --loglevel=info

Start a worker (Windows — solo pool avoids multiprocessing issues):
    celery -A app.celery_app worker --loglevel=info --pool=solo
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "where2now",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.jobs.tasks"],
)

celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
