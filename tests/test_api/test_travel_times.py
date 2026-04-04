"""Tests for POST /api/travel-times."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_travel_time_engine
from app.models.delivery_points import DeliveryPoint
from app.travel_times_subsystem.engine import TravelTimeEngine
from app.travel_times_subsystem.schemas import (
    TravelTimeLeg,
    TravelTimeResult,
)
from main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LATLNG_ORIGIN = {"type": "latlng", "lat": 52.37, "lng": 4.89}
LATLNG_DEST = {"type": "latlng", "lat": 52.38, "lng": 4.90}

LATLNG_PAYLOAD = {
    "origins": [LATLNG_ORIGIN],
    "destinations": [LATLNG_DEST],
}

STUB_LEG = TravelTimeLeg(
    origin_index=0,
    destination_index=0,
    duration_seconds=300,
    distance_meters=1500,
)

STUB_RESULT = TravelTimeResult(provider="google", legs=[STUB_LEG])


def stub_engine() -> TravelTimeEngine:
    """Returns a MagicMock that behaves like a TravelTimeEngine."""
    engine = MagicMock(spec=TravelTimeEngine)
    engine.get_travel_times.return_value = STUB_RESULT
    return engine


# ---------------------------------------------------------------------------
# Route tests (engine stubbed — verify HTTP layer only)
# ---------------------------------------------------------------------------

def test_post_travel_times_latlng_returns_200(client: TestClient):
    """Happy path: LatLng request returns 200 with the engine result."""
    app.dependency_overrides[get_travel_time_engine] = stub_engine

    response = client.post("/api/travel-times/", json=LATLNG_PAYLOAD)

    app.dependency_overrides.pop(get_travel_time_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "google"
    assert len(data["legs"]) == 1
    assert data["legs"][0]["duration_seconds"] == 300


def test_post_travel_times_location_resolution_failure_returns_200(client: TestClient):
    """When the engine returns a resolution error, the route still returns 200."""
    error_result = TravelTimeResult(
        provider="engine",
        errors=[{"message": "Delivery point 99 not found", "code": "location_resolution_failed"}],
    )
    mock_engine = MagicMock(spec=TravelTimeEngine)
    mock_engine.get_travel_times.return_value = error_result

    app.dependency_overrides[get_travel_time_engine] = lambda: mock_engine

    response = client.post(
        "/api/travel-times/",
        json={
            "origins": [{"type": "delivery_point", "delivery_point_id": 99}],
            "destinations": [LATLNG_DEST],
        },
    )

    app.dependency_overrides.pop(get_travel_time_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "engine"
    assert data["errors"][0]["code"] == "location_resolution_failed"


def test_post_travel_times_provider_failure_returns_200(client: TestClient):
    """When the engine reports a provider failure, the route still returns 200."""
    error_result = TravelTimeResult(
        provider="engine",
        errors=[{"message": "Google failed", "code": "single_provider_failed"}],
    )
    mock_engine = MagicMock(spec=TravelTimeEngine)
    mock_engine.get_travel_times.return_value = error_result

    app.dependency_overrides[get_travel_time_engine] = lambda: mock_engine

    response = client.post("/api/travel-times/", json=LATLNG_PAYLOAD)

    app.dependency_overrides.pop(get_travel_time_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "engine"
    assert data["errors"][0]["code"] == "single_provider_failed"


def test_post_travel_times_invalid_payload_returns_422(client: TestClient):
    """Missing required fields return 422 (FastAPI validation)."""
    response = client.post("/api/travel-times/", json={"origins": []})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Integration test (real dependency graph, DB-backed resolver)
# ---------------------------------------------------------------------------

def test_post_travel_times_delivery_point_ref_resolves_via_db(client: TestClient, db_session):
    """DeliveryPointRef with a missing ID resolves to location_resolution_failed via the real engine."""
    # Override the engine with a real one backed by the test DB session,
    # but stub the Google provider so no HTTP call is made.
    from app.travel_times_subsystem.engine import EngineStrategy
    from app.travel_times_subsystem.resolvers import DbLocationResolver
    from app.travel_times_subsystem.providers import TravelTimeProvider, TravelTimeProviderError

    class NeverCalledProvider(TravelTimeProvider):
        @property
        def name(self) -> str:
            return "never_called"

        def get_travel_times(self, request):
            raise AssertionError("Provider should not be called when resolution fails")

    real_engine = TravelTimeEngine(
        providers=[NeverCalledProvider()],
        strategy=EngineStrategy.SINGLE,
        resolver=DbLocationResolver(db_session),
    )

    app.dependency_overrides[get_travel_time_engine] = lambda: real_engine

    response = client.post(
        "/api/travel-times/",
        json={
            "origins": [{"type": "delivery_point", "delivery_point_id": 9999}],
            "destinations": [LATLNG_DEST],
        },
    )

    app.dependency_overrides.pop(get_travel_time_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "engine"
    assert any(e["code"] == "location_resolution_failed" for e in data["errors"])
