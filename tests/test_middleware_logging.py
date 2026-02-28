"""Tests for request/response logging middleware."""

import uuid

import pytest
from fastapi.testclient import TestClient


def test_middleware_adds_x_request_id_to_response(client: TestClient):
    """Response includes X-Request-ID header so clients can correlate logs."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert request_id
    # Should be a valid UUID (we generate one if client does not send it)
    uuid.UUID(request_id)


def test_middleware_uses_client_request_id_when_provided(client: TestClient):
    """When client sends X-Request-ID, the same value is returned in the response."""
    client_request_id = "my-trace-id-12345"
    response = client.get(
        "/api/health",
        headers={"X-Request-ID": client_request_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == client_request_id


def test_middleware_succeeds_for_api_requests(client: TestClient):
    """Middleware does not break normal API calls (e.g. list clients)."""
    response = client.get("/api/clients/")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.json() == []


def test_middleware_returns_error_status_on_exception():
    """When an endpoint raises, middleware still logs and response has status error (via exception handler)."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient as StarletteTestClient

    from app.middleware_logging import RequestLoggingMiddleware

    test_app = FastAPI()
    test_app.add_middleware(RequestLoggingMiddleware)

    @test_app.get("/fail")
    def fail():
        raise ValueError("expected test failure")

    @test_app.exception_handler(ValueError)
    def handle_value_error(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    with StarletteTestClient(test_app) as c:
        response = c.get("/fail")
        assert response.status_code == 500
        assert "X-Request-ID" in response.headers
