"""Tests for schema introspection module."""

import pytest
from unittest.mock import Mock, MagicMock
from src.schema import SchemaReader, SchemaInfo, TableInfo, ColumnInfo
from src.connection import DatabaseConnection


class TestSchemaReader:
    """Test SchemaReader class."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        return MagicMock(spec=DatabaseConnection)

    def test_get_schemas_no_filter(self, mock_db_connection):
        """Test getting all schemas without filter."""
        # Mock database response
        mock_row1 = MagicMock()
        mock_row1.schema_name = "dbo"
        mock_row1.owner = "sa"

        mock_row2 = MagicMock()
        mock_row2.schema_name = "MQTT"
        mock_row2.owner = "dbo"

        mock_row3 = MagicMock()
        mock_row3.schema_name = "Logging"
        mock_row3.owner = "dbo"

        mock_db_connection.fetch_all.return_value = [mock_row1, mock_row2, mock_row3]

        reader = SchemaReader(mock_db_connection)
        schemas = reader.get_schemas()

        assert len(schemas) == 3
        assert schemas[0].name == "dbo"
        assert schemas[0].owner == "sa"
        assert schemas[1].name == "MQTT"
        assert schemas[2].name == "Logging"

        # Verify query was called
        mock_db_connection.fetch_all.assert_called_once()
        call_args = mock_db_connection.fetch_all.call_args
        assert "sys.schemas" in call_args[0][0]
        assert "NOT IN" in call_args[0][0]

    def test_get_schemas_with_filter(self, mock_db_connection):
        """Test getting schemas with filter."""
        mock_row1 = MagicMock()
        mock_row1.schema_name = "MQTT"
        mock_row1.owner = "dbo"

        mock_row2 = MagicMock()
        mock_row2.schema_name = "Logging"
        mock_row2.owner = "dbo"

        mock_db_connection.fetch_all.return_value = [mock_row1, mock_row2]

        reader = SchemaReader(mock_db_connection)
        schemas = reader.get_schemas(schema_filter=["MQTT", "Logging"])

        assert len(schemas) == 2
        assert schemas[0].name == "MQTT"
        assert schemas[1].name == "Logging"

        # Verify parameterized query
        call_args = mock_db_connection.fetch_all.call_args
        assert "IN (?,?)" in call_args[0][0]
        assert call_args[0][1] == ("MQTT", "Logging")

    def test_get_schemas_empty_result(self, mock_db_connection):
        """Test getting schemas returns empty list when no schemas found."""
        mock_db_connection.fetch_all.return_value = []

        reader = SchemaReader(mock_db_connection)
        schemas = reader.get_schemas()

        assert len(schemas) == 0

    def test_get_schemas_null_owner(self, mock_db_connection):
        """Test getting schemas with null owner defaults to 'dbo'."""
        mock_row = MagicMock()
        mock_row.schema_name = "CustomSchema"
        mock_row.owner = None

        mock_db_connection.fetch_all.return_value = [mock_row]

        reader = SchemaReader(mock_db_connection)
        schemas = reader.get_schemas()

        assert schemas[0].owner == "dbo"

    def test_get_tables_no_filter(self, mock_db_connection):
        """Test getting all tables without filter."""
        # Mock tables query
        mock_table_row = MagicMock()
        mock_table_row.schema_name = "dbo"
        mock_table_row.table_name = "Config"

        # Mock columns query
        mock_col_row = MagicMock()
        mock_col_row.column_name = "ConfigID"
        mock_col_row.data_type = "int"
        mock_col_row.max_length = 4
        mock_col_row.precision = 10
        mock_col_row.scale = 0
        mock_col_row.is_nullable = False
        mock_col_row.is_identity = True
        mock_col_row.is_computed = False
        mock_col_row.default_value = None
        mock_col_row.computed_definition = None

        # Setup mock to return different results for different queries
        call_count = [0]
        def fetch_all_side_effect(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:  # First call is for tables
                return [mock_table_row]
            else:  # Second call is for columns
                return [mock_col_row]

        mock_db_connection.fetch_all.side_effect = fetch_all_side_effect

        reader = SchemaReader(mock_db_connection)
        tables = reader.get_tables()

        assert len(tables) == 1
        assert tables[0].schema_name == "dbo"
        assert tables[0].table_name == "Config"
        assert len(tables[0].columns) == 1
        assert tables[0].columns[0].name == "ConfigID"
        assert tables[0].columns[0].is_identity is True

    def test_get_tables_with_filter(self, mock_db_connection):
        """Test getting tables with schema filter."""
        mock_table_row = MagicMock()
        mock_table_row.schema_name = "MQTT"
        mock_table_row.table_name = "Broker"

        # Mock empty columns
        call_count = [0]
        def fetch_all_side_effect(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:  # First call is for tables
                return [mock_table_row]
            else:  # Subsequent calls are for columns
                return []

        mock_db_connection.fetch_all.side_effect = fetch_all_side_effect

        reader = SchemaReader(mock_db_connection)
        tables = reader.get_tables(schema_filter=["MQTT"])

        assert len(tables) == 1
        assert tables[0].schema_name == "MQTT"

    def test_get_table_columns_with_various_types(self, mock_db_connection):
        """Test getting table columns with various data types."""
        # Create mock rows for different column types
        col_int = MagicMock()
        col_int.column_name = "ID"
        col_int.data_type = "int"
        col_int.max_length = 4
        col_int.precision = 10
        col_int.scale = 0
        col_int.is_nullable = False
        col_int.is_identity = True
        col_int.is_computed = False
        col_int.default_value = None
        col_int.computed_definition = None

        col_nvarchar = MagicMock()
        col_nvarchar.column_name = "Name"
        col_nvarchar.data_type = "nvarchar"
        col_nvarchar.max_length = 200  # Will be divided by 2
        col_nvarchar.precision = 0
        col_nvarchar.scale = 0
        col_nvarchar.is_nullable = False
        col_nvarchar.is_identity = False
        col_nvarchar.is_computed = False
        col_nvarchar.default_value = None
        col_nvarchar.computed_definition = None

        col_computed = MagicMock()
        col_computed.column_name = "Total"
        col_computed.data_type = "decimal"
        col_computed.max_length = 9
        col_computed.precision = 18
        col_computed.scale = 2
        col_computed.is_nullable = True
        col_computed.is_identity = False
        col_computed.is_computed = True
        col_computed.default_value = None
        col_computed.computed_definition = "([SubTotal]*[TaxRate])"

        col_with_default = MagicMock()
        col_with_default.column_name = "IsEnabled"
        col_with_default.data_type = "bit"
        col_with_default.max_length = 1
        col_with_default.precision = 0
        col_with_default.scale = 0
        col_with_default.is_nullable = False
        col_with_default.is_identity = False
        col_with_default.is_computed = False
        col_with_default.default_value = "((1))"
        col_with_default.computed_definition = None

        mock_db_connection.fetch_all.return_value = [
            col_int, col_nvarchar, col_computed, col_with_default
        ]

        reader = SchemaReader(mock_db_connection)
        columns = reader.get_table_columns("dbo", "TestTable")

        assert len(columns) == 4

        # Test int column
        assert columns[0].name == "ID"
        assert columns[0].data_type == "int"
        assert columns[0].is_identity is True
        assert columns[0].is_computed is False

        # Test nvarchar column (max_length should be halved)
        assert columns[1].name == "Name"
        assert columns[1].data_type == "nvarchar"
        assert columns[1].max_length == 100  # 200 / 2
        assert columns[1].is_nullable is False

        # Test computed column
        assert columns[2].name == "Total"
        assert columns[2].is_computed is True
        assert columns[2].computed_definition == "([SubTotal]*[TaxRate])"
        assert columns[2].precision == 18
        assert columns[2].scale == 2

        # Test column with default value
        assert columns[3].name == "IsEnabled"
        assert columns[3].default_value == "((1))"
        assert columns[3].is_nullable is False

    def test_get_table_columns_nvarchar_max(self, mock_db_connection):
        """Test nvarchar(MAX) handling."""
        col_nvarchar_max = MagicMock()
        col_nvarchar_max.column_name = "Description"
        col_nvarchar_max.data_type = "nvarchar"
        col_nvarchar_max.max_length = -1  # MAX type
        col_nvarchar_max.precision = 0
        col_nvarchar_max.scale = 0
        col_nvarchar_max.is_nullable = True
        col_nvarchar_max.is_identity = False
        col_nvarchar_max.is_computed = False
        col_nvarchar_max.default_value = None
        col_nvarchar_max.computed_definition = None

        mock_db_connection.fetch_all.return_value = [col_nvarchar_max]

        reader = SchemaReader(mock_db_connection)
        columns = reader.get_table_columns("dbo", "TestTable")

        assert columns[0].max_length is None  # MAX should be None

    def test_get_views_no_filter(self, mock_db_connection):
        """Test getting all views."""
        mock_view1 = MagicMock()
        mock_view1.schema_name = "MQTT"
        mock_view1.view_name = "vwActiveReceivers"
        mock_view1.definition = "CREATE VIEW MQTT.vwActiveReceivers AS SELECT * FROM ..."

        mock_view2 = MagicMock()
        mock_view2.schema_name = "dbo"
        mock_view2.view_name = "vwSummary"
        mock_view2.definition = "CREATE VIEW dbo.vwSummary AS SELECT COUNT(*) ..."

        mock_db_connection.fetch_all.return_value = [mock_view1, mock_view2]

        reader = SchemaReader(mock_db_connection)
        views = reader.get_views()

        assert len(views) == 2
        assert views[0]['schema_name'] == "MQTT"
        assert views[0]['view_name'] == "vwActiveReceivers"
        assert "CREATE VIEW" in views[0]['definition']
        assert views[1]['schema_name'] == "dbo"

    def test_get_views_with_filter(self, mock_db_connection):
        """Test getting views with schema filter."""
        mock_view = MagicMock()
        mock_view.schema_name = "MQTT"
        mock_view.view_name = "vwActiveReceivers"
        mock_view.definition = "CREATE VIEW ..."

        mock_db_connection.fetch_all.return_value = [mock_view]

        reader = SchemaReader(mock_db_connection)
        views = reader.get_views(schema_filter=["MQTT"])

        assert len(views) == 1
        assert views[0]['schema_name'] == "MQTT"

        call_args = mock_db_connection.fetch_all.call_args
        assert "IN (?)" in call_args[0][0]
        assert call_args[0][1] == ("MQTT",)

    def test_get_stored_procedures_no_filter(self, mock_db_connection):
        """Test getting all stored procedures."""
        mock_proc1 = MagicMock()
        mock_proc1.schema_name = "MQTT"
        mock_proc1.procedure_name = "sp_GetReceiversByBroker"
        mock_proc1.definition = "CREATE PROCEDURE MQTT.sp_GetReceiversByBroker ..."

        mock_proc2 = MagicMock()
        mock_proc2.schema_name = "dbo"
        mock_proc2.procedure_name = "sp_Cleanup"
        mock_proc2.definition = "CREATE PROCEDURE dbo.sp_Cleanup ..."

        mock_db_connection.fetch_all.return_value = [mock_proc1, mock_proc2]

        reader = SchemaReader(mock_db_connection)
        procedures = reader.get_stored_procedures()

        assert len(procedures) == 2
        assert procedures[0]['schema_name'] == "MQTT"
        assert procedures[0]['procedure_name'] == "sp_GetReceiversByBroker"
        assert procedures[1]['schema_name'] == "dbo"

    def test_get_stored_procedures_skip_encrypted(self, mock_db_connection):
        """Test that encrypted stored procedures are skipped."""
        mock_proc_normal = MagicMock()
        mock_proc_normal.schema_name = "dbo"
        mock_proc_normal.procedure_name = "sp_Normal"
        mock_proc_normal.definition = "CREATE PROCEDURE ..."

        mock_proc_encrypted = MagicMock()
        mock_proc_encrypted.schema_name = "dbo"
        mock_proc_encrypted.procedure_name = "sp_Encrypted"
        mock_proc_encrypted.definition = None  # Encrypted

        mock_db_connection.fetch_all.return_value = [mock_proc_normal, mock_proc_encrypted]

        reader = SchemaReader(mock_db_connection)
        procedures = reader.get_stored_procedures()

        # Only non-encrypted procedure should be returned
        assert len(procedures) == 1
        assert procedures[0]['procedure_name'] == "sp_Normal"

    def test_get_functions_all_types(self, mock_db_connection):
        """Test getting all function types (scalar, inline table-valued, multi-statement table-valued)."""
        mock_fn_scalar = MagicMock()
        mock_fn_scalar.schema_name = "dbo"
        mock_fn_scalar.function_name = "fn_GetConfigValue"
        mock_fn_scalar.function_type = "SQL_SCALAR_FUNCTION"
        mock_fn_scalar.definition = "CREATE FUNCTION dbo.fn_GetConfigValue(...) RETURNS NVARCHAR ..."

        mock_fn_inline_tvf = MagicMock()
        mock_fn_inline_tvf.schema_name = "Logging"
        mock_fn_inline_tvf.function_name = "fn_GetRecentEvents"
        mock_fn_inline_tvf.function_type = "SQL_INLINE_TABLE_VALUED_FUNCTION"
        mock_fn_inline_tvf.definition = "CREATE FUNCTION Logging.fn_GetRecentEvents(...) RETURNS TABLE AS RETURN ..."

        mock_fn_mstvf = MagicMock()
        mock_fn_mstvf.schema_name = "dbo"
        mock_fn_mstvf.function_name = "fn_SplitString"
        mock_fn_mstvf.function_type = "SQL_TABLE_VALUED_FUNCTION"
        mock_fn_mstvf.definition = "CREATE FUNCTION dbo.fn_SplitString(...) RETURNS @Result TABLE ..."

        mock_db_connection.fetch_all.return_value = [mock_fn_scalar, mock_fn_inline_tvf, mock_fn_mstvf]

        reader = SchemaReader(mock_db_connection)
        functions = reader.get_functions()

        assert len(functions) == 3

        assert functions[0]['function_name'] == "fn_GetConfigValue"
        assert functions[0]['function_type'] == "SQL_SCALAR_FUNCTION"

        assert functions[1]['function_name'] == "fn_GetRecentEvents"
        assert functions[1]['function_type'] == "SQL_INLINE_TABLE_VALUED_FUNCTION"

        assert functions[2]['function_name'] == "fn_SplitString"
        assert functions[2]['function_type'] == "SQL_TABLE_VALUED_FUNCTION"

    def test_get_functions_with_filter(self, mock_db_connection):
        """Test getting functions with schema filter."""
        mock_function = MagicMock()
        mock_function.schema_name = "dbo"
        mock_function.function_name = "fn_Test"
        mock_function.function_type = "SQL_SCALAR_FUNCTION"
        mock_function.definition = "CREATE FUNCTION ..."

        mock_db_connection.fetch_all.return_value = [mock_function]

        reader = SchemaReader(mock_db_connection)
        functions = reader.get_functions(schema_filter=["dbo"])

        assert len(functions) == 1
        assert functions[0]['schema_name'] == "dbo"

        call_args = mock_db_connection.fetch_all.call_args
        assert "IN (?)" in call_args[0][0]
        assert call_args[0][1] == ("dbo",)


class TestDataClasses:
    """Test schema dataclasses."""

    def test_schema_info(self):
        """Test SchemaInfo dataclass."""
        schema = SchemaInfo(name="MQTT", owner="sa")

        assert schema.name == "MQTT"
        assert schema.owner == "sa"

    def test_schema_info_default_owner(self):
        """Test SchemaInfo with default owner."""
        schema = SchemaInfo(name="CustomSchema")

        assert schema.name == "CustomSchema"
        assert schema.owner == "dbo"

    def test_column_info(self):
        """Test ColumnInfo dataclass."""
        column = ColumnInfo(
            name="ConfigID",
            data_type="int",
            max_length=4,
            precision=10,
            scale=0,
            is_nullable=False,
            is_identity=True,
            is_computed=False,
            default_value=None,
            computed_definition=None
        )

        assert column.name == "ConfigID"
        assert column.data_type == "int"
        assert column.is_identity is True
        assert column.is_computed is False

    def test_table_info(self):
        """Test TableInfo dataclass."""
        col1 = ColumnInfo(
            name="ID",
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
            name="Name",
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

        table = TableInfo(
            schema_name="dbo",
            table_name="Config",
            columns=[col1, col2]
        )

        assert table.schema_name == "dbo"
        assert table.table_name == "Config"
        assert len(table.columns) == 2
        assert table.columns[0].name == "ID"
        assert table.columns[1].name == "Name"
