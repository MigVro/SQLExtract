"""Tests for index extraction module."""

import pytest
from unittest.mock import MagicMock
from src.indexes import IndexExtractor, IndexInfo


class TestIndexExtractor:
    """Test IndexExtractor class."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        return MagicMock()

    def test_get_indexes_clustered(self, mock_db_connection):
        """Test getting clustered index."""
        mock_row = MagicMock()
        mock_row.index_name = "IX_Config_Key"
        mock_row.schema_name = "dbo"
        mock_row.table_name = "Config"
        mock_row.index_type = "CLUSTERED"
        mock_row.is_unique = True
        mock_row.is_primary_key = False  # PK indexes are excluded
        mock_row.is_unique_constraint = False
        mock_row.filter_definition = None
        mock_row.column_name = "ConfigKey"
        mock_row.is_included_column = False
        mock_row.key_ordinal = 1

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = IndexExtractor(mock_db_connection)
        indexes = extractor.get_indexes()

        assert len(indexes) == 1
        assert indexes[0].index_name == "IX_Config_Key"
        assert indexes[0].is_clustered is True
        assert indexes[0].is_unique is True
        assert indexes[0].is_primary_key is False
        assert indexes[0].columns == ["ConfigKey"]

    def test_get_indexes_with_included_columns(self, mock_db_connection):
        """Test getting index with included columns."""
        mock_key_col = MagicMock()
        mock_key_col.index_name = "IX_EventLog_Type"
        mock_key_col.schema_name = "Logging"
        mock_key_col.table_name = "EventLog"
        mock_key_col.index_type = "NONCLUSTERED"
        mock_key_col.is_unique = False
        mock_key_col.is_primary_key = False
        mock_key_col.is_unique_constraint = False
        mock_key_col.filter_definition = None
        mock_key_col.column_name = "EventType"
        mock_key_col.is_included_column = False
        mock_key_col.key_ordinal = 1

        mock_inc_col = MagicMock()
        mock_inc_col.index_name = "IX_EventLog_Type"
        mock_inc_col.schema_name = "Logging"
        mock_inc_col.table_name = "EventLog"
        mock_inc_col.index_type = "NONCLUSTERED"
        mock_inc_col.is_unique = False
        mock_inc_col.is_primary_key = False
        mock_inc_col.is_unique_constraint = False
        mock_inc_col.filter_definition = None
        mock_inc_col.column_name = "Message"
        mock_inc_col.is_included_column = True
        mock_inc_col.key_ordinal = 0

        mock_db_connection.fetch_all.return_value = [mock_key_col, mock_inc_col]

        extractor = IndexExtractor(mock_db_connection)
        indexes = extractor.get_indexes()

        assert len(indexes) == 1
        assert indexes[0].columns == ["EventType"]
        assert indexes[0].included_columns == ["Message"]

    def test_get_indexes_filtered(self, mock_db_connection):
        """Test getting filtered index."""
        mock_row = MagicMock()
        mock_row.index_name = "IX_ReceiverConfig_Topic"
        mock_row.schema_name = "MQTT"
        mock_row.table_name = "ReceiverConfig"
        mock_row.index_type = "NONCLUSTERED"
        mock_row.is_unique = False
        mock_row.is_primary_key = False
        mock_row.is_unique_constraint = False
        mock_row.filter_definition = "([IsEnabled]=(1))"
        mock_row.column_name = "Topic"
        mock_row.is_included_column = False
        mock_row.key_ordinal = 1

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = IndexExtractor(mock_db_connection)
        indexes = extractor.get_indexes()

        assert len(indexes) == 1
        assert indexes[0].filter_definition == "([IsEnabled]=(1))"
