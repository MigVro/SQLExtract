"""Tests for core extractor module."""

import pytest
from unittest.mock import MagicMock, patch
from src.extractor import DatabaseExtractor
from src.connection import ConnectionConfig, DatabaseConnection


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
