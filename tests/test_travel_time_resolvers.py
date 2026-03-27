"""Tests for travel-time location resolvers."""

import pytest

from app.models.delivery_points import DeliveryPoint
from app.travel_times_subsystem.resolvers import DbLocationResolver, LocationResolutionError
from app.travel_times_subsystem.schemas import DeliveryPointRef


def test_db_location_resolver_returns_latlng_mapping(db_session):
    point = DeliveryPoint(
        name="Warehouse A",
        address="Rua A",
        city="Porto",
        country="PT",
        latitude=41.1496,
        longitude=-8.6109,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)

    resolver = DbLocationResolver(db=db_session)
    result = resolver.resolve([DeliveryPointRef(delivery_point_id=point.id)])

    assert point.id in result
    assert result[point.id].lat == pytest.approx(41.1496)
    assert result[point.id].lng == pytest.approx(-8.6109)


def test_db_location_resolver_raises_for_missing_id(db_session):
    resolver = DbLocationResolver(db=db_session)

    with pytest.raises(LocationResolutionError) as exc_info:
        resolver.resolve([DeliveryPointRef(delivery_point_id=9999)])

    assert exc_info.value.missing_ids == [9999]


def test_db_location_resolver_raises_for_point_without_coordinates(db_session):
    point = DeliveryPoint(
        name="NoCoords Point",
        address="Rua B",
        city="Porto",
        country="PT",
        latitude=None,
        longitude=None,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)

    resolver = DbLocationResolver(db=db_session)
    with pytest.raises(LocationResolutionError) as exc_info:
        resolver.resolve([DeliveryPointRef(delivery_point_id=point.id)])

    assert exc_info.value.missing_ids == [point.id]
