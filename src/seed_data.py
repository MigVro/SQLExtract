"""Seed data extraction module."""

from typing import List, Optional, Dict, Any
from .connection import DatabaseConnection
from .schema import ColumnInfo
from .utils import get_logger, escape_sql_string, escape_sql_identifier

logger = get_logger(__name__)


class SeedDataExtractor:
    """Extract seed data from tables."""

    def __init__(self, connection: DatabaseConnection):
        """Initialize seed data extractor.

        Args:
            connection: Database connection
        """
        self.connection = connection

    def extract_table_data(
        self,
        schema_name: str,
        table_name: str,
        columns: List[ColumnInfo],
        max_rows: Optional[int] = None,
        where_clause: Optional[str] = None
    ) -> List[str]:
        """Extract data from a table as INSERT statements.

        Args:
            schema_name: Schema name
            table_name: Table name
            columns: List of column information
            max_rows: Maximum number of rows to extract
            where_clause: Optional WHERE clause filter

        Returns:
            List of INSERT SQL statements
        """
        # Build column list (exclude computed columns)
        data_columns = [col for col in columns if not col.is_computed]

        if not data_columns:
            logger.warning(f"Table {schema_name}.{table_name} has no non-computed columns")
            return []

        column_names = [escape_sql_identifier(col.name) for col in data_columns]
        column_list = ', '.join(column_names)

        # Build SELECT query
        select_columns = []
        for col in data_columns:
            select_columns.append(escape_sql_identifier(col.name))

        query = f"""
        SELECT {', '.join(select_columns)}
        FROM {escape_sql_identifier(schema_name)}.{escape_sql_identifier(table_name)}
        """

        if where_clause:
            query += f" WHERE {where_clause}"

        if max_rows:
            query = f"SELECT TOP {max_rows} * FROM ({query}) AS T"

        # Execute query
        try:
            results = self.connection.fetch_all(query)
        except Exception as e:
            logger.error(f"Failed to extract data from {schema_name}.{table_name}: {e}")
            return []

        if not results:
            logger.info(f"No data found in {schema_name}.{table_name}")
            return []

        # Check if table has identity column
        has_identity = any(col.is_identity for col in data_columns)

        insert_statements = []

        # Add IDENTITY_INSERT ON if needed
        if has_identity:
            insert_statements.append(
                f"SET IDENTITY_INSERT {escape_sql_identifier(schema_name)}.{escape_sql_identifier(table_name)} ON"
            )
            insert_statements.append("GO")

        # Generate INSERT statements
        for row in results:
            values = []
            for i, col in enumerate(data_columns):
                value = row[i]
                if value is None:
                    values.append("NULL")
                elif col.data_type in ('int', 'bigint', 'smallint', 'tinyint', 'bit', 'decimal', 'numeric', 'float', 'real', 'money', 'smallmoney'):
                    values.append(str(value))
                elif col.data_type in ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext'):
                    escaped_value = escape_sql_string(str(value))
                    if col.data_type.startswith('n'):
                        values.append(f"N'{escaped_value}'")
                    else:
                        values.append(f"'{escaped_value}'")
                elif col.data_type in ('datetime', 'datetime2', 'smalldatetime', 'date', 'time', 'datetimeoffset'):
                    values.append(f"'{value}'")
                elif col.data_type in ('uniqueidentifier',):
                    values.append(f"'{value}'")
                elif col.data_type in ('varbinary', 'binary', 'image'):
                    # Convert binary to hex string
                    hex_value = value.hex() if value else ''
                    values.append(f"0x{hex_value}" if hex_value else "NULL")
                else:
                    # Default: treat as string
                    escaped_value = escape_sql_string(str(value))
                    values.append(f"'{escaped_value}'")

            values_list = ', '.join(values)
            insert_stmt = f"INSERT INTO {escape_sql_identifier(schema_name)}.{escape_sql_identifier(table_name)} ({column_list}) VALUES ({values_list})"
            insert_statements.append(insert_stmt)

        # Add IDENTITY_INSERT OFF if needed
        if has_identity:
            insert_statements.append("GO")
            insert_statements.append(
                f"SET IDENTITY_INSERT {escape_sql_identifier(schema_name)}.{escape_sql_identifier(table_name)} OFF"
            )
            insert_statements.append("GO")

        logger.info(f"Extracted {len(results)} rows from {schema_name}.{table_name}")
        return insert_statements
