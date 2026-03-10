"""Logging handler that writes log records to the database."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.log_entry import LogEntry


class DatabaseLogHandler(logging.Handler):
    """Persist log records to the database as LogEntry rows."""

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            message = self.format(record)

            # Extract contextual fields if present
            context_data: dict[str, object] = {}
            for key in ("request_id",):
                value = getattr(record, key, None)
                if value is not None:
                    context_data[key] = value

            context_json = json.dumps(context_data) if context_data else None

            # Use an independent session so logging does not interfere with request transactions.
            session: Session = SessionLocal()
            try:
                entry = LogEntry(
                    created_at=datetime.now(timezone.utc),
                    level=record.levelname,
                    logger_name=record.name,
                    message=message,
                    context=context_json,
                )
                session.add(entry)
                session.commit()
            except Exception:
                session.rollback()
                # Avoid infinite recursion by logging the failure only via the base handler infrastructure.
                # Use handleError to let logging module decide what to do.
                self.handleError(record)
            finally:
                session.close()
        except Exception:
            self.handleError(record)

