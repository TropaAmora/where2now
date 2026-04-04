"""Tests for JobService — B2 job lifecycle management."""

import uuid

import pytest

from app.jobs.service import (
    InvalidJobTransitionError,
    JobNotFoundError,
    JobService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_service(db_session):
    return JobService(db_session)


def create_pending(svc: JobService) -> object:
    return svc.create_job(type="test", input_payload={"k": "v"}, tenant_id="tenant-1")


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------

class TestCreateJob:
    def test_status_is_pending(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        assert job.status == "pending"

    def test_timestamps_are_none_after_creation(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        assert job.started_at is None
        assert job.finished_at is None

    def test_payload_fields_are_none_after_creation(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        assert job.result_payload is None
        assert job.error is None

    def test_two_jobs_have_different_ids(self, db_session):
        svc = make_service(db_session)
        job1 = create_pending(svc)
        job2 = create_pending(svc)
        assert job1.id != job2.id


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------

class TestGetJob:
    def test_returns_job_by_uuid(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        fetched = svc.get_job(job.id)
        assert fetched is not None
        assert fetched.id == job.id

    def test_returns_none_for_unknown_uuid(self, db_session):
        svc = make_service(db_session)
        result = svc.get_job(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# mark_running
# ---------------------------------------------------------------------------

class TestMarkRunning:
    def test_transitions_pending_to_running(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        updated = svc.mark_running(job.id)
        assert updated.status == "running"

    def test_sets_started_at(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        updated = svc.mark_running(job.id)
        assert updated.started_at is not None

    def test_finished_at_remains_none(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        updated = svc.mark_running(job.id)
        assert updated.finished_at is None


# ---------------------------------------------------------------------------
# mark_success
# ---------------------------------------------------------------------------

class TestMarkSuccess:
    def test_transitions_running_to_success(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_success(job.id, result_payload={"score": 42})
        assert updated.status == "success"

    def test_sets_result_payload_and_finished_at(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_success(job.id, result_payload={"score": 42})
        assert updated.result_payload == {"score": 42}
        assert updated.finished_at is not None

    def test_error_remains_none(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_success(job.id, result_payload=None)
        assert updated.error is None


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------

class TestMarkFailed:
    def test_transitions_running_to_failed(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_failed(job.id, error="something broke")
        assert updated.status == "failed"

    def test_sets_error_and_finished_at(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_failed(job.id, error="something broke")
        assert updated.error == "something broke"
        assert updated.finished_at is not None

    def test_result_payload_remains_none(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.mark_failed(job.id, error="oops")
        assert updated.result_payload is None


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_cancels_pending_job(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        updated = svc.cancel_job(job.id)
        assert updated.status == "cancelled"
        assert updated.finished_at is not None

    def test_cancels_running_job(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        updated = svc.cancel_job(job.id)
        assert updated.status == "cancelled"
        assert updated.finished_at is not None


# ---------------------------------------------------------------------------
# Invalid transitions — InvalidJobTransitionError
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_pending_to_success_raises(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        with pytest.raises(InvalidJobTransitionError) as exc_info:
            svc.mark_success(job.id, result_payload=None)
        msg = str(exc_info.value)
        assert "pending" in msg
        assert "success" in msg

    def test_pending_to_failed_raises(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        with pytest.raises(InvalidJobTransitionError):
            svc.mark_failed(job.id, error="nope")

    def test_success_to_running_raises_with_terminal_message(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        svc.mark_success(job.id, result_payload=None)
        with pytest.raises(InvalidJobTransitionError) as exc_info:
            svc.mark_running(job.id)
        msg = str(exc_info.value).lower()
        assert "terminal" in msg or "set()" in msg

    def test_failed_to_running_raises(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.mark_running(job.id)
        svc.mark_failed(job.id, error="boom")
        with pytest.raises(InvalidJobTransitionError):
            svc.mark_running(job.id)

    def test_cancelled_to_running_raises(self, db_session):
        svc = make_service(db_session)
        job = create_pending(svc)
        svc.cancel_job(job.id)
        with pytest.raises(InvalidJobTransitionError):
            svc.mark_running(job.id)


# ---------------------------------------------------------------------------
# JobNotFoundError
# ---------------------------------------------------------------------------

class TestJobNotFoundError:
    def test_mark_running_unknown_id_raises(self, db_session):
        svc = make_service(db_session)
        with pytest.raises(JobNotFoundError):
            svc.mark_running(uuid.uuid4())

    def test_mark_success_unknown_id_raises(self, db_session):
        svc = make_service(db_session)
        with pytest.raises(JobNotFoundError):
            svc.mark_success(uuid.uuid4(), result_payload=None)

    def test_mark_failed_unknown_id_raises(self, db_session):
        svc = make_service(db_session)
        with pytest.raises(JobNotFoundError):
            svc.mark_failed(uuid.uuid4(), error="x")

    def test_cancel_job_unknown_id_raises(self, db_session):
        svc = make_service(db_session)
        with pytest.raises(JobNotFoundError):
            svc.cancel_job(uuid.uuid4())
