"""SQL script formatter and generator."""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from .schema import SchemaInfo, TableInfo, ColumnInfo
from .constraints import PrimaryKeyInfo, ForeignKeyInfo, UniqueConstraintInfo, CheckConstraintInfo
from .indexes import IndexInfo
from .utils import get_logger, escape_sql_identifier, OutputError

logger = get_logger(__name__)


class SQLFormatter:
    """Format and generate SQL scripts."""

    def __init__(self, output_dir: str, omit_ts: bool = False, no_header: bool = False):
        """Initialize SQL formatter.

        Args:
            output_dir: Output directory path
            omit_ts: Omit the generation timestamp from output headers
            no_header: Omit the header comment block from output files entirely
        """
        self.output_dir = output_dir
        self.omit_ts = omit_ts
        self.no_header = no_header
        os.makedirs(output_dir, exist_ok=True)

    def format_schema(self, schema: SchemaInfo) -> str:
        """Generate CREATE SCHEMA statement.

        Args:
            schema: Schema information

        Returns:
            SQL statement
        """
        return f"""
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = '{schema.name}')
BEGIN
    EXEC('CREATE SCHEMA {escape_sql_identifier(schema.name)}')
END
GO
"""

    def format_table(self, table: TableInfo) -> str:
        """Generate CREATE TABLE statement.

        Args:
            table: Table information

        Returns:
            SQL statement
        """
        lines = []
        lines.append(f"CREATE TABLE {escape_sql_identifier(table.schema_name)}.{escape_sql_identifier(table.table_name)} (")

        column_defs = []
        for col in table.columns:
            col_def = f"    {escape_sql_identifier(col.name)} {self._format_data_type(col)}"

            if col.is_identity:
                col_def += " IDENTITY(1,1)"

            if col.is_computed:
                col_def += f" AS {col.computed_definition}"
            else:
                col_def += " NULL" if col.is_nullable else " NOT NULL"

                if col.default_value:
                    col_def += f" DEFAULT {col.default_value}"

            column_defs.append(col_def)

        lines.append(',\n'.join(column_defs))
        lines.append(")")
        lines.append("GO")

        return '\n'.join(lines)

    def _format_data_type(self, col: ColumnInfo) -> str:
        """Format column data type.

        Args:
            col: Column information

        Returns:
            Formatted data type string
        """
        data_type = col.data_type

        if col.data_type in ('varchar', 'nvarchar', 'char', 'nchar', 'varbinary', 'binary'):
            if col.max_length == -1:
                return f"{data_type}(MAX)"
            elif col.max_length:
                return f"{data_type}({col.max_length})"
            else:
                return data_type

        elif col.data_type in ('decimal', 'numeric'):
            if col.precision and col.scale is not None:
                return f"{data_type}({col.precision},{col.scale})"
            elif col.precision:
                return f"{data_type}({col.precision})"
            else:
                return data_type

        elif col.data_type in ('datetime2', 'time', 'datetimeoffset'):
            if col.scale is not None:
                return f"{data_type}({col.scale})"
            else:
                return data_type

        else:
            return data_type

    def format_primary_key(self, pk: PrimaryKeyInfo) -> str:
        """Generate ALTER TABLE ADD PRIMARY KEY statement.

        Args:
            pk: Primary key information

        Returns:
            SQL statement
        """
        columns = ', '.join([escape_sql_identifier(col) for col in pk.columns])
        clustered = "CLUSTERED" if pk.is_clustered else "NONCLUSTERED"

        return f"""
ALTER TABLE {escape_sql_identifier(pk.schema_name)}.{escape_sql_identifier(pk.table_name)}
ADD CONSTRAINT {escape_sql_identifier(pk.constraint_name)} PRIMARY KEY {clustered} ({columns})
GO
"""

    def format_foreign_key(self, fk: ForeignKeyInfo) -> str:
        """Generate ALTER TABLE ADD FOREIGN KEY statement.

        Args:
            fk: Foreign key information

        Returns:
            SQL statement
        """
        columns = ', '.join([escape_sql_identifier(col) for col in fk.columns])
        ref_columns = ', '.join([escape_sql_identifier(col) for col in fk.referenced_columns])

        sql = f"""
ALTER TABLE {escape_sql_identifier(fk.schema_name)}.{escape_sql_identifier(fk.table_name)}
ADD CONSTRAINT {escape_sql_identifier(fk.constraint_name)} FOREIGN KEY ({columns})
REFERENCES {escape_sql_identifier(fk.referenced_schema)}.{escape_sql_identifier(fk.referenced_table)} ({ref_columns})"""

        if fk.delete_action != 'NO_ACTION':
            sql += f" ON DELETE {fk.delete_action}"

        if fk.update_action != 'NO_ACTION':
            sql += f" ON UPDATE {fk.update_action}"

        sql += "\nGO\n"
        return sql

    def format_unique_constraint(self, uq: UniqueConstraintInfo) -> str:
        """Generate ALTER TABLE ADD UNIQUE constraint statement.

        Args:
            uq: Unique constraint information

        Returns:
            SQL statement
        """
        columns = ', '.join([escape_sql_identifier(col) for col in uq.columns])

        return f"""
ALTER TABLE {escape_sql_identifier(uq.schema_name)}.{escape_sql_identifier(uq.table_name)}
ADD CONSTRAINT {escape_sql_identifier(uq.constraint_name)} UNIQUE ({columns})
GO
"""

    def format_check_constraint(self, check: CheckConstraintInfo) -> str:
        """Generate ALTER TABLE ADD CHECK constraint statement.

        Args:
            check: Check constraint information

        Returns:
            SQL statement
        """
        disabled = " NOCHECK" if check.is_disabled else ""

        return f"""
ALTER TABLE {escape_sql_identifier(check.schema_name)}.{escape_sql_identifier(check.table_name)}
ADD CONSTRAINT {escape_sql_identifier(check.constraint_name)} CHECK{disabled} {check.definition}
GO
"""

    def format_index(self, idx: IndexInfo) -> str:
        """Generate CREATE INDEX statement.

        Args:
            idx: Index information

        Returns:
            SQL statement
        """
        unique = "UNIQUE " if idx.is_unique else ""
        clustered = "CLUSTERED" if idx.is_clustered else "NONCLUSTERED"
        columns = ', '.join([escape_sql_identifier(col) for col in idx.columns])

        sql = f"""
CREATE {unique}{clustered} INDEX {escape_sql_identifier(idx.index_name)}
ON {escape_sql_identifier(idx.schema_name)}.{escape_sql_identifier(idx.table_name)} ({columns})"""

        if idx.included_columns:
            included = ', '.join([escape_sql_identifier(col) for col in idx.included_columns])
            sql += f"\nINCLUDE ({included})"

        if idx.filter_definition:
            sql += f"\nWHERE {idx.filter_definition}"

        sql += "\nGO\n"
        return sql

    def format_view(self, view: Dict[str, Any]) -> str:
        """Generate CREATE VIEW statement.

        Args:
            view: View information dictionary

        Returns:
            SQL statement
        """
        definition = view['definition']

        # Clean up definition if it starts with CREATE VIEW
        if definition.strip().upper().startswith('CREATE VIEW'):
            return definition + "\nGO\n"
        else:
            return f"""
CREATE VIEW {escape_sql_identifier(view['schema_name'])}.{escape_sql_identifier(view['view_name'])}
AS
{definition}
GO
"""

    def format_procedure(self, proc: Dict[str, Any]) -> str:
        """Generate CREATE PROCEDURE statement.

        Args:
            proc: Procedure information dictionary

        Returns:
            SQL statement
        """
        definition = proc['definition']

        # Definition already includes CREATE PROCEDURE
        return definition + "\nGO\n"

    def format_function(self, func: Dict[str, Any]) -> str:
        """Generate CREATE FUNCTION statement.

        Args:
            func: Function information dictionary

        Returns:
            SQL statement
        """
        definition = func['definition']

        # Definition already includes CREATE FUNCTION
        return definition + "\nGO\n"

    def format_trigger(self, trigger: Dict[str, Any]) -> str:
        """Generate CREATE TRIGGER statement.

        Args:
            trigger: Trigger information dictionary

        Returns:
            SQL statement
        """
        definition = trigger['definition']
        sql = definition + "\nGO\n"

        if trigger['is_disabled']:
            sql += f"""
DISABLE TRIGGER {escape_sql_identifier(trigger['trigger_name'])} ON {escape_sql_identifier(trigger['schema_name'])}.{escape_sql_identifier(trigger['table_name'])}
GO
"""

        return sql

    def write_header(self) -> str:
        """Generate SQL script header.

        Returns:
            Header comment
        """
        if self.no_header:
            comment_block = ""
        else:
            date_line = "" if self.omit_ts else f" * Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            comment_block = f"""/*
 * Database Schema Export
 * Generated by: SQL Extract v1.0.0
{date_line} */

