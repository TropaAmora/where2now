"""Tests for clients API."""

import pytest
from fastapi.testclient import TestClient

from app.models.clients import Client


def test_list_clients_empty(client: TestClient):
    """GET /api/clients/ returns empty list when no clients."""
    response = client.get("/api/clients/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_client(client: TestClient):
    """POST /api/clients/ creates a client and returns 201 with body."""
    response = client.post(
        "/api/clients/",
        json={"name": "Acme Corp", "email": "acme@example.com", "phone": "+1 555 123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["email"] == "acme@example.com"
    assert data["phone"] == "+1 555 123"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_client_minimal(client: TestClient):
    """POST with only required field (name) succeeds."""
    response = client.post("/api/clients/", json={"name": "Minimal Client"})
    assert response.status_code == 201
    assert response.json()["name"] == "Minimal Client"
    assert response.json()["email"] is None
    assert response.json()["phone"] is None


def test_list_clients_returns_created(client: TestClient):
    """After create, GET /api/clients/ returns the client."""
    client.post("/api/clients/", json={"name": "Listed Client"})
    response = client.get("/api/clients/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Listed Client"


def test_get_client(client: TestClient, db_session):
    """GET /api/clients/{id} returns the client."""
    c = Client(name="Get Me", email="get@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.get(f"/api/clients/{c.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Me"
    assert response.json()["id"] == c.id


def test_get_client_404(client: TestClient):
    """GET /api/clients/{id} returns 404 for missing id."""
    response = client.get("/api/clients/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_client_partial(client: TestClient, db_session):
    """PATCH /api/clients/{id} updates only sent fields."""
    c = Client(name="Original", email="old@example.com", phone="111")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.patch(
        f"/api/clients/{c.id}",
        json={"email": "new@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Original"
    assert response.json()["email"] == "new@example.com"
    assert response.json()["phone"] == "111"


def test_update_client_404(client: TestClient):
    """PATCH /api/clients/{id} returns 404 for missing id."""
    response = client.patch("/api/clients/99999", json={"name": "No"})
    assert response.status_code == 404


def test_delete_client(client: TestClient, db_session):
    """DELETE /api/clients/{id} returns 204 and removes client."""
    c = Client(name="To Delete")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.delete(f"/api/clients/{c.id}")
    assert response.status_code == 204
    assert response.content == b""
    get_response = client.get(f"/api/clients/{c.id}")
    assert get_response.status_code == 404


def test_delete_client_404(client: TestClient):
    """DELETE /api/clients/{id} returns 404 for missing id."""
    response = client.delete("/api/clients/99999")
    assert response.status_code == 404
