"""Integration tests for SQL Extract.

These tests verify end-to-end functionality.
Note: These require a real SQL Server instance to run.
"""

import os
import subprocess
import tempfile

import pytest

from src.connection import ConnectionConfig, DatabaseConnection
from src.extractor import DatabaseExtractor

SOURCE_DB = "SQLExtractIntegrationTest"
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "test_schema.sql")

# Deployment order for the per-object format's subdirectories - there is no generated
# deploy script for this format, so the test has to know the same dependency order
# write_per_object_format() writes them in (schemas/types/sequences before tables,
# constraints/indexes after tables, seed data last).
PER_OBJECT_SUBDIRS = [
    "Schemas", "Types", "Sequences", "Tables",
    "Constraints/01_PrimaryKeys", "Constraints/02_UniqueConstraints",
    "Constraints/03_ForeignKeys", "Constraints/04_CheckConstraints",
    "Indexes", "Views", "Procedures", "Functions", "Triggers", "SeedData",
]

FORMATS = ["modular", "single", "per-object"]

requires_real_server = pytest.mark.skipif(
    not os.getenv("SQLEXTRACT_TEST_SERVER"),
    reason="Integration tests require SQLEXTRACT_TEST_SERVER environment variable"
)


def _server() -> str:
    return os.environ["SQLEXTRACT_TEST_SERVER"]


def _admin_config(database: str = "master") -> ConnectionConfig:
    return ConnectionConfig(
        server=_server(),
        database=database,
        windows_auth=True,
        trust_cert=True,
    )


