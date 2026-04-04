"""Celery task definitions for the jobs subsystem.

B3: ping probe task — verifies broker connection and worker startup.
B4: run_travel_time_job — calls TravelTimeEngine and writes result via JobService.
"""

from app.celery_app import celery_app


@celery_app.task(name="where2now.ping")
def ping() -> str:
    return "pong"
