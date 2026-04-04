"""Pydantic schema tests for Story B1 — JobStatus and JobRead."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.jobs.schemas import JobRead, JobStatus
from app.models.job import Job


# ---------------------------------------------------------------------------
# JobStatus
# ---------------------------------------------------------------------------

def test_job_status_all_values_are_valid():
    assert JobStatus("pending") == JobStatus.PENDING
    assert JobStatus("running") == JobStatus.RUNNING
    assert JobStatus("success") == JobStatus.SUCCESS
    assert JobStatus("failed") == JobStatus.FAILED
    assert JobStatus("cancelled") == JobStatus.CANCELLED


def test_job_status_invalid_value_raises():
    with pytest.raises(ValueError):
        JobStatus("unknown")


def test_job_status_serializes_to_string():
    """JobStatus values serialize as plain strings, not enum repr."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.FAILED.value == "failed"


# ---------------------------------------------------------------------------
# JobRead — from_attributes round-trip
# ---------------------------------------------------------------------------

def _make_orm_job(**kwargs) -> Job:
    """Build an in-memory Job ORM instance (not persisted) for schema tests."""
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id="default",
        type="travel_time",
        status="pending",
        input_payload={"origin": "A"},
        result_payload=None,
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
    )
    defaults.update(kwargs)
    job = Job.__new__(Job)
    job.__dict__.update(defaults)
    return job


def test_job_read_maps_fields_from_orm_instance():
    orm_job = _make_orm_job()
    read = JobRead.model_validate(orm_job)

    assert read.id == orm_job.id
    assert read.type == "travel_time"
    assert read.status == JobStatus.PENDING
    assert read.input_payload == {"origin": "A"}
    assert read.result_payload is None
    assert read.error is None
    assert read.started_at is None
    assert read.finished_at is None


def test_job_read_does_not_expose_tenant_id():
    orm_job = _make_orm_job(tenant_id="acme")
    read = JobRead.model_validate(orm_job)

    assert not hasattr(read, "tenant_id")


def test_job_read_status_is_job_status_enum():
    orm_job = _make_orm_job(status="running")
    read = JobRead.model_validate(orm_job)

    assert read.status == JobStatus.RUNNING
    assert isinstance(read.status, JobStatus)


def test_job_read_started_at_and_finished_at_accept_datetime():
    now = datetime.now(timezone.utc)
    orm_job = _make_orm_job(
        status="success",
        started_at=now,
        finished_at=now,
        result_payload={"duration_seconds": 300},
    )
    read = JobRead.model_validate(orm_job)

    assert read.started_at == now
    assert read.finished_at == now
    assert read.result_payload == {"duration_seconds": 300}


def test_job_read_serializes_status_as_string_in_json():
    orm_job = _make_orm_job(status="failed", error="timeout")
    read = JobRead.model_validate(orm_job)
    data = read.model_dump()

    assert data["status"] == "failed"
    assert data["error"] == "timeout"
