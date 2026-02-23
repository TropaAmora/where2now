"""Pytest fixtures and configuration."""

import sys
from pathlib import Path

# Make project root importable (e.g. "app", "main") when running pytest from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.dependencies import get_db_session
from app.models import Client, DeliveryPoint  # noqa: F401 - register models with Base
from main import app

# In-memory SQLite for tests; StaticPool so one connection = one DB (tables visible to session).
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Fresh DB session per test; tables exist, data is test-specific."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with DB dependency overridden to use the test session."""

    def get_test_db():
        yield db_session

    app.dependency_overrides[get_db_session] = get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
