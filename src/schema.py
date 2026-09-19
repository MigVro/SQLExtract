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
