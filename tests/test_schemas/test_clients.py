"""Tests for Client Pydantic schemas (and model_dump(exclude_unset=True))."""

import pytest

from app.schemas.clients import ClientCreate, ClientRead, ClientUpdate


def test_client_create_full():
    """ClientCreate accepts name, email, phone."""
    payload = ClientCreate(name="Acme", email="a@b.com", phone="123")
    assert payload.model_dump() == {"name": "Acme", "email": "a@b.com", "phone": "123"}


def test_client_create_minimal():
    """ClientCreate allows email and phone omitted (default None)."""
    payload = ClientCreate(name="Only Name")
    assert payload.model_dump() == {"name": "Only Name", "email": None, "phone": None}


def test_client_update_exclude_unset_empty():
    """ClientUpdate with no fields set: model_dump(exclude_unset=True) is empty."""
    payload = ClientUpdate()
    assert payload.model_dump(exclude_unset=True) == {}
    # Without exclude_unset you get all keys with their defaults:
    assert payload.model_dump() == {"name": None, "email": None, "phone": None}


def test_client_update_exclude_unset_only_sent():
    """ClientUpdate with only email set: only email appears in exclude_unset dump."""
    payload = ClientUpdate(email="new@example.com")
    assert payload.model_dump(exclude_unset=True) == {"email": "new@example.com"}
    assert "name" not in payload.model_dump(exclude_unset=True)
    assert "phone" not in payload.model_dump(exclude_unset=True)


def test_client_update_exclude_unset_multiple():
    """ClientUpdate with name and phone set: both appear; email does not."""
    payload = ClientUpdate(name="New Name", phone="+1 555")
    data = payload.model_dump(exclude_unset=True)
    assert data == {"name": "New Name", "phone": "+1 555"}
    assert "email" not in data
