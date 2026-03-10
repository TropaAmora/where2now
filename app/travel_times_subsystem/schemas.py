"""Travel-time contracts (Story A1).

These Pydantic models define the shared "language" for every travel-time
provider.  Any component that *asks* for travel times builds a
TravelTimeRequest; any component that *answers* returns a TravelTimeResult.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Location references
# ---------------------------------------------------------------------------

class LatLng(BaseModel):
    """A concrete geographic coordinate."""

    type: Literal["latlng"] = "latlng"
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")


class DeliveryPointRef(BaseModel):
    """A reference to a delivery point stored in the database.

    The engine resolves this to a LatLng before calling any provider.
    """

    type: Literal["delivery_point"] = "delivery_point"
    delivery_point_id: int = Field(..., gt=0)


# Union between concrete coordinate and delivery-point reference
LocationRef = Annotated[
    LatLng | DeliveryPointRef,
    Field(discriminator="type"),
]
"""A location is either a concrete coordinate or a delivery-point reference."""


# ---------------------------------------------------------------------------
# Transport mode
# ---------------------------------------------------------------------------

# string enum. Using str, Enum means it serializes to clean strings like "driving" rather than TransportMode.DRIVING
class TransportMode(str, Enum):
    DRIVING = "driving"
    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"


# ---------------------------------------------------------------------------
# Request metadata
# ---------------------------------------------------------------------------

class RequestMetadata(BaseModel):
    """Optional context attached to a request for logging and analytics."""

    request_id: str | None = None
    scenario_id: str | None = None
    user_id: str | None = None


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class TravelTimeRequest(BaseModel):
    """A single logical request for travel-time information.

    Supports 1-to-1 *and* N-to-M (matrix) queries -- providers that only
    handle 1:1 can be called in a loop by the engine.
    """
    origins: list[LocationRef] = Field(..., min_length=1)
    destinations: list[LocationRef] = Field(..., min_length=1)
    departure_time: datetime | None = None
    transport_mode: TransportMode = TransportMode.DRIVING
    restrictions: dict | None = None  # shape defined in Epic C
    metadata: RequestMetadata | None = None


# ---------------------------------------------------------------------------
# Confidence level
# ---------------------------------------------------------------------------

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Result building blocks
# ---------------------------------------------------------------------------

class TravelTimeError(BaseModel):
    """An error that occurred for a specific leg or for the request globally."""

    origin_index: int | None = None
    destination_index: int | None = None
    message: str
    code: str | None = None


class TravelTimeLeg(BaseModel):
    """Result for a single origin-destination pair."""

    origin_index: int = Field(..., ge=0)
    destination_index: int = Field(..., ge=0)
    duration_seconds: int | None = None
    distance_meters: int | None = None
    confidence: Confidence | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class TravelTimeResult(BaseModel):
    """Complete result returned by a provider or the engine.

    Contains one TravelTimeLeg per (origin, destination) pair from the
    request, plus any errors that occurred.  The ``provider`` field
    identifies which provider produced this result.
    """

    request_id: str | None = None
    provider: str
    legs: list[TravelTimeLeg] = Field(default_factory=list)
    errors: list[TravelTimeError] = Field(default_factory=list)
