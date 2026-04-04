"""Travel time routes."""

import logging
from fastapi import APIRouter, Depends

from app.dependencies import get_travel_time_engine
from app.travel_times_subsystem.engine import TravelTimeEngine
from app.travel_times_subsystem.schemas import TravelTimeRequest, TravelTimeResult

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=TravelTimeResult)
def post_travel_times(
    payload: TravelTimeRequest,
    engine: TravelTimeEngine = Depends(get_travel_time_engine),
) -> TravelTimeResult:
    """Calculate travel times between origins and destinations."""
    return engine.get_travel_times(payload)
