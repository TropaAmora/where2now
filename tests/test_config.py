"""Tests for application settings (app.config)."""

import os

import pytest

from app.config import Settings


def test_settings_defaults():
    """Settings have expected defaults when no env is set."""
    # Instantiate without env overrides to get defaults (may read .env if present)
    s = Settings()
    assert s.ENV == "dev"
    assert s.DEBUG is False
    assert "where2now" in s.DATABASE_URL or "sqlite" in s.DATABASE_URL
    assert s.LOG_LEVEL == "INFO"
    assert s.LOG_TO_FILE is True
    assert s.LOG_FILE_PATH == "logs/app.log"
    assert s.LOG_TO_DB is False
    assert s.LOG_DB_LEVEL == "WARNING"
    assert s.GOOGLE_MAPS_API_KEY is None


def test_settings_read_from_env(monkeypatch):
    """Settings read LOG_LEVEL and LOG_TO_DB from environment."""
    monkeypatch.setitem(os.environ, "LOG_LEVEL", "DEBUG")
    monkeypatch.setitem(os.environ, "LOG_TO_DB", "true")
    monkeypatch.setitem(os.environ, "LOG_DB_LEVEL", "ERROR")

    s = Settings()
    assert s.LOG_LEVEL == "DEBUG"
    assert s.LOG_TO_DB is True
    assert s.LOG_DB_LEVEL == "ERROR"


def test_settings_log_to_file_path_from_env(monkeypatch):
    """LOG_FILE_PATH can be overridden via environment."""
    monkeypatch.setitem(os.environ, "LOG_FILE_PATH", "/var/log/app.log")

    s = Settings()
    assert s.LOG_FILE_PATH == "/var/log/app.log"


def test_settings_database_url_from_env(monkeypatch):
    """DATABASE_URL can be overridden via environment."""
    monkeypatch.setitem(os.environ, "DATABASE_URL", "postgresql://u:p@localhost/db")

    s = Settings()
    assert s.DATABASE_URL == "postgresql://u:p@localhost/db"
