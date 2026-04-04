"""Tests for the job API endpoints (B5).

run_travel_time_job.delay is patched in every test that hits POST /travel-time
so no real Celery broker is required.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.jobs.service import JobService

VALID_PAYLOAD = {
    "origins": [{"type": "latlng", "lat": 52.37, "lng": 4.89}],
    "destinations": [{"type": "latlng", "lat": 52.38, "lng": 4.90}],
    "transport_mode": "driving",
}

TASK_PATH = "app.api.routes.jobs.run_travel_time_job"


# ---------------------------------------------------------------------------
# POST /api/jobs/travel-time
# ---------------------------------------------------------------------------

class TestCreateTravelTimeJob:
    def test_returns_202(self, client: TestClient):
        with patch(TASK_PATH) as mock_task:
            response = client.post("/api/jobs/travel-time", json=VALID_PAYLOAD)
        assert response.status_code == 202

    def test_status_is_pending(self, client: TestClient):
        with patch(TASK_PATH):
            response = client.post("/api/jobs/travel-time", json=VALID_PAYLOAD)
        assert response.json()["status"] == "pending"

    def test_response_contains_uuid_id(self, client: TestClient):
        with patch(TASK_PATH):
            response = client.post("/api/jobs/travel-time", json=VALID_PAYLOAD)
        job_id = response.json()["id"]
        uuid.UUID(job_id)  # raises if not a valid UUID

    def test_delay_called_once_with_job_id(self, client: TestClient):
        with patch(TASK_PATH) as mock_task:
            response = client.post("/api/jobs/travel-time", json=VALID_PAYLOAD)
        job_id = response.json()["id"]
        mock_task.delay.assert_called_once_with(job_id)

    def test_invalid_payload_returns_422(self, client: TestClient):
        response = client.post("/api/jobs/travel-time", json={"bad": "data"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

class TestGetJob:
    def test_returns_200_for_existing_job(self, client: TestClient, db_session):
        svc = JobService(db_session)
        job = svc.create_job(type="travel_time", input_payload={}, tenant_id="default")

        response = client.get(f"/api/jobs/{job.id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(job.id)
        assert response.json()["status"] == "pending"

    def test_returns_404_for_unknown_id(self, client: TestClient):
        response = client.get(f"/api/jobs/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/cancel
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_cancels_pending_job(self, client: TestClient, db_session):
        svc = JobService(db_session)
        job = svc.create_job(type="travel_time", input_payload={}, tenant_id="default")

        response = client.post(f"/api/jobs/{job.id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_returns_404_for_unknown_id(self, client: TestClient):
        response = client.post(f"/api/jobs/{uuid.uuid4()}/cancel")
        assert response.status_code == 404

    def test_returns_409_for_terminal_job(self, client: TestClient, db_session):
        svc = JobService(db_session)
        job = svc.create_job(type="travel_time", input_payload={}, tenant_id="default")
        svc.mark_running(job.id)
        svc.mark_success(job.id, result_payload={"done": True})

        response = client.post(f"/api/jobs/{job.id}/cancel")

        assert response.status_code == 409
        assert "terminal" in response.json()["detail"].lower()
