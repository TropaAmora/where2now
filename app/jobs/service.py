"""Job lifecycle service — owns all status transitions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import Job


class InvalidJobTransitionError(RuntimeError):
    """Raised when a caller attempts an illegal job status transition."""


class JobNotFoundError(RuntimeError):
    """Raised when job_id does not exist in the database."""


VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"running", "cancelled"},
    "running":   {"success", "failed", "cancelled"},
    "success":   set(),
    "failed":    set(),
    "cancelled": set(),
}


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, type: str, input_payload: dict | None, tenant_id: str) -> Job:
        job = Job(type=type, input_payload=input_payload, tenant_id=tenant_id)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def mark_running(self, job_id: uuid.UUID) -> Job:
        job = self._get_or_raise(job_id)
        self._transition(job, "running")
        job.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_success(self, job_id: uuid.UUID, result_payload: dict | None) -> Job:
        job = self._get_or_raise(job_id)
        self._transition(job, "success")
        job.result_payload = result_payload
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job_id: uuid.UUID, error: str) -> Job:
        job = self._get_or_raise(job_id)
        self._transition(job, "failed")
        job.error = error
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def cancel_job(self, job_id: uuid.UUID) -> Job:
        job = self._get_or_raise(job_id)
        self._transition(job, "cancelled")
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _transition(self, job: Job, new_status: str) -> None:
        allowed = VALID_TRANSITIONS[job.status]
        if new_status not in allowed:
            if not allowed:
                detail = "state is terminal — no transitions are allowed"
            else:
                detail = f"allowed transitions: {allowed}"
            raise InvalidJobTransitionError(
                f"Job {job.id}: cannot transition from '{job.status}' to '{new_status}' "
                f"({detail})"
            )
        job.status = new_status

    def _get_or_raise(self, job_id: uuid.UUID) -> Job:
        job = self.db.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} not found")
        return job
