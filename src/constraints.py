"""Constraint extraction module."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .connection import DatabaseConnection
from .utils import get_logger

logger = get_logger(__name__)


@dataclass
class PrimaryKeyInfo:
    """Primary key metadata."""
    constraint_name: str
    schema_name: str
    table_name: str
    columns: List[str]
    is_clustered: bool


@dataclass
class ForeignKeyInfo:
    """Foreign key metadata."""
    constraint_name: str
    schema_name: str
    table_name: str
    columns: List[str]
    referenced_schema: str
    referenced_table: str
    referenced_columns: List[str]
    delete_action: str
    update_action: str


@dataclass
class UniqueConstraintInfo:
    """Unique constraint metadata."""
    constraint_name: str
    schema_name: str
    table_name: str
    columns: List[str]


@dataclass
class CheckConstraintInfo:
    """Check constraint metadata."""
    constraint_name: str
    schema_name: str
    table_name: str
    definition: str
    is_disabled: bool


class ConstraintExtractor:
    """Extract constraints from database."""

    def __init__(self, connection: DatabaseConnection):
        """Initialize constraint extractor.

        Args:
            connection: Database connection
        """
        self.connection = connection

    def get_primary_keys(self, schema_filter: Optional[List[str]] = None) -> List[PrimaryKeyInfo]:
        """Get all primary keys.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of primary key information
        """
        query = """
        SELECT
            kc.name AS constraint_name,
            s.name AS schema_name,
            t.name AS table_name,
            i.type_desc AS index_type,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.key_ordinal
        FROM sys.key_constraints kc
        INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.indexes i ON kc.parent_object_id = i.object_id AND kc.unique_index_id = i.index_id
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE kc.type = 'PK'
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name, ic.key_ordinal"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name, ic.key_ordinal"
            results = self.connection.fetch_all(query)

        # Group by constraint
        pk_dict = {}
        for row in results:
            key = (row.constraint_name, row.schema_name, row.table_name)
            if key not in pk_dict:
                pk_dict[key] = {
                    'constraint_name': row.constraint_name,
                    'schema_name': row.schema_name,
                    'table_name': row.table_name,
                    'is_clustered': row.index_type == 'CLUSTERED',
                    'columns': []
                }
            pk_dict[key]['columns'].append(row.column_name)

        pks = [
            PrimaryKeyInfo(
                constraint_name=v['constraint_name'],
                schema_name=v['schema_name'],
                table_name=v['table_name'],
                columns=v['columns'],
                is_clustered=v['is_clustered']
            )
            for v in pk_dict.values()
        ]

        logger.info(f"Found {len(pks)} primary keys")
        return pks

    def get_foreign_keys(self, schema_filter: Optional[List[str]] = None) -> List[ForeignKeyInfo]:
        """Get all foreign keys.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of foreign key information
        """
        query = """
        SELECT
            fk.name AS constraint_name,
            s.name AS schema_name,
            t.name AS table_name,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
            rs.name AS referenced_schema,
            rt.name AS referenced_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column,
            fk.delete_referential_action_desc AS delete_action,
            fk.update_referential_action_desc AS update_action,
            fkc.constraint_column_id
        FROM sys.foreign_keys fk
        INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
        INNER JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" WHERE s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name, fk.name, fkc.constraint_column_id"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name, fk.name, fkc.constraint_column_id"
            results = self.connection.fetch_all(query)

        # Group by constraint
        fk_dict = {}
        for row in results:
            key = (row.constraint_name, row.schema_name, row.table_name)
            if key not in fk_dict:
                fk_dict[key] = {
                    'constraint_name': row.constraint_name,
                    'schema_name': row.schema_name,
                    'table_name': row.table_name,
                    'referenced_schema': row.referenced_schema,
                    'referenced_table': row.referenced_table,
                    'delete_action': row.delete_action,
                    'update_action': row.update_action,
                    'columns': [],
                    'referenced_columns': []
                }
            fk_dict[key]['columns'].append(row.column_name)
            fk_dict[key]['referenced_columns'].append(row.referenced_column)

        fks = [
            ForeignKeyInfo(
                constraint_name=v['constraint_name'],
                schema_name=v['schema_name'],
                table_name=v['table_name'],
                columns=v['columns'],
                referenced_schema=v['referenced_schema'],
                referenced_table=v['referenced_table'],
                referenced_columns=v['referenced_columns'],
                delete_action=v['delete_action'],
                update_action=v['update_action']
            )
            for v in fk_dict.values()
        ]

        logger.info(f"Found {len(fks)} foreign keys")
        return fks

    def get_unique_constraints(self, schema_filter: Optional[List[str]] = None) -> List[UniqueConstraintInfo]:
        """Get all unique constraints.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of unique constraint information
        """
        query = """
        SELECT
            kc.name AS constraint_name,
            s.name AS schema_name,
            t.name AS table_name,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.key_ordinal
        FROM sys.key_constraints kc
        INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.indexes i ON kc.parent_object_id = i.object_id AND kc.unique_index_id = i.index_id
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE kc.type = 'UQ'
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name, ic.key_ordinal"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name, ic.key_ordinal"
            results = self.connection.fetch_all(query)

        # Group by constraint
        uq_dict = {}
        for row in results:
            key = (row.constraint_name, row.schema_name, row.table_name)
            if key not in uq_dict:
                uq_dict[key] = {
                    'constraint_name': row.constraint_name,
                    'schema_name': row.schema_name,
                    'table_name': row.table_name,
                    'columns': []
                }
            uq_dict[key]['columns'].append(row.column_name)

        uqs = [
            UniqueConstraintInfo(
                constraint_name=v['constraint_name'],
                schema_name=v['schema_name'],
                table_name=v['table_name'],
                columns=v['columns']
            )
            for v in uq_dict.values()
        ]

        logger.info(f"Found {len(uqs)} unique constraints")
        return uqs

    def get_check_constraints(self, schema_filter: Optional[List[str]] = None) -> List[CheckConstraintInfo]:
        """Get all check constraints.

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of check constraint information
        """
        query = """
        SELECT
            cc.name AS constraint_name,
            s.name AS schema_name,
            t.name AS table_name,
            cc.definition,
            cc.is_disabled
        FROM sys.check_constraints cc
        INNER JOIN sys.tables t ON cc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        """

        if schema_filter:
            placeholders = ','.join(['?' for _ in schema_filter])
            query += f" WHERE s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name"
            results = self.connection.fetch_all(query)

        checks = [
            CheckConstraintInfo(
                constraint_name=row.constraint_name,
                schema_name=row.schema_name,
                table_name=row.table_name,
                definition=row.definition,
                is_disabled=row.is_disabled
            )
            for row in results
        ]

        logger.info(f"Found {len(checks)} check constraints")
        return checks
