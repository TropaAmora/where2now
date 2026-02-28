"""Tests for the database logging handler."""

import logging
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.logging_config import RequestContextFilter, set_request_id
from app.logging_db_handler import DatabaseLogHandler
from app.models import LogEntry  # noqa: F401 - register with Base


@pytest.fixture
def log_entry_engine_and_session():
    """In-memory SQLite engine and session factory for LogEntry table only."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield engine, Session
    Base.metadata.drop_all(bind=engine)


def test_database_log_handler_writes_log_entry(log_entry_engine_and_session):
    """DatabaseLogHandler creates a LogEntry row when a log record is emitted."""
    engine, TestSession = log_entry_engine_and_session

    with patch("app.logging_db_handler.SessionLocal", TestSession):
        handler = DatabaseLogHandler()
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(RequestContextFilter())

        logger = logging.getLogger("test.db.handler")
        logger.setLevel(logging.WARNING)
        logger.addHandler(handler)

        logger.warning("Database handler test message")

    session = TestSession()
    try:
        entries = list(session.execute(select(LogEntry)).scalars().all())
        assert len(entries) == 1
        assert entries[0].level == "WARNING"
        assert entries[0].logger_name == "test.db.handler"
        assert "Database handler test message" in entries[0].message
    finally:
        session.close()


def test_database_log_handler_stores_request_id_in_context(log_entry_engine_and_session):
    """When request_id is set, it is stored in LogEntry.context JSON."""
    engine, TestSession = log_entry_engine_and_session

    with patch("app.logging_db_handler.SessionLocal", TestSession):
        handler = DatabaseLogHandler()
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(RequestContextFilter())

        logger = logging.getLogger("test.db.context")
        logger.setLevel(logging.WARNING)
        logger.addHandler(handler)

        set_request_id("req-xyz-789")
        try:
            logger.warning("Message with request id")
        finally:
            set_request_id(None)

    session = TestSession()
    try:
        entries = list(session.execute(select(LogEntry)).scalars().all())
        assert len(entries) == 1
        assert entries[0].context is not None
        assert "req-xyz-789" in entries[0].context
        assert "request_id" in entries[0].context
    finally:
        session.close()


def test_database_log_handler_respects_level(log_entry_engine_and_session):
    """Records below the handler level are not written to the database."""
    engine, TestSession = log_entry_engine_and_session

    with patch("app.logging_db_handler.SessionLocal", TestSession):
        handler = DatabaseLogHandler()
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(RequestContextFilter())

        logger = logging.getLogger("test.db.level")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("This should not be written")
        logger.warning("This should not be written either")

    session = TestSession()
    try:
        entries = list(session.execute(select(LogEntry)).scalars().all())
        assert len(entries) == 0
    finally:
        session.close()
