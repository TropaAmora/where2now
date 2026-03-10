"""Tests for logging context (request_id) and configuration."""

import logging
import logging.handlers

import pytest

from app.logging_config import RequestContextFilter, set_request_id


def test_request_context_filter_injects_request_id():
    """RequestContextFilter adds request_id to the log record."""
    filt = RequestContextFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    # Before filter: no request_id
    assert not hasattr(record, "request_id")

    set_request_id("req-abc-123")
    try:
        result = filt.filter(record)
        assert result is True
        assert record.request_id == "req-abc-123"
    finally:
        set_request_id(None)


def test_request_context_filter_defaults_to_dash_when_no_id():
    """When request_id is not set, filter uses '-' so formatter does not crash."""
    set_request_id(None)
    filt = RequestContextFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert record.request_id == "-"


def test_log_record_contains_request_id_when_set():
    """Logging with request_id set produces a record with request_id in message or attribute."""
    # MemoryHandler keeps records in .buffer (target is for flushing to another handler)
    handler = logging.handlers.MemoryHandler(capacity=10)
    handler.setFormatter(logging.Formatter("%(request_id)s %(message)s"))
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        set_request_id("trace-99")
        try:
            root.info("test message")
        finally:
            set_request_id(None)

        assert len(handler.buffer) == 1
        record = handler.buffer[0]
        assert hasattr(record, "request_id")
        assert record.request_id == "trace-99"
        assert record.getMessage() == "test message"
    finally:
        root.removeHandler(handler)
