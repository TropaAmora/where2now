"""Geocoding service."""

from __future__ import annotations

from typing import Optional

from app.config import settings
from app.geocoding.providers import NominatimProvider, GeocodingError
from app.geocoding.schemas import GeocodeResult


def _format_address_for_geocoder(
    address: str,
    zip: Optional[str],
    city: Optional[str],
    country_code: Optional[str],
) -> str:
    """Build a free-text address string suitable for external geocoders."""
    parts: list[str] = []

    # Base address is always first
    parts.append(address.strip())

    # Locality: zip + city if present
    locality_bits: list[str] = []
    if zip:
        locality_bits.append(zip.strip())
    if city:
        locality_bits.append(city.strip())
    if locality_bits:
        parts.append(" ".join(locality_bits))

    # Country: map PT -> Portugal for better results; otherwise use code as-is
    if country_code:
        cc = country_code.strip().upper()
        if cc == "PT":
            parts.append("Portugal")
        else:
            parts.append(cc)

    return ", ".join([p for p in parts if p])


def geocode_for_delivery_point(
    address: str,
    zip: Optional[str],
    city: Optional[str],
    country_code: Optional[str],
) -> tuple[Optional[GeocodeResult], Optional[str]]:
    """Sync function to get the geocode result for a delivery point.

    Returns (GeocodeResult or None, provider_name or None).

    - If GEOCODER_ENABLED is False, returns (None, None).
    - If provider finds no match, returns (None, provider_name).
    - If provider has a transient error, raises GeocodingError.
    """
    if not settings.GEOCODER_ENABLED:
        return None, None

    query = _format_address_for_geocoder(address, zip, city, country_code)

    # For now we only support Nominatim, but we already pass back the provider name
    provider_name = settings.GEOCODER_PROVIDER
    provider = NominatimProvider()

    # This may raise GeocodingError; the caller (e.g. delivery-points route)
    # will decide whether to return 503 or schedule a retry in the future.
    result = provider.geocode(query, country_code=country_code)

    return result, provider_name