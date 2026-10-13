"""Tests for SQL formatter module."""

import pytest
import tempfile
import os
from pathlib import Path
from src.formatter import SQLFormatter
from src.schema import SchemaInfo, TableInfo, ColumnInfo
from src.constraints import PrimaryKeyInfo, ForeignKeyInfo


class TestSQLFormatter:
    """Test SQLFormatter class."""

    def test_formatter_initialization(self):
        """Test formatter initialization creates output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            assert formatter.output_dir == tmpdir
            assert os.path.exists(tmpdir)

    def test_format_schema(self):
        """Test formatting schema CREATE statement."""
        formatter = SQLFormatter("/tmp/test")

        schema = SchemaInfo(name="MQTT", owner="dbo")
        sql = formatter.format_schema(schema)

        assert "CREATE SCHEMA" in sql
        assert "MQTT" in sql
        assert "sys.schemas" in sql

    def test_format_sequence_default_bigint(self):
        """Test formatting a sequence with the default bigint type omits the AS clause."""
        formatter = SQLFormatter("/tmp/test")

        seq = {
            'schema_name': 'dbo', 'sequence_name': 'seq_OrderNumbers', 'data_type': 'bigint',
            'precision': 19, 'scale': 0, 'start_value': 1, 'increment': 1,
            'minimum_value': 1, 'maximum_value': 9223372036854775807,
            'is_cycling': False, 'is_cached': True, 'cache_size': 50
        }

        sql = formatter.format_sequence(seq)

        assert "CREATE SEQUENCE [dbo].[seq_OrderNumbers]" in sql
        assert " AS " not in sql.split("START WITH")[0]
        assert "START WITH 1" in sql
        assert "INCREMENT BY 1" in sql
        assert "NO CYCLE" in sql
        assert "CACHE 50" in sql

    def test_format_sequence_non_default_type_and_cycle(self):
        """Test formatting a non-bigint, cycling, uncached sequence."""
        formatter = SQLFormatter("/tmp/test")

        seq = {
            'schema_name': 'dbo', 'sequence_name': 'seq_SmallCounter', 'data_type': 'int',
            'precision': 10, 'scale': 0, 'start_value': 1, 'increment': 1,
            'minimum_value': 1, 'maximum_value': 100,
            'is_cycling': True, 'is_cached': False, 'cache_size': None
        }

        sql = formatter.format_sequence(seq)

        assert "AS int" in sql
        assert "CYCLE" in sql and "NO CYCLE" not in sql
        assert "NO CACHE" in sql

    def test_format_extended_properties_table_and_columns(self):
        """Test formatting sp_addextendedproperty statements for a table and its columns."""
        formatter = SQLFormatter("/tmp/test")

        properties = {
            'table_description': "Customer orders.",
            'columns': {"OrderID": "Primary key.", "Notes": None}
        }

        sql = formatter.format_extended_properties("dbo", "Orders", properties)

        assert "@level1type=N'TABLE', @level1name=N'Orders'" in sql
        assert "@value=N'Customer orders.'" in sql
        assert "@level2type=N'COLUMN', @level2name=N'OrderID'" in sql
        assert "@value=N'Primary key.'" in sql
        assert "Notes" not in sql  # No description -> not emitted

    def test_format_extended_properties_stable_column_order(self):
        """Test column descriptions have stable output regardless of input order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)
            columns = {
                "Unknown_YN": "Use this value if no eExact_id can be found",
                "GeneralLedgerType": "1 = sales; 2 = purchase; 3 = stock",
            }
            properties = {'table_description': "Article codes", 'columns': columns}
            reversed_properties = {
                'table_description': properties['table_description'],
                'columns': dict(reversed(list(columns.items()))),
            }

            sql = formatter.format_extended_properties("dbo", "ArticleExactCode", properties)

            assert sql == formatter.format_extended_properties(
                "dbo", "ArticleExactCode", reversed_properties
            )
            assert sql.index("Article codes") < sql.index("GeneralLedgerType")
            assert sql.index("GeneralLedgerType") < sql.index("Unknown_YN")

    def test_format_extended_properties_empty(self):
        """Test formatting extended properties for a table with no descriptions."""
        formatter = SQLFormatter("/tmp/test")

        sql = formatter.format_extended_properties("dbo", "Orders", {'table_description': None, 'columns': {}})

        assert sql == ""

    def test_format_extended_properties_escapes_quotes(self):
        """Test that single quotes in descriptions are escaped for the SQL string literal."""
        formatter = SQLFormatter("/tmp/test")

        properties = {'table_description': "Customer's orders.", 'columns': {}}
        sql = formatter.format_extended_properties("dbo", "Orders", properties)

        assert "Customer''s orders." in sql

    def test_format_user_defined_type_alias(self):
        """Test formatting an alias type as CREATE TYPE ... FROM <base type>."""
        formatter = SQLFormatter("/tmp/test")

        udt = {
            'kind': 'alias', 'schema_name': 'dbo', 'type_name': 'PhoneNumber',
            'base_type': 'varchar', 'max_length': 20, 'precision': None, 'scale': None,
            'is_nullable': True
        }

        sql = formatter.format_user_defined_type(udt)

        assert "CREATE TYPE [dbo].[PhoneNumber]" in sql
        assert "FROM varchar(20) NULL" in sql

    def test_format_user_defined_type_table(self):
        """Test formatting a table type as CREATE TYPE ... AS TABLE, including inline PRIMARY KEY."""
        formatter = SQLFormatter("/tmp/test")

        col = ColumnInfo(
            name="ID", data_type="int", max_length=None, precision=None, scale=None,
            is_nullable=False, is_identity=False, is_computed=False,
            default_value=None, computed_definition=None
        )
        udt = {
            'kind': 'table', 'schema_name': 'dbo', 'type_name': 'IdList',
            'columns': [col], 'primary_key_columns': ['ID']
        }

        sql = formatter.format_user_defined_type(udt)

        assert "CREATE TYPE [dbo].[IdList] AS TABLE" in sql
        assert "[ID] int NOT NULL" in sql
        assert "PRIMARY KEY ([ID])" in sql

    def test_format_user_defined_type_clr(self):
        """Test that a CLR type is emitted as a metadata comment, not a CREATE TYPE statement."""
        formatter = SQLFormatter("/tmp/test")

        udt = {
            'kind': 'clr', 'schema_name': 'dbo', 'type_name': 'GeoPoint',
            'assembly_name': 'SpatialTypes', 'class_name': 'SpatialTypes.GeoPoint'
        }

        sql = formatter.format_user_defined_type(udt)

        assert sql.startswith("--")
        assert "CREATE TYPE [dbo].[GeoPoint]" not in sql
        assert "SpatialTypes" in sql

    def test_format_function_clr(self):
        """Test that a CLR function is emitted as a metadata comment, not a CREATE FUNCTION statement."""
        formatter = SQLFormatter("/tmp/test")

        func = {
            'kind': 'clr', 'schema_name': 'dbo', 'function_name': 'fn_GeoDistance',
            'function_type': 'CLR_SCALAR_FUNCTION', 'assembly_name': 'SpatialTypes',
            'class_name': 'SpatialTypes.GeoFunctions', 'method_name': 'Distance'
        }

        sql = formatter.format_function(func)

        assert sql.startswith("--")
        assert "CREATE FUNCTION dbo.fn_GeoDistance" not in sql
        assert "SpatialTypes" in sql
        assert "Distance" in sql

    def test_format_function_sql(self):
        """Test that a SQL function's definition is passed through as-is."""
        formatter = SQLFormatter("/tmp/test")

        func = {
            'kind': 'sql', 'schema_name': 'dbo', 'function_name': 'fn_Test',
            'function_type': 'SQL_SCALAR_FUNCTION', 'definition': 'CREATE FUNCTION dbo.fn_Test() RETURNS int AS ...'
        }

        sql = formatter.format_function(func)

        assert sql.startswith("CREATE FUNCTION dbo.fn_Test()")
        assert sql.endswith("\nGO\n")

    def test_format_table(self):
        """Test formatting table CREATE statement."""
        formatter = SQLFormatter("/tmp/test")

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

        table = TableInfo(
            schema_name="dbo",
            table_name="Config",
            columns=[col1, col2]
        )

        sql = formatter.format_table(table)

        assert "CREATE TABLE" in sql
        assert "[dbo].[Config]" in sql
        assert "ConfigID" in sql
        assert "IDENTITY" in sql
        assert "nvarchar(100)" in sql

    def test_format_view_with_leading_comment(self):
        """The raw definition (which may include a leading comment in the same batch as
        CREATE VIEW) must be emitted as-is, not wrapped in a second synthetic CREATE VIEW."""
        formatter = SQLFormatter("/tmp/test")

        view = {
            'schema_name': 'MQTT', 'view_name': 'vwActiveReceivers',
            'definition': "-- Create view\nCREATE VIEW MQTT.vwActiveReceivers\nAS\nSELECT 1"
        }

        sql = formatter.format_view(view)

        assert sql.count("CREATE VIEW") == 1

    def test_format_table_computed_column(self):
        """Computed columns must not get a data type before AS, and PERSISTED only when set."""
        formatter = SQLFormatter("/tmp/test")

        base_col = ColumnInfo(
            name="SubTotal", data_type="decimal", max_length=None, precision=18, scale=2,
            is_nullable=False, is_identity=False, is_computed=False,
            default_value=None, computed_definition=None
        )
        persisted_col = ColumnInfo(
            name="TaxAmount", data_type="decimal", max_length=None, precision=24, scale=6,
            is_nullable=True, is_identity=False, is_computed=True,
            default_value=None, computed_definition="([SubTotal]*[TaxRate])", is_persisted=True
        )
        non_persisted_col = ColumnInfo(
            name="TotalAmount", data_type="decimal", max_length=None, precision=25, scale=6,
            is_nullable=True, is_identity=False, is_computed=True,
            default_value=None, computed_definition="([SubTotal]*((1)+[TaxRate]))", is_persisted=False
        )

        table = TableInfo(
            schema_name="dbo", table_name="Orders",
            columns=[base_col, persisted_col, non_persisted_col]
        )

        sql = formatter.format_table(table)

        assert "[TaxAmount] AS ([SubTotal]*[TaxRate]) PERSISTED" in sql
        assert "[TotalAmount] AS ([SubTotal]*((1)+[TaxRate]))" in sql
        assert "[TotalAmount] AS ([SubTotal]*((1)+[TaxRate])) PERSISTED" not in sql
        assert "decimal(24,6) AS" not in sql
        assert "decimal(25,6) AS" not in sql

    def test_format_primary_key(self):
        """Test formatting primary key constraint."""
        formatter = SQLFormatter("/tmp/test")

        pk = PrimaryKeyInfo(
            constraint_name="PK_Config",
            schema_name="dbo",
            table_name="Config",
            columns=["ConfigID"],
            is_clustered=True
        )

        sql = formatter.format_primary_key(pk)

        assert "ALTER TABLE" in sql
        assert "PRIMARY KEY CLUSTERED" in sql
        assert "PK_Config" in sql

    def test_format_foreign_key(self):
        """Test formatting foreign key constraint."""
        formatter = SQLFormatter("/tmp/test")

        fk = ForeignKeyInfo(
            constraint_name="FK_ReceiverConfig_Broker",
            schema_name="MQTT",
            table_name="ReceiverConfig",
            columns=["BrokerID"],
            referenced_schema="MQTT",
            referenced_table="Broker",
            referenced_columns=["BrokerID"],
            delete_action="CASCADE",
            update_action="NO_ACTION"
        )

        sql = formatter.format_foreign_key(fk)

        assert "ALTER TABLE" in sql
        assert "FOREIGN KEY" in sql
        assert "REFERENCES" in sql
        assert "ON DELETE CASCADE" in sql

    def test_format_trigger_enabled(self):
        """Test formatting an enabled trigger emits only the CREATE TRIGGER statement."""
        formatter = SQLFormatter("/tmp/test")

        trigger = {
            'schema_name': 'dbo',
            'table_name': 'Orders',
            'trigger_name': 'trg_Orders_Audit',
            'is_instead_of': False,
            'is_disabled': False,
            'events': ['INSERT', 'UPDATE'],
            'definition': 'CREATE TRIGGER dbo.trg_Orders_Audit ON dbo.Orders AFTER INSERT, UPDATE AS ...'
        }

        sql = formatter.format_trigger(trigger)

        assert "CREATE TRIGGER" in sql
        assert "DISABLE TRIGGER" not in sql

    def test_format_trigger_disabled(self):
        """Test formatting a disabled trigger appends a DISABLE TRIGGER statement."""
        formatter = SQLFormatter("/tmp/test")

        trigger = {
            'schema_name': 'dbo',
            'table_name': 'Orders',
            'trigger_name': 'trg_Orders_Audit',
            'is_instead_of': False,
            'is_disabled': True,
            'events': ['DELETE'],
            'definition': 'CREATE TRIGGER dbo.trg_Orders_Audit ON dbo.Orders AFTER DELETE AS ...'
        }

        sql = formatter.format_trigger(trigger)

        assert "CREATE TRIGGER" in sql
        assert "DISABLE TRIGGER [dbo].[Orders]" not in sql
        assert "DISABLE TRIGGER [trg_Orders_Audit] ON [dbo].[Orders]" in sql

    def test_write_modular_format_generates_deploy_scripts(self):
        """Test that deploy.sh/deploy.ps1 list only the files actually written, in order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            col = ColumnInfo(
                name="ID", data_type="int", max_length=None, precision=None, scale=None,
                is_nullable=False, is_identity=True, is_computed=False,
                default_value=None, computed_definition=None
            )
            table = TableInfo(schema_name="dbo", table_name="Config", columns=[col])

            formatter.write_modular_format(
                schemas=[], user_defined_types=[], sequences=[], tables=[table], extended_properties={},
                primary_keys=[], foreign_keys=[],
                deferred_foreign_keys=[], unique_constraints=[], check_constraints=[],
                indexes=[], views=[], procedures=[], functions=[], triggers=[],
                seed_data=[]
            )

            # Only tables were provided, so only 04_CREATE_TABLES.sql should exist
            # and be the only entry in the deploy scripts.
            assert os.path.exists(os.path.join(tmpdir, '04_CREATE_TABLES.sql'))
            assert not os.path.exists(os.path.join(tmpdir, '01_CREATE_SCHEMAS.sql'))

            sh_content = Path(tmpdir, 'deploy.sh').read_text(encoding='utf-8')
            assert '04_CREATE_TABLES.sql' in sh_content
            assert '01_CREATE_SCHEMAS.sql' not in sh_content
            assert 'sqlcmd' in sh_content

            ps1_content = Path(tmpdir, 'deploy.ps1').read_text(encoding='utf-8')
            assert '04_CREATE_TABLES.sql' in ps1_content
            assert '01_CREATE_SCHEMAS.sql' not in ps1_content
            assert 'sqlcmd' in ps1_content

    def test_write_modular_format_writes_types_file(self):
        """Test that user-defined types are written to their own numbered modular file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            udt = {
                'kind': 'alias', 'schema_name': 'dbo', 'type_name': 'PhoneNumber',
                'base_type': 'varchar', 'max_length': 20, 'precision': None, 'scale': None,
                'is_nullable': True
            }

            formatter.write_modular_format(
                schemas=[], user_defined_types=[udt], sequences=[], tables=[], extended_properties={},
                primary_keys=[], foreign_keys=[],
                deferred_foreign_keys=[], unique_constraints=[], check_constraints=[],
                indexes=[], views=[], procedures=[], functions=[], triggers=[],
                seed_data=[]
            )

            assert os.path.exists(os.path.join(tmpdir, '02_CREATE_TYPES.sql'))
            content = Path(tmpdir, '02_CREATE_TYPES.sql').read_text(encoding='utf-8')
            assert "CREATE TYPE [dbo].[PhoneNumber]" in content

            sh_content = Path(tmpdir, 'deploy.sh').read_text(encoding='utf-8')
            assert '02_CREATE_TYPES.sql' in sh_content

    def test_write_modular_format_includes_extended_properties(self):
        """Test that table/column descriptions are written into the tables file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            col = ColumnInfo(
                name="ID", data_type="int", max_length=None, precision=None, scale=None,
                is_nullable=False, is_identity=True, is_computed=False,
                default_value=None, computed_definition=None
            )
            table = TableInfo(schema_name="dbo", table_name="Config", columns=[col])
            extended_properties = {
                ("dbo", "Config"): {'table_description': "App configuration.", 'columns': {"ID": "Row identifier."}}
            }

            formatter.write_modular_format(
                schemas=[], user_defined_types=[], sequences=[], tables=[table], extended_properties=extended_properties,
                primary_keys=[], foreign_keys=[],
                deferred_foreign_keys=[], unique_constraints=[], check_constraints=[],
                indexes=[], views=[], procedures=[], functions=[], triggers=[],
                seed_data=[]
            )

            content = Path(tmpdir, '04_CREATE_TABLES.sql').read_text(encoding='utf-8')
            assert "sp_addextendedproperty" in content
            assert "App configuration." in content
            assert "Row identifier." in content

    def test_write_readme_modular(self):
        """Test README generation for modular format lists objects and deploy instructions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            col = ColumnInfo(
                name="ID", data_type="int", max_length=None, precision=None, scale=None,
                is_nullable=False, is_identity=True, is_computed=False,
                default_value=None, computed_definition=None
            )
            table = TableInfo(schema_name="dbo", table_name="Config", columns=[col])
            view = {"schema_name": "dbo", "view_name": "vwConfig", "definition": "..."}

            formatter.write_readme(
                output_format='modular',
                group_by_table=False,
                schemas=[], user_defined_types=[], sequences=[], tables=[table], views=[view], procedures=[], functions=[],
                triggers=[], indexes=[], deferred_foreign_keys=[], has_seed_data=True
            )

            content = Path(tmpdir, 'README.md').read_text(encoding='utf-8')
            assert "dbo.Config" in content
            assert "dbo.vwConfig" in content
            assert "deploy.sh" in content
            assert "deploy.ps1" in content
            assert "Seed data is included" in content

    def test_write_readme_procedure_signature(self):
        """Test that README lists a procedure's parsed parameters as a signature, and tags CLR functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = SQLFormatter(tmpdir)

            proc = {
                'schema_name': 'dbo', 'procedure_name': 'sp_GetUser',
                'definition': '...',
                'parameters': [
                    {
                        'name': '@UserId', 'data_type': 'int', 'max_length': None,
                        'precision': None, 'scale': None, 'is_output': False,
                        'has_default_value': False, 'default_value': None
                    },
                    {
                        'name': '@Name', 'data_type': 'nvarchar', 'max_length': 50,
                        'precision': None, 'scale': None, 'is_output': True,
                        'has_default_value': True, 'default_value': 'NULL'
                    }
                ]
            }
            proc_no_params = {
                'schema_name': 'dbo', 'procedure_name': 'sp_Cleanup',
                'definition': '...', 'parameters': []
            }
            clr_func = {
                'kind': 'clr', 'schema_name': 'dbo', 'function_name': 'fn_GeoDistance',
                'function_type': 'CLR_SCALAR_FUNCTION', 'assembly_name': 'SpatialTypes',
                'class_name': 'SpatialTypes.GeoFunctions', 'method_name': 'Distance'
            }

            formatter.write_readme(
                output_format='modular',
                group_by_table=False,
                schemas=[], user_defined_types=[], sequences=[], tables=[], views=[],
                procedures=[proc, proc_no_params], functions=[clr_func],
                triggers=[], indexes=[], deferred_foreign_keys=[], has_seed_data=False
            )

            content = Path(tmpdir, 'README.md').read_text(encoding='utf-8')
            assert "dbo.sp_GetUser(@UserId int, @Name nvarchar(50) = NULL OUTPUT)" in content
            assert "dbo.sp_Cleanup()" in content
            assert "dbo.fn_GeoDistance (CLR)" in content

    def test_write_header(self):
        """Test SQL script header generation."""
        formatter = SQLFormatter("/tmp/test")

        header = formatter.write_header()

        assert "SQL Extract" in header
        assert "Generated by" in header
        assert "SET QUOTED_IDENTIFIER ON" in header
