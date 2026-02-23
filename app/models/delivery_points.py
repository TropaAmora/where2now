"""Delivery points model."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

# Import the association table (defined in clients.py) for the relationship.
from app.models.clients import client_delivery_points


class DeliveryPoint(Base):
    __tablename__ = "delivery_points"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    address = Column(String(512), index=True)
    city = Column(String(128), index=True)
    state = Column(String(128), index=True)
    zip = Column(String(32), index=True)
    country = Column(String(2), index=True)  # ISO 3166-1 alpha-2
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    clients = relationship(
        "Client",
        secondary=client_delivery_points,
        back_populates="delivery_points",
    )