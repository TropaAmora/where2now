"""Delivery points routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.models.clients import Client
from app.models.delivery_points import DeliveryPoint
from app.schemas.clients import ClientRead
from app.schemas.delivery_points import (
    DeliveryPointClientsLink,
    DeliveryPointCreate,
    DeliveryPointRead,
    DeliveryPointUpdate,
)
from app.geocoding.service import geocode_for_delivery_point
from app.geocoding.providers import GeocodingError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=list[DeliveryPointRead])
def list_delivery_points(db: Session = Depends(get_db_session)):
    """List all delivery points."""
    result = db.execute(select(DeliveryPoint))
    return list(result.scalars().all())

@router.post("/", response_model=DeliveryPointRead, status_code=201)
def create_delivery_point(payload: DeliveryPointCreate, db: Session = Depends(get_db_session)):
    """Create a delivery point."""
    # Build ORM instance from payload
    delivery_point = DeliveryPoint(**payload.model_dump())

    # Try geocoding before we commit anything
    try:
        result, provider_name = geocode_for_delivery_point(
            address=payload.address,
            zip=payload.zip,
            city=None,
            country_code=payload.country,
        )
    except GeocodingError as e:
        # Infra problem talking to provider; surface as 503 for now
        raise HTTPException(status_code=503, detail=f"Geocoding service unavailable: {e}") from e

    if provider_name is not None:
        delivery_point.geocode_provider = provider_name
        if result is not None:
            delivery_point.latitude = result.latitude
            delivery_point.longitude = result.longitude
            delivery_point.geocode_status = "SUCCESS"
        else:
            delivery_point.geocode_status = "FAILED"

    db.add(delivery_point)
    db.commit()
    db.refresh(delivery_point)
    logger.info("Created delivery_point id=%s name=%s", delivery_point.id, delivery_point.name)
    return delivery_point

@router.get("/{delivery_point_id}", response_model=DeliveryPointRead)
def get_delivery_point(delivery_point_id: int, db: Session = Depends(get_db_session)):
    """Get one delivery point by id."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")
    return delivery_point

@router.patch("/{delivery_point_id}", response_model=DeliveryPointRead)
def update_delivery_point(delivery_point_id: int, payload: DeliveryPointUpdate, db: Session = Depends(get_db_session)):
    """Update a delivery point (partial)."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(delivery_point, key, value)

    # Decide if we need to re-geocode (only if address-related fields changed)
    needs_geocode = any(field in data for field in ("address", "zip", "country"))
    if needs_geocode:
        try:
            result, provider_name = geocode_for_delivery_point(
                address=delivery_point.address,
                zip=delivery_point.zip,
                city=delivery_point.city,
                country_code=delivery_point.country,
            )
        except GeocodingError as exc:
            raise HTTPException(status_code=503, detail=f"Geocoding service unavailable: {exc}") from exc

        if provider_name is not None:
            delivery_point.latitude = result.latitude,
            delivery_point.longitude = result.longitude,
            delivery_point.geocode_status = "SUCCESS"
        else:
            # We can either clear coords or leave them; for now we clear.
            delivery_point.latitude = None
            delivery_point.longitude = None
            delivery_point.geocode_status = "FAILED"
    
    db.commit()
    db.refresh(delivery_point)
    logger.info("Updated delivery_point id=%s", delivery_point_id)
    return delivery_point

@router.delete("/{delivery_point_id}", status_code=204)
def delete_delivery_point(delivery_point_id: int, db: Session = Depends(get_db_session)):
    """Delete a delivery point."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")
    db.delete(delivery_point)
    db.commit()
    logger.info("Deleted delivery_point id=%s", delivery_point_id)
    return None


@router.get("/{delivery_point_id}/clients", response_model=list[ClientRead])
def list_delivery_point_clients(
    delivery_point_id: int,
    db: Session = Depends(get_db_session)
):
    """Get a list of clients for a delivery point id."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")

    return list(delivery_point.clients)

@router.post("/{delivery_point_id}/clients", response_model=list[ClientRead])
def link_delivery_point_clients(
    delivery_point_id: int,
    payload: DeliveryPointClientsLink,
    db: Session = Depends(get_db_session)
):
    """Link one or more clients to a delivery point"""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")

    if not payload.client_ids:
        # Nothing to add; returning the current links
        return list(delivery_point.clients)

    # load all clients for the given id's
    result = db.execute(
        select(Client)
        .where(Client.id.in_(payload.client_ids))
    )
    clients = list(result.scalars().all())

    found_ids = {client.id for client in clients}
    request_ids = set(payload.client_ids)
    missing_ids = request_ids - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Clients not found: {sorted(missing_ids)}."
        )
    
    # Add links (idempotent: skip if already linked)
    added = 0
    for client in clients:
        if client not in delivery_point.clients:
            delivery_point.clients.append(client)
            added += 1

    db.commit()
    db.refresh(delivery_point)
    logger.info("Linked delivery_point id=%s to client ids=%s (added=%s)", delivery_point_id, payload.client_ids, added)
    return list(delivery_point.clients)

@router.delete("/{delivery_point_id}/clients/{client_id}", status_code=204)
def unlink_delivery_point_client(
    delivery_point_id: int,
    client_id: int,
    db: Session = Depends(get_db_session)
):
    """Unlink a client from a delivery point."""
    # Check if the delivery point exists
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")

    # Check if the client exists
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    # Check if the client is associated with the delivery point
    if client not in delivery_point.clients:
        raise HTTPException(status_code=404, detail="Client not associated with delivery point.")

    delivery_point.clients.remove(client)
    db.commit()
    logger.info("Unlinked delivery_point id=%s from client id=%s", delivery_point_id, client_id)
    return None