"""Tests for utility functions."""

import pytest
from src.utils import get_logger, ConnectionError


class TestUtils:
    """Test utility functions."""

    def test_get_logger(self):
        """Test logger creation."""
        logger = get_logger("test_module")

        assert logger is not None
        assert logger.name == "test_module"

    def test_connection_error(self):
        """Test ConnectionError exception."""
        error_msg = "Failed to connect to database"

        with pytest.raises(ConnectionError, match="Failed to connect"):
            raise ConnectionError(error_msg)

    def test_connection_error_inheritance(self):
        """Test ConnectionError inherits from Exception."""
        error = ConnectionError("Test error")

        assert isinstance(error, Exception)
        assert str(error) == "Test error"
