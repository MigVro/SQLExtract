"""SQL script formatter and generator."""

import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .schema import SchemaInfo, TableInfo, ColumnInfo
from .constraints import PrimaryKeyInfo, ForeignKeyInfo, UniqueConstraintInfo, CheckConstraintInfo
from .indexes import IndexInfo
from .utils import get_logger, escape_sql_identifier, escape_sql_string, OutputError

logger = get_logger(__name__)


class SQLFormatter:
    """Format and generate SQL scripts."""

    def __init__(self, output_dir: str, omit_ts: bool = False, no_header: bool = False, trust_cert: bool = False):
        """Initialize SQL formatter.

        Args:
            output_dir: Output directory path
            omit_ts: Omit the generation timestamp from output headers
            no_header: Omit the header comment block from output files entirely
            trust_cert: Whether the generated deploy scripts should pass sqlcmd's
                TrustServerCertificate flag (-C), matching the connection used to extract
        """
        self.output_dir = output_dir
        self.omit_ts = omit_ts
        self.no_header = no_header
        self.trust_cert = trust_cert
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

    def format_sequence(self, seq: Dict[str, Any]) -> str:
        """Generate CREATE SEQUENCE statement.

        Args:
            seq: Sequence information dictionary

        Returns:
            SQL statement
        """
        data_type = seq['data_type']

        if data_type in ('decimal', 'numeric') and seq.get('precision') and seq.get('scale') is not None:
            type_clause = f" AS {data_type}({seq['precision']},{seq['scale']})"
        elif data_type != 'bigint':
            type_clause = f" AS {data_type}"
        else:
            type_clause = ""

        cycle_clause = "CYCLE" if seq['is_cycling'] else "NO CYCLE"
        cache_clause = f"CACHE {seq['cache_size']}" if seq['is_cached'] else "NO CACHE"

        return f"""
CREATE SEQUENCE {escape_sql_identifier(seq['schema_name'])}.{escape_sql_identifier(seq['sequence_name'])}{type_clause}
START WITH {seq['start_value']}
INCREMENT BY {seq['increment']}
MINVALUE {seq['minimum_value']}
MAXVALUE {seq['maximum_value']}
{cycle_clause}
{cache_clause}
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
        lines.append(',\n'.join(self._format_column_def(col) for col in table.columns))
        lines.append(")")
        lines.append("GO")

        return '\n'.join(lines)

    def _format_column_def(self, col: ColumnInfo) -> str:
        """Format a single column definition line for a CREATE TABLE/TYPE statement.

        Args:
            col: Column information

        Returns:
            Column definition, indented with 4 spaces
        """
        if col.is_computed:
            col_def = f"    {escape_sql_identifier(col.name)} AS {col.computed_definition}"
            if col.is_persisted:
                col_def += " PERSISTED"
            return col_def

        col_def = f"    {escape_sql_identifier(col.name)} {self._format_data_type(col.data_type, col.max_length, col.precision, col.scale)}"

        if col.is_identity:
            col_def += " IDENTITY(1,1)"

        col_def += " NULL" if col.is_nullable else " NOT NULL"

        if col.default_value:
            col_def += f" DEFAULT {col.default_value}"

        return col_def

    def format_user_defined_type(self, udt: Dict[str, Any]) -> str:
        """Generate a CREATE TYPE statement (or, for CLR types, a metadata comment).

        Args:
            udt: User-defined type information, as returned by
                SchemaReader.get_user_defined_types() (tagged with 'kind')

        Returns:
            SQL statement
        """
        if udt['kind'] == 'alias':
            return self._format_alias_type(udt)
        elif udt['kind'] == 'table':
            return self._format_table_type(udt)
        else:
            return self._format_clr_type_comment(udt)

    def _format_alias_type(self, udt: Dict[str, Any]) -> str:
        """Generate CREATE TYPE ... FROM <base type> statement for an alias type."""
        type_suffix = self._format_data_type(udt['base_type'], udt['max_length'], udt['precision'], udt['scale'])
        null_clause = "NULL" if udt['is_nullable'] else "NOT NULL"

        return f"""
