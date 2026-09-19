# SQL Extract - Implementation Checklist

## Phase 1: Foundation (Week 1) ✅ COMPLETE

### Project Setup ✅
- [x] Initialize Git repository
- [x] Create Python virtual environment
- [x] Create `pyproject.toml` or `setup.py`
- [x] Add `.gitignore` (Python, IDE files)
- [x] Create `requirements.txt` and `requirements-dev.txt`
- [x] Set up pre-commit hooks (black, mypy, pytest)
- [x] Create initial directory structure

### Core Infrastructure ✅
- [x] Database connection module (`src/connection.py`)
  - [x] Connection string parsing
  - [x] Connection pooling
  - [x] Retry logic with exponential backoff
  - [x] Connection validation
  - [x] Support for Windows Auth, SQL Auth, connection strings
- [x] Logging setup (`src/utils.py`)
  - [x] Structured logging with levels
  - [x] File and console output
  - [x] Progress indicators
- [x] CLI framework (`src/cli.py`)
  - [x] Argument parsing with Click
  - [x] Help text and examples
  - [x] Version display
  - [x] Config file loading (YAML/JSON)

### Schema Introspection ✅
- [x] Schema reader module (`src/schema.py`)
  - [x] List all schemas
  - [x] List all tables with columns
  - [x] List all constraints
  - [x] List all indexes
  - [x] List all views, procedures, functions
  - [x] Filter by schema/pattern

### Testing Infrastructure ✅
- [x] Set up pytest configuration
- [x] Create test fixtures (sample database schema)
- [x] Set up Docker Compose with SQL Server for integration tests
- [x] Add test coverage reporting
- [x] Create sample test database script

---

## Phase 2: Table Extraction (Week 2) ✅ COMPLETE

### Table Definition Extraction ✅
- [x] Extract table columns (`src/tables.py`)
  - [x] Column names, data types, precision, scale
  - [x] Nullability
  - [x] Default constraints
  - [x] Computed columns (persisted/non-persisted)
  - [x] Identity columns (seed, increment)
- [x] Generate `CREATE TABLE` statements
  - [x] Use Jinja2 templates
  - [x] Include IF EXISTS checks
  - [x] Proper formatting and indentation

### Constraint Extraction ✅
- [x] Extract primary keys (`src/constraints.py`)
  - [x] Single and composite PKs
  - [x] Named constraints
- [x] Extract foreign keys
  - [x] Referenced table/column
  - [x] ON DELETE/UPDATE actions
  - [x] Named constraints
- [x] Extract unique constraints
- [x] Extract check constraints
  - [x] Constraint expressions
  - [x] Enabled/disabled state
- [x] Extract default constraints

### Dependency Ordering ✅
- [x] Build dependency graph (`src/dependency.py`)
  - [x] Parse FK relationships
  - [x] Topological sort (FIXED: was inverted, now correct)
  - [x] Detect circular dependencies
- [x] Order table creation scripts
- [x] Handle circular FKs (create tables first, add FKs later)

### Testing ✅
- [x] Unit tests for table extraction
- [x] Unit tests for constraint extraction
- [x] Unit tests for dependency ordering (13 tests)
- [x] Integration test: extract and re-deploy sample database tables

---

## Phase 3: Index and View Extraction (Week 3) ✅ COMPLETE

### Index Extraction ✅
- [x] Extract all indexes (`src/indexes.py`)
  - [x] Clustered/non-clustered
  - [x] Unique indexes
  - [x] Filtered indexes (WHERE clause)
  - [x] Included columns
  - [x] Index options (FILLFACTOR, PAD_INDEX, etc.)
- [x] Exclude PK/unique constraint indexes (already scripted)
- [x] Generate `CREATE INDEX` statements

### View Extraction ✅
- [x] Extract view definitions (`src/schema.py: get_views`, not a standalone `src/views.py`)
  - [x] Use `sys.sql_modules` definition
  - [x] Handle SCHEMABINDING (definition captured as-is)
  - [x] Handle indexed views (definition captured as-is)
- [x] Order views by dependencies (`src/schema.py: get_view_dependencies` + `src/dependency.py: order_views_by_dependency`)
- [x] Generate `CREATE VIEW` statements

### Testing ✅
- [x] Unit tests for index extraction (3 tests)
- [x] Unit tests for view extraction
- [x] Integration test: extract and re-deploy indexes and views

---

## Phase 4: Stored Procedures and Functions (Week 4) - MOSTLY COMPLETE

> Note: procedure/view/function extraction was implemented in `src/schema.py` (not
> standalone `src/procedures.py`/`src/functions.py` modules as originally planned),
> with `CREATE` statement generation in `src/formatter.py`.

### Stored Procedure Extraction ✅
- [x] Extract procedure definitions (`src/schema.py: get_stored_procedures`)
  - [x] Use `sys.sql_modules` definition
  - [x] Handle encrypted procedures (warn and skip)
  - [ ] Preserve parameters (definition captured as-is; parameters not parsed separately)
