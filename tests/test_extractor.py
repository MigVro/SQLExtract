"""Tests for core extractor module."""

import pytest
from unittest.mock import MagicMock, patch
from src.extractor import DatabaseExtractor
from src.connection import ConnectionConfig


class TestDatabaseExtractor:
    """Test DatabaseExtractor class."""

    def test_extractor_initialization(self):
        """Test extractor initialization."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass"
        )

        extractor = DatabaseExtractor(config)

        assert extractor.config == config
        assert extractor.connection is None
