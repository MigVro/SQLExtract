"""Index extraction module."""

from typing import List, Optional
from dataclasses import dataclass
from .connection import DatabaseConnection
from .utils import get_logger

logger = get_logger(__name__)


@dataclass
class IndexInfo:
    """Index metadata."""

    index_name: str
    schema_name: str
    table_name: str
    is_unique: bool
    is_clustered: bool
    is_primary_key: bool
    is_unique_constraint: bool
    columns: List[str]
    included_columns: List[str]
    filter_definition: Optional[str]


class IndexExtractor:
    """Extract indexes from database."""

    def __init__(self, connection: DatabaseConnection):
        """Initialize index extractor.

        Args:
            connection: Database connection
        """
        self.connection = connection

    def get_indexes(self, schema_filter: Optional[List[str]] = None) -> List[IndexInfo]:
        """Get all indexes (excluding PK and unique constraint indexes).

        Args:
            schema_filter: Optional list of schema names to include

        Returns:
            List of index information
        """
        query = """
        SELECT
            i.name AS index_name,
            s.name AS schema_name,
            t.name AS table_name,
            i.is_unique,
            i.type_desc AS index_type,
            i.is_primary_key,
            i.is_unique_constraint,
            i.filter_definition,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.is_included_column,
            ic.key_ordinal
        FROM sys.indexes i
        INNER JOIN sys.tables t ON i.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.is_primary_key = 0
          AND i.is_unique_constraint = 0
          AND i.type > 0
        """

        if schema_filter:
            placeholders = ",".join(["?" for _ in schema_filter])
            query += f" AND s.name IN ({placeholders})"
            query += " ORDER BY s.name, t.name, i.name, ic.key_ordinal, ic.index_column_id"
            results = self.connection.fetch_all(query, tuple(schema_filter))
        else:
            query += " ORDER BY s.name, t.name, i.name, ic.key_ordinal, ic.index_column_id"
            results = self.connection.fetch_all(query)

        # Group by index
        index_dict = {}
        for row in results:
            key = (row.index_name, row.schema_name, row.table_name)
            if key not in index_dict:
                index_dict[key] = {
                    "index_name": row.index_name,
                    "schema_name": row.schema_name,
                    "table_name": row.table_name,
                    "is_unique": row.is_unique,
                    "is_clustered": row.index_type == "CLUSTERED",
                    "is_primary_key": row.is_primary_key,
                    "is_unique_constraint": row.is_unique_constraint,
                    "filter_definition": row.filter_definition,
                    "columns": [],
                    "included_columns": [],
                }

            if row.is_included_column:
                index_dict[key]["included_columns"].append(row.column_name)
            else:
                index_dict[key]["columns"].append(row.column_name)

        indexes = [
            IndexInfo(
                index_name=v["index_name"],
                schema_name=v["schema_name"],
                table_name=v["table_name"],
                is_unique=v["is_unique"],
                is_clustered=v["is_clustered"],
                is_primary_key=v["is_primary_key"],
                is_unique_constraint=v["is_unique_constraint"],
                columns=v["columns"],
                included_columns=v["included_columns"],
                filter_definition=v["filter_definition"],
            )
            for v in index_dict.values()
        ]

        logger.info(f"Found {len(indexes)} indexes")
        return indexes
