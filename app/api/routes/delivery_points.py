"""Delivery points routes."""

# Dependencies
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

# Local stuff
from app.dependencies import get_db_session
from app.models.clients import Client
from app.models.delivery_points import DeliveryPoint
from app.schemas.clients import ClientRead
from app.schemas.delivery_points import DeliveryPointClientsLink, DeliveryPointRead, DeliveryPointCreate, DeliveryPointUpdate

router = APIRouter()

@router.get("/", response_model=list[DeliveryPointRead])
def list_delivery_points(db: Session = Depends(get_db_session)):
    """List all delivery points."""
    result = db.execute(select(DeliveryPoint))
    return list(result.scalars().all())

@router.post("/", response_model=DeliveryPointRead, status_code=201)
def create_delivery_point(payload: DeliveryPointCreate, db: Session = Depends(get_db_session)):
    """Create a delivery point."""
    delivery_point = DeliveryPoint(**payload.model_dump())
    db.add(delivery_point)
    db.commit()
    db.refresh(delivery_point)
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
    db.commit()
    db.refresh(delivery_point)
    return delivery_point

@router.delete("/{delivery_point_id}", status_code=204)
def delete_delivery_point(delivery_point_id: int, db: Session = Depends(get_db_session)):
    """Delete a delivery point."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")
    db.delete(delivery_point)
    db.commit()
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
    for client in clients:
        if client not in delivery_point.clients:
            delivery_point.clients.append(client)

    db.commit()
    db.refresh(delivery_point)

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
    return None