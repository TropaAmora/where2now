"""Tests for Story A1 travel-time contracts."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.travel_times_subsystem.schemas import (
    Confidence,
    DeliveryPointRef,
    LatLng,
    RequestMetadata,
    TransportMode,
    TravelTimeError,
    TravelTimeLeg,
    TravelTimeRequest,
    TravelTimeResult,
)


# ── LocationRef (discriminated union) ─────────────────────────────────────

class TestLatLng:
    def test_valid(self):
        loc = LatLng(lat=-33.87, lng=151.21)
        assert loc.type == "latlng"
        assert loc.lat == -33.87
        assert loc.lng == 151.21

    def test_lat_out_of_range(self):
        with pytest.raises(ValidationError):
            LatLng(lat=91, lng=0)

    def test_lng_out_of_range(self):
        with pytest.raises(ValidationError):
            LatLng(lat=0, lng=181)

    def test_boundary_values(self):
        loc = LatLng(lat=-90, lng=180)
        assert loc.lat == -90
        assert loc.lng == 180


class TestDeliveryPointRef:
    def test_valid(self):
        ref = DeliveryPointRef(delivery_point_id=42)
        assert ref.type == "delivery_point"
        assert ref.delivery_point_id == 42

    def test_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            DeliveryPointRef(delivery_point_id=0)

    def test_id_must_be_positive_negative(self):
        with pytest.raises(ValidationError):
            DeliveryPointRef(delivery_point_id=-1)


class TestLocationRefDiscriminator:
    """Verify that the discriminated union routes correctly via raw dicts."""

    def test_latlng_from_dict(self):
        req = TravelTimeRequest(
            origins=[{"type": "latlng", "lat": 1.0, "lng": 2.0}],
            destinations=[{"type": "latlng", "lat": 3.0, "lng": 4.0}],
        )
        assert isinstance(req.origins[0], LatLng)

    def test_delivery_point_from_dict(self):
        req = TravelTimeRequest(
            origins=[{"type": "delivery_point", "delivery_point_id": 7}],
            destinations=[{"type": "latlng", "lat": 3.0, "lng": 4.0}],
        )
        assert isinstance(req.origins[0], DeliveryPointRef)

    def test_mixed_locations(self):
        req = TravelTimeRequest(
            origins=[
                {"type": "latlng", "lat": 1.0, "lng": 2.0},
                {"type": "delivery_point", "delivery_point_id": 5},
            ],
            destinations=[{"type": "latlng", "lat": 3.0, "lng": 4.0}],
        )
        assert isinstance(req.origins[0], LatLng)
        assert isinstance(req.origins[1], DeliveryPointRef)

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            TravelTimeRequest(
                origins=[{"type": "magic", "value": "nope"}],
                destinations=[{"type": "latlng", "lat": 0, "lng": 0}],
            )


# ── TravelTimeRequest ────────────────────────────────────────────────────

class TestTravelTimeRequest:
    def _origin(self):
        return LatLng(lat=1.0, lng=2.0)

    def _destination(self):
        return LatLng(lat=3.0, lng=4.0)

    def test_minimal_request(self):
        req = TravelTimeRequest(
            origins=[self._origin()],
            destinations=[self._destination()],
        )
        assert req.transport_mode == TransportMode.DRIVING
        assert req.departure_time is None
        assert req.restrictions is None
        assert req.metadata is None

    def test_full_request(self):
        dep = datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)
        req = TravelTimeRequest(
            origins=[self._origin()],
            destinations=[self._destination()],
            departure_time=dep,
            transport_mode=TransportMode.WALKING,
            restrictions={"avoid_tolls": True},
            metadata=RequestMetadata(request_id="abc-123", user_id="u1"),
        )
        assert req.departure_time == dep
        assert req.transport_mode == TransportMode.WALKING
        assert req.restrictions == {"avoid_tolls": True}
        assert req.metadata.request_id == "abc-123"

    def test_origins_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            TravelTimeRequest(origins=[], destinations=[self._destination()])

    def test_destinations_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            TravelTimeRequest(origins=[self._origin()], destinations=[])

    def test_matrix_request(self):
        req = TravelTimeRequest(
            origins=[LatLng(lat=i, lng=i) for i in range(3)],
            destinations=[LatLng(lat=i + 10, lng=i + 10) for i in range(4)],
        )
        assert len(req.origins) == 3
        assert len(req.destinations) == 4


# ── TravelTimeLeg ────────────────────────────────────────────────────────

class TestTravelTimeLeg:
    def test_successful_leg(self):
        leg = TravelTimeLeg(
            origin_index=0,
            destination_index=1,
            duration_seconds=600,
            distance_meters=5000,
            confidence=Confidence.HIGH,
        )
        assert leg.duration_seconds == 600
        assert leg.error is None

    def test_failed_leg(self):
        leg = TravelTimeLeg(
            origin_index=0,
            destination_index=0,
            duration_seconds=None,
            distance_meters=None,
            error="No route found",
        )
        assert leg.duration_seconds is None
        assert leg.error == "No route found"

    def test_negative_index_rejected(self):
        with pytest.raises(ValidationError):
            TravelTimeLeg(origin_index=-1, destination_index=0)


# ── TravelTimeResult ────────────────────────────────────────────────────

class TestTravelTimeResult:
    def test_minimal_result(self):
        result = TravelTimeResult(provider="google")
        assert result.provider == "google"
        assert result.legs == []
        assert result.errors == []
        assert result.request_id is None

    def test_full_result(self):
        result = TravelTimeResult(
            request_id="req-1",
            provider="google",
            legs=[
                TravelTimeLeg(
                    origin_index=0,
                    destination_index=0,
                    duration_seconds=300,
                    distance_meters=2000,
                    confidence=Confidence.HIGH,
                ),
            ],
            errors=[
                TravelTimeError(
                    origin_index=0,
                    destination_index=1,
                    message="No route found",
                    code="NO_ROUTE",
                ),
            ],
        )
        assert len(result.legs) == 1
        assert result.legs[0].duration_seconds == 300
        assert len(result.errors) == 1
        assert result.errors[0].code == "NO_ROUTE"

    def test_global_error(self):
        err = TravelTimeError(message="Provider timeout")
        assert err.origin_index is None
        assert err.destination_index is None
        assert err.code is None


# ── Serialization round-trip ─────────────────────────────────────────────

class TestSerialization:
    def test_request_round_trip(self):
        req = TravelTimeRequest(
            origins=[LatLng(lat=1.0, lng=2.0)],
            destinations=[DeliveryPointRef(delivery_point_id=10)],
            transport_mode=TransportMode.BICYCLING,
        )
        data = req.model_dump()
        restored = TravelTimeRequest.model_validate(data)
        assert isinstance(restored.origins[0], LatLng)
        assert isinstance(restored.destinations[0], DeliveryPointRef)
        assert restored.transport_mode == TransportMode.BICYCLING

    def test_result_round_trip(self):
        result = TravelTimeResult(
            provider="historical",
            legs=[
                TravelTimeLeg(
                    origin_index=0,
                    destination_index=0,
                    duration_seconds=120,
                ),
            ],
        )
        data = result.model_dump()
        restored = TravelTimeResult.model_validate(data)
        assert restored.provider == "historical"
        assert restored.legs[0].duration_seconds == 120
