"""Google Maps Distance Matrix provider for travel times (Story A3)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.travel_times_subsystem.providers import TravelTimeProvider, TravelTimeProviderError
from app.travel_times_subsystem.schemas import (
    Confidence,
    LatLng,
    TravelTimeLeg,
    TravelTimeRequest,
    TravelTimeResult,
    TransportMode,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# TransportMode → Google Distance Matrix `mode` parameter.
# Our enum values ("driving", "walking", "bicycling", "transit") match Google's
# accepted values exactly, so the mapping is a direct `.value` pass-through.
TRANSPORT_MODE_MAP: dict[TransportMode, str] = {
    TransportMode.DRIVING: "driving",
    TransportMode.WALKING: "walking",
    TransportMode.BICYCLING: "bicycling",
    TransportMode.TRANSIT: "transit",
}

# Top-level status codes that indicate auth / quota problems (non-retryable).
_AUTH_STATUSES = frozenset({"REQUEST_DENIED", "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT"})

# Element-level status codes that mean "no route" rather than a hard failure.
_NO_ROUTE_STATUSES = frozenset({"NOT_FOUND", "ZERO_RESULTS", "MAX_ROUTE_LENGTH_EXCEEDED"})


class GoogleTravelTimeProvider(TravelTimeProvider):
    """Calls the Google Distance Matrix API and maps the response to
    ``TravelTimeResult``.

    Parameters
    ----------
    client:
        Pre-configured ``httpx.Client`` — tests inject a mock here.
    api_key:
        Google server API key.
    base_url:
        Override the endpoint (useful for tests or regional endpoints).
    max_retries:
        Number of retries on transient (5xx) errors before giving up.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        return "google"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_travel_times(self, request: TravelTimeRequest) -> TravelTimeResult:
        request_id = request.metadata.request_id if request.metadata else None
        params = self._build_params(request)

        data = self._call_api(params)
        self._check_top_level_status(data)

        legs = self._parse_legs(data)

        return TravelTimeResult(
            request_id=request_id,
            provider=self.name,
            legs=legs,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _format_locations(locations: list[LatLng]) -> str:
        """Pipe-separated ``lat,lng`` string expected by the API."""
        return "|".join(f"{loc.lat},{loc.lng}" for loc in locations)

    def _build_params(self, request: TravelTimeRequest) -> dict:
        origins = [loc for loc in request.origins if isinstance(loc, LatLng)]
        destinations = [loc for loc in request.destinations if isinstance(loc, LatLng)]

        params: dict[str, str] = {
            "origins": self._format_locations(origins),
            "destinations": self._format_locations(destinations),
            "mode": TRANSPORT_MODE_MAP[request.transport_mode],
            "key": self._api_key,
        }

        # departure_time activates traffic-aware estimates for driving mode.
        # Google expects a Unix-epoch integer or the literal "now".
        if request.departure_time is not None and request.transport_mode == TransportMode.DRIVING:
            ts = int(request.departure_time.timestamp())
            params["departure_time"] = str(ts)

        return params

    def _call_api(self, params: dict) -> dict:
        """GET with simple retry on 5xx."""
        last_exc: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                response = self._client.get(self._base_url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("Google API transport error (attempt %d): %s", attempt + 1, exc)
                continue

            if response.status_code in {401, 403}:
                raise TravelTimeProviderError(
                    provider_name=self.name,
                    message=f"Google API auth error: HTTP {response.status_code}",
                )

            if response.status_code >= 500:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                logger.warning("Google API 5xx (attempt %d): %s", attempt + 1, response.status_code)
                continue

            response.raise_for_status()
            return response.json()

        raise TravelTimeProviderError(
            provider_name=self.name,
            message=f"Google API failed after {1 + self._max_retries} attempts",
            original_error=last_exc,
        )

    def _check_top_level_status(self, data: dict) -> None:
        status = data.get("status", "UNKNOWN_ERROR")
        if status == "OK":
            return

        if status in _AUTH_STATUSES:
            raise TravelTimeProviderError(
                provider_name=self.name,
                message=f"Google API rejected request: {status} — {data.get('error_message', '')}",
            )

        raise TravelTimeProviderError(
            provider_name=self.name,
            message=f"Google Distance Matrix error: {status} — {data.get('error_message', '')}",
        )

    @staticmethod
    def _parse_legs(data: dict) -> list[TravelTimeLeg]:
        """Build legs in row-major order (origin_i, dest_j)."""
        legs: list[TravelTimeLeg] = []
        for origin_idx, row in enumerate(data.get("rows", [])):
            for dest_idx, element in enumerate(row.get("elements", [])):
                elem_status = element.get("status", "UNKNOWN")
                if elem_status == "OK":
                    duration = element.get("duration_in_traffic") or element.get("duration")
                    legs.append(
                        TravelTimeLeg(
                            origin_index=origin_idx,
                            destination_index=dest_idx,
                            duration_seconds=duration["value"] if duration else None,
                            distance_meters=element["distance"]["value"] if "distance" in element else None,
                            confidence=Confidence.HIGH,
                        )
                    )
                elif elem_status in _NO_ROUTE_STATUSES:
                    legs.append(
                        TravelTimeLeg(
                            origin_index=origin_idx,
                            destination_index=dest_idx,
                            error=f"No route: {elem_status}",
                        )
                    )
                else:
                    legs.append(
                        TravelTimeLeg(
                            origin_index=origin_idx,
                            destination_index=dest_idx,
                            error=f"Element error: {elem_status}",
                        )
                    )
        return legs
