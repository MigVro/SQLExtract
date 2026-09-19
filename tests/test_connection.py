"""Tests for database connection module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pyodbc
from src.connection import ConnectionConfig, DatabaseConnection
from src.utils import ConnectionError as ConnError


class TestConnectionConfig:
    """Test ConnectionConfig dataclass."""

    def test_connection_config_defaults(self):
        """Test default values for connection config."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB"
        )

        assert config.server == "localhost"
        assert config.database == "TestDB"
        assert config.port == 1433
        assert config.user is None
        assert config.password is None
        assert config.windows_auth is False
        assert config.trust_cert is False
        assert config.connection_timeout == 30
        assert config.command_timeout == 300

    def test_connection_string_sql_auth(self):
        """Test connection string with SQL authentication."""
        config = ConnectionConfig(
            server="testserver.database.windows.net",
            database="TestDB",
            user="testuser",
            password="TestPass123!",
            trust_cert=True
        )

        conn_str = config.to_connection_string()

        assert "DRIVER={ODBC Driver 18 for SQL Server}" in conn_str
        assert "SERVER=testserver.database.windows.net" in conn_str
        assert "DATABASE=TestDB" in conn_str
        assert "UID=testuser" in conn_str
        assert "PWD=TestPass123!" in conn_str
        assert "TrustServerCertificate=yes" in conn_str
        assert "Connection Timeout=30" in conn_str

    def test_connection_string_windows_auth(self):
        """Test connection string with Windows authentication."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            windows_auth=True
        )

        conn_str = config.to_connection_string()

        assert "Trusted_Connection=yes" in conn_str
        assert "UID" not in conn_str
        assert "PWD" not in conn_str

    def test_connection_string_custom_port(self):
        """Test connection string with custom port."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            port=14333,
            user="sa",
            password="TestPass"
        )

        conn_str = config.to_connection_string()

        assert "SERVER=localhost,14333" in conn_str

    def test_connection_string_missing_credentials(self):
        """Test connection string raises error when credentials missing."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="testuser"
            # Missing password
        )

        with pytest.raises(ValueError, match="Username and password required"):
            config.to_connection_string()

    def test_connection_string_encrypt_without_trust(self):
        """Test connection string uses encryption without trust cert."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=False
        )

        conn_str = config.to_connection_string()

        assert "Encrypt=yes" in conn_str
        assert "TrustServerCertificate" not in conn_str


class TestDatabaseConnection:
    """Test DatabaseConnection class."""

    @patch('src.connection.pyodbc.connect')
    def test_connect_success(self, mock_connect):
        """Test successful database connection."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        assert db_conn.connection is not None
        assert db_conn.cursor is not None
        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_with("SELECT 1")

    @patch('src.connection.pyodbc.connect')
    def test_connect_with_label_prefixes_log_messages(self, mock_connect, caplog):
        """Test that a label, when given, is included in the connect/close log messages."""
        import logging

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost", database="TestDB", user="sa", password="TestPass", trust_cert=True
        )

        db_conn = DatabaseConnection(config, label="tables")
        with caplog.at_level(logging.INFO):
            db_conn.connect()
            db_conn.close()

        assert any("[tables] Connecting to" in message for message in caplog.messages)
        assert any("[tables] Connection established successfully" in message for message in caplog.messages)
        assert any("[tables] Connection closed" in message for message in caplog.messages)

    @patch('src.connection.pyodbc.connect')
    def test_connect_authentication_failure(self, mock_connect):
        """Test connection failure due to authentication."""
        mock_connect.side_effect = pyodbc.Error("Login failed for user 'sa'")

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="WrongPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config, max_retries=1)

        with pytest.raises(ConnError, match="Authentication failed"):
            db_conn.connect()

    @patch('src.connection.pyodbc.connect')
    def test_connect_database_not_found(self, mock_connect):
        """Test connection failure when database not found."""
        mock_connect.side_effect = pyodbc.Error("Cannot open database 'MissingDB'")

        config = ConnectionConfig(
            server="localhost",
            database="MissingDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config, max_retries=1)

        with pytest.raises(ConnError, match="Database not found"):
            db_conn.connect()

    @patch('src.connection.pyodbc.connect')
    @patch('src.connection.time.sleep')
    def test_connect_retry_logic(self, mock_sleep, mock_connect):
        """Test connection retry with exponential backoff."""
        # Fail twice, succeed on third attempt
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_connect.side_effect = [
            pyodbc.Error("Network error"),
            pyodbc.Error("Network error"),
            mock_conn
        ]

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config, max_retries=3)
        db_conn.connect()

        assert mock_connect.call_count == 3
        assert mock_sleep.call_count == 2
        # Check exponential backoff: 2^1=2, 2^2=4
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    @patch('src.connection.pyodbc.connect')
    @patch('src.connection.time.sleep')
    def test_connect_max_retries_exceeded(self, mock_sleep, mock_connect):
        """Test connection failure after max retries."""
        mock_connect.side_effect = pyodbc.Error("Network error")

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config, max_retries=2)

        with pytest.raises(ConnError, match="Connection failed after 2 attempts"):
            db_conn.connect()

        assert mock_connect.call_count == 2

    def test_execute_query_not_connected(self):
        """Test execute_query raises error when not connected."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass"
        )

        db_conn = DatabaseConnection(config)

        with pytest.raises(ConnError, match="Not connected to database"):
            db_conn.execute_query("SELECT 1")

    @patch('src.connection.pyodbc.connect')
    def test_execute_query_success(self, mock_connect):
        """Test successful query execution."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        result = db_conn.execute_query("SELECT * FROM dbo.Config")

        assert result == mock_cursor
        mock_cursor.execute.assert_called_with("SELECT * FROM dbo.Config")

    @patch('src.connection.pyodbc.connect')
    def test_execute_query_with_params(self, mock_connect):
        """Test query execution with parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        db_conn.execute_query("SELECT * FROM dbo.Config WHERE ConfigID = ?", (1,))

        mock_cursor.execute.assert_called_with(
            "SELECT * FROM dbo.Config WHERE ConfigID = ?",
            (1,)
        )

    @patch('src.connection.pyodbc.connect')
    def test_fetch_all(self, mock_connect):
        """Test fetch_all returns all results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [(1, 'Row1'), (2, 'Row2'), (3, 'Row3')]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        results = db_conn.fetch_all("SELECT * FROM dbo.Config")

        assert len(results) == 3
        assert results[0] == (1, 'Row1')
        assert results[2] == (3, 'Row3')

    @patch('src.connection.pyodbc.connect')
    def test_fetch_one(self, mock_connect):
        """Test fetch_one returns single result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(1,), (100, 'TestValue')]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        result = db_conn.fetch_one("SELECT ConfigID, ConfigKey FROM dbo.Config WHERE ConfigID = 1")

        assert result == (100, 'TestValue')

    @patch('src.connection.pyodbc.connect')
    def test_close_connection(self, mock_connect):
        """Test connection is properly closed."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        db_conn = DatabaseConnection(config)
        db_conn.connect()

        assert db_conn.connection is not None
        assert db_conn.cursor is not None

        db_conn.close()

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        assert db_conn.connection is None
        assert db_conn.cursor is None

    @patch('src.connection.pyodbc.connect')
    def test_context_manager(self, mock_connect):
        """Test DatabaseConnection works as context manager."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass",
            trust_cert=True
        )

        with DatabaseConnection(config) as db_conn:
            assert db_conn.connection is not None
            db_conn.execute_query("SELECT 1")

        # Connection should be closed after exiting context
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
