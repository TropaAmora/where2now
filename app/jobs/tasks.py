"""Celery task definitions for the jobs subsystem.

B3: ping              — probe task, proves broker + worker are wired up.
B4: run_travel_time_job — calls TravelTimeEngine, writes result via JobService.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.jobs.service import JobService
from app.travel_times_subsystem.engine import TravelTimeEngine
from app.travel_times_subsystem.provider_factory import build_travel_time_engine
from app.travel_times_subsystem.schemas import TravelTimeRequest

logger = logging.getLogger(__name__)


@celery_app.task(name="where2now.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="where2now.run_travel_time_job")
def run_travel_time_job(job_id_str: str) -> None:
    """Celery entry-point. Opens a DB session, builds the engine, delegates to _execute."""
    db = SessionLocal()
    try:
        engine = build_travel_time_engine(db)
        _execute_travel_time_job(uuid.UUID(job_id_str), db, engine)
    finally:
        db.close()


def _execute_travel_time_job(
    job_id: uuid.UUID,
    db: Session,
    engine: TravelTimeEngine,
) -> None:
    """Business logic for a travel-time job. Directly testable without a broker."""
    svc = JobService(db)
    job = svc.mark_running(job_id)
    try:
        request = TravelTimeRequest.model_validate(job.input_payload)
        result = engine.get_travel_times(request)
        if result.errors:
            error_msg = "; ".join(e.message for e in result.errors)
            svc.mark_failed(job_id, error=error_msg)
        else:
            svc.mark_success(job_id, result_payload=result.model_dump(mode="json"))
    except Exception as exc:
        logger.exception("Unexpected error in travel time job %s", job_id)
        try:
            svc.mark_failed(job_id, error=str(exc))
        except Exception:
            logger.exception("Failed to mark job %s as failed after error", job_id)
