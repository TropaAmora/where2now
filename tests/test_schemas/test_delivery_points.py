"""Tests for DeliveryPoint Pydantic schemas."""

from datetime import datetime

from app.schemas.delivery_points import (
    DeliveryPointCreate,
    DeliveryPointRead,
    DeliveryPointUpdate,
)


def test_delivery_point_create_full():
    """DeliveryPointCreate accepts all required fields."""
    payload = DeliveryPointCreate(
        name="Warehouse",
        address="123 Main St",
        state="CA",
        zip="90210",
        country="US",
    )
    assert payload.model_dump() == {
        "name": "Warehouse",
        "address": "123 Main St",
        "state": "CA",
        "zip": "90210",
        "country": "US",
    }


def test_delivery_point_update_exclude_unset_empty():
    """DeliveryPointUpdate with no fields set: model_dump(exclude_unset=True) is empty."""
    payload = DeliveryPointUpdate()
    assert payload.model_dump(exclude_unset=True) == {}


def test_delivery_point_update_exclude_unset_only_address_and_coords():
    """DeliveryPointUpdate only includes explicitly set fields when exclude_unset=True."""
    payload = DeliveryPointUpdate(
        address="New Address",
        latitude=10.0,
        longitude=20.0,
    )
    data = payload.model_dump(exclude_unset=True)
    assert data == {
        "address": "New Address",
        "latitude": 10.0,
        "longitude": 20.0,
    }
    assert "name" not in data
    assert "state" not in data
    assert "zip" not in data
    assert "country" not in data


def test_delivery_point_read_from_attributes_like_shape():
    """DeliveryPointRead can be instantiated from an object-like source."""

    class Obj:
        def __init__(self):
            self.id = 1
            self.name = "Warehouse"
            self.address = "123 Main St"
            self.state = "CA"
            self.zip = "90210"
            self.country = "US"
            self.latitude = None
            self.longitude = None
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    obj = Obj()
    schema = DeliveryPointRead.model_validate(obj)
    assert schema.id == obj.id
    assert schema.name == obj.name
    assert schema.latitude is None
    assert schema.longitude is None

