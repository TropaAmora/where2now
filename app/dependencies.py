"""FastAPI dependencies."""

from typing import Generator

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.travel_times_subsystem.engine import EngineStrategy, TravelTimeEngine
from app.travel_times_subsystem.google_provider import GoogleTravelTimeProvider
from app.travel_times_subsystem.resolvers import DbLocationResolver


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_travel_time_engine(db: Session = Depends(get_db_session)) -> TravelTimeEngine:
    resolver = DbLocationResolver(db)
    client = httpx.Client(timeout=settings.GOOGLE_DISTANCE_MATRIX_TIMEOUT)
    google_provider = GoogleTravelTimeProvider(
        client=client,
        api_key=settings.GOOGLE_MAPS_API_KEY,
        base_url=settings.GOOGLE_DISTANCE_MATRIX_BASE_URL,
        max_retries=settings.GOOGLE_DISTANCE_MATRIX_MAX_RETRIES,
    )
    return TravelTimeEngine(
        providers=[google_provider],
        strategy=EngineStrategy.SINGLE,
        resolver=resolver,
    )