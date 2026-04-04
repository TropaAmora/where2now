"""Tests for Story A3 — GoogleTravelTimeProvider with mocked httpx."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.travel_times_subsystem.google_provider import GoogleTravelTimeProvider
from app.travel_times_subsystem.providers import TravelTimeProviderError
from app.travel_times_subsystem.schemas import (
    Confidence,
    LatLng,
    RequestMetadata,
    TransportMode,
    TravelTimeRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_matrix_response(
    rows: list[list[dict]],
) -> dict:
    """Build a minimal Distance Matrix JSON body with the given element rows."""
    return {
        "status": "OK",
        "rows": [
            {"elements": elements}
            for elements in rows
        ],
    }


def _make_provider(
    handler: httpx.MockTransport | None = None,
    *,
    api_key: str = "test-key",
    max_retries: int = 0,
) -> GoogleTravelTimeProvider:
    transport = handler or httpx.MockTransport(lambda _req: httpx.Response(200, json={"status": "OK", "rows": []}))
    client = httpx.Client(transport=transport)
    return GoogleTravelTimeProvider(
        client=client,
        api_key=api_key,
        max_retries=max_retries,
    )


def _simple_request(**overrides) -> TravelTimeRequest:
    defaults = dict(
        origins=[LatLng(lat=40.0, lng=-8.0)],
        destinations=[LatLng(lat=41.0, lng=-8.5)],
        metadata=RequestMetadata(request_id="req-g1"),
    )
    defaults.update(overrides)
    return TravelTimeRequest(**defaults)


# ---------------------------------------------------------------------------
# Success: 1×1 matrix
# ---------------------------------------------------------------------------

def test_single_leg_success():
    body = _ok_matrix_response([
        [{"status": "OK", "duration": {"value": 3600}, "distance": {"value": 120000}}],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    result = provider.get_travel_times(_simple_request())

    assert result.provider == "google"
    assert result.request_id == "req-g1"
    assert len(result.legs) == 1

    leg = result.legs[0]
    assert leg.origin_index == 0
    assert leg.destination_index == 0
    assert leg.duration_seconds == 3600
    assert leg.distance_meters == 120000
    assert leg.confidence == Confidence.HIGH
    assert leg.error is None


# ---------------------------------------------------------------------------
# Success: 2×2 matrix — row-major ordering
# ---------------------------------------------------------------------------

def test_matrix_row_major_order():
    body = _ok_matrix_response([
        [
            {"status": "OK", "duration": {"value": 100}, "distance": {"value": 1000}},
            {"status": "OK", "duration": {"value": 200}, "distance": {"value": 2000}},
        ],
        [
            {"status": "OK", "duration": {"value": 300}, "distance": {"value": 3000}},
            {"status": "OK", "duration": {"value": 400}, "distance": {"value": 4000}},
        ],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    request = _simple_request(
        origins=[LatLng(lat=40.0, lng=-8.0), LatLng(lat=40.5, lng=-8.2)],
        destinations=[LatLng(lat=41.0, lng=-8.5), LatLng(lat=41.5, lng=-8.7)],
    )
    result = provider.get_travel_times(request)

    assert len(result.legs) == 4
    assert (result.legs[0].origin_index, result.legs[0].destination_index) == (0, 0)
    assert (result.legs[1].origin_index, result.legs[1].destination_index) == (0, 1)
    assert (result.legs[2].origin_index, result.legs[2].destination_index) == (1, 0)
    assert (result.legs[3].origin_index, result.legs[3].destination_index) == (1, 1)
    assert result.legs[3].duration_seconds == 400


# ---------------------------------------------------------------------------
# Prefers duration_in_traffic when available
# ---------------------------------------------------------------------------

def test_prefers_duration_in_traffic():
    body = _ok_matrix_response([
        [{"status": "OK", "duration": {"value": 3600}, "duration_in_traffic": {"value": 4200}, "distance": {"value": 1000}}],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    result = provider.get_travel_times(_simple_request())

    assert result.legs[0].duration_seconds == 4200


# ---------------------------------------------------------------------------
# departure_time parameter
# ---------------------------------------------------------------------------

def test_departure_time_sent_for_driving():
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"status": "OK", "rows": []})

    transport = httpx.MockTransport(handler)
    provider = _make_provider(transport)

    dt = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
    request = _simple_request(departure_time=dt, transport_mode=TransportMode.DRIVING)
    provider.get_travel_times(request)

    url = str(captured_requests[0].url)
    assert f"departure_time={int(dt.timestamp())}" in url


def test_departure_time_not_sent_for_walking():
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"status": "OK", "rows": []})

    transport = httpx.MockTransport(handler)
    provider = _make_provider(transport)

    dt = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
    request = _simple_request(departure_time=dt, transport_mode=TransportMode.WALKING)
    provider.get_travel_times(request)

    url = str(captured_requests[0].url)
    assert "departure_time" not in url


# ---------------------------------------------------------------------------
# Element-level failures → leg with error (not exception)
# ---------------------------------------------------------------------------

def test_element_not_found_produces_leg_with_error():
    body = _ok_matrix_response([
        [{"status": "NOT_FOUND"}],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    result = provider.get_travel_times(_simple_request())

    assert len(result.legs) == 1
    leg = result.legs[0]
    assert leg.error is not None
    assert "NOT_FOUND" in leg.error
    assert leg.duration_seconds is None


def test_element_zero_results_produces_leg_with_error():
    body = _ok_matrix_response([
        [{"status": "ZERO_RESULTS"}],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    result = provider.get_travel_times(_simple_request())

    assert result.legs[0].error is not None
    assert "ZERO_RESULTS" in result.legs[0].error


# ---------------------------------------------------------------------------
# Partial element failure in a matrix
# ---------------------------------------------------------------------------

def test_partial_element_failure():
    body = _ok_matrix_response([
        [
            {"status": "OK", "duration": {"value": 100}, "distance": {"value": 500}},
            {"status": "NOT_FOUND"},
        ],
    ])
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    request = _simple_request(
        destinations=[LatLng(lat=41.0, lng=-8.5), LatLng(lat=42.0, lng=-9.0)],
    )
    result = provider.get_travel_times(request)

    assert len(result.legs) == 2
    assert result.legs[0].duration_seconds == 100
    assert result.legs[0].error is None
    assert result.legs[1].error is not None


# ---------------------------------------------------------------------------
# HTTP 401/403 → TravelTimeProviderError (no retry)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_code", [401, 403])
def test_http_auth_error_raises_provider_error(status_code: int):
    transport = httpx.MockTransport(lambda _req: httpx.Response(status_code))
    provider = _make_provider(transport)

    with pytest.raises(TravelTimeProviderError) as exc_info:
        provider.get_travel_times(_simple_request())

    assert "auth" in exc_info.value.message.lower()
    assert exc_info.value.provider_name == "google"


# ---------------------------------------------------------------------------
# HTTP 5xx → retries then TravelTimeProviderError
# ---------------------------------------------------------------------------

def test_5xx_retries_then_raises():
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    provider = _make_provider(transport, max_retries=2)

    with pytest.raises(TravelTimeProviderError) as exc_info:
        provider.get_travel_times(_simple_request())

    assert call_count == 3  # 1 initial + 2 retries
    assert "failed after" in exc_info.value.message.lower()


def test_5xx_succeeds_on_retry():
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"status": "OK", "rows": []})

    transport = httpx.MockTransport(handler)
    provider = _make_provider(transport, max_retries=2)

    result = provider.get_travel_times(_simple_request())
    assert result.provider == "google"
    assert call_count == 2


# ---------------------------------------------------------------------------
# Top-level REQUEST_DENIED → TravelTimeProviderError
# ---------------------------------------------------------------------------

def test_top_level_request_denied():
    body = {"status": "REQUEST_DENIED", "error_message": "Invalid API key"}
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=body))
    provider = _make_provider(transport)

    with pytest.raises(TravelTimeProviderError) as exc_info:
        provider.get_travel_times(_simple_request())

    assert "REQUEST_DENIED" in exc_info.value.message
    assert exc_info.value.provider_name == "google"


# ---------------------------------------------------------------------------
# Transport error (network failure) → TravelTimeProviderError
# ---------------------------------------------------------------------------

def test_transport_error_raises_provider_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    provider = _make_provider(transport, max_retries=1)

    with pytest.raises(TravelTimeProviderError):
        provider.get_travel_times(_simple_request())


# ---------------------------------------------------------------------------
# name property
# ---------------------------------------------------------------------------

def test_name_property_returns_google():
    provider = _make_provider()
    assert provider.name == "google"
