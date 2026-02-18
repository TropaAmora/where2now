"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes import health

app = FastAPI()

app.include_router(health.router, prefix="/api", tags=["health"])