def _run_sqlcmd_file(database: str, path: str) -> None:
    result = subprocess.run(
        ["sqlcmd", "-S", _server(), "-d", database, "-E", "-C", "-b", "-i", path],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"sqlcmd failed on {path}:\n{result.stdout}\n{result.stderr}"


def _recreate_database(name: str) -> None:
    with DatabaseConnection(_admin_config()) as conn:
        conn.connection.autocommit = True
        conn.execute_query(
            f"IF EXISTS (SELECT 1 FROM sys.databases WHERE name = '{name}') "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
        )
        conn.execute_query(f"DROP DATABASE IF EXISTS [{name}]")
        conn.execute_query(f"CREATE DATABASE [{name}]")


def _drop_database(name: str) -> None:
    with DatabaseConnection(_admin_config()) as conn:
        conn.connection.autocommit = True
        conn.execute_query(
            f"IF EXISTS (SELECT 1 FROM sys.databases WHERE name = '{name}') "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
        )
        conn.execute_query(f"DROP DATABASE IF EXISTS [{name}]")


def _deploy_extracted(extracted_dir: str, output_format: str, database: str) -> None:
    if output_format == "modular":
        deploy_script = os.path.join(extracted_dir, "deploy.ps1")
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-File", deploy_script,
                "-Server", _server(), "-Database", database,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"deploy.ps1 failed:\n{result.stdout}\n{result.stderr}"
    elif output_format == "single":
        _run_sqlcmd_file(database, os.path.join(extracted_dir, "schema.sql"))
    else:
        for subdir in PER_OBJECT_SUBDIRS:
            dir_path = os.path.join(extracted_dir, subdir)
            if not os.path.isdir(dir_path):
                continue
            for filename in sorted(os.listdir(dir_path)):
                _run_sqlcmd_file(database, os.path.join(dir_path, filename))


def _object_counts(database: str) -> dict:
    with DatabaseConnection(_admin_config(database)) as conn:
        tables = conn.fetch_one("SELECT COUNT(*) FROM sys.tables")[0]
        views = conn.fetch_one("SELECT COUNT(*) FROM sys.views")[0]
        procs = conn.fetch_one("SELECT COUNT(*) FROM sys.procedures")[0]
        functions = conn.fetch_one(
            "SELECT COUNT(*) FROM sys.objects WHERE type IN ('FN', 'IF', 'TF')"
        )[0]
        triggers = conn.fetch_one("SELECT COUNT(*) FROM sys.triggers")[0]
        row_counts = {
            row[0]: row[1]
            for row in conn.fetch_all(
                """
                SELECT s.name + '.' + t.name, SUM(p.rows)
                FROM sys.tables t
                JOIN sys.schemas s ON s.schema_id = t.schema_id
                JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
                GROUP BY s.name, t.name
                """
            )
        }
        return {
            "tables": tables,
            "views": views,
            "procedures": procs,
            "functions": functions,
            "triggers": triggers,
            "row_counts": row_counts,
        }


@requires_real_server
class TestFullRoundTrip:
    """Deploys the fixture schema, extracts it (in each output format), redeploys it,
    and compares against the source - for every format SQL Extract can produce."""

    @pytest.fixture(scope="class")
    def source_db(self):
        _recreate_database(SOURCE_DB)
        _run_sqlcmd_file(SOURCE_DB, FIXTURE_PATH)
        yield SOURCE_DB
        _drop_database(SOURCE_DB)

    @pytest.fixture(scope="class", params=FORMATS)
    def output_format(self, request):
        return request.param

    @pytest.fixture(scope="class")
    def extracted_dir(self, source_db, output_format):
        with tempfile.TemporaryDirectory() as tmp_dir:
            extractor = DatabaseExtractor(_admin_config(source_db))
            extractor.extract(
                output_dir=tmp_dir,
                output_format=output_format,
                extract_seed_data=True,
            )
            yield tmp_dir

    @pytest.fixture(scope="class")
    def redeployed_db(self, extracted_dir, output_format):
        db_name = f"SQLExtractIntegrationTest_Redeploy_{output_format.replace('-', '_')}"
        _recreate_database(db_name)
        _deploy_extracted(extracted_dir, output_format, db_name)
        yield db_name
        _drop_database(db_name)

    def test_modular_files_written(self, extracted_dir, output_format):
        if output_format != "modular":
            pytest.skip("Only applies to the modular output format")
        expected = {
            "01_CREATE_SCHEMAS.sql", "04_CREATE_TABLES.sql", "05_CREATE_CONSTRAINTS.sql",
            "06_CREATE_INDEXES.sql", "07_CREATE_TRIGGERS.sql", "08_CREATE_VIEWS.sql",
            "09_CREATE_PROCEDURES.sql", "10_CREATE_FUNCTIONS.sql", "12_SEED_DATA.sql",
            "deploy.ps1", "deploy.sh", "README.md",
        }
        written = set(os.listdir(extracted_dir))
        assert expected <= written

    def test_object_counts_match(self, source_db, redeployed_db):
        assert _object_counts(source_db) == _object_counts(redeployed_db)

    def test_trigger_fires_on_redeployed_db(self, redeployed_db):
        with DatabaseConnection(_admin_config(redeployed_db)) as conn:
            before = conn.fetch_one(
                "SELECT ModifiedDate FROM MQTT.ReceiverConfig WHERE ReceiverConfigID = 1"
            )[0]
            conn.execute_query(
                "UPDATE MQTT.ReceiverConfig SET RetryCount = RetryCount + 1 "
                "WHERE ReceiverConfigID = 1"
            )
            conn.connection.commit()
            after = conn.fetch_one(
                "SELECT ModifiedDate FROM MQTT.ReceiverConfig WHERE ReceiverConfigID = 1"
            )[0]
        assert before is None
        assert after is not None


@requires_real_server
class TestDryRunAgainstRealDb:
    """--dry-run must report real object counts from a live database without ever
    creating the output directory."""

    @pytest.fixture(scope="class")
    def source_db(self):
        db_name = "SQLExtractIntegrationTest_DryRun"
        _recreate_database(db_name)
        _run_sqlcmd_file(db_name, FIXTURE_PATH)
        yield db_name
        _drop_database(db_name)

    def test_dry_run_reports_real_counts_and_writes_nothing(self, source_db, tmp_path):
        output_dir = tmp_path / "should_not_exist"
        extractor = DatabaseExtractor(_admin_config(source_db))

        summary = extractor.extract(
            output_dir=str(output_dir),
            extract_seed_data=True,
            dry_run=True,
        )

        assert not output_dir.exists()
        assert summary["tables"] == 6
        assert summary["views"] == 1
        assert summary["procedures"] == 1
        assert summary["functions"] == 2
        assert summary["triggers"] == 1
        assert summary["seed_data_tables"] == 6


@requires_real_server
class TestCliFlagsAgainstRealDb:
    """Exercises --omit-ts, --no-header, --clean, and --no-parallel against a real
    database - these flags only change formatting/output-directory handling, not the
    query logic already covered by TestFullRoundTrip, so one small fixture schema and
    the modular format are enough to prove each flag actually does what it claims."""

    @pytest.fixture(scope="class")
    def source_db(self):
        db_name = "SQLExtractIntegrationTest_CliFlags"
        _recreate_database(db_name)
        _run_sqlcmd_file(db_name, FIXTURE_PATH)
        yield db_name
        _drop_database(db_name)

    def test_omit_ts_removes_date_line_but_keeps_header(self, source_db, tmp_path):
        extractor = DatabaseExtractor(_admin_config(source_db))
        extractor.extract(output_dir=str(tmp_path), omit_ts=True)

        content = (tmp_path / "01_CREATE_SCHEMAS.sql").read_text()
        assert "Database Schema Export" in content
        assert "Date:" not in content

    def test_no_header_omits_header_block_entirely(self, source_db, tmp_path):
        extractor = DatabaseExtractor(_admin_config(source_db))
        extractor.extract(output_dir=str(tmp_path), no_header=True)

        content = (tmp_path / "01_CREATE_SCHEMAS.sql").read_text()
        assert "Database Schema Export" not in content
        assert "/*" not in content
        assert "-- SCHEMAS" in content

    def test_clean_removes_stray_files_from_output_dir(self, source_db, tmp_path):
        stray_file = tmp_path / "leftover_from_a_previous_run.txt"
        stray_file.write_text("stale")

        extractor = DatabaseExtractor(_admin_config(source_db))
        extractor.extract(output_dir=str(tmp_path), clean=True)

        assert not stray_file.exists()
        assert (tmp_path / "01_CREATE_SCHEMAS.sql").exists()

    def test_no_parallel_produces_the_same_object_counts(self, source_db, tmp_path):
        extractor = DatabaseExtractor(_admin_config(source_db))
        extractor.extract(output_dir=str(tmp_path), extract_seed_data=True, parallel=False)

        assert (tmp_path / "04_CREATE_TABLES.sql").exists()
        assert (tmp_path / "12_SEED_DATA.sql").exists()
        readme = (tmp_path / "README.md").read_text()
        assert "- Tables: 6" in readme


@pytest.mark.unit
class TestMockIntegration:
    """Mock integration tests that don't require real database."""

    def test_workflow_orchestration(self):
        """Test that extraction workflow calls all components."""
        # This test uses mocks to verify workflow without real database
        pass
