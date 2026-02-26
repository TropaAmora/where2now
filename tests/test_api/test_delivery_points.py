"""Tests for delivery points API."""

from fastapi.testclient import TestClient

from app.models.clients import Client
from app.models.delivery_points import DeliveryPoint


def test_list_delivery_points_empty(client: TestClient):
    """GET /api/delivery-points/ returns empty list when no delivery points exist."""
    response = client.get("/api/delivery-points/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_delivery_point(client: TestClient):
    """POST /api/delivery-points/ creates a delivery point and returns 201 with body."""
    payload = {
        "name": "Warehouse A",
        "address": "123 Main St",
        "state": "CA",
        "zip": "90210",
        "country": "US",
    }
    response = client.post("/api/delivery-points/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["address"] == payload["address"]
    assert data["state"] == payload["state"]
    assert data["zip"] == payload["zip"]
    assert data["country"] == payload["country"]
    # Coordinates are nullable in this development phase.
    assert "latitude" in data
    assert "longitude" in data
    assert data["latitude"] is None
    assert data["longitude"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_list_delivery_points_returns_created(client: TestClient):
    """After create, GET /api/delivery-points/ returns the delivery point."""
    client.post(
        "/api/delivery-points/",
        json={
            "name": "Listed DP",
            "address": "456 Side St",
            "state": "NY",
            "zip": "10001",
            "country": "US",
        },
    )
    response = client.get("/api/delivery-points/")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Listed DP"


def test_get_delivery_point(client: TestClient, db_session):
    """GET /api/delivery-points/{id} returns the delivery point."""
    dp = DeliveryPoint(
        name="Get Me",
        address="789 Road",
        state="TX",
        zip="73301",
        country="US",
    )
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)

    response = client.get(f"/api/delivery-points/{dp.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == dp.id
    assert data["name"] == "Get Me"


def test_get_delivery_point_404(client: TestClient):
    """GET /api/delivery-points/{id} returns 404 for missing id."""
    response = client.get("/api/delivery-points/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_delivery_point_partial(client: TestClient, db_session):
    """PATCH /api/delivery-points/{id} updates only sent fields."""
    dp = DeliveryPoint(
        name="Original",
        address="1 Old St",
        state="WA",
        zip="98101",
        country="US",
    )
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)

    response = client.patch(
        f"/api/delivery-points/{dp.id}",
        json={"address": "2 New St"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Original"
    assert data["address"] == "2 New St"
    assert data["state"] == "WA"
    assert data["zip"] == "98101"
    assert data["country"] == "US"


def test_update_delivery_point_404(client: TestClient):
    """PATCH /api/delivery-points/{id} returns 404 for missing id."""
    response = client.patch(
        "/api/delivery-points/99999",
        json={"name": "Nope"},
    )
    assert response.status_code == 404


def test_delete_delivery_point(client: TestClient, db_session):
    """DELETE /api/delivery-points/{id} returns 204 and removes the delivery point."""
    dp = DeliveryPoint(
        name="To Delete",
        address="Delete St",
        state="OR",
        zip="97035",
        country="US",
    )
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)

    response = client.delete(f"/api/delivery-points/{dp.id}")
    assert response.status_code == 204
    assert response.content == b""

    get_response = client.get(f"/api/delivery-points/{dp.id}")
    assert get_response.status_code == 404


def test_delete_delivery_point_404(client: TestClient):
    """DELETE /api/delivery-points/{id} returns 404 for missing id."""
    response = client.delete("/api/delivery-points/99999")
    assert response.status_code == 404


# --- Delivery point → clients (relationship) ---


def test_list_delivery_point_clients_empty(client: TestClient, db_session):
    """GET /api/delivery-points/{id}/clients returns empty list when delivery point has no links."""
    dp = DeliveryPoint(
        name="No Clients",
        address="A",
        state="S",
        zip="Z",
        country="US",
    )
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)
    response = client.get(f"/api/delivery-points/{dp.id}/clients")
    assert response.status_code == 200
    assert response.json() == []


def test_list_delivery_point_clients_404(client: TestClient):
    """GET /api/delivery-points/{id}/clients returns 404 when delivery point does not exist."""
    response = client.get("/api/delivery-points/99999/clients")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_delivery_point_clients_returns_linked(client: TestClient, db_session):
    """GET /api/delivery-points/{id}/clients returns linked clients."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c = Client(name="Linked Client", email="linked@example.com")
    db_session.add(dp)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(dp)
    db_session.refresh(c)
    dp.clients.append(c)
    db_session.commit()
    response = client.get(f"/api/delivery-points/{dp.id}/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == c.id
    assert data[0]["name"] == "Linked Client"


def test_link_delivery_point_clients(client: TestClient, db_session):
    """POST /api/delivery-points/{id}/clients links clients and returns the list."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c1 = Client(name="C1", email="c1@example.com")
    c2 = Client(name="C2", email="c2@example.com")
    db_session.add(dp)
    db_session.add(c1)
    db_session.add(c2)
    db_session.commit()
    db_session.refresh(dp)
    response = client.post(
        f"/api/delivery-points/{dp.id}/clients",
        json={"client_ids": [c1.id, c2.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {d["id"] for d in data}
    assert ids == {c1.id, c2.id}
    get_resp = client.get(f"/api/delivery-points/{dp.id}/clients")
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 2


def test_link_delivery_point_clients_empty_body_returns_current(client: TestClient, db_session):
    """POST with empty client_ids returns current links (no change)."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c = Client(name="C", email="c@example.com")
    db_session.add(dp)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(dp)
    db_session.refresh(c)
    dp.clients.append(c)
    db_session.commit()
    response = client.post(
        f"/api/delivery-points/{dp.id}/clients",
        json={"client_ids": []},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == c.id


def test_link_delivery_point_clients_404_delivery_point(client: TestClient, db_session):
    """POST returns 404 when delivery point does not exist."""
    c = Client(name="C", email="c@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.post(
        "/api/delivery-points/99999/clients",
        json={"client_ids": [c.id]},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_link_delivery_point_clients_404_client(client: TestClient, db_session):
    """POST returns 404 when one or more client ids do not exist."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)
    response = client.post(
        f"/api/delivery-points/{dp.id}/clients",
        json={"client_ids": [99998, 99999]},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_link_delivery_point_clients_idempotent(client: TestClient, db_session):
    """Linking the same client again does not duplicate; response still has one."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c = Client(name="C", email="c@example.com")
    db_session.add(dp)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(dp)
    db_session.refresh(c)
    client.post(f"/api/delivery-points/{dp.id}/clients", json={"client_ids": [c.id]})
    response = client.post(f"/api/delivery-points/{dp.id}/clients", json={"client_ids": [c.id]})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_unlink_delivery_point_client(client: TestClient, db_session):
    """DELETE /api/delivery-points/{id}/clients/{client_id} removes the link and returns 204."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c = Client(name="Unlink Me", email="u@example.com")
    db_session.add(dp)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(dp)
    db_session.refresh(c)
    dp.clients.append(c)
    db_session.commit()
    response = client.delete(f"/api/delivery-points/{dp.id}/clients/{c.id}")
    assert response.status_code == 204
    assert response.content == b""
    get_resp = client.get(f"/api/delivery-points/{dp.id}/clients")
    assert get_resp.status_code == 200
    assert get_resp.json() == []


def test_unlink_delivery_point_client_404_delivery_point(client: TestClient, db_session):
    """DELETE returns 404 when delivery point does not exist."""
    c = Client(name="C", email="c@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    response = client.delete(f"/api/delivery-points/99999/clients/{c.id}")
    assert response.status_code == 404


def test_unlink_delivery_point_client_404_client(client: TestClient, db_session):
    """DELETE returns 404 when client does not exist."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    db_session.add(dp)
    db_session.commit()
    db_session.refresh(dp)
    response = client.delete(f"/api/delivery-points/{dp.id}/clients/99999")
    assert response.status_code == 404


def test_unlink_delivery_point_client_404_not_associated(client: TestClient, db_session):
    """DELETE returns 404 when client is not linked to the delivery point."""
    dp = DeliveryPoint(name="DP", address="A", state="S", zip="Z", country="US")
    c = Client(name="C", email="c@example.com")
    db_session.add(dp)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(dp)
    db_session.refresh(c)
    response = client.delete(f"/api/delivery-points/{dp.id}/clients/{c.id}")
    assert response.status_code == 404
    assert "not associated" in response.json()["detail"].lower()

