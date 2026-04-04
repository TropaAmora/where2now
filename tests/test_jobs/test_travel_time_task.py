"""Tests for the travel-time Celery task (B4).

All tests call _execute_travel_time_job directly — no broker or live engine needed.
The TravelTimeEngine is replaced with a MagicMock in every test.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from app.celery_app import celery_app
from app.jobs.service import JobService
from app.jobs.tasks import _execute_travel_time_job
from app.travel_times_subsystem.schemas import (
    TravelTimeLeg,
    TravelTimeError,
    TravelTimeResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_INPUT_PAYLOAD = {
    "origins": [{"type": "latlng", "lat": 52.37, "lng": 4.89}],
    "destinations": [{"type": "latlng", "lat": 52.38, "lng": 4.90}],
    "transport_mode": "driving",
}


@pytest.fixture
def svc(db_session):
    return JobService(db_session)


@pytest.fixture
def pending_job(svc):
    return svc.create_job(
        type="travel_time",
        input_payload=VALID_INPUT_PAYLOAD,
        tenant_id="test",
    )


def make_mock_engine(result: TravelTimeResult) -> MagicMock:
    engine = MagicMock()
    engine.get_travel_times.return_value = result
    return engine


def success_result() -> TravelTimeResult:
    return TravelTimeResult(
        provider="mock",
        legs=[
            TravelTimeLeg(
                origin_index=0,
                destination_index=0,
                duration_seconds=300,
                distance_meters=2000,
            )
        ],
    )


def error_result(message: str = "quota exceeded") -> TravelTimeResult:
    return TravelTimeResult(
        provider="mock",
        errors=[TravelTimeError(message=message, code="quota")],
    )


# ---------------------------------------------------------------------------
# Happy path — SUCCESS
# ---------------------------------------------------------------------------

class TestSuccess:
    def test_status_is_success(self, db_session, svc, pending_job):
        engine = make_mock_engine(success_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.status == "success"

    def test_result_payload_contains_legs(self, db_session, svc, pending_job):
        engine = make_mock_engine(success_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert "legs" in job.result_payload
        assert job.result_payload["legs"][0]["duration_seconds"] == 300

    def test_result_payload_contains_provider(self, db_session, svc, pending_job):
        engine = make_mock_engine(success_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.result_payload["provider"] == "mock"

    def test_error_is_none(self, db_session, svc, pending_job):
        engine = make_mock_engine(success_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.error is None

    def test_timestamps_set(self, db_session, svc, pending_job):
        engine = make_mock_engine(success_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.started_at is not None
        assert job.finished_at is not None


# ---------------------------------------------------------------------------
# Provider errors — FAILED
# ---------------------------------------------------------------------------

class TestProviderErrors:
    def test_status_is_failed(self, db_session, svc, pending_job):
        engine = make_mock_engine(error_result("quota exceeded"))
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.status == "failed"

    def test_error_message_propagated(self, db_session, svc, pending_job):
        engine = make_mock_engine(error_result("quota exceeded"))
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert "quota exceeded" in job.error

    def test_result_payload_is_none(self, db_session, svc, pending_job):
        engine = make_mock_engine(error_result())
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.result_payload is None

    def test_multiple_errors_joined(self, db_session, svc, pending_job):
        result = TravelTimeResult(
            provider="mock",
            errors=[
                TravelTimeError(message="error one", code="e1"),
                TravelTimeError(message="error two", code="e2"),
            ],
        )
        engine = make_mock_engine(result)
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert "error one" in job.error
        assert "error two" in job.error


# ---------------------------------------------------------------------------
# Unexpected exception — FAILED
# ---------------------------------------------------------------------------

class TestUnexpectedException:
    def test_status_is_failed(self, db_session, svc, pending_job):
        engine = MagicMock()
        engine.get_travel_times.side_effect = RuntimeError("network timeout")
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert job.status == "failed"

    def test_error_contains_exception_message(self, db_session, svc, pending_job):
        engine = MagicMock()
        engine.get_travel_times.side_effect = RuntimeError("network timeout")
        _execute_travel_time_job(pending_job.id, db_session, engine)
        job = svc.get_job(pending_job.id)
        assert "network timeout" in job.error


# ---------------------------------------------------------------------------
# Invalid input_payload — FAILED
# ---------------------------------------------------------------------------

class TestInvalidPayload:
    def test_status_is_failed(self, db_session, svc):
        job = svc.create_job(
            type="travel_time",
            input_payload={"bad": "data"},
            tenant_id="test",
        )
        engine = MagicMock()
        _execute_travel_time_job(job.id, db_session, engine)
        updated = svc.get_job(job.id)
        assert updated.status == "failed"
        assert updated.error

    def test_engine_never_called(self, db_session, svc):
        job = svc.create_job(
            type="travel_time",
            input_payload={"bad": "data"},
            tenant_id="test",
        )
        engine = MagicMock()
        _execute_travel_time_job(job.id, db_session, engine)
        engine.get_travel_times.assert_not_called()


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

def test_task_registered():
    assert "where2now.run_travel_time_job" in celery_app.tasks
