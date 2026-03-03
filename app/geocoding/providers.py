"""Geocoding providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.geocoding.schemas import GeocodeResult
from app.config import settings, Settings


class GeocodingError(Exception):
    """Represents a transient error talking to the external geocoding API."""
    pass

class GeocodingProvider(ABC):
    """Abstract base for all geocoding providers."""

    @abstractmethod
    def geocode(self, query: str, country_code: str | None = None) -> GeocodeResult | None:
        """Return a GeocodeResult for the query, None if no match.
        
        Should raise GeocodingError for network / timeout / 5xx type problems.
        """
        raise NotImplementedError


class NominatimProvider(GeocodingProvider):
    """Geocoding provider using an OpenStreetMap Nominatim-compatible API.

    NOTE: The default base URL points at the public Nominatim service and is
    intended for development / low-volume use. For production workloads you
    should configure a private Nominatim instance or a commercial provider
    and respect their usage policies and rate limits.
    """

    def __init__(self, app_settings: Settings | None = None) -> None:
        self._settings = app_settings or settings
        # For now we use the public nominatim endpoint; later we can make this configurable
        self._base_url = "https://nominatim.openstreetmap.org/search"
        # One client per provider instance; simple and testable
        self._client = httpx.Client(timeout=self._settings.GEOCODER_TIMEOUT)

    def geocode(self, query: str, country_code: Optional[str] = None) -> Optional[GeocodeResult]:
        """Sync geocode call against a Nominatim-compatible API."""
        params: dict[str, str] = {
            "q": query,
            "format": "json",
            "addressdetails": "1",
            "limit": "1",
        }
        if country_code:
            params["countrycodes"] = country_code.lower()

        headers = {
            # Nominatim requires a valid, identifying User-Agent
            "User-Agent": "where2now-geocoder/0.1",
        }

        try:
            resp = self._client.get(self._base_url, params=params, headers=headers)
        except httpx.RequestError as exc:
            raise GeocodingError(f"Network error talking to Nominatim: {exc}") from exc

        # Treat 5xx and 429 as transient provider errors
        if resp.status_code >= 500 or resp.status_code == 429:
            raise GeocodingError(f"Nominatim returned {resp.status_code}")
        # For other non-200 responses, we treat as "no result"
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, list) or not data:
            return None

        first = data[0]
        try:
            lat = float(first["lat"])
            lon = float(first["lon"])
        except (KeyError, ValueError, TypeError):
            # Malformed result; treat as no match
            return None

        address_info = first.get("address", {}) or {}
        street = (
            address_info.get("road")
            or address_info.get("pedestrian")
            or address_info.get("footway")
        )
        city = (
            address_info.get("city")
            or address_info.get("town")
            or address_info.get("village")
            or address_info.get("municipality")
        )
        postal_code = address_info.get("postcode")
        cc = address_info.get("country_code")
        country_code_norm = cc.upper() if isinstance(cc, str) else None

        # Map Nominatim's "importance" score into a simple confidence label
        importance = first.get("importance")
        confidence: str | None = None
        if isinstance(importance, (int, float)):
            if importance >= 0.75:
                confidence = "HIGH"
            elif importance >= 0.4:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

        return GeocodeResult(
            latitude=lat,
            longitude=lon,
            formatted_address=first.get("display_name"),
            street=street,
            city=city,
            postal_code=postal_code,
            country_code=country_code_norm,
            confidence=confidence,
            provider="nominatim",
        )