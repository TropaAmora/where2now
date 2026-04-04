"""Jobs model."""

import uuid

from sqlalchemy import Column, DateTime, String, Text, Uuid, JSON
from datetime import datetime, timezone

from app.db.base import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, index=True, default="default")
    type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True, default="pending")
    input_payload = Column(JSON(), nullable=True)
    result_payload = Column(JSON(), nullable=True)
    error = Column(Text())
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)