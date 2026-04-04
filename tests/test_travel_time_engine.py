"""Tests for Story A2 travel-time engine interfaces."""

from __future__ import annotations

from app.travel_times_subsystem.engine import EngineStrategy, TravelTimeEngine
from app.travel_times_subsystem.providers import TravelTimeProvider, TravelTimeProviderError
from app.travel_times_subsystem.resolvers import LocationResolver, LocationResolutionError
from app.travel_times_subsystem.schemas import (
    DeliveryPointRef,
    LatLng,
    RequestMetadata,
    TravelTimeRequest,
    TravelTimeResult,
)


class StubResolver(LocationResolver):
    def __init__(self, mapping: dict[int, LatLng]) -> None:
        self._mapping = mapping

    def resolve(self, refs: list[DeliveryPointRef]) -> dict[int, LatLng]:
        missing = [ref.delivery_point_id for ref in refs if ref.delivery_point_id not in self._mapping]
        if missing:
            raise LocationResolutionError(
                missing_ids=missing,
                message=f"Could not resolve delivery points: {missing}",
            )
        return {ref.delivery_point_id: self._mapping[ref.delivery_point_id] for ref in refs}


class CapturingProvider(TravelTimeProvider):
    def __init__(self, provider_name: str = "capturing") -> None:
        self._name = provider_name
        self.last_request: TravelTimeRequest | None = None

    @property
    def name(self) -> str:
        return self._name

    def get_travel_times(self, request: TravelTimeRequest) -> TravelTimeResult:
        self.last_request = request
        request_id = request.metadata.request_id if request.metadata else None
        return TravelTimeResult(request_id=request_id, provider=self.name)


class FailingProvider(TravelTimeProvider):
    def __init__(self, provider_name: str, message: str = "provider failed") -> None:
        self._name = provider_name
        self._message = message

    @property
    def name(self) -> str:
        return self._name

    def get_travel_times(self, request: TravelTimeRequest) -> TravelTimeResult:
        raise TravelTimeProviderError(provider_name=self.name, message=self._message)


def test_init_requires_at_least_one_provider():
    resolver = StubResolver(mapping={})
    try:
        TravelTimeEngine(providers=[], strategy=EngineStrategy.SINGLE, resolver=resolver)
        assert False, "Expected ValueError for empty provider list"
    except ValueError:
        assert True


def test_single_strategy_resolves_delivery_point_refs_before_provider_call():
    resolver = StubResolver(mapping={10: LatLng(lat=40.1, lng=-8.4)})
    provider = CapturingProvider(provider_name="google")
    engine = TravelTimeEngine(
        providers=[provider],
        strategy=EngineStrategy.SINGLE,
        resolver=resolver,
    )
    request = TravelTimeRequest(
        origins=[DeliveryPointRef(delivery_point_id=10)],
        destinations=[LatLng(lat=41.2, lng=-8.6)],
        metadata=RequestMetadata(request_id="req-1"),
    )

    result = engine.get_travel_times(request)

    assert result.provider == "google"
    assert provider.last_request is not None
    assert isinstance(provider.last_request.origins[0], LatLng)
    assert provider.last_request.origins[0].lat == 40.1
    assert provider.last_request.origins[0].lng == -8.4


def test_single_strategy_returns_error_result_when_provider_fails():
    resolver = StubResolver(mapping={})
    provider = FailingProvider(provider_name="google", message="timeout")
    engine = TravelTimeEngine(
        providers=[provider],
        strategy=EngineStrategy.SINGLE,
        resolver=resolver,
    )
    request = TravelTimeRequest(
        origins=[LatLng(lat=40.0, lng=-8.0)],
        destinations=[LatLng(lat=41.0, lng=-8.6)],
        metadata=RequestMetadata(request_id="req-2"),
    )

    result = engine.get_travel_times(request)

    assert result.provider == "engine"
    assert result.request_id == "req-2"
    assert len(result.errors) == 1
    assert result.errors[0].code == "single_provider_failed"


def test_fallback_chain_uses_next_provider_after_failure():
    resolver = StubResolver(mapping={})
    first = FailingProvider(provider_name="google", message="network down")
    second = CapturingProvider(provider_name="historical")
    engine = TravelTimeEngine(
        providers=[first, second],
        strategy=EngineStrategy.FALLBACK_CHAIN,
        resolver=resolver,
    )
    request = TravelTimeRequest(
        origins=[LatLng(lat=40.0, lng=-8.0)],
        destinations=[LatLng(lat=41.0, lng=-8.6)],
        metadata=RequestMetadata(request_id="req-3"),
    )

    result = engine.get_travel_times(request)

    assert result.provider == "historical"
    assert second.last_request is not None


def test_returns_location_resolution_error_result_without_calling_providers():
    resolver = StubResolver(mapping={})
    provider = CapturingProvider(provider_name="google")
    engine = TravelTimeEngine(
        providers=[provider],
        strategy=EngineStrategy.SINGLE,
        resolver=resolver,
    )
    request = TravelTimeRequest(
        origins=[DeliveryPointRef(delivery_point_id=99)],
        destinations=[LatLng(lat=41.0, lng=-8.6)],
        metadata=RequestMetadata(request_id="req-4"),
    )

    result = engine.get_travel_times(request)

    assert result.provider == "engine"
    assert result.request_id == "req-4"
    assert len(result.errors) == 1
    assert result.errors[0].code == "location_resolution_failed"
    assert provider.last_request is None