- [x] Generate `CREATE PROCEDURE` statements
- [ ] Handle procedure dependencies (if needed)

### Function Extraction ✅
- [x] Extract function definitions (`src/schema.py: get_functions`)
  - [x] Scalar functions
  - [x] Inline table-valued functions
  - [x] Multi-statement table-valued functions
  - [ ] CLR functions (metadata only)
- [x] Generate `CREATE FUNCTION` statements

### Trigger Extraction ✅
- [x] Extract trigger definitions (`src/schema.py: get_triggers`, not a standalone `src/triggers.py`)
  - [x] Table triggers (AFTER, INSTEAD OF)
  - [ ] Database triggers (scoped out — deliberately out of scope, see 2026-09-19 update)
  - [ ] Trigger order (first/last via `sp_settriggerorder` — deliberately out of scope, see 2026-09-19 update)
  - [x] Enabled/disabled state (emitted as a separate `DISABLE TRIGGER` statement after `CREATE TRIGGER`)
- [x] Generate `CREATE TRIGGER` statements

### Testing
- [x] Unit tests for procedure extraction (`tests/test_schema.py`)
- [x] Unit tests for function extraction (`tests/test_schema.py`)
- [x] Unit tests for trigger extraction (`tests/test_schema.py`, `tests/test_formatter.py`)
- [x] Integration test: extract and re-deploy all programmability objects (`tests/test_integration.py:TestFullRoundTrip`, see 2026-09-19 update)

---

## Phase 5: Seed Data Extraction (Week 5) ✅ COMPLETE

### Data Extraction ✅
- [x] Extract table data (`src/seed_data.py`)
  - [x] SELECT data from tables
  - [x] Handle NULL values
  - [x] Handle identity columns
  - [x] Escape special characters (quotes, backslashes)
  - [x] Handle binary data (warn and skip or convert to hex)
- [x] Generate `INSERT` statements
  - [x] Batching (e.g., 100 rows per batch)
  - [x] `SET IDENTITY_INSERT ON/OFF`
  - [x] Proper formatting
- [x] Support filtering
  - [x] Table whitelist/blacklist
  - [x] WHERE clause filters
  - [x] Row count limits

### Dependency Ordering for Data ✅
- [x] Order data insertion by FK dependencies
- [x] Disable FK constraints during data load (optional)
- [x] Re-enable FK constraints after load

### Testing ✅
- [x] Unit tests for data extraction (5 tests)
- [x] Unit tests for INSERT generation
- [x] Integration test: extract and re-deploy seed data, verify row counts

---

## Phase 6: Output Formatting (Week 6) ✅ COMPLETE

### Single File Format ✅
- [x] Implement single file output (`src/formatter.py`)
  - [x] Combine all objects into one file
  - [x] Add section comments
  - [x] Add batch separators (GO)

### Per-Object Format ✅
- [x] Implement per-object file output
  - [x] Create subdirectories (tables/, procedures/, etc.)
  - [x] Generate filenames from schema and object name
  - [x] Write each object to separate file

### Modular Format ✅
- [x] Implement modular file output
  - [x] Generate numbered files (01_, 02_, etc.)
  - [x] Group objects by type
  - [x] Create deployment script (deploy.sh, deploy.ps1) — lists only the files actually
        written, in order, and runs them via `sqlcmd`

### Documentation Generation ✅
- [x] Generate README.md for extracted schema (all formats, not just modular)
  - [x] List of objects
  - [x] Deployment instructions (format-specific)
  - [x] Dependencies

### Testing
- [x] Unit tests for each output format (deploy scripts + README; `write_single_file`/
      `write_per_object_format` themselves still untested beyond the smoke checks below)
- [x] Integration test: extract with each format, verify file structure (`tests/test_integration.py:TestFullRoundTrip`, see 2026-09-19 update)
- [x] Integration test: deploy from each format (same test, see 2026-09-19 update)

---

## Phase 7: Advanced Features (Week 7) - COMPLETE

### Sequence Extraction ✅
- [x] Extract sequences (`src/schema.py: get_sequences`, not a standalone `src/sequences.py`)
  - [x] START WITH, INCREMENT BY
  - [x] MIN/MAX values
  - [x] CYCLE option
  - [x] CACHE / NO CACHE, and non-default data type (incl. `decimal`/`numeric` precision/scale)
- [x] Generate `CREATE SEQUENCE` statements

### User-Defined Type Extraction ✅
- [x] Extract user-defined table types (`src/schema.py: get_user_defined_types` /
      `_get_table_types`), including columns and an inline `PRIMARY KEY` clause if the
      table type has one. Unique/check constraints on table types are not extracted.
- [x] Extract alias types (`_get_alias_types`) — `CREATE TYPE ... FROM <base type>`
- [x] Extract CLR types (metadata only) (`_get_clr_types`) — emitted as a comment with
      the assembly/class name, not a `CREATE TYPE ... EXTERNAL NAME` statement, since
      recreating the type requires deploying the assembly first (out of scope)
