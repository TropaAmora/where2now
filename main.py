"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes import health, clients, delivery_points
from app.config import settings
from app.logging_config import configure_logging
from app.middleware_logging import RequestLoggingMiddleware


configure_logging(settings)

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)

app.include_router(
    health.router,
    prefix="/api",
    tags=["health"],
)
app.include_router(
    clients.router,
    prefix="/api/clients",
    tags=["clients"],
)
app.include_router(
    delivery_points.router,
    prefix="/api/delivery-points",
    tags=["delivery_points"],
)
