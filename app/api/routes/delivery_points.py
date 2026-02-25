"""Delivery points routes."""

# Dependencies
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

# Local stuff
from app.dependencies import get_db_session
from app.models.delivery_points import DeliveryPoint
from app.schemas.delivery_points import DeliveryPointRead, DeliveryPointCreate, DeliveryPointUpdate

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
        raise HTTPException(status_code=404, detail="Delivery point not found")
    return delivery_point

@router.patch("/{delivery_point_id}", response_model=DeliveryPointRead)
def update_delivery_point(delivery_point_id: int, payload: DeliveryPointUpdate, db: Session = Depends(get_db_session)):
    """Update a delivery point (partial)."""
    delivery_point = db.get(DeliveryPoint, delivery_point_id)
    if delivery_point is None:
        raise HTTPException(status_code=404, detail="Delivery point not found")
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
        raise HTTPException(status_code=404, detail="Delivery point not found")
    db.delete(delivery_point)
    db.commit()
    return None
