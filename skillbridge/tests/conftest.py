# tests/conftest.py
#
# PURPOSE: pytest fixtures shared across all test files.
# conftest.py is auto-loaded by pytest — no import needed in test files.
#
# We use a REAL test database (SQLite in-memory) as required by the assignment.
# SQLite is file-compatible with SQLAlchemy and needs no external service.

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for tests — no external DB needed, runs in memory
TEST_DATABASE_URL = "sqlite:///./test.db"

# We must set the env var BEFORE importing settings/app
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "1440"
os.environ["MONITORING_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["MONITORING_API_KEY"] = "test-monitoring-key"

# NOW import app (settings are already set via env vars above)
from src.db.database import Base, get_db
from src.main import app

# Create a test engine
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite with multiple threads
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Replace the real DB session with the test DB session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency so all routes use the test DB
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """
    Create all tables before each test, drop them after.
    scope="function": each test gets a fresh, empty database.
    autouse=True: this fixture runs automatically for every test.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Return a TestClient that hits our FastAPI app with the test DB."""
    return TestClient(app)


@pytest.fixture(scope="function")
def db():
    """Provide a direct DB session for fixtures that need to insert data."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
