"""Clients routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.models.clients import Client
from app.models.delivery_points import DeliveryPoint
from app.schemas.clients import ClientCreate, ClientDeliveryPointsLink, ClientRead, ClientUpdate
from app.schemas.delivery_points import DeliveryPointRead

router = APIRouter()


@router.get("/", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db_session)):
    """List all clients."""
    result = db.execute(select(Client))
    return list(result.scalars().all())


@router.post("/", response_model=ClientRead, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db_session)):
    """Create a client."""
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, db: Session = Depends(get_db_session)):
    """Get one client by id."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db_session)):
    """Update a client (partial)."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db_session)):
    """Delete a client."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    db.delete(client)
    db.commit()
    return None

@router.get("/{client_id}/delivery-points", response_model=list[DeliveryPointRead])
def list_client_delivery_points(client_id: int, db: Session = Depends(get_db_session)):
    """Get a list of delivery points for a client id."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    # Using the relationship in place, SQLAlchemy handles the join
    return list(client.delivery_points)

@router.post("/{client_id}/delivery-points", response_model=list[DeliveryPointRead])
def link_client_delivery_points(
    client_id: int, 
    payload: ClientDeliveryPointsLink, 
    db: Session = Depends(get_db_session)
):
    """Link one or more delivery points to a client."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    if not payload.delivery_point_ids:
        # Nothing to add; just return current links
        return list(client.delivery_points)

    # load all delivery points for the given IDs
    result = db.execute(
        select(DeliveryPoint)
        .where(DeliveryPoint.id.in_(payload.delivery_point_ids))
    )
    delivery_points = list(result.scalars().all())

    found_ids = {dp.id for dp in delivery_points}
    request_ids = set(payload.delivery_point_ids)
    missing_ids = request_ids - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Delivery points not found: {sorted(missing_ids)}."
        )

    # Add links (idempotent: skip if already linked)
    for dp in delivery_points:
        if dp not in client.delivery_points:
            client.delivery_points.append(dp)

    db.commit()
    db.refresh(client)

    return list(client.delivery_points)

@router.delete("/{client_id}/delivery-points/{delivery_point_id}", status_code=204)
def unlink_client_delivery_point(client_id: int, delivery_point_id: int, db: Session = Depends(get_db_session)):
    """Unlink a delivery point from a client."""
    # Check if the client exists
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    # Check if the delivery point exists
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found.")

    # Check if the delivery point is associated with the client
    if delivery_point not in client.delivery_points:
        raise HTTPException(status_code=404, detail="Delivery point not associated with client.")

    # Unlink the delivery point from the client
    client.delivery_points.remove(delivery_point)
    db.commit()
    return None