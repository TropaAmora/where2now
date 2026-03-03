"""Pydantic models used by the geocoding subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GeocodeResult(BaseModel):
    """Provider-agnostic geocoding result used by the app.

    This is what our code trusts, regardless of which external API we call.
    """

    # Required core fields
    latitude: float
    longitude: float

    # Helpful, but optional
    formatted_address: str | None = None
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country_code: str | None = None

    # Quality/metadata
    confidence: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    provider: str
