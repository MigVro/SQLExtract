"""Tests for constraint extraction module."""

import pytest
from unittest.mock import MagicMock
from src.constraints import (
    ConstraintExtractor,
    PrimaryKeyInfo,
    ForeignKeyInfo,
    UniqueConstraintInfo,
    CheckConstraintInfo
)


class TestConstraintExtractor:
    """Test ConstraintExtractor class."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        return MagicMock()

    def test_get_primary_keys(self, mock_db_connection):
        """Test getting primary keys."""
        mock_row = MagicMock()
        mock_row.constraint_name = "PK_Config"
        mock_row.schema_name = "dbo"
        mock_row.table_name = "Config"
        mock_row.index_type = "CLUSTERED"
        mock_row.column_name = "ConfigID"
        mock_row.key_ordinal = 1

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = ConstraintExtractor(mock_db_connection)
        pks = extractor.get_primary_keys()

        assert len(pks) == 1
        assert pks[0].constraint_name == "PK_Config"
        assert pks[0].schema_name == "dbo"
        assert pks[0].table_name == "Config"
        assert pks[0].is_clustered is True
        assert pks[0].columns == ["ConfigID"]

    def test_get_foreign_keys(self, mock_db_connection):
        """Test getting foreign keys."""
        mock_row = MagicMock()
        mock_row.constraint_name = "FK_ReceiverConfig_Broker"
        mock_row.schema_name = "MQTT"
        mock_row.table_name = "ReceiverConfig"
        mock_row.column_name = "BrokerID"
        mock_row.referenced_schema = "MQTT"
        mock_row.referenced_table = "Broker"
        mock_row.referenced_column = "BrokerID"
        mock_row.delete_action = "CASCADE"
        mock_row.update_action = "NO_ACTION"
        mock_row.constraint_column_id = 1

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = ConstraintExtractor(mock_db_connection)
        fks = extractor.get_foreign_keys()

        assert len(fks) == 1
        assert fks[0].constraint_name == "FK_ReceiverConfig_Broker"
        assert fks[0].schema_name == "MQTT"
        assert fks[0].table_name == "ReceiverConfig"
        assert fks[0].columns == ["BrokerID"]
        assert fks[0].referenced_schema == "MQTT"
        assert fks[0].referenced_table == "Broker"
        assert fks[0].delete_action == "CASCADE"

    def test_get_unique_constraints(self, mock_db_connection):
        """Test getting unique constraints."""
        mock_row = MagicMock()
        mock_row.constraint_name = "UQ_Config_Key"
        mock_row.schema_name = "dbo"
        mock_row.table_name = "Config"
        mock_row.column_name = "ConfigKey"
        mock_row.key_ordinal = 1

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = ConstraintExtractor(mock_db_connection)
        uqs = extractor.get_unique_constraints()

        assert len(uqs) == 1
        assert uqs[0].constraint_name == "UQ_Config_Key"
        assert uqs[0].columns == ["ConfigKey"]

    def test_get_check_constraints(self, mock_db_connection):
        """Test getting check constraints."""
        mock_row = MagicMock()
        mock_row.constraint_name = "CK_Config_Key"
        mock_row.schema_name = "dbo"
        mock_row.table_name = "Config"
        mock_row.definition = "([ConfigKey]<>'')"
        mock_row.is_disabled = False

        mock_db_connection.fetch_all.return_value = [mock_row]

        extractor = ConstraintExtractor(mock_db_connection)
        checks = extractor.get_check_constraints()

        assert len(checks) == 1
        assert checks[0].constraint_name == "CK_Config_Key"
        assert checks[0].definition == "([ConfigKey]<>'')"
        assert checks[0].is_disabled is False
