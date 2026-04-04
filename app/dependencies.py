"""FastAPI dependencies."""

from typing import Generator

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.jobs.service import JobService
from app.travel_times_subsystem.engine import TravelTimeEngine
from app.travel_times_subsystem.provider_factory import build_travel_time_engine


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_travel_time_engine(db: Session = Depends(get_db_session)) -> TravelTimeEngine:
    return build_travel_time_engine(db)


def get_job_service(db: Session = Depends(get_db_session)) -> JobService:
    return JobService(db)