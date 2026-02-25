"""Pydantic schemas for DeliveryPoint"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

class DeliveryPointCreate(BaseModel):
    """Payload for creating a delivery point"""

    name: str
    address: str
    state: str
    zip: str
    country: str

class DeliveryPointRead(BaseModel):
    """Response shape for a delivery point"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    state: str
    zip: str
    country: str
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime

class DeliveryPointUpdate(BaseModel):
    """Payload for partial update"""

    name: str | None = None
    address: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None