- [x] Generate `CREATE TYPE` statements (alias and table types)

### Extended Properties ✅
- [x] Extract table descriptions (`src/schema.py: get_extended_properties`)
- [x] Extract column descriptions
- [x] Generate `EXEC sp_addextendedproperty` statements (not plain SQL comments — this
      restores the descriptions as real MS_Description metadata on redeploy, visible in
      SSMS; see 2026-09-19 update)

### Parallel Extraction (Optional) ✅
- [x] Extract objects in parallel using threading (`DatabaseExtractor._run_jobs` in
      `src/extractor.py`) — each of the 15 independent, schema-filtered metadata queries
      (schemas, types, sequences, tables, extended properties, constraints, indexes,
      views, view dependencies, procedures, functions, triggers) and each table's seed
      data extraction runs on its own `DatabaseConnection` via `ThreadPoolExecutor`,
      since pyodbc connections/cursors aren't thread-safe and can't be shared across
      threads. `--no-parallel` (CLI) / `parallel=False` (API) falls back to the original
      sequential behavior on a single shared connection. Default: parallel, 8 workers
      (`--max-workers`).
- [ ] Benchmark performance improvement — not done; needs a real DB with meaningful
      network/query latency to be meaningful (mocked unit tests can't show a real
      speedup). See Phase 6 Testing for the same "needs a real DB" caveat.

### Testing
- [x] Unit tests for sequence extraction (`tests/test_schema.py`, `tests/test_formatter.py`)
- [x] Unit tests for extended properties (`tests/test_schema.py`, `tests/test_formatter.py`)
- [x] Unit tests for user-defined types (`tests/test_schema.py`, `tests/test_formatter.py`)
- [x] Unit tests for parallel/sequential job execution (`tests/test_extractor.py`)
- [ ] Integration tests

---

## Phase 8: Error Handling and Polish (Week 8)

### Error Handling
- [x] Connection error handling with retries (`src/connection.py:DatabaseConnection.connect`,
      pre-existing: exponential backoff, `max_retries`)
- [x] Permission error handling (clear messages) — `PermissionDeniedError` for object-level
      denials during query execution (`src/connection.py:execute_query`); login-time
      "Cannot open database" (SQL Server error 4060) is ambiguous between "doesn't exist"
      and "login has no access" by design (SQL Server uses identical wording for both to
      avoid leaking which case it is), so `DatabaseAccessError` states that explicitly
      rather than asserting one
- [x] Invalid argument validation — `--user`/`--password` without `--windows-auth`,
      Click's own required-option/choice validation, and range checks on `--port`
      (1-65535), `--max-rows` (positive), `--max-workers` (>=1) all map to exit 5.
      `--tables`/`--schemas` format is deliberately left as warn-and-skip at runtime
      (not upfront validation) — an invalid entry there is dropped with a warning,
      not a hard failure (explicit decision, not an oversight)
- [ ] SQL syntax validation (dry-run mode)
- [x] Detailed error messages with troubleshooting hints — each `except` branch in
      `src/cli.py`'s `_run()` prints a one-line `Hint:` tailored to that exit code
      (e.g. check firewall/port for connection errors, check credentials for auth
      errors, rerun with `--verbose` for unclassified ones)

### Logging and Progress
- [x] Progress bars for long operations (using `tqdm` or `rich`) — `create_progress()`
      (`src/utils.py`) is wired into `DatabaseExtractor._run_jobs` (`src/extractor.py`),
      covering the metadata-extraction and seed-data-extraction job batches; disabled via
      `--quiet` (`show_progress=not quiet` in `src/cli.py`)
- [x] Verbose mode for debugging (`--verbose`, pre-existing)
- [x] Quiet mode for CI/CD (`--quiet`, pre-existing)
- [x] Log file output (`--log-file`, pre-existing)

### Exit Codes
- [x] Define exit codes for different error types (`src/utils.py`: `AuthenticationError`,
      `DatabaseAccessError`, `PermissionDeniedError`, `ExtractionError`, `OutputError`
      under `SQLExtractError`/`ConnectionError`)
- [x] Return appropriate exit codes (`src/cli.py`: 1 connection, 2 auth, 3 database
      access, 4 permission denied, 5 invalid arguments, 10 extraction error, 11 output
      write error — matches the scheme in CLAUDE.md)

### Documentation
- [ ] Complete README.md
- [ ] Add usage examples
- [ ] Add troubleshooting section
- [ ] Add FAQ

### Testing
- [ ] Test all error scenarios
- [ ] Test all CLI flags and options
- [ ] Test on different SQL Server versions (2012, 2016, 2019, 2022)
- [ ] Test on Azure SQL Database
- [ ] Test on Windows, Linux, macOS

---

## Phase 9: Packaging and Distribution (Week 9)

### Packaging
- [ ] Create `pyproject.toml` for Poetry or setuptools
- [ ] Define package metadata (name, version, author, license)
- [ ] Create wheel and source distribution
- [ ] Test installation with pip

