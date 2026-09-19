"""Tests for core extractor module."""

import pytest
from unittest.mock import MagicMock, patch
from src.extractor import DatabaseExtractor
from src.connection import ConnectionConfig, DatabaseConnection
from src.utils import AuthenticationError, ExtractionError, OutputError


EMPTY_METADATA_RESULTS = {
    'schemas': [],
    'user_defined_types': [],
    'sequences': [],
    'tables': [],
    'extended_properties': {},
    'primary_keys': [],
    'foreign_keys': [],
    'unique_constraints': [],
    'check_constraints': [],
    'indexes': [],
    'views': [],
    'view_dependencies': [],
    'procedures': [],
    'functions': [],
    'triggers': [],
}


class FakeConnection:
    """Stand-in for DatabaseConnection that connects/closes without touching pyodbc."""

    def __init__(self, cfg, label=None):
        self.label = label

    def connect(self):
        pass

    def close(self):
        pass


class TestDatabaseExtractor:
    """Test DatabaseExtractor class."""

    def test_extractor_initialization(self):
        """Test extractor initialization."""
        config = ConnectionConfig(
            server="localhost",
            database="TestDB",
            user="sa",
            password="TestPass"
        )

        extractor = DatabaseExtractor(config)

        assert extractor.config == config
        assert extractor.connection is None

    def test_run_jobs_sequential_reuses_single_connection(self):
        """Test that parallel=False reuses self.connection for every job, without opening new ones."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)
        extractor.connection = MagicMock(spec=DatabaseConnection)

        jobs = {
            'a': lambda conn: (conn, 1),
            'b': lambda conn: (conn, 2),
        }

        results = extractor._run_jobs(jobs, parallel=False, max_workers=4)

        assert results['a'] == (extractor.connection, 1)
        assert results['b'] == (extractor.connection, 2)

    def test_run_jobs_parallel_opens_one_connection_per_job(self):
        """Test that parallel=True opens and closes a fresh connection per job."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        created_connections = []

        class FakeConnection:
            def __init__(self, cfg, label=None):
                self.label = label
                self.connected = False
                self.closed = False
                created_connections.append(self)

            def connect(self):
                self.connected = True

            def close(self):
                self.closed = True

        with patch('src.extractor.DatabaseConnection', FakeConnection):
            jobs = {
                'a': lambda conn: conn.connected,
                'b': lambda conn: conn.connected,
                'c': lambda conn: conn.connected,
            }
            results = extractor._run_jobs(jobs, parallel=True, max_workers=4)

        assert results == {'a': True, 'b': True, 'c': True}
        assert len(created_connections) == 3
        assert all(c.closed for c in created_connections)
        assert sorted(c.label for c in created_connections) == ['a', 'b', 'c']

    def test_run_jobs_empty(self):
        """Test that an empty job dict returns an empty result without touching connections."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        assert extractor._run_jobs({}, parallel=True, max_workers=4) == {}
        assert extractor._run_jobs({}, parallel=False, max_workers=4) == {}


class TestExtractErrorMapping:
    """Test that extract() surfaces the right exception type for each failure stage,
    so cli.py can map it to the right exit code."""

    def test_connection_error_propagates_unwrapped(self, tmp_path):
        """A specific connection-stage error (e.g. AuthenticationError) must reach the
        caller as-is, not be flattened into a generic ExtractionError."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        class FailingConnection(FakeConnection):
            def connect(self):
                raise AuthenticationError("bad login")

        with patch('src.extractor.DatabaseConnection', FailingConnection):
            with pytest.raises(AuthenticationError, match="bad login"):
                extractor.extract(output_dir=str(tmp_path))

    def test_unexpected_metadata_error_wrapped_as_extraction_error(self, tmp_path):
        """An unclassified error while reading schema metadata becomes an ExtractionError."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        with patch('src.extractor.DatabaseConnection', FakeConnection):
            with patch.object(extractor, '_run_jobs', side_effect=RuntimeError("boom")):
                with pytest.raises(ExtractionError, match="boom"):
                    extractor.extract(output_dir=str(tmp_path))

    def test_output_write_failure_wrapped_as_output_error(self, tmp_path):
        """A file I/O failure while writing the generated SQL becomes an OutputError,
        not an ExtractionError - so the CLI exits with the output-error code."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        with patch('src.extractor.DatabaseConnection', FakeConnection):
            with patch.object(extractor, '_run_jobs', return_value=EMPTY_METADATA_RESULTS):
                with patch(
                    'src.extractor.SQLFormatter.write_modular_format',
                    side_effect=OSError("disk full"),
                ):
                    with pytest.raises(OutputError, match="disk full"):
                        extractor.extract(output_dir=str(tmp_path), output_format='modular')

    def test_output_directory_creation_failure_wrapped_as_output_error(self, tmp_path):
        """A failure preparing the output directory (before any DB work starts) is
        also an OutputError."""
        config = ConnectionConfig(server="localhost", database="TestDB", user="sa", password="TestPass")
        extractor = DatabaseExtractor(config)

        with patch('src.extractor.SQLFormatter.__init__', side_effect=OSError("permission denied")):
            with pytest.raises(OutputError, match="permission denied"):
                extractor.extract(output_dir=str(tmp_path))
