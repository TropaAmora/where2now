"""Clients routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.models.clients import Client
from app.schemas.clients import ClientCreate, ClientRead, ClientUpdate

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
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db_session)):
    """Update a client (partial)."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
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
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return None
