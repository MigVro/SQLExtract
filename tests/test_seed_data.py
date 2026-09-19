"""Tests for seed data extraction module."""

import pytest
from unittest.mock import MagicMock
from src.seed_data import SeedDataExtractor
from src.schema import ColumnInfo


class TestSeedDataExtractor:
    """Test SeedDataExtractor class."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        return MagicMock()

    def test_extract_table_data(self, mock_db_connection):
        """Test extracting data from a table."""
        # Mock column info
        col1 = ColumnInfo(
            name="ConfigID",
            data_type="int",
            max_length=None,
            precision=None,
            scale=None,
            is_nullable=False,
            is_identity=True,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        col2 = ColumnInfo(
            name="ConfigKey",
            data_type="nvarchar",
            max_length=100,
            precision=None,
            scale=None,
            is_nullable=False,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        # Mock data rows - return as tuple, not object
        mock_db_connection.fetch_all.return_value = [(1, "AppName")]

        extractor = SeedDataExtractor(mock_db_connection)
        statements = extractor.extract_table_data(
            "dbo",
            "Config",
            [col1, col2]
        )

        # Should return INSERT statements (with IDENTITY_INSERT wrapper)
        assert len(statements) > 0
        # Find the actual INSERT statement (not SET IDENTITY_INSERT or GO)
        insert_stmts = [s for s in statements if "INSERT INTO" in s]
        assert len(insert_stmts) > 0
        assert "dbo" in insert_stmts[0]
        assert "Config" in insert_stmts[0]

    def test_extract_with_max_rows(self, mock_db_connection):
        """Test extract table data with row limit."""
        col = ColumnInfo(
            name="ID",
            data_type="int",
            max_length=None,
            precision=None,
            scale=None,
            is_nullable=False,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        mock_db_connection.fetch_all.return_value = []

        extractor = SeedDataExtractor(mock_db_connection)
        extractor.extract_table_data("dbo", "Config", [col], max_rows=100)

        # Verify TOP clause was used
        call_args = mock_db_connection.fetch_all.call_args
        assert "TOP" in call_args[0][0]
        assert "100" in call_args[0][0]

    def test_extract_with_where_clause(self, mock_db_connection):
        """Test extracting data with WHERE filter."""
        col = ColumnInfo(
            name="ID",
            data_type="int",
            max_length=None,
            precision=None,
            scale=None,
            is_nullable=False,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        mock_db_connection.fetch_all.return_value = []

        extractor = SeedDataExtractor(mock_db_connection)
        extractor.extract_table_data(
            "dbo",
            "Config",
            [col],
            where_clause="IsEnabled = 1"
        )

        # Verify WHERE clause was used
        call_args = mock_db_connection.fetch_all.call_args
        assert "WHERE" in call_args[0][0]
        assert "IsEnabled = 1" in call_args[0][0]

    def test_extract_excludes_computed_columns(self, mock_db_connection):
        """Test that computed columns are excluded from data extraction."""
        col1 = ColumnInfo(
            name="SubTotal",
            data_type="decimal",
            max_length=None,
            precision=18,
            scale=2,
            is_nullable=False,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        col2 = ColumnInfo(
            name="Total",
            data_type="decimal",
            max_length=None,
            precision=18,
            scale=2,
            is_nullable=False,
            is_identity=False,
            is_computed=True,  # Computed column
            default_value=None,
            computed_definition="([SubTotal]*[TaxRate])"
        )

        mock_db_connection.fetch_all.return_value = [(100.00,)]

        extractor = SeedDataExtractor(mock_db_connection)
        statements = extractor.extract_table_data(
            "dbo",
            "Orders",
            [col1, col2]
        )

        # Should only have SubTotal in INSERT, not Total (computed)
        insert_stmt = [s for s in statements if "INSERT INTO" in s][0]
        # SubTotal should be in the column list
        assert "[SubTotal]" in insert_stmt
        # Total should NOT be in the column list (it's computed)
        assert "[Total]" not in insert_stmt

    def test_extract_handles_null_values(self, mock_db_connection):
        """Test that NULL values are properly handled."""
        col = ColumnInfo(
            name="Notes",
            data_type="nvarchar",
            max_length=500,
            precision=None,
            scale=None,
            is_nullable=True,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        mock_db_connection.fetch_all.return_value = [(None,)]

        extractor = SeedDataExtractor(mock_db_connection)
        statements = extractor.extract_table_data(
            "dbo",
            "Config",
            [col]
        )

        insert_stmt = [s for s in statements if "INSERT INTO" in s][0]
        assert "NULL" in insert_stmt

    def test_extract_bit_column_uses_1_0_not_python_bool(self, mock_db_connection):
        """pyodbc returns Python bool for BIT columns; str(True)/str(False) are not
        valid SQL literals and get parsed as (invalid) column references."""
        col = ColumnInfo(
            name="IsEnabled",
            data_type="bit",
            max_length=None,
            precision=None,
            scale=None,
            is_nullable=False,
            is_identity=False,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        mock_db_connection.fetch_all.return_value = [(True,), (False,)]

        extractor = SeedDataExtractor(mock_db_connection)
        statements = extractor.extract_table_data("dbo", "Config", [col])

        insert_stmts = [s for s in statements if "INSERT INTO" in s]
        assert "VALUES (1)" in insert_stmts[0]
        assert "VALUES (0)" in insert_stmts[1]