### Docker
- [ ] Create Dockerfile
- [ ] Create Docker Compose for testing
- [ ] Push to Docker Hub
- [ ] Test Docker image on different platforms

### CI/CD
- [ ] Set up GitHub Actions or GitLab CI
  - [ ] Run tests on push
  - [ ] Run tests on multiple Python versions (3.9, 3.10, 3.11, 3.12)
  - [ ] Run tests on multiple platforms (Windows, Linux, macOS)
  - [ ] Build and publish Docker image
  - [ ] Build and publish to PyPI (on tag)
- [ ] Set up code coverage reporting (Codecov or Coveralls)
- [ ] Set up linting (black, mypy, pylint)

### Release
- [ ] Tag v1.0.0
- [ ] Create GitHub release with changelog
- [ ] Publish to PyPI
- [ ] Announce on social media, forums

---

## Phase 10: Future Enhancements (Post v1.0)

See [FUTURE.md](FUTURE.md) for:
- [ ] Permissions extraction (GRANT/DENY)
- [ ] Comparison mode (diff two databases)
- [ ] GUI frontend (web or desktop)
- [ ] Database documentation generation (HTML/Markdown)
- [ ] Azure AD authentication
- [ ] Always Encrypted column support
- [ ] Graph database support
- [ ] SQL Agent job extraction

---

## Testing Milestones

### Milestone 1: Unit Test Coverage ✅
- [x] Achieve 80%+ test coverage (77 passing tests)
- [x] All core modules have unit tests
- [x] All edge cases covered

### Milestone 2: Integration Test Suite
- [ ] Create sample database with 50+ tables, 100+ procedures
- [ ] Full extraction and re-deployment test
- [ ] Verify data integrity
- [ ] Performance benchmarks

### Milestone 3: Cross-Platform Testing
- [ ] Test on Windows 10/11
- [ ] Test on Ubuntu 20.04, 22.04
- [ ] Test on macOS 12+
- [ ] Test on Docker

### Milestone 4: SQL Server Version Testing
- [ ] Test on SQL Server 2012
- [ ] Test on SQL Server 2016
- [ ] Test on SQL Server 2019
- [ ] Test on SQL Server 2022
- [ ] Test on Azure SQL Database
- [ ] Test on Azure SQL Managed Instance

---

## Documentation Milestones

### Milestone 1: Basic Documentation ✅
- [x] README.md with quick start
- [x] REQUIREMENTS.md with detailed specs
- [x] TODO.md with implementation checklist
- [x] SETUP.md with development guide
- [x] CODE_OF_CONDUCT.md
- [x] CONTRIBUTING.md
- [x] GitHub issue templates

### Milestone 2: User Guide
- [ ] Installation instructions
- [ ] Usage examples (common scenarios)
- [ ] Command reference
- [ ] Troubleshooting guide
- [ ] FAQ

### Milestone 3: Developer Guide
- [ ] Architecture documentation
- [ ] API reference
- [ ] Contributing guidelines
- [ ] Code style guide

---

## Performance Targets

- [ ] Extract 100-table database in <10 seconds
- [ ] Extract 1000-table database in <60 seconds
- [ ] Extract 100K rows of seed data in <10 seconds
- [ ] Memory usage <500MB for large databases
- [ ] Support databases up to 10,000 tables

---

## Quality Gates

Before releasing v1.0:
- [ ] 80%+ test coverage
- [ ] Zero critical bugs
- [ ] All acceptance criteria met (see REQUIREMENTS.md)
- [ ] Documentation complete
- [ ] Tested on all target platforms
- [ ] Performance targets met
- [ ] Code review complete
- [ ] Security audit complete

---

## Recent Updates

### 2026-09-19: Troubleshooting Hints in Error Messages (Phase 8, partial)
- **Added**: a `Hint:` line under each exception branch in `src/cli.py`'s `_run()`,
  tailored to that exit code — e.g. connection errors point at
  `--server`/`--port`/firewall, authentication errors point at credentials and
  SQL-auth being enabled, database-access errors mention the 4060 ambiguity, output
  errors point at disk space/permissions on `--output`, and the unclassified (99)
  branch suggests `--verbose` and reporting a bug.
- **Tests**: extended the existing exit-code parametrized test in `tests/test_cli.py`
  to also assert `"Hint:"` appears in the output for every exception type. Full suite:
  138 passed, 9 skipped (need real DB).

### 2026-09-19: Deeper Argument Validation (Phase 8, partial)
- **Added**: range checks in `src/cli.py`'s `_run()`, alongside the existing
  `--user`/`--password` check — `--port` must be 1-65535, `--max-rows` (if given) must
  be positive, `--max-workers` must be at least 1. All three exit 5, matching the
  existing "Invalid Arguments" code.
