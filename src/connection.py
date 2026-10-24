"""Database connection management."""

import pyodbc
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from .utils import (
    get_logger,
    ConnectionError as ConnError,
    AuthenticationError,
    DatabaseAccessError,
    PermissionDeniedError,
)

logger = get_logger(__name__)


@dataclass
class ConnectionConfig:
    """Database connection configuration."""

    server: str
    database: str
    port: int = 1433
    user: Optional[str] = None
    password: Optional[str] = None
    windows_auth: bool = False
    trust_cert: bool = False
    connection_timeout: int = 30
    command_timeout: int = 300

    def to_connection_string(self) -> str:
        """Generate ODBC connection string.

        Returns:
            ODBC connection string
        """
        parts = []

        # Driver
        parts.append("DRIVER={ODBC Driver 18 for SQL Server}")

        # Server and port
        if self.port != 1433:
            parts.append(f"SERVER={self.server},{self.port}")
        else:
            parts.append(f"SERVER={self.server}")

        # Database
        parts.append(f"DATABASE={self.database}")

        # Authentication
        if self.windows_auth:
            parts.append("Trusted_Connection=yes")
        else:
            if not self.user or not self.password:
                raise ValueError("Username and password required for SQL Authentication")
            parts.append(f"UID={self.user}")
            parts.append(f"PWD={self.password}")

        # SSL/TLS
        if self.trust_cert:
            parts.append("TrustServerCertificate=yes")
        else:
            parts.append("Encrypt=yes")

        # Timeouts
        parts.append(f"Connection Timeout={self.connection_timeout}")

        return ";".join(parts)


class DatabaseConnection:
    """Manage database connection with retry logic."""

    def __init__(self, config: ConnectionConfig, max_retries: int = 3, label: Optional[str] = None):
        """Initialize connection manager.

        Args:
            config: Connection configuration
            max_retries: Maximum number of connection retry attempts
            label: Optional identifier included in log messages, to tell apart the
                many connections opened during parallel extraction
        """
        self.config = config
        self.max_retries = max_retries
        self.label = label
        self.connection: Optional[pyodbc.Connection] = None
        self.cursor: Optional[pyodbc.Cursor] = None

    def _log_prefix(self) -> str:
        return f"[{self.label}] " if self.label else ""

    def connect(self) -> None:
        """Establish database connection with retry logic.

        Raises:
            ConnError: If connection fails after all retries
        """
        connection_string = self.config.to_connection_string()
        prefix = self._log_prefix()

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"{prefix}Connecting to {self.config.server}/{self.config.database} (attempt {attempt}/{self.max_retries})"
                )

                self.connection = pyodbc.connect(
                    connection_string, timeout=self.config.connection_timeout
                )
                self.cursor = self.connection.cursor()

                # Test connection
                self.cursor.execute("SELECT 1")
                self.cursor.fetchone()

                logger.info(f"{prefix}Connection established successfully")
                return

            except pyodbc.Error as e:
                error_msg = str(e)

                if "Login failed" in error_msg or "Login timeout" in error_msg:
                    raise AuthenticationError(f"Authentication failed: {error_msg}")

                if "Cannot open database" in error_msg:
                    raise DatabaseAccessError(
                        f"Cannot access database '{self.config.database}': "
                        "either it doesn't exist, or the login lacks permission "
                        "to it (SQL Server reports both cases identically)"
                    )

                if attempt < self.max_retries:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"{prefix}Connection failed: {error_msg}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    raise ConnError(
                        f"Connection failed after {self.max_retries} attempts: {error_msg}"
                    )

    def execute_query(self, query: str, params: Optional[tuple] = None) -> pyodbc.Cursor:
        """Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Cursor with query results

        Raises:
            PermissionDeniedError: If the login lacks permission on the queried object
            ConnError: If not connected or query fails for another reason
        """
        if not self.cursor:
            raise ConnError("Not connected to database")

        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor
        except pyodbc.Error as e:
            error_msg = str(e)
            if "permission was denied" in error_msg:
                raise PermissionDeniedError(f"Permission denied: {error_msg}")
            raise ConnError(f"Query execution failed: {error_msg}")

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> list:
        """Execute query and fetch all results.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of result rows
        """
        cursor = self.execute_query(query, params)
        return cursor.fetchall()

    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Any]:
        """Execute query and fetch one result.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Single result row or None
        """
        cursor = self.execute_query(query, params)
        return cursor.fetchone()

    def close(self) -> None:
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None

        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info(f"{self._log_prefix()}Connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
