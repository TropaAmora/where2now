"""Health check routes."""

import logging

from fastapi import APIRouter, Depends
from fastapi_health import health
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db_session

logger = logging.getLogger(__name__)


def is_database_online(db: Session = Depends(get_db_session)):
    try:
        db.execute(text("SELECT 1"))
        logger.debug("Health check: database online")
        return True
    except Exception as e:
        logger.warning("Health check: database unreachable: %s", e)
        return False

router = APIRouter()
router.add_api_route("/health", health([is_database_online]))