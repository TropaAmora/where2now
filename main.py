"""FastAPI application entry point."""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx

from app.api.routes import health, clients, delivery_points, travel_times
from app.config import settings
from app.logging_config import configure_logging
from app.middleware_logging import RequestLoggingMiddleware
from app.travel_times_subsystem.provider_factory import build_providers, build_strategy, ConfigurationError

configure_logging(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate provider config at startup — raises ConfigurationError for bad config"""
    _client = httpx.Client()
    build_providers(_client)
    build_strategy()
    _client.close()
    yield

app = FastAPI(lifespan=lifespan)
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
app.include_router(
    travel_times.router,
    prefix="/api/travel-times",
    tags=["travel_times"],
)
