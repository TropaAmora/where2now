"""Travel time resolvers."""

from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_points import DeliveryPoint
from app.travel_times_subsystem.schemas import DeliveryPointRef, LatLng

class LocationResolver(ABC):
    """Resolves delivery-point references into coordinates."""

    @abstractmethod
    def resolve(self, refs: list[DeliveryPointRef]) -> dict[int, LatLng]:
        """Return a mapping of delivery_point_id to coordinates."""

        raise NotImplementedError


class LocationResolutionError(Exception):
    """Raised when one or more delivery points cannot be resolved."""

    def __init__(self, missing_ids: list[int], message: str) -> None:
        super().__init__(message)
        self.missing_ids = missing_ids
        self.message = message


class DbLocationResolver(LocationResolver):
    """Database-backed resolver using the delivery_points table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def resolve(self, refs: list[DeliveryPointRef]) -> dict[int, LatLng]:
        if not refs:
            return {}

        ids = list(dict.fromkeys(ref.delivery_point_id for ref in refs))
        rows = self._db.execute(
            select(DeliveryPoint.id, DeliveryPoint.latitude, DeliveryPoint.longitude)
            .where(DeliveryPoint.id.in_(ids))
        ).all()

        resolved: dict[int, LatLng] = {}
        invalid_ids: set[int] = set()
        found_ids: set[int] = set()

        for delivery_point_id, lat, lng in rows:
            found_ids.add(delivery_point_id)
            if lat is None or lng is None:
                invalid_ids.add(delivery_point_id)
                continue
            resolved[delivery_point_id] = LatLng(lat=lat, lng=lng)

        missing_ids = sorted((set(ids) - found_ids) | invalid_ids)
        if missing_ids:
            raise LocationResolutionError(
                missing_ids=missing_ids,
                message=f"Could not resolve delivery points: {missing_ids}",
            )

        return resolved
