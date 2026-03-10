"""Tests for the Nominatim geocoding provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.geocoding.providers import NominatimProvider, GeocodingError


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_nominatim_success_parses_result(monkeypatch):
    """Provider parses a basic successful response into GeocodeResult."""

    def fake_get(self, url, params=None, headers=None):
        assert "q" in params
        payload = [
            {
                "lat": "41.15",
                "lon": "-8.61",
                "display_name": "Rua de Teste 123, Porto, Portugal",
                "address": {
                    "road": "Rua de Teste",
                    "city": "Porto",
                    "postcode": "4000-123",
                    "country_code": "pt",
                },
                "importance": 0.8,
            }
        ]
        return _FakeResponse(200, payload)

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    provider = NominatimProvider()
    result = provider.geocode("Rua de Teste 123, 4000-123 Porto, Portugal", country_code="PT")

    assert result is not None
    assert result.latitude == 41.15
    assert result.longitude == -8.61
    assert result.city == "Porto"
    assert result.postal_code == "4000-123"
    assert result.country_code == "PT"
    assert result.confidence == "HIGH"
    assert result.provider == "nominatim"


def test_nominatim_returns_none_on_empty_list(monkeypatch):
    """Provider returns None when Nominatim returns an empty list."""

    def fake_get(self, url, params=None, headers=None):
        return _FakeResponse(200, [])

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    provider = NominatimProvider()
    result = provider.geocode("No match street", country_code="PT")
    assert result is None


def test_nominatim_raises_geocoding_error_on_5xx(monkeypatch):
    """5xx responses are treated as transient provider errors."""

    def fake_get(self, url, params=None, headers=None):
        return _FakeResponse(503, [])

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    provider = NominatimProvider()
    try:
        provider.geocode("Rua de Teste 123", country_code="PT")
        assert False, "Expected GeocodingError"
    except GeocodingError:
        pass


def test_nominatim_raises_geocoding_error_on_request_error(monkeypatch):
    """Network errors from httpx are wrapped in GeocodingError."""

    def fake_get(self, url, params=None, headers=None):
        raise httpx.RequestError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    provider = NominatimProvider()
    try:
        provider.geocode("Rua de Teste 123", country_code="PT")
        assert False, "Expected GeocodingError"
    except GeocodingError:
        pass