- **Explicit decision**: `--tables`/`--schemas` entry format (e.g. `schema.table`) is
  *not* validated upfront. It stays as the existing runtime behavior in
  `src/extractor.py` (`extract()`): an invalid `--tables` entry logs a warning and is
  skipped, the rest of the extraction still succeeds with exit 0. Making that fail fast
  would be a behavior change for existing callers and was declined.
- **Tests**: 5 new parametrized cases in `tests/test_cli.py`. Full suite: 138 passed,
  9 skipped (need real DB).

### 2026-09-19: Progress Bars (Phase 8, partial)
- **Added**: `progress`/`task_description` params to `DatabaseExtractor._run_jobs()`
  (`src/extractor.py`) — adds a `rich` progress task sized to the job batch and advances
  it as each job completes, for both the sequential and parallel (`ThreadPoolExecutor`)
  branches.
- **Added**: `show_progress: bool = True` param on `DatabaseExtractor.extract()`. Wraps
  the connect + metadata-extraction + seed-data-extraction stage in a started/stopped
  `Progress` instance (from `create_progress()`), covering both `_run_jobs()` calls
  (`"Extracting metadata"`, `"Extracting seed data"`). The output-writing stage
  (single/per-object/modular file generation) is local disk I/O, not network-bound, and
  was left without a progress bar.
- **Changed**: `src/utils.py` now holds one shared `rich.console.Console` instance, used
  by both `RichHandler` (in `setup_logging`) and `create_progress()`. Rich's `Live`
  display (used internally by `Progress`) and logging need to share a console to render
  correctly together — two independent consoles writing to the same terminal would
  garble each other's output.
- **Wired into**: `src/cli.py` passes `show_progress=not quiet` to `extract()`, so
  `--quiet` suppresses the progress bar along with regular log output.
- **Tests**: no new automated tests (progress-bar rendering isn't meaningfully
  assertable via mocked unit tests); verified manually with a mocked `_run_jobs` that
  sleeps between jobs. Full suite: 133 passed, 9 skipped (need real DB).

### 2026-09-19: Structured Exit Codes (Phase 8, partial)
- **Added**: `AuthenticationError`, `DatabaseAccessError`, `PermissionDeniedError` in
  `src/utils.py`, all subclasses of `ConnectionError`.
- **Changed**: `DatabaseConnection.connect()` (`src/connection.py`) now raises
  `AuthenticationError` or `DatabaseAccessError` instead of a generic `ConnectionError`,
  distinguished by message text as before. `DatabaseAccessError` covers SQL Server error
  4060 ("Cannot open database"), which is worded identically whether the database
  doesn't exist or the login just lacks access to it (by design, so an unauthorized
  login can't tell which); the raised message says so explicitly instead of asserting
  "not found". `execute_query()` now raises `PermissionDeniedError` for object-level
  permission denials (e.g. `SELECT`/`EXECUTE` denied on a table or procedure).
- **Changed**: `DatabaseExtractor.extract()` (`src/extractor.py`) no longer wraps
  everything in one `try/except Exception → ExtractionError`. Split into three stages —
  output-directory preparation, connect + metadata extraction, output-file writing — so
  a connection-stage error keeps its specific type instead of being flattened, and an
  `OSError` while writing output now raises `OutputError` (previously such errors were
  silently absorbed into `ExtractionError`, since `OutputError` existed in `src/utils.py`
  but was never actually raised anywhere).
- **Changed**: `src/cli.py`'s exception→exit-code mapping now matches the scheme
  documented in CLAUDE.md: 1 connection, 2 authentication, 3 database access,
  4 permission denied, 5 invalid arguments, 10 extraction error, 11 output write error,
  99 unexpected/internal error. Previously there were only 3 buckets (`ConnectionError`→1,
  any other `SQLExtractError`→10, everything else→11), which conflated all of the above.
  99 is a new addition to CLAUDE.md's documented scheme — none of the original codes
  covered a genuinely unclassified exception (one that isn't any of `SQLExtractError`'s
  subclasses or a `ValueError`).
- **Added**: a `main()` wrapper around the Click command (renamed to `_run`) so Click's
  own argument-validation errors (missing `--server`/`--database`, invalid `--format`
  choice) also exit 5, instead of Click's own default exit code 2.
- **Not done** (deliberately out of scope for this pass — see checklist above):
  SQL syntax validation/dry-run mode, troubleshooting hints in error messages, deeper
  argument validation (e.g. `--max-rows` range checking), progress bars.
- **Tests**: 4 new in `tests/test_connection.py`, 5 new in `tests/test_extractor.py`,
  new `tests/test_cli.py` (11 tests) covering the full exit-code mapping via
  `click.testing.CliRunner`. Full suite: 133 passed, 9 skipped (need real DB).

### 2026-09-19: Full Extract/Redeploy Integration Test (Phase 4 + Phase 6 testing gaps closed)
- **Added**: `tests/test_integration.py:TestFullRoundTrip`, a real (non-mocked) integration
  test gated behind `SQLEXTRACT_TEST_SERVER` (Windows Auth). Deploys
  `tests/fixtures/test_schema.sql` to a scratch database, runs `DatabaseExtractor.extract()`,
  redeploys the output to a second scratch database, and compares object/row counts —
  parametrized across all three output formats (`modular`, `single`, `per-object`). Also
  verifies the new trigger (below) actually fires post-redeploy.