CREATE TYPE {escape_sql_identifier(udt['schema_name'])}.{escape_sql_identifier(udt['type_name'])}
FROM {type_suffix} {null_clause}
GO
"""

    def _format_table_type(self, udt: Dict[str, Any]) -> str:
        """Generate CREATE TYPE ... AS TABLE statement for a table type."""
        lines = [f"CREATE TYPE {escape_sql_identifier(udt['schema_name'])}.{escape_sql_identifier(udt['type_name'])} AS TABLE ("]

        column_defs = [self._format_column_def(col) for col in udt['columns']]

        if udt['primary_key_columns']:
            pk_columns = ', '.join(escape_sql_identifier(c) for c in udt['primary_key_columns'])
            column_defs.append(f"    PRIMARY KEY ({pk_columns})")

        lines.append(',\n'.join(column_defs))
        lines.append(")")
        lines.append("GO")

        return '\n'.join(lines)

    def _format_clr_type_comment(self, udt: Dict[str, Any]) -> str:
        """Generate a metadata comment for a CLR type (not enough info to recreate the assembly)."""
        return (
            f"-- CLR type {udt['schema_name']}.{udt['type_name']} "
            f"(assembly '{udt['assembly_name']}', class '{udt['class_name']}') - metadata only; "
            "deploy the assembly and run CREATE TYPE ... EXTERNAL NAME manually.\n"
        )

    def format_extended_properties(self, schema_name: str, table_name: str, properties: Dict[str, Any]) -> str:
        """Generate sp_addextendedproperty statements for a table's MS_Description properties.

        Args:
            schema_name: Table's schema name
            table_name: Table name
            properties: Dict with 'table_description' (Optional[str]) and 'columns'
                (Dict[str, str]), as returned by SchemaReader.get_extended_properties()

        Returns:
            SQL statements, or an empty string if the table has no descriptions
        """
        statements = []

        table_description = properties.get('table_description')
        if table_description:
            statements.append(
                "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
                f"@value=N'{escape_sql_string(table_description)}', "
                f"@level0type=N'SCHEMA', @level0name=N'{schema_name}', "
                f"@level1type=N'TABLE', @level1name=N'{table_name}'\nGO\n"
            )

        for column_name, description in properties.get('columns', {}).items():
            if not description:
                continue
            statements.append(
                "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
                f"@value=N'{escape_sql_string(description)}', "
                f"@level0type=N'SCHEMA', @level0name=N'{schema_name}', "
                f"@level1type=N'TABLE', @level1name=N'{table_name}', "
                f"@level2type=N'COLUMN', @level2name=N'{column_name}'\nGO\n"
            )

        return '\n'.join(statements)

    def _format_data_type(
        self,
        data_type: str,
        max_length: Optional[int],
        precision: Optional[int],
        scale: Optional[int]
    ) -> str:
        """Format a data type with its length/precision/scale suffix.

        Args:
            data_type: Base data type name
            max_length: Max length (for character/binary types)
            precision: Precision (for decimal/numeric types)
            scale: Scale (for decimal/numeric/datetime2/time/datetimeoffset types)

        Returns:
            Formatted data type string
        """
        if data_type in ('varchar', 'nvarchar', 'char', 'nchar', 'varbinary', 'binary'):
            if max_length == -1:
                return f"{data_type}(MAX)"
            elif max_length:
                return f"{data_type}({max_length})"
            else:
                return data_type

        elif data_type in ('decimal', 'numeric'):
            if precision and scale is not None:
                return f"{data_type}({precision},{scale})"
            elif precision:
                return f"{data_type}({precision})"
            else:
                return data_type

        elif data_type in ('datetime2', 'time', 'datetimeoffset'):
            if scale is not None:
                return f"{data_type}({scale})"
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
        # Definition already includes CREATE VIEW (captured as-is via sys.sql_modules)
        return view['definition'] + "\nGO\n"

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
        user_defined_types: List[Dict[str, Any]],
        sequences: List[Dict[str, Any]],
        tables: List[TableInfo],
        extended_properties: Dict[Tuple[str, str], Dict[str, Any]],
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
            user_defined_types: List of user-defined types (alias, table, CLR)
            sequences: List of sequences
            tables: List of tables
            extended_properties: Table/column descriptions keyed by (schema_name, table_name)
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

            if user_defined_types:
                f.write("-- USER-DEFINED TYPES\n\n")
                for udt in user_defined_types:
                    f.write(self.format_user_defined_type(udt))
                    f.write("\n")

            if sequences:
                f.write("-- SEQUENCES\n\n")
                for seq in sequences:
                    f.write(self.format_sequence(seq))
                    f.write("\n")

            if tables:
                f.write("-- TABLES\n\n")
                for table in tables:
                    f.write(self.format_table(table))
                    f.write("\n")
                    props = extended_properties.get((table.schema_name, table.table_name))
                    if props:
                        f.write(self.format_extended_properties(table.schema_name, table.table_name, props))
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
        user_defined_types: List[Dict[str, Any]],
        sequences: List[Dict[str, Any]],
        tables: List[TableInfo],
        extended_properties: Dict[Tuple[str, str], Dict[str, Any]],
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
            user_defined_types: List of user-defined types (alias, table, CLR)
            sequences: List of sequences
            tables: List of tables
            extended_properties: Table/column descriptions keyed by (schema_name, table_name)
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

        for udt in user_defined_types:
            write_object('Types', f"{udt['schema_name']}.{udt['type_name']}", self.format_user_defined_type(udt))

        for seq in sequences:
            write_object('Sequences', f"{seq['schema_name']}.{seq['sequence_name']}", self.format_sequence(seq))

        for table in tables:
            table_sql = self.format_table(table)
            props = extended_properties.get((table.schema_name, table.table_name))
            if props:
                table_sql += "\n" + self.format_extended_properties(table.schema_name, table.table_name, props)
            write_object('Tables', f"{table.schema_name}.{table.table_name}", table_sql)

        # Split by constraint type into separately-numbered subfolders, so a plain
        # alphabetical deploy of Constraints/ doesn't run a foreign key before the
        # primary/unique key it references.
        for pk in primary_keys:
            write_object('Constraints/01_PrimaryKeys', pk.constraint_name, self.format_primary_key(pk))

        for uq in unique_constraints:
            write_object('Constraints/02_UniqueConstraints', uq.constraint_name, self.format_unique_constraint(uq))

        regular_fks = [fk for fk in foreign_keys if fk not in deferred_foreign_keys]
        for fk in regular_fks:
            write_object('Constraints/03_ForeignKeys', fk.constraint_name, self.format_foreign_key(fk))

        for check in check_constraints:
            write_object('Constraints/04_CheckConstraints', check.constraint_name, self.format_check_constraint(check))

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
            write_object('Constraints/03_ForeignKeys', f"{fk.constraint_name}_DEFERRED", self.format_foreign_key(fk))

        for table_key, statements in seed_data_by_table.items():
            write_object('SeedData', table_key, '\n'.join(statements))

        logger.info(f"Per-object SQL scripts written to {self.output_dir}")

    def write_modular_format(
        self,
        schemas: List[SchemaInfo],
        user_defined_types: List[Dict[str, Any]],
        sequences: List[Dict[str, Any]],
        tables: List[TableInfo],
        extended_properties: Dict[Tuple[str, str], Dict[str, Any]],
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
            user_defined_types: List of user-defined types (alias, table, CLR)
            sequences: List of sequences
            tables: List of tables
            extended_properties: Table/column descriptions keyed by (schema_name, table_name)
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

        # 02: User-defined types
        if user_defined_types:
            filename = '02_CREATE_TYPES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- USER-DEFINED TYPES\n\n")
                for udt in user_defined_types:
                    f.write(self.format_user_defined_type(udt))
                    f.write("\n")
            written_files.append(filename)

        # 03: Sequences
        if sequences:
            filename = '03_CREATE_SEQUENCES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- SEQUENCES\n\n")
                for seq in sequences:
                    f.write(self.format_sequence(seq))
                    f.write("\n")
            written_files.append(filename)

        # 04: Tables
        if tables:
            filename = '04_CREATE_TABLES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- TABLES\n\n")
                for table in tables:
                    f.write(self.format_table(table))
                    f.write("\n")
                    props = extended_properties.get((table.schema_name, table.table_name))
                    if props:
                        f.write(self.format_extended_properties(table.schema_name, table.table_name, props))
                        f.write("\n")
            written_files.append(filename)

        # 05: Constraints (PK, FK, Unique, Check)
        if primary_keys or foreign_keys or unique_constraints or check_constraints:
            filename = '05_CREATE_CONSTRAINTS.sql'
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

        # 06: Indexes
        if indexes:
            filename = '06_CREATE_INDEXES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- INDEXES\n\n")
                for idx in indexes:
                    f.write(self.format_index(idx))
                    f.write("\n")
            written_files.append(filename)

        # 07: Triggers
        if triggers:
            filename = '07_CREATE_TRIGGERS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- TRIGGERS\n\n")
                for trigger in triggers:
                    f.write(self.format_trigger(trigger))
                    f.write("\n")
            written_files.append(filename)

        # 08: Views
        if views:
            filename = '08_CREATE_VIEWS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- VIEWS\n\n")
                for view in views:
                    f.write(self.format_view(view))
                    f.write("\n")
            written_files.append(filename)

        # 09: Procedures
        if procedures:
            filename = '09_CREATE_PROCEDURES.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- STORED PROCEDURES\n\n")
                for proc in procedures:
                    f.write(self.format_procedure(proc))
                    f.write("\n")
            written_files.append(filename)

        # 10: Functions
        if functions:
            filename = '10_CREATE_FUNCTIONS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- FUNCTIONS\n\n")
                for func in functions:
                    f.write(self.format_function(func))
                    f.write("\n")
            written_files.append(filename)

        # 11: Deferred foreign keys (for circular dependencies)
        if deferred_foreign_keys:
            filename = '11_CREATE_DEFERRED_FKS.sql'
            with open(os.path.join(self.output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("-- DEFERRED FOREIGN KEYS (Circular Dependencies)\n\n")
                for fk in deferred_foreign_keys:
                    f.write(self.format_foreign_key(fk))
                    f.write("\n")
            written_files.append(filename)

        # 12: Seed data
        if seed_data:
            filename = '12_SEED_DATA.sql'
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
        trust_cert_flag = " -C" if self.trust_cert else ""
        sh_lines.extend([
            ")",
            "",
            'for f in "${FILES[@]}"; do',
            '    echo "Deploying $f..."',
            '    if [ -n "$SQLUSER" ]; then',
            f'        sqlcmd -S "$SERVER" -d "$DATABASE" -U "$SQLUSER" -P "$SQLPASSWORD"{trust_cert_flag} -i "$SCRIPT_DIR/$f" -b',
            "    else",
            f'        sqlcmd -S "$SERVER" -d "$DATABASE" -E{trust_cert_flag} -i "$SCRIPT_DIR/$f" -b',
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
            f"        sqlcmd -S $Server -d $Database -U $User -P $Password{trust_cert_flag} -i $path -b",
            "    } else {",
            f"        sqlcmd -S $Server -d $Database -E{trust_cert_flag} -i $path -b",
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
        user_defined_types: List[Dict[str, Any]],
        sequences: List[Dict[str, Any]],
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
            user_defined_types: List of user-defined types (alias, table, CLR)
            sequences: List of sequences
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
        lines.append(f"- User-Defined Types: {len(user_defined_types)}")
        lines.append(f"- Sequences: {len(sequences)}")
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

        list_section("User-Defined Types", user_defined_types, lambda u: f"{u['schema_name']}.{u['type_name']} ({u['kind']})")
        list_section("Sequences", sequences, lambda s: f"{s['schema_name']}.{s['sequence_name']}")
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
                "Objects are organized into subdirectories by type. Deploy them in this order (there is no single "
                "combined script for this format): `Schemas/`, `Types/`, `Sequences/`, `Tables/`, "
                "`Constraints/01_PrimaryKeys/`, `Constraints/02_UniqueConstraints/`, `Constraints/03_ForeignKeys/`, "
                "`Constraints/04_CheckConstraints/`, `Indexes/`, `Views/`, `Procedures/`, `Functions/`, `Triggers/`, "
                "`SeedData/`."
            )
        lines.append("")

        if has_seed_data:
            lines.append("Seed data is included and should be applied after all schema objects are created.")
            lines.append("")

        path = os.path.join(self.output_dir, 'README.md')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(f"README written to {path}")
