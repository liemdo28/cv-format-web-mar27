"""
Pytest configuration + shared fixtures for CV Format Tool tests.
"""
import os
import sys

# Add backend to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set test env vars BEFORE any module imports (auth.py checks JWT_SECRET at import time)
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CVFORMAT_MAX_WORKERS", "2")

import pytest


def pytest_configure(config):
    """Register custom markers before collection."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
