""""""

from datetime import datetime
from enum import Enum

import uuid

from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: str
    type: str
    status: JobStatus
    input_payload: dict | None
    result_payload: dict | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
