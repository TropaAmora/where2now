"""Pydantic schemas for Client."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    """Payload for creating a client."""

    name: str
    email: str | None = None
    phone: str | None = None


class ClientRead(BaseModel):
    """Response shape for a client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    phone: str | None
    created_at: datetime
    updated_at: datetime


class ClientUpdate(BaseModel):
    """Payload for partial update."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None


class ClientDeliveryPointsLink(BaseModel):
    """Payload for linking delivery points to a client"""

    delivery_point_ids: list[int]