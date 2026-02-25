"""Tests for delivery points API."""

from fastapi.testclient import TestClient

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

