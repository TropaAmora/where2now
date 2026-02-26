"""Tests for clients API."""

import pytest
from fastapi.testclient import TestClient

from app.models.clients import Client
from app.models.delivery_points import DeliveryPoint


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


# --- Client → delivery points (relationship) ---


def test_list_client_delivery_points_empty(client: TestClient, db_session):
    """GET /api/clients/{id}/delivery-points returns empty list when client has no links."""
    c = Client(name="No Points")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.get(f"/api/clients/{c.id}/delivery-points")
    assert response.status_code == 200
    assert response.json() == []


def test_list_client_delivery_points_404(client: TestClient):
    """GET /api/clients/{id}/delivery-points returns 404 when client does not exist."""
    response = client.get("/api/clients/99999/delivery-points")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_client_delivery_points_returns_linked(client: TestClient, db_session):
    """GET /api/clients/{id}/delivery-points returns linked delivery points."""
    c = Client(name="Has Points")
    dp = DeliveryPoint(name="DP1", address="A", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(c)
    db_session.refresh(dp)
    c.delivery_points.append(dp)
    db_session.commit()
    response = client.get(f"/api/clients/{c.id}/delivery-points")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == dp.id
    assert data[0]["name"] == "DP1"


def test_link_client_delivery_points(client: TestClient, db_session):
    """POST /api/clients/{id}/delivery-points links delivery points and returns the list."""
    c = Client(name="Link Me")
    dp1 = DeliveryPoint(name="DP1", address="A1", state="S", zip="Z", country="US")
    dp2 = DeliveryPoint(name="DP2", address="A2", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp1)
    db_session.add(dp2)
    db_session.commit()
    db_session.refresh(c)
    response = client.post(
        f"/api/clients/{c.id}/delivery-points",
        json={"delivery_point_ids": [dp1.id, dp2.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {d["id"] for d in data}
    assert ids == {dp1.id, dp2.id}
    # Verify via GET
    get_resp = client.get(f"/api/clients/{c.id}/delivery-points")
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 2


def test_link_client_delivery_points_empty_body_returns_current(client: TestClient, db_session):
    """POST with empty delivery_point_ids returns current links (no change)."""
    c = Client(name="Empty Link")
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(c)
    db_session.refresh(dp)
    c.delivery_points.append(dp)
    db_session.commit()
    response = client.post(
        f"/api/clients/{c.id}/delivery-points",
        json={"delivery_point_ids": []},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == dp.id


def test_link_client_delivery_points_404_client(client: TestClient, db_session):
    """POST /api/clients/{id}/delivery-points returns 404 when client does not exist."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)
    response = client.post(
        "/api/clients/99999/delivery-points",
        json={"delivery_point_ids": [dp.id]},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_link_client_delivery_points_404_delivery_point(client: TestClient, db_session):
    """POST returns 404 when one or more delivery point ids do not exist."""
    c = Client(name="Client")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.post(
        f"/api/clients/{c.id}/delivery-points",
        json={"delivery_point_ids": [99998, 99999]},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_link_client_delivery_points_idempotent(client: TestClient, db_session):
    """Linking the same delivery point again does not duplicate; response still has one."""
    c = Client(name="Idem")
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(c)
    db_session.refresh(dp)
    client.post(f"/api/clients/{c.id}/delivery-points", json={"delivery_point_ids": [dp.id]})
    response = client.post(f"/api/clients/{c.id}/delivery-points", json={"delivery_point_ids": [dp.id]})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_unlink_client_delivery_point(client: TestClient, db_session):
    """DELETE /api/clients/{id}/delivery-points/{dp_id} removes the link and returns 204."""
    c = Client(name="Unlink Me")
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(c)
    db_session.refresh(dp)
    c.delivery_points.append(dp)
    db_session.commit()
    response = client.delete(f"/api/clients/{c.id}/delivery-points/{dp.id}")
    assert response.status_code == 204
    assert response.content == b""
    get_resp = client.get(f"/api/clients/{c.id}/delivery-points")
    assert get_resp.status_code == 200
    assert get_resp.json() == []


def test_unlink_client_delivery_point_404_client(client: TestClient, db_session):
    """DELETE returns 404 when client does not exist."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)
    response = client.delete(f"/api/clients/99999/delivery-points/{dp.id}")
    assert response.status_code == 404


def test_unlink_client_delivery_point_404_delivery_point(client: TestClient, db_session):
    """DELETE returns 404 when delivery point does not exist."""
    c = Client(name="Client")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.delete(f"/api/clients/{c.id}/delivery-points/99999")
    assert response.status_code == 404


def test_unlink_client_delivery_point_404_not_associated(client: TestClient, db_session):
    """DELETE returns 404 when delivery point is not linked to the client."""
    c = Client(name="Client")
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(c)
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(c)
    db_session.refresh(dp)
    # Do not link dp to c
    response = client.delete(f"/api/clients/{c.id}/delivery-points/{dp.id}")
    assert response.status_code == 404
    assert "not associated" in response.json()["detail"].lower()
