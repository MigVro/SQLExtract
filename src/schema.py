"""Schema introspection and metadata extraction."""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from .connection import DatabaseConnection
from .utils import get_logger

logger = get_logger(__name__)


@dataclass
class SchemaInfo:
    """Schema metadata."""
    name: str
    owner: str = "dbo"


@dataclass
class ColumnInfo:
    """Column metadata."""
    name: str
    data_type: str
    max_length: Optional[int]
    precision: Optional[int]
    scale: Optional[int]
    is_nullable: bool
    is_identity: bool
    is_computed: bool
    default_value: Optional[str]
    computed_definition: Optional[str]


@dataclass
class TableInfo:
    """Table metadata."""
    schema_name: str
    table_name: str
    columns: List[ColumnInfo]


class SchemaReader:
    """Read schema metadata from database."""

    def __init__(self, connection: DatabaseConnection):
        """Initialize schema reader.

        Args:
            connection: Database connection
        """
        self.connection = connection

    def get_schemas(self, schema_filter: Optional[List[str]] = None) -> List[SchemaInfo]:
        """Get all schemas from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of schema information
        """
        query = """
        SELECT
            s.name AS schema_name,
            USER_NAME(s.principal_id) AS owner
        FROM sys.schemas s
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner', 'db_accessadmin',
                              'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                              'db_datareader', 'db_datawriter', 'db_denydatareader',
                              'db_denydatawriter')
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        schemas = []
        for row in results:
            schemas.append(SchemaInfo(name=row.schema_name, owner=row.owner or 'dbo'))

        logger.info(f"Found {len(schemas)} schemas")
        return schemas

    def get_tables(self, schema_filter: Optional[List[str]] = None) -> List[TableInfo]:
        """Get all tables from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of table information
        """
        query = """
        SELECT
            s.name AS schema_name,
            t.name AS table_name
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        tables = []
        for row in results:
            columns = self.get_table_columns(row.schema_name, row.table_name)
            tables.append(TableInfo(
                schema_name=row.schema_name,
                table_name=row.table_name,
                columns=columns
            ))

        logger.info(f"Found {len(tables)} tables")
        return tables

    def get_table_columns(self, schema_name: str, table_name: str) -> List[ColumnInfo]:
        """Get columns for a specific table.

        Args:
            schema_name: Schema name
            table_name: Table name

        Returns:
            List of column information
        """
        query = """
        SELECT
            c.name AS column_name,
            TYPE_NAME(c.user_type_id) AS data_type,
            c.max_length,
            c.precision,
            c.scale,
            c.is_nullable,
            c.is_identity,
            c.is_computed,
            dc.definition AS default_value,
            cc.definition AS computed_definition
        FROM sys.columns c
        INNER JOIN sys.tables t ON c.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        LEFT JOIN sys.computed_columns cc ON c.object_id = cc.object_id AND c.column_id = cc.column_id
        WHERE s.name = ? AND t.name = ?
        ORDER BY c.column_id
        """

        results = self.connection.fetch_all(query, (schema_name, table_name))

        columns = []
        for row in results:
            # Adjust max_length for unicode types
            max_length = row.max_length
            if row.data_type in ('nvarchar', 'nchar'):
                max_length = max_length // 2 if max_length > 0 else max_length

            columns.append(ColumnInfo(
                name=row.column_name,
                data_type=row.data_type,
                max_length=max_length if max_length >= 0 else None,
                precision=row.precision if row.precision > 0 else None,
                scale=row.scale if row.scale > 0 else None,
                is_nullable=row.is_nullable,
                is_identity=row.is_identity,
                is_computed=row.is_computed,
                default_value=row.default_value,
                computed_definition=row.computed_definition
            ))

        return columns

    def get_sequences(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all sequences from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of sequence information dictionaries
        """
        query = """
        SELECT
            s.name AS schema_name,
            seq.name AS sequence_name,
            TYPE_NAME(seq.system_type_id) AS data_type,
            seq.precision,
            seq.scale,
            seq.start_value,
            seq.increment,
            seq.minimum_value,
            seq.maximum_value,
            seq.is_cycling,
            seq.is_cached,
            seq.cache_size
        FROM sys.sequences seq
        INNER JOIN sys.schemas s ON seq.schema_id = s.schema_id
        WHERE seq.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        sequences = [
            {
                'schema_name': row.schema_name,
                'sequence_name': row.sequence_name,
                'data_type': row.data_type,
                'precision': row.precision,
                'scale': row.scale,
                'start_value': row.start_value,
                'increment': row.increment,
                'minimum_value': row.minimum_value,
                'maximum_value': row.maximum_value,
                'is_cycling': bool(row.is_cycling),
                'is_cached': bool(row.is_cached),
                'cache_size': row.cache_size
            }
            for row in results
        ]

        logger.info(f"Found {len(sequences)} sequences")
        return sequences

    def get_views(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all views from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of view information
        """
        query = """
        SELECT
            s.name AS schema_name,
            v.name AS view_name,
            m.definition AS definition
        FROM sys.views v
        INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON v.object_id = m.object_id
        WHERE v.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        views = []
        for row in results:
            if row.definition is None:
                logger.warning(f"View {row.schema_name}.{row.view_name} is encrypted - skipping")
                continue

            views.append({
                'schema_name': row.schema_name,
                'view_name': row.view_name,
                'definition': row.definition.replace('\r\n', '\n')
            })

        logger.info(f"Found {len(views)} views")
        return views

    def get_view_dependencies(self, schema_filter: Optional[List[str]] = None) -> List[Tuple[str, str, str, str]]:
        """Get view-to-view dependencies (views referenced by other views).

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of (schema_name, view_name, referenced_schema_name, referenced_view_name) tuples
        """
        query = """
        SELECT
            s1.name AS schema_name,
            o1.name AS view_name,
            s2.name AS referenced_schema_name,
            o2.name AS referenced_view_name
        FROM sys.sql_expression_dependencies d
        INNER JOIN sys.objects o1 ON d.referencing_id = o1.object_id
        INNER JOIN sys.schemas s1 ON o1.schema_id = s1.schema_id
        INNER JOIN sys.objects o2 ON d.referenced_id = o2.object_id
        INNER JOIN sys.schemas s2 ON o2.schema_id = s2.schema_id
        WHERE o1.type = 'V' AND o2.type = 'V' AND o1.object_id <> o2.object_id
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s1.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        dependencies = [
            (row.schema_name, row.view_name, row.referenced_schema_name, row.referenced_view_name)
            for row in results
        ]

        logger.info(f"Found {len(dependencies)} view-to-view dependencies")
        return dependencies

    def get_triggers(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all DML triggers on tables (AFTER and INSTEAD OF).

        Database-level DDL triggers are out of scope.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of trigger information dictionaries
        """
        query = """
        SELECT
            s.name AS schema_name,
            t.name AS table_name,
            tr.name AS trigger_name,
            tr.is_instead_of_trigger,
            tr.is_disabled,
            te.type_desc AS event_type,
            m.definition AS definition
        FROM sys.triggers tr
        INNER JOIN sys.tables t ON tr.parent_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.trigger_events te ON tr.object_id = te.object_id
        LEFT JOIN sys.sql_modules m ON tr.object_id = m.object_id
        WHERE tr.is_ms_shipped = 0 AND tr.parent_class = 1
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name, tr.name"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name, tr.name"
            results = self.connection.fetch_all(query)

        trigger_dict: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        skipped_encrypted: set = set()

        for row in results:
            key = (row.schema_name, row.table_name, row.trigger_name)
            if key in skipped_encrypted:
                continue

            if key not in trigger_dict:
                if row.definition is None:
                    logger.warning(f"Trigger {row.schema_name}.{row.table_name}.{row.trigger_name} is encrypted - skipping")
                    skipped_encrypted.add(key)
                    continue

                trigger_dict[key] = {
                    'schema_name': row.schema_name,
                    'table_name': row.table_name,
                    'trigger_name': row.trigger_name,
                    'is_instead_of': bool(row.is_instead_of_trigger),
                    'is_disabled': bool(row.is_disabled),
                    'events': [],
                    'definition': row.definition.replace('\r\n', '\n')
                }

            if row.event_type not in trigger_dict[key]['events']:
                trigger_dict[key]['events'].append(row.event_type)

        triggers = list(trigger_dict.values())
        logger.info(f"Found {len(triggers)} triggers")
        return triggers

    def get_extended_properties(self, schema_filter: Optional[List[str]] = None) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Get MS_Description extended properties (descriptions) for tables and columns.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            Dict keyed by (schema_name, table_name), each value a dict with
            'table_description' (Optional[str]) and 'columns' (Dict[str, str]
            mapping column name to description)
        """
        query = """
        SELECT
            s.name AS schema_name,
            t.name AS table_name,
            c.name AS column_name,
            CAST(ep.value AS nvarchar(max)) AS description
        FROM sys.extended_properties ep
        INNER JOIN sys.tables t ON ep.major_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.columns c ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
        WHERE ep.class = 1 AND ep.name = 'MS_Description' AND t.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        properties: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in results:
            key = (row.schema_name, row.table_name)
            entry = properties.setdefault(key, {'table_description': None, 'columns': {}})
            if row.column_name is None:
                entry['table_description'] = row.description
            else:
                entry['columns'][row.column_name] = row.description

        count = sum(
            (1 if v['table_description'] else 0) + len(v['columns'])
            for v in properties.values()
        )
        logger.info(f"Found {count} extended properties (descriptions)")
        return properties

    def get_user_defined_types(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all user-defined types: alias types, table types, and CLR types (metadata only).

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of user-defined type information dictionaries, each tagged with 'kind'
            ('alias', 'table', or 'clr'). Ordered alias types first, then table types
            (which may reference alias types as column data types), then CLR types.
        """
        types: List[Dict[str, Any]] = []
        types.extend(self._get_alias_types(schema_filter))
        types.extend(self._get_table_types(schema_filter))
        types.extend(self._get_clr_types(schema_filter))

        logger.info(f"Found {len(types)} user-defined types")
        return types

    def _get_alias_types(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get alias types (CREATE TYPE ... FROM <base type>)."""
        query = """
        SELECT
            s.name AS schema_name,
            t.name AS type_name,
            TYPE_NAME(t.system_type_id) AS base_type,
            t.max_length,
            t.precision,
            t.scale,
            t.is_nullable
        FROM sys.types t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.is_user_defined = 1 AND t.is_table_type = 0 AND t.is_assembly_type = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        alias_types = []
        for row in results:
            max_length = row.max_length
            if row.base_type in ('nvarchar', 'nchar'):
                max_length = max_length // 2 if max_length > 0 else max_length

            alias_types.append({
                'kind': 'alias',
                'schema_name': row.schema_name,
                'type_name': row.type_name,
                'base_type': row.base_type,
                'max_length': max_length if max_length >= 0 else None,
                'precision': row.precision if row.precision > 0 else None,
                'scale': row.scale if row.scale > 0 else None,
                'is_nullable': bool(row.is_nullable)
            })

        return alias_types

    def _get_table_types(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get table types (CREATE TYPE ... AS TABLE (...))."""
        query = """
        SELECT
            s.name AS schema_name,
            tt.name AS type_name,
            tt.type_table_object_id
        FROM sys.table_types tt
        INNER JOIN sys.schemas s ON tt.schema_id = s.schema_id
        WHERE tt.is_user_defined = 1
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        table_types = []
        for row in results:
            table_types.append({
                'kind': 'table',
                'schema_name': row.schema_name,
                'type_name': row.type_name,
                'columns': self._get_table_type_columns(row.type_table_object_id),
                'primary_key_columns': self._get_table_type_primary_key(row.type_table_object_id)
            })

        return table_types

    def _get_table_type_columns(self, object_id: int) -> List[ColumnInfo]:
        """Get columns for a table type by its type_table_object_id."""
        query = """
        SELECT
            c.name AS column_name,
            TYPE_NAME(c.user_type_id) AS data_type,
            c.max_length,
            c.precision,
            c.scale,
            c.is_nullable,
            c.is_identity,
            c.is_computed,
            dc.definition AS default_value,
            cc.definition AS computed_definition
        FROM sys.columns c
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        LEFT JOIN sys.computed_columns cc ON c.object_id = cc.object_id AND c.column_id = cc.column_id
        WHERE c.object_id = ?
        ORDER BY c.column_id
        """

        results = self.connection.fetch_all(query, (object_id,))

        columns = []
        for row in results:
            max_length = row.max_length
            if row.data_type in ('nvarchar', 'nchar'):
                max_length = max_length // 2 if max_length > 0 else max_length

            columns.append(ColumnInfo(
                name=row.column_name,
                data_type=row.data_type,
                max_length=max_length if max_length >= 0 else None,
                precision=row.precision if row.precision > 0 else None,
                scale=row.scale if row.scale > 0 else None,
                is_nullable=row.is_nullable,
                is_identity=row.is_identity,
                is_computed=row.is_computed,
                default_value=row.default_value,
                computed_definition=row.computed_definition
            ))

        return columns

    def _get_table_type_primary_key(self, object_id: int) -> List[str]:
        """Get primary key column names for a table type, in key order."""
        query = """
        SELECT c.name AS column_name
        FROM sys.indexes i
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        WHERE i.object_id = ? AND i.is_primary_key = 1
        ORDER BY ic.key_ordinal
        """

        results = self.connection.fetch_all(query, (object_id,))
        return [row.column_name for row in results]

    def _get_clr_types(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get CLR (assembly-based) types. Metadata only - not enough to regenerate the
        assembly itself, so no CREATE TYPE statement is produced for these.
        """
        query = """
        SELECT
            s.name AS schema_name,
            t.name AS type_name,
            a.name AS assembly_name,
            at.assembly_class AS class_name
        FROM sys.types t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.assembly_types at ON t.user_type_id = at.user_type_id
        INNER JOIN sys.assemblies a ON at.assembly_id = a.assembly_id
        WHERE t.is_assembly_type = 1
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        return [
            {
                'kind': 'clr',
                'schema_name': row.schema_name,
                'type_name': row.type_name,
                'assembly_name': row.assembly_name,
                'class_name': row.class_name
            }
            for row in results
        ]

    def get_stored_procedures(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all stored procedures from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of stored procedure information
        """
        query = """
        SELECT
            s.name AS schema_name,
            p.name AS procedure_name,
            m.definition AS definition
        FROM sys.procedures p
        INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON p.object_id = m.object_id
        WHERE p.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        procedures = []
        for row in results:
            if row.definition is None:
                logger.warning(f"Procedure {row.schema_name}.{row.procedure_name} is encrypted - skipping")
                continue

            procedures.append({
                'schema_name': row.schema_name,
                'procedure_name': row.procedure_name,
                'definition': row.definition.replace('\r\n', '\n')
            })

        logger.info(f"Found {len(procedures)} stored procedures")
        return procedures

    def get_functions(self, schema_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all functions from database.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of function information
        """
        query = """
        SELECT
            s.name AS schema_name,
            o.name AS function_name,
            o.type_desc AS function_type,
            m.definition AS definition
        FROM sys.objects o
        INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
        WHERE o.type IN ('FN', 'IF', 'TF') AND o.is_ms_shipped = 0
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            results = self.connection.fetch_all(query)

        functions = []
        for row in results:
            if row.definition is None:
                logger.warning(f"Function {row.schema_name}.{row.function_name} is encrypted - skipping")
                continue

            functions.append({
                'schema_name': row.schema_name,
                'function_name': row.function_name,
                'function_type': row.function_type,
                'definition': row.definition.replace('\r\n', '\n')
            })

        logger.info(f"Found {len(functions)} functions")
        return functions
