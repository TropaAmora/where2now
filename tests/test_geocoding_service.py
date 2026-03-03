"""Tests for the geocoding service helpers."""

from app.geocoding.service import _format_address_for_geocoder, geocode_for_delivery_point
from app.geocoding.schemas import GeocodeResult
from app.geocoding.providers import NominatimProvider, GeocodingError
from app.config import settings


def test_format_address_for_geocoder_full_portugal_address():
    """Formats PT address as 'Rua X, ZIP City, Portugal'."""
    formatted = _format_address_for_geocoder(
        address="Rua de Teste 123",
        zip="4000-123",
        city="Porto",
        country_code="PT",
    )
    assert formatted == "Rua de Teste 123, 4000-123 Porto, Portugal"


def test_format_address_for_geocoder_without_city():
    """When city is missing, format omits it but keeps ZIP and country."""
    formatted = _format_address_for_geocoder(
        address="Rua de Teste 123",
        zip="4000-123",
        city=None,
        country_code="PT",
    )
    assert formatted == "Rua de Teste 123, 4000-123, Portugal"


def test_geocode_for_delivery_point_returns_none_when_disabled(monkeypatch):
    """When GEOCODER_ENABLED is False, geocode_for_delivery_point is a no-op."""
    old_enabled = settings.GEOCODER_ENABLED
    settings.GEOCODER_ENABLED = False
    try:
        result, provider = geocode_for_delivery_point(
            address="Anything",
            zip=None,
            city=None,
            country_code=None,
        )
        assert result is None
        assert provider is None
    finally:
        settings.GEOCODER_ENABLED = old_enabled


def test_geocode_for_delivery_point_calls_provider_and_returns_result(monkeypatch):
    """When enabled, geocode_for_delivery_point returns provider result and name."""
    old_enabled = settings.GEOCODER_ENABLED
    settings.GEOCODER_ENABLED = True

    fake_result = GeocodeResult(
        latitude=1.23,
        longitude=4.56,
        formatted_address="Somewhere",
        provider="nominatim",
    )

    def fake_geocode(self, query: str, country_code: str | None = None):
        assert "Rua" in query  # sanity check on formatting
        return fake_result

    try:
        monkeypatch.setattr(NominatimProvider, "geocode", fake_geocode)
        result, provider_name = geocode_for_delivery_point(
            address="Rua Teste 1",
            zip="4000-123",
            city="Porto",
            country_code="PT",
        )
        assert result is fake_result
        assert provider_name == settings.GEOCODER_PROVIDER
    finally:
        settings.GEOCODER_ENABLED = old_enabled

