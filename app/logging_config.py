"""Application-wide logging configuration and request context."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from contextvars import ContextVar

from app.config import Settings, settings


_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestContextFilter(logging.Filter):
    """Inject request-scoped context (e.g. request_id) into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        request_id = _request_id_var.get()
        # Expose as attribute used by format string; fall back to "-"
        record.request_id = request_id or "-"
        return True


def set_request_id(request_id: str | None) -> None:
    """Set the current request id for logging context."""

    _request_id_var.set(request_id)


def configure_logging(app_settings: Settings | None = None) -> None:
    """Configure root logger with console, optional file and DB handlers."""

    cfg = app_settings or settings

    # Clear exisitng handlers on the root logger and set the root level from settings.LOG_LEVEL
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(cfg.LOG_LEVEL)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [request_id=%(request_id)s] %(message)s"
    )

    context_filter = RequestContextFilter()

    # Console handler (always on)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if cfg.LOG_TO_FILE:
        log_path = Path(cfg.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
        )
        file_handler.setLevel(cfg.LOG_LEVEL)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # Optional DB handler
    if cfg.LOG_TO_DB:
        try:
            from app.logging_db_handler import DatabaseLogHandler
        except Exception:  # pragma: no cover - defensive; should not normally trigger
            DatabaseLogHandler = None  # type: ignore[assignment]
        else:
            db_handler = DatabaseLogHandler()
            db_handler.setLevel(cfg.LOG_DB_LEVEL)
            db_handler.setFormatter(formatter)
            db_handler.addFilter(context_filter)
            root_logger.addHandler(db_handler)

