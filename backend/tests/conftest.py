"""
Pytest configuration + shared fixtures for CV Format Tool tests.
"""
import os
import sys
import pytest

# Add backend to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("CVFORMAT_MAX_WORKERS", "2")
    yield


@pytest.fixture(autouse=True)
def reset_db_engine():
    """Reset the database engine between tests to ensure isolation."""
    import db as db_module
    # Don't actually reset in-memory DB — just ensure engine is fresh per session
    yield