- **Added**: one trigger to `tests/fixtures/test_schema.sql`
  (`MQTT.trg_ReceiverConfig_SetModifiedDate`) — the only Phase 4 object type with no
  integration coverage before this.
- **Fixed** (all previously uncovered by any unit test): 
  - `deploy.sh`/`deploy.ps1` had no `TrustServerCertificate` option, so they failed against
    any self-signed instance (the ODBC Driver 18 default). `SQLFormatter` now takes
    `trust_cert`, threaded from `ConnectionConfig`, and passes `sqlcmd -C` when set.
  - Computed columns generated invalid `CREATE TABLE` SQL (a data type before `AS (...)`,
    which SQL Server rejects) and silently dropped `PERSISTED`. Added `ColumnInfo.is_persisted`
    and fixed `_format_column_def` in `src/formatter.py`.
  - A view definition with a leading comment in the same batch as `CREATE VIEW` produced a
    duplicated `CREATE VIEW` statement on redeploy. `format_view()` now always emits the
    captured definition as-is (matching how procedures/functions/triggers already worked),
    removing the buggy "clean up" branch.
  - `nvarchar(MAX)`/`varchar(MAX)`/`varbinary(MAX)` columns lost their `MAX` marker
    (`max_length == -1` was being collapsed to `None` in `src/schema.py`), producing a bare
    type that SQL Server defaults to size 1 — causing truncation errors on any real data.
  - `BIT` column values were rendered as Python `True`/`False` (pyodbc's native type for
    `BIT`), which are not valid SQL literals and get parsed as invalid column references.
    `src/seed_data.py` now emits `1`/`0`.
  - Per-object format dumped PK/unique/FK/check constraints into one flat `Constraints/`
    folder with no ordering, so a plain alphabetical deploy could run a FK before the PK it
    references. Split into `Constraints/01_PrimaryKeys/`, `02_UniqueConstraints/`,
    `03_ForeignKeys/`, `04_CheckConstraints/`. Also fixed the per-object deployment
    instructions in the generated `README.md`, which were missing `Schemas/`/`Types/`/
    `Sequences/` entirely and listed the wrong order.
- **Tests**: 4 new unit tests (`test_format_table_computed_column`,
  `test_format_view_with_leading_comment` in `tests/test_formatter.py`,
  `test_extract_bit_column_uses_1_0_not_python_bool` in `tests/test_seed_data.py`, plus the
  corrected `test_get_table_columns_nvarchar_max` assertion), and 10 new integration tests
  (3 output formats × 3 checks + 1 modular-only file-listing check). Full unit suite: 117
  passed. Integration suite: 10 passed against `(local)\MSSQL2017`.

### 2026-09-19: User-Defined Types and Parallel Extraction (Phase 7 complete)
- **Added**: `SchemaReader.get_user_defined_types()` in `src/schema.py`, covering three
  kinds (`kind` field): `alias` (`sys.types`, `CREATE TYPE ... FROM <base type>`), `table`
  (`sys.table_types` + `sys.columns` + an inline `PRIMARY KEY` from `sys.indexes`,
  `CREATE TYPE ... AS TABLE`), and `clr` (`sys.assembly_types`, metadata only — emitted
  as a comment, since recreating it needs the assembly deployed first, out of scope).
- **Added**: `SQLFormatter.format_user_defined_type()` (+ `_format_alias_type`,
  `_format_table_type`, `_format_clr_type_comment`). Refactored `_format_data_type` to
  take plain values instead of a `ColumnInfo`, and extracted `_format_column_def`, so
  both `format_table` and the new table-type formatting share the same column-rendering
  logic.
- **Wired into**: all three output formats and `write_readme()`. Types are extracted and
  written *before* sequences/tables, since a column's data type may reference one.
- **Breaking change**: modular output filenames renumbered again — `02_CREATE_TYPES.sql`
  is new; sequences/tables/constraints/indexes/triggers/views/procedures/functions/
  deferred-FKs/seed-data all shifted up by one (03-12, previously 02-11).
