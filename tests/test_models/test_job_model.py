"""ORM round-trip tests for the Job model (Story B1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.job import Job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job(**kwargs) -> Job:
    """Return a Job instance with sensible defaults; caller can override any field."""
    defaults = dict(
        type="travel_time",
        input_payload={"origin": "A", "destination": "B"},
    )
    defaults.update(kwargs)
    return Job(**defaults)


# ---------------------------------------------------------------------------
# Primary key
# ---------------------------------------------------------------------------

def test_job_id_is_auto_generated_uuid(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert isinstance(job.id, uuid.UUID)


def test_two_jobs_get_different_ids(db_session):
    job_a = make_job()
    job_b = make_job()
    db_session.add_all([job_a, job_b])
    db_session.commit()

    assert job_a.id != job_b.id


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_status_defaults_to_pending(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.status == "pending"


def test_tenant_id_defaults_to_default(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.tenant_id == "default"


def test_started_at_and_finished_at_default_to_none(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.started_at is None
    assert job.finished_at is None


def test_result_payload_and_error_default_to_none(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.result_payload is None
    assert job.error is None


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------

def test_created_at_and_updated_at_are_set_on_insert(db_session):
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.created_at is not None
    assert job.updated_at is not None


def test_created_at_is_a_datetime(db_session):
    # SQLite strips tzinfo on read-back; on PostgreSQL created_at is timezone-aware.
    # We verify the value is set and is a datetime — timezone-awareness is tested at the
    # model level (the default lambda uses timezone.utc) rather than via SQLite round-trip.
    job = make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert isinstance(job.created_at, datetime)


# ---------------------------------------------------------------------------
# Field round-trips
# ---------------------------------------------------------------------------

def test_input_payload_round_trips_as_json(db_session):
    payload = {"key": "value", "count": 3}
    job = make_job(input_payload=payload)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.input_payload == payload


def test_result_payload_and_error_can_be_set(db_session):
    job = make_job(
        result_payload={"duration_seconds": 600},
        error=None,
    )
    db_session.add(job)
    db_session.commit()

    job.status = "success"
    job.result_payload = {"duration_seconds": 600}
    db_session.commit()
    db_session.refresh(job)

    assert job.status == "success"
    assert job.result_payload["duration_seconds"] == 600


def test_started_at_and_finished_at_can_be_set_explicitly(db_session):
    now = datetime.now(timezone.utc)
    job = make_job(started_at=now, finished_at=now, status="success")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.started_at is not None
    assert job.finished_at is not None


def test_error_field_stores_message(db_session):
    job = make_job(status="failed", error="Provider timed out")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.error == "Provider timed out"
