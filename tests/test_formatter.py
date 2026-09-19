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
                schemas=[], tables=[table], primary_keys=[], foreign_keys=[],
                deferred_foreign_keys=[], unique_constraints=[], check_constraints=[],
                indexes=[], views=[], procedures=[], functions=[], triggers=[],
                seed_data=[]
            )

            # Only tables were provided, so only 02_CREATE_TABLES.sql should exist
            # and be the only entry in the deploy scripts.
            assert os.path.exists(os.path.join(tmpdir, '02_CREATE_TABLES.sql'))
            assert not os.path.exists(os.path.join(tmpdir, '01_CREATE_SCHEMAS.sql'))

            sh_content = Path(tmpdir, 'deploy.sh').read_text(encoding='utf-8')
            assert '02_CREATE_TABLES.sql' in sh_content
            assert '01_CREATE_SCHEMAS.sql' not in sh_content
            assert 'sqlcmd' in sh_content

            ps1_content = Path(tmpdir, 'deploy.ps1').read_text(encoding='utf-8')
            assert '02_CREATE_TABLES.sql' in ps1_content
            assert '01_CREATE_SCHEMAS.sql' not in ps1_content
            assert 'sqlcmd' in ps1_content

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
                schemas=[], tables=[table], views=[view], procedures=[], functions=[],
                triggers=[], indexes=[], deferred_foreign_keys=[], has_seed_data=True
            )

            content = Path(tmpdir, 'README.md').read_text(encoding='utf-8')
            assert "dbo.Config" in content
            assert "dbo.vwConfig" in content
            assert "deploy.sh" in content
            assert "deploy.ps1" in content
            assert "Seed data is included" in content

    def test_write_header(self):
        """Test SQL script header generation."""
        formatter = SQLFormatter("/tmp/test")

        header = formatter.write_header()

        assert "SQL Extract" in header
        assert "Generated by" in header
        assert "SET QUOTED_IDENTIFIER ON" in header