- **Added**: `DatabaseExtractor._run_jobs()` in `src/extractor.py` — runs the 15
  independent, schema-filtered metadata queries (and, when extracting seed data, each
  table's data pull) concurrently via `ThreadPoolExecutor`, each on its own
  `DatabaseConnection` (pyodbc connections/cursors are not thread-safe, so they can't be
  shared across threads). New `parallel: bool = True` / `max_workers: int = 8` params on
  `DatabaseExtractor.extract()`, and `--no-parallel` / `--max-workers` CLI flags. Output
  is identical either way — only the extraction strategy changes; results are
  reassembled in dependency order, not completion order.
- **Added**: `DatabaseConnection.label` — each per-job connection is now tagged with its
  job name (e.g. `[tables]`, `[triggers]`) and every log line from that connection
  (connecting, established, retrying, closed) is prefixed with it, so the many
  concurrent "Connecting..." / "Connection established" log lines from parallel
  extraction can be told apart.
- **Not done**: benchmarking the actual speedup — needs a real DB with real network/query
  latency to be meaningful, same caveat as the Phase 6 integration tests.
- **Tests**: 4 new unit tests in `tests/test_schema.py`, 7 new in `tests/test_formatter.py`,
  4 new in `tests/test_extractor.py`, 1 new in `tests/test_connection.py` (label
  prefixing), plus a manual end-to-end smoke test of the full `extract()` pipeline with
  a mocked connection (types file, table file, deploy scripts, parallel execution all
  verified). Full suite: 114 passed, 4 skipped (need real DB).

### 2026-09-19: Extended Properties (Table/Column Descriptions)
- **Added**: `SchemaReader.get_extended_properties()` in `src/schema.py`, querying
  `sys.extended_properties` (`class = 1`, `name = 'MS_Description'`) joined to
  `sys.tables`/`sys.columns`, grouped by `(schema_name, table_name)` into a dict with
  `table_description` and a `columns` dict.
- **Added**: `SQLFormatter.format_extended_properties()` — emits `EXEC sys.sp_addextendedproperty`
  statements for the table description and each described column.
- **Deviated from the original checklist wording** ("include as SQL comments"): plain
  comments would be lost on redeploy. `sp_addextendedproperty` calls are still human-readable
  in the generated SQL, but also restore the descriptions as real MS_Description metadata
  (visible in SSMS) on the redeployed database, which is more useful for an extraction/
  redeployment tool.
- **Wired into**: all three output formats, written immediately after each table's
  `CREATE TABLE` statement (single file: same TABLES section; per-object: appended to the
  table's own file; modular: same `03_CREATE_TABLES.sql`). No new modular file and no
  filename renumbering.
- **Tests**: 2 new unit tests in `tests/test_schema.py`, 4 new in `tests/test_formatter.py`.
  Full suite: 102 passed, 4 skipped (need real DB).

### 2026-09-19: Sequence Extraction
- **Added**: `SchemaReader.get_sequences()` in `src/schema.py`, querying `sys.sequences`
  for START WITH, INCREMENT BY, MIN/MAX values, CYCLE, CACHE/NO CACHE, and data type
  (including `decimal`/`numeric` precision/scale via `sys.sequences.precision`/`.scale`).
- **Added**: `SQLFormatter.format_sequence()` — emits `CREATE SEQUENCE`, omitting the
  `AS <type>` clause only for the default `bigint`.
- **Wired into**: all three output formats and `write_readme()`. Sequences are extracted
  and written *before* tables, since a column's `DEFAULT NEXT VALUE FOR <sequence>` needs
  the sequence to already exist.
- **Breaking change**: modular output filenames renumbered again — `02_CREATE_SEQUENCES.sql`
  is new; tables/constraints/indexes/triggers/views/procedures/functions/deferred-FKs/
  seed-data all shifted up by one (03-11, previously 02-10).
- **Tests**: 2 new unit tests in `tests/test_schema.py`, 2 new in `tests/test_formatter.py`,
  plus a manual end-to-end smoke test of the modular output, deploy script, and README.
  Full suite: 96 passed, 4 skipped (need real DB).

### 2026-09-19: Deployment Scripts and README Generation
- **Added**: `SQLFormatter._write_deploy_scripts()`, called from `write_modular_format()`.
  Generates `deploy.sh` and `deploy.ps1` listing only the numbered `.sql` files that were
  actually written (empty sections are skipped, as before), in deployment order, run via
  `sqlcmd`. `deploy.sh` is written with executable permissions.
- **Added**: `SQLFormatter.write_readme()`, called once from `DatabaseExtractor.extract()`
  after whichever format was written. Generates `README.md` with object counts, per-type
  object lists, a short note on dependency ordering (tables/views/deferred FKs), and
  format-specific deployment instructions. Applies to all three output formats, not just
  modular.
- **Tests**: 2 new unit tests in `tests/test_formatter.py`, plus manual end-to-end checks
  of the generated `deploy.sh`/`deploy.ps1`/`README.md` content. Full suite: 92 passed,
  4 skipped (need real DB).
- **Still open**: no integration test extracts with each format and verifies the resulting
  file structure or actually deploys it (needs a real DB — see Phase 6 Testing).

### 2026-09-19: Trigger Extraction (DML table triggers only)
- **Added**: `SchemaReader.get_triggers()` in `src/schema.py`, querying `sys.triggers` +
  `sys.trigger_events` for AFTER/INSTEAD OF table triggers, their INSERT/UPDATE/DELETE
  events, enabled/disabled state, and definition (encrypted triggers warn and skip,
  matching the procedure/function/view pattern).
- **Added**: `SQLFormatter.format_trigger()` — emits the `CREATE TRIGGER` statement, plus
  a trailing `DISABLE TRIGGER` statement if the source trigger was disabled (there's no
  `DISABLED` clause on `CREATE TRIGGER` itself).
- **Scoped out** (by explicit decision, not an oversight): database-level DDL triggers
  (`ON DATABASE`/`ON ALL SERVER` — a different catalog/event model) and explicit
  first/last trigger execution order (`sp_settriggerorder`) — both rare in practice
  and roughly doubling the scope of this pass.
- **Breaking change**: modular output filenames were renumbered to insert triggers —
  `05_CREATE_TRIGGERS.sql` is new; views/procedures/functions/deferred-FKs/seed-data
  shifted from 05-09 to 06-10. Anything scripted against the old fixed filenames
  (e.g. `09_SEED_DATA.sql`) will need updating. No versioned release exists yet, so this
  was done without a deprecation path.
- **Tests**: 4 new unit tests in `tests/test_schema.py`, 2 new in `tests/test_formatter.py`.
  Full suite: 90 passed, 4 skipped (need real DB).

### 2026-09-19: View Dependency Ordering
- **Added**: `SchemaReader.get_view_dependencies()` in `src/schema.py`, querying
  `sys.sql_expression_dependencies` for view-to-view references.
- **Added**: `order_views_by_dependency()` in `src/dependency.py`, reusing the existing
  `DependencyGraph`/topological sort to order a view after any view it references.
  Falls back to original order with a warning if a circular dependency is ever found
  (shouldn't happen — SQL Server doesn't allow circular view creation).
- **Wired into**: `DatabaseExtractor.extract()` in `src/extractor.py`, so all three
  output formats now emit views in dependency-safe order.
- **Tests**: 2 new unit tests in `tests/test_schema.py`, 5 new unit tests in
  `tests/test_dependency.py`. Full suite: 84 passed, 4 skipped (need real DB).

### 2026-09-19: Checklist Reconciled with Actual Code State
- **Found**: This checklist had drifted significantly from the codebase (no updates since 2025-10-09).
- **Phase 4** (procedures/functions): largely implemented, but in `src/schema.py` + `src/formatter.py`
  rather than the planned standalone `src/procedures.py`/`src/functions.py` modules. Triggers remain unimplemented.
- **Phase 6** (output formatting): single-file, per-object, and modular formats are all implemented in
  `src/formatter.py` and wired into the CLI via `--format`. Deployment script and README generation are not done.
- **Phase 3**: view dependency ordering was marked done but is not implemented (`src/dependency.py` only orders tables/FKs).
- Recent commits not previously reflected here: `--clean`, `--omit-ts`, `--no-header` CLI options, and
  fixes for blank lines / crash risk in extracted views/procedures/functions.

### 2025-10-09: Critical Bug Fix - Topological Sort
- **Fixed**: Inverted topological sort algorithm in `src/dependency.py:94-99`
- **Issue**: Tables were ordered with dependencies BEFORE their parents (backwards)
- **Root Cause**: In-degree calculation counted wrong direction
- **Solution**: Changed from iterative increment to direct length calculation
- **Impact**: All dependency ordering now works correctly
- **Tests**: Updated 13 dependency tests to expect correct ordering - all passing ✅

### 2025-10-09: Complete Test Infrastructure
- **Created**: 10 comprehensive test files with 77 passing tests
- **Coverage**: All core modules (connection, schema, dependency, constraints, indexes, seed_data, formatter, extractor, utils)
- **Test Types**: Unit tests (73), integration tests (4 skipped, need real DB)
- **Test Approach**: Mock-based testing - no database required for unit tests
- **Quality**: 100% test success rate, comprehensive edge case coverage

### 2025-10-09: Repository Enhancement
- **Added**: CODE_OF_CONDUCT.md (Contributor Covenant)
- **Enhanced**: README.md with badges, ASCII demo, performance metrics
- **Added**: GitHub issue templates (bug reports, features, questions)
- **Status**: Professional open-source project ready for community contribution

---

**Last Updated**: 2026-09-19
**Status**: Phases 1, 2, 3, 5, 6, 7 Complete; Phase 4 Mostly Complete
**Current Phase**: Remaining gaps: procedure parameter parsing, procedure dependency
ordering, CLR function metadata, database-level DDL triggers + explicit trigger order
(Phase 4, deliberately deferred — see 2026-09-19 update). Phase 6 and Phase 4's integration
tests are now done against a real DB (see 2026-09-19 update); Phase 7's parallel-extraction
speedup is still unbenchmarked (needs a real DB with meaningful network/query latency).
Phase 8 (error handling/polish) is now partially started — exit codes,
permission/database-access error mapping, progress bars, numeric argument validation,
and troubleshooting hints are done (see 2026-09-19 updates); dry-run mode remains.
Phase 9 (packaging/distribution) not started.
**Estimated Completion**: Not re-estimated — verify remaining Phase 8-9 scope before committing to a timeline
