"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, MagicMock
from src.connection import ConnectionConfig, DatabaseConnection


@pytest.fixture
def mock_connection_config():
    """Create a mock connection configuration."""
    return ConnectionConfig(
        server="localhost",
        database="TestDB",
        user="sa",
        password="TestPassword123!",
        trust_cert=True
    )


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Create a mock database connection."""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    return conn
