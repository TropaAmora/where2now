"""Job API endpoints (Story B5)."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_job_service
from app.jobs.schemas import JobRead
from app.jobs.service import InvalidJobTransitionError, JobNotFoundError, JobService
from app.jobs.tasks import run_travel_time_job
from app.travel_times_subsystem.schemas import TravelTimeRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/travel-time", response_model=JobRead, status_code=202)
def create_travel_time_job(
    payload: TravelTimeRequest,
    svc: JobService = Depends(get_job_service),
) -> JobRead:
    """Create an async travel-time job. Returns immediately with status PENDING."""
    job = svc.create_job(
        type="travel_time",
        input_payload=payload.model_dump(mode="json"),
        tenant_id="default",
    )
    run_travel_time_job.delay(str(job.id))
    logger.info("Enqueued travel_time job id=%s", job.id)
    return job


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    svc: JobService = Depends(get_job_service),
) -> JobRead:
    """Get job status and result by ID."""
    job = svc.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: uuid.UUID,
    svc: JobService = Depends(get_job_service),
) -> JobRead:
    """Cancel a pending or running job. Returns 409 if already in a terminal state."""
    try:
        return svc.cancel_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    except InvalidJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
