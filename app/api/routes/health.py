"""Health check routes."""

from fastapi import APIRouter, Depends
from fastapi_health import health
from app.dependencies import get_db_session
from sqlalchemy.orm import Session
from sqlalchemy import text

def is_database_online(db: Session = Depends(get_db_session)):
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

router = APIRouter()
router.add_api_route("/health", health([is_database_online]))