"""
        return f"""{comment_block}SET QUOTED_IDENTIFIER ON
GO
SET ANSI_NULLS ON
GO

"""

    def write_single_file(
        self,
        schemas: List[SchemaInfo],
        tables: List[TableInfo],
        primary_keys: List[PrimaryKeyInfo],
        foreign_keys: List[ForeignKeyInfo],
        deferred_foreign_keys: List[ForeignKeyInfo],
        unique_constraints: List[UniqueConstraintInfo],
        check_constraints: List[CheckConstraintInfo],
        indexes: List[IndexInfo],
        views: List[Dict[str, Any]],
        procedures: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
        triggers: List[Dict[str, Any]],
        seed_data: List[str]
    ) -> None:
        """Write all SQL scripts to a single file with section comments.

        Args:
            schemas: List of schemas
            tables: List of tables
            primary_keys: List of primary keys
            foreign_keys: List of foreign keys
            deferred_foreign_keys: List of deferred foreign keys
            unique_constraints: List of unique constraints
            check_constraints: List of check constraints
            indexes: List of indexes
            views: List of views
            procedures: List of procedures
            functions: List of functions
            triggers: List of triggers
            seed_data: List of seed data INSERT statements
        """
        path = os.path.join(self.output_dir, 'schema.sql')
        regular_fks = [fk for fk in foreign_keys if fk not in deferred_foreign_keys]

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.write_header())

            if schemas:
                f.write("-- SCHEMAS\n\n")
                for schema in schemas:
                    f.write(self.format_schema(schema))
                    f.write("\n")

            if tables:
                f.write("-- TABLES\n\n")
                for table in tables:
                    f.write(self.format_table(table))
                    f.write("\n")

            if primary_keys:
                f.write("-- PRIMARY KEYS\n\n")
                for pk in primary_keys:
                    f.write(self.format_primary_key(pk))
                    f.write("\n")

            if unique_constraints:
                f.write("-- UNIQUE CONSTRAINTS\n\n")
                for uq in unique_constraints:
                    f.write(self.format_unique_constraint(uq))
                    f.write("\n")

            if regular_fks:
                f.write("-- FOREIGN KEYS\n\n")
                for fk in regular_fks:
                    f.write(self.format_foreign_key(fk))
                    f.write("\n")

            if check_constraints:
                f.write("-- CHECK CONSTRAINTS\n\n")
                for check in check_constraints:
                    f.write(self.format_check_constraint(check))
                    f.write("\n")

            if indexes:
                f.write("-- INDEXES\n\n")
                for idx in indexes:
                    f.write(self.format_index(idx))
                    f.write("\n")

            if views:
                f.write("-- VIEWS\n\n")
                for view in views:
                    f.write(self.format_view(view))
                    f.write("\n")

            if procedures:
                f.write("-- STORED PROCEDURES\n\n")
                for proc in procedures:
                    f.write(self.format_procedure(proc))
                    f.write("\n")

            if functions:
                f.write("-- FUNCTIONS\n\n")
                for func in functions:
                    f.write(self.format_function(func))
                    f.write("\n")

            if triggers:
                f.write("-- TRIGGERS\n\n")
                for trigger in triggers:
                    f.write(self.format_trigger(trigger))
                    f.write("\n")

            if deferred_foreign_keys:
                f.write("-- DEFERRED FOREIGN KEYS (Circular Dependencies)\n\n")
                for fk in deferred_foreign_keys:
                    f.write(self.format_foreign_key(fk))
                    f.write("\n")

            if seed_data:
                f.write("-- SEED DATA\n\n")
                for stmt in seed_data:
                    f.write(stmt)
                    f.write("\n")

        logger.info(f"Single-file SQL script written to {path}")

    def write_per_object_format(
        self,
        schemas: List[SchemaInfo],
        tables: List[TableInfo],
        primary_keys: List[PrimaryKeyInfo],
        foreign_keys: List[ForeignKeyInfo],
        deferred_foreign_keys: List[ForeignKeyInfo],
        unique_constraints: List[UniqueConstraintInfo],
        check_constraints: List[CheckConstraintInfo],
        indexes: List[IndexInfo],
        views: List[Dict[str, Any]],
        procedures: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
        triggers: List[Dict[str, Any]],
        seed_data_by_table: Dict[str, List[str]]
    ) -> None:
        """Write each object to its own file, organized in subdirectories by type.

        Args:
            schemas: List of schemas
            tables: List of tables
            primary_keys: List of primary keys
            foreign_keys: List of foreign keys
            deferred_foreign_keys: List of deferred foreign keys
            unique_constraints: List of unique constraints
            check_constraints: List of check constraints
            indexes: List of indexes
            views: List of views
            procedures: List of procedures
            functions: List of functions
            triggers: List of triggers
            seed_data_by_table: Seed data INSERT statements keyed by "schema.table"
        """
        header = self.write_header()

        def write_object(subdir: str, filename: str, sql: str) -> None:
            dir_path = os.path.join(self.output_dir, subdir)
            os.makedirs(dir_path, exist_ok=True)
            with open(os.path.join(dir_path, f"{filename}.sql"), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write(sql)

        for schema in schemas:
            write_object('Schemas', schema.name, self.format_schema(schema))

        for table in tables:
            write_object('Tables', f"{table.schema_name}.{table.table_name}", self.format_table(table))

        for pk in primary_keys:
            write_object('Constraints', pk.constraint_name, self.format_primary_key(pk))

        for uq in unique_constraints:
            write_object('Constraints', uq.constraint_name, self.format_unique_constraint(uq))

        regular_fks = [fk for fk in foreign_keys if fk not in deferred_foreign_keys]
        for fk in regular_fks:
            write_object('Constraints', fk.constraint_name, self.format_foreign_key(fk))

        for check in check_constraints:
            write_object('Constraints', check.constraint_name, self.format_check_constraint(check))

        for idx in indexes:
            write_object('Indexes', idx.index_name, self.format_index(idx))

        for view in views:
            write_object('Views', f"{view['schema_name']}.{view['view_name']}", self.format_view(view))

        for proc in procedures:
            write_object('Procedures', f"{proc['schema_name']}.{proc['procedure_name']}", self.format_procedure(proc))

        for func in functions:
            write_object('Functions', f"{func['schema_name']}.{func['function_name']}", self.format_function(func))

        for trigger in triggers:
            write_object('Triggers', f"{trigger['schema_name']}.{trigger['table_name']}.{trigger['trigger_name']}", self.format_trigger(trigger))

        for fk in deferred_foreign_keys:
            write_object('Constraints', f"{fk.constraint_name}_DEFERRED", self.format_foreign_key(fk))

        for table_key, statements in seed_data_by_table.items():
            write_object('SeedData', table_key, '\n'.join(statements))

        logger.info(f"Per-object SQL scripts written to {self.output_dir}")

    def write_modular_format(
        self,
        schemas: List[SchemaInfo],
        tables: List[TableInfo],
        primary_keys: List[PrimaryKeyInfo],
        foreign_keys: List[ForeignKeyInfo],
        deferred_foreign_keys: List[ForeignKeyInfo],
        unique_constraints: List[UniqueConstraintInfo],
        check_constraints: List[CheckConstraintInfo],
        indexes: List[IndexInfo],
        views: List[Dict[str, Any]],
        procedures: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
        triggers: List[Dict[str, Any]],
        seed_data: List[str]
    ) -> None:
        """Write SQL scripts in modular format.

        Args:
            schemas: List of schemas
            tables: List of tables
            primary_keys: List of primary keys
            foreign_keys: List of foreign keys
            deferred_foreign_keys: List of deferred foreign keys
            unique_constraints: List of unique constraints
            check_constraints: List of check constraints
            indexes: List of indexes
            views: List of views
            procedures: List of procedures
            functions: List of functions
            triggers: List of triggers
            seed_data: List of seed data INSERT statements
        """
        header = self.write_header()
        written_files: List[str] = []

        # 01: Schemas
        if schemas:
            filename = '01_CREATE_SCHEMAS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- SCHEMAS\n\n")
                for schema in schemas:
                    f.write(self.format_schema(schema))
                    f.write("\n")
            written_files.append(filename)

        # 02: Tables
        if tables:
            filename = '02_CREATE_TABLES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- TABLES\n\n")
                for table in tables:
                    f.write(self.format_table(table))
                    f.write("\n")
            written_files.append(filename)

        # 03: Constraints (PK, FK, Unique, Check)
        if primary_keys or foreign_keys or unique_constraints or check_constraints:
            filename = '03_CREATE_CONSTRAINTS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)

                if primary_keys:
                    f.write("-- PRIMARY KEYS\n\n")
                    for pk in primary_keys:
                        f.write(self.format_primary_key(pk))
                        f.write("\n")

                if unique_constraints:
                    f.write("-- UNIQUE CONSTRAINTS\n\n")
                    for uq in unique_constraints:
                        f.write(self.format_unique_constraint(uq))
                        f.write("\n")

                # Regular foreign keys (not deferred)
                regular_fks = [fk for fk in foreign_keys if fk not in deferred_foreign_keys]
                if regular_fks:
                    f.write("-- FOREIGN KEYS\n\n")
                    for fk in regular_fks:
                        f.write(self.format_foreign_key(fk))
                        f.write("\n")

                if check_constraints:
                    f.write("-- CHECK CONSTRAINTS\n\n")
                    for check in check_constraints:
                        f.write(self.format_check_constraint(check))
                        f.write("\n")
            written_files.append(filename)

        # 04: Indexes
        if indexes:
            filename = '04_CREATE_INDEXES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- INDEXES\n\n")
                for idx in indexes:
                    f.write(self.format_index(idx))
                    f.write("\n")
            written_files.append(filename)

        # 05: Triggers
        if triggers:
            filename = '05_CREATE_TRIGGERS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- TRIGGERS\n\n")
                for trigger in triggers:
                    f.write(self.format_trigger(trigger))
                    f.write("\n")
            written_files.append(filename)

        # 06: Views
        if views:
            filename = '06_CREATE_VIEWS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- VIEWS\n\n")
                for view in views:
                    f.write(self.format_view(view))
                    f.write("\n")
            written_files.append(filename)

        # 07: Procedures
        if procedures:
            filename = '07_CREATE_PROCEDURES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- STORED PROCEDURES\n\n")
                for proc in procedures:
                    f.write(self.format_procedure(proc))
                    f.write("\n")
            written_files.append(filename)

        # 08: Functions
        if functions:
            filename = '08_CREATE_FUNCTIONS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- FUNCTIONS\n\n")
                for func in functions:
                    f.write(self.format_function(func))
                    f.write("\n")
            written_files.append(filename)

        # 09: Deferred foreign keys (for circular dependencies)
        if deferred_foreign_keys:
            filename = '09_CREATE_DEFERRED_FKS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- DEFERRED FOREIGN KEYS (Circular Dependencies)\n\n")
                for fk in deferred_foreign_keys:
                    f.write(self.format_foreign_key(fk))
                    f.write("\n")
            written_files.append(filename)

        # 10: Seed data
        if seed_data:
            filename = '10_SEED_DATA.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- SEED DATA\n\n")
                for stmt in seed_data:
                    f.write(stmt)
                    f.write("\n")
            written_files.append(filename)

        self._write_deploy_scripts(written_files)

        logger.info(f"Modular SQL scripts written to {self.output_dir}")

    def _write_deploy_scripts(self, sql_files: List[str]) -> None:
        """Write deploy.sh and deploy.ps1 scripts that run the given SQL files in order via sqlcmd.

        Args:
            sql_files: Modular SQL filenames, in the order they should be deployed
        """
        sh_lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            ': "${1:?Usage: deploy.sh <server> <database> [user] [password]}"',
            ': "${2:?Usage: deploy.sh <server> <database> [user] [password]}"',
            "SERVER=\"$1\"",
            "DATABASE=\"$2\"",
            "SQLUSER=\"${3:-}\"",
            "SQLPASSWORD=\"${4:-}\"",
            "",
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
            "",
            "FILES=(",
        ]
        sh_lines.extend(f'    "{name}"' for name in sql_files)
        sh_lines.extend([
            ")",
            "",
            'for f in "${FILES[@]}"; do',
            '    echo "Deploying $f..."',
            '    if [ -n "$SQLUSER" ]; then',
            '        sqlcmd -S "$SERVER" -d "$DATABASE" -U "$SQLUSER" -P "$SQLPASSWORD" -i "$SCRIPT_DIR/$f" -b',
            "    else",
            '        sqlcmd -S "$SERVER" -d "$DATABASE" -E -i "$SCRIPT_DIR/$f" -b',
            "    fi",
            "done",
            "",
        ])

        sh_path = os.path.join(self.output_dir, 'deploy.sh')
        with open(sh_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(sh_lines))
        try:
            os.chmod(sh_path, 0o755)
        except OSError:
            pass

        ps1_lines = [
            "param(",
            "    [Parameter(Mandatory = $true)][string]$Server,",
            "    [Parameter(Mandatory = $true)][string]$Database,",
            "    [string]$User,",
            "    [string]$Password",
            ")",
            "",
            "$ErrorActionPreference = 'Stop'",
            "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path",
            "",
            "$Files = @(",
        ]
        ps1_lines.extend(f"    '{name}'" for name in sql_files)
        ps1_lines.extend([
            ")",
            "",
            "foreach ($f in $Files) {",
            '    Write-Host "Deploying $f..."',
            "    $path = Join-Path $ScriptDir $f",
            "    if ($User) {",
            "        sqlcmd -S $Server -d $Database -U $User -P $Password -i $path -b",
            "    } else {",
            "        sqlcmd -S $Server -d $Database -E -i $path -b",
            "    }",
            "    if ($LASTEXITCODE -ne 0) { throw \"Deployment failed on $f\" }",
            "}",
            "",
        ])

        ps1_path = os.path.join(self.output_dir, 'deploy.ps1')
        with open(ps1_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(ps1_lines))

        logger.info(f"Deployment scripts written to {self.output_dir}")

    def write_readme(
        self,
        output_format: str,
        schemas: List[SchemaInfo],
        tables: List[TableInfo],
        views: List[Dict[str, Any]],
        procedures: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
        triggers: List[Dict[str, Any]],
        indexes: List[IndexInfo],
        deferred_foreign_keys: List[ForeignKeyInfo],
        has_seed_data: bool
    ) -> None:
        """Generate a README.md summarizing the extracted schema.

        Args:
            output_format: 'single', 'per-object', or 'modular'
            schemas: List of schemas
            tables: List of tables (in dependency order)
            views: List of views (in dependency order)
            procedures: List of procedures
            functions: List of functions
            triggers: List of triggers
            indexes: List of indexes
            deferred_foreign_keys: Foreign keys deferred due to circular dependencies
            has_seed_data: Whether seed data was extracted
        """
        lines = ["# Database Schema Export", ""]

        if not self.omit_ts:
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")

        lines.append("## Objects")
        lines.append("")
        lines.append(f"- Schemas: {len(schemas)}")
        lines.append(f"- Tables: {len(tables)}")
        lines.append(f"- Indexes: {len(indexes)}")
        lines.append(f"- Views: {len(views)}")
        lines.append(f"- Stored Procedures: {len(procedures)}")
        lines.append(f"- Functions: {len(functions)}")
        lines.append(f"- Triggers: {len(triggers)}")
        lines.append("")

        def list_section(title: str, items: List[Any], name_fn) -> None:
            if not items:
                return
            lines.append(f"### {title}")
            lines.append("")
            for item in items:
                lines.append(f"- {name_fn(item)}")
            lines.append("")

        list_section("Tables", tables, lambda t: f"{t.schema_name}.{t.table_name}")
        list_section("Views", views, lambda v: f"{v['schema_name']}.{v['view_name']}")
        list_section("Stored Procedures", procedures, lambda p: f"{p['schema_name']}.{p['procedure_name']}")
        list_section("Functions", functions, lambda fn: f"{fn['schema_name']}.{fn['function_name']}")
        list_section("Triggers", triggers, lambda t: f"{t['schema_name']}.{t['table_name']}.{t['trigger_name']}")

        lines.append("## Dependencies")
        lines.append("")
        lines.append("- Tables are ordered by foreign key dependency (a referenced table is created before the table that references it).")
        if deferred_foreign_keys:
            lines.append(
                f"- {len(deferred_foreign_keys)} foreign key(s) form a circular dependency and are added "
                "after all tables are created, rather than inline with the table's other foreign keys."
            )
        lines.append("- Views are ordered so a view referenced by another view is created first.")
        lines.append("")

        lines.append("## Deployment")
        lines.append("")
        if output_format == 'modular':
            lines.append(
                "Run the numbered `.sql` files in order (01, 02, 03, ...), or use the generated "
                "`deploy.sh` (Linux/macOS) or `deploy.ps1` (Windows) script, which runs them in order via `sqlcmd`:"
            )
            lines.append("")
            lines.append("```")
            lines.append("./deploy.sh <server> <database> [user] [password]")
            lines.append(".\\deploy.ps1 -Server <server> -Database <database> [-User <user> -Password <password>]")
            lines.append("```")
            lines.append("")
            lines.append("Omit user/password to connect with Windows/trusted authentication.")
        elif output_format == 'single':
            lines.append(
                "Run `schema.sql` against the target database (e.g. with `sqlcmd` or SQL Server Management Studio). "
                "Objects are already ordered by dependency within the file."
            )
        else:
            lines.append(
                "Objects are organized into subdirectories by type (Tables/, Constraints/, Indexes/, Triggers/, "
                "Views/, Procedures/, Functions/, SeedData/). Deploy the subdirectories in that order; there is no "
                "single combined script for this format."
            )
        lines.append("")

        if has_seed_data:
            lines.append("Seed data is included and should be applied after all schema objects are created.")
            lines.append("")

        path = os.path.join(self.output_dir, 'README.md')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(f"README written to {path}")
