"""Tests for Celery task definitions — B3 probe task."""

import pytest

from app.celery_app import celery_app
from app.jobs.tasks import ping


@pytest.fixture
def eager_celery():
    """Run tasks synchronously in-process; no broker required."""
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
    yield celery_app
    celery_app.conf.update(task_always_eager=False, task_eager_propagates=False)


# ---------------------------------------------------------------------------
# ping — direct function call
# ---------------------------------------------------------------------------

def test_ping_direct():
    assert ping() == "pong"


# ---------------------------------------------------------------------------
# ping — via .apply() with eager mode
# ---------------------------------------------------------------------------

def test_ping_apply(eager_celery):
    result = ping.apply()
    assert result.result == "pong"


def test_ping_delay(eager_celery):
    celery_app.conf.update(task_ignore_result=False)
    try:
        result = ping.delay()
        assert result.get(timeout=5) == "pong"
    finally:
        celery_app.conf.update(task_ignore_result=True)


# ---------------------------------------------------------------------------
# Celery app config sanity checks
# ---------------------------------------------------------------------------

def test_task_serializer():
    assert celery_app.conf.task_serializer == "json"


def test_enable_utc():
    assert celery_app.conf.enable_utc is True


def test_task_ignore_result():
    assert celery_app.conf.task_ignore_result is True


def test_ping_registered():
    assert "where2now.ping" in celery_app.tasks
