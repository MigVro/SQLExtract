# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SQL Extract** is a cross-platform CLI tool for extracting complete SQL Server database schemas, programmability objects, and seed data. It addresses limitations in existing tools like `mssql-scripter` (Python 2.7 dependency) and SSMS (Windows-only GUI).

**Core Value Proposition:**
- Dependency-ordered output (tables by FK graph, views by view-to-view references)
- Deterministic output across runs (stable ordering of objects and extended properties)
- Seed data extraction with table and row-count filters
- Four output formats (single, per-object, per-object-cons, modular)
- CI/CD ready with specific exit codes and logging

**Target Users:** DevOps engineers, DBAs, development teams managing schema versioning and database migrations.

## Development Setup

### Prerequisites
- **Python 3.9+**
- **ODBC Driver for SQL Server 17 or 18**
  - Linux: `sudo apt-get install msodbcsql18`
  - macOS: `brew install msodbcsql18`
  - Windows: install from Microsoft if not present
- **SQL Server instance** for integration tests (local instance or Docker)
- **sqlcmd** on PATH (integration tests shell out to it)

### Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt -r requirements-dev.txt
# or
pip install -e ".[dev]"
```

### Test Database (Docker)
`docker-compose.yml` defines container `sqlextract-test-db` (SQL Server 2022 Developer, `sa` / `Test@Password123!`, port 1433, with a healthcheck). `test-extraction.sh` starts it, creates `SQLExtractTest`, loads `tests/fixtures/test_schema.sql` and runs an extraction.

```bash
docker-compose up -d
```

## Common Commands

### Running the CLI
```bash
python sqlextract.py --help

# SQL auth, default modular format into ./output
python sqlextract.py -s localhost -d TestDB -u sa -P "..." --trust-cert -o ./output

# Windows auth, specific schemas, clean output dir first
python sqlextract.py -s localhost -d MyDb -w --schemas "dbo,MQTT" --clean

# Seed data from specific tables, capped
python sqlextract.py -s localhost -d MyDb -w --seed-data --tables "MQTT.ReceiverConfig,MQTT.SourceConfig" --max-rows 1000

# Report what would be extracted without writing files
python sqlextract.py -s localhost -d MyDb -w --dry-run
```

Options (see `src/cli.py`): `--server/-s`, `--port/-p`, `--database/-d`, `--user/-u`, `--password/-P`, `--windows-auth/-w`, `--trust-cert`, `--output/-o`, `--format`, `--clean`, `--dry-run`, `--omit-ts`, `--no-header`, `--schemas`, `--seed-data`, `--tables`, `--max-rows`, `--no-parallel`, `--max-workers` (default 8), `--verbose/-v`, `--quiet/-q`, `--log-file`.

### Testing
```bash
pytest                                   # all tests; addopts already add -v and coverage
pytest tests/test_formatter.py
pytest tests/test_formatter.py::TestX::test_y
```

Integration tests (`tests/test_integration.py`) are skipped unless `SQLEXTRACT_TEST_SERVER` is set. They connect with **Windows authentication**, recreate a database from the fixture via `sqlcmd -E -C`, and extract in each format.

```powershell
$env:SQLEXTRACT_TEST_SERVER = "localhost"; pytest tests/test_integration.py
```

### Code Quality
```bash
black src/ tests/
black --check src/ tests/
mypy src/
pylint src/
flake8 src/
```

### Docker Image
```bash
docker build -t sqlextract:latest .
docker run --rm sqlextract:latest --help
```

## Architecture

### Module Structure
```
sqlextract.py           # Entry point -> src.cli:main
src/
├── cli.py              # Click command; maps exceptions to exit codes
├── connection.py       # ConnectionConfig (connection string), DatabaseConnection (pyodbc, retry with exponential backoff)
├── extractor.py        # DatabaseExtractor: runs extraction jobs (parallel, one connection per worker), orders results, calls formatter
├── schema.py           # SchemaReader: schemas, tables, columns, sequences, UDTs (alias/table/CLR), views, triggers,
│                       #   procedures, functions (SQL + CLR), parameters, extended properties, view dependencies
├── constraints.py      # ConstraintExtractor: PK, FK, unique, check
├── indexes.py          # IndexExtractor
├── dependency.py       # DependencyGraph, topological sort, table and view ordering
├── seed_data.py        # SeedDataExtractor: INSERT generation with IDENTITY_INSERT handling
├── formatter.py        # SQLFormatter: SQL text generation and all output formats, deploy scripts, README
└── utils.py            # Logging, rich progress, identifier/string escaping, exception hierarchy
tests/
├── conftest.py
├── test_<module>.py    # Unit tests with mocked connections
├── test_integration.py # Real-server tests (see above)
└── fixtures/test_schema.sql
```

### Key Patterns

**Dependency Ordering:**
- Tables: directed graph from FKs, topological sort; FKs that close a cycle are deferred and added after all tables
- Views: ordered by view-to-view references
- Ordering must be deterministic; ties are broken by name

**SQL Generation:**
- Plain Python string building in `SQLFormatter` (no template engine)
- SQL Server 2012+ syntax
- Header comment with tool version and timestamp (`--omit-ts`, `--no-header` to suppress)
- Always qualified, bracketed names (`[schema].[object]`) via `escape_sql_identifier`
- Encrypted views/procedures/functions/triggers are skipped with a warning

**Data Extraction:**
- `SET IDENTITY_INSERT ON/OFF` around identity tables
- Escape string values via `escape_sql_string`
- Stream large result sets; don't load whole tables into memory

**Output Formats (`--format`):**
1. **single**: one file with section comments
2. **per-object**: one file per object in subdirectories by type
3. **per-object-cons**: per-object, but each table's PK, unique/check constraints, indexes and triggers are bundled into its `Tables/` file; FKs stay separate
4. **modular** (default): numbered deployment files plus deploy scripts:
   `01_CREATE_SCHEMAS`, `02_CREATE_TYPES`, `03_CREATE_SEQUENCES`, `04_CREATE_TABLES`, `05_CREATE_CONSTRAINTS`, `06_CREATE_INDEXES`, `07_CREATE_TRIGGERS`, `08_CREATE_VIEWS`, `09_CREATE_PROCEDURES`, `10_CREATE_FUNCTIONS`, `11_CREATE_DEFERRED_FKS`, `12_SEED_DATA`

### Catalog Queries
- `sys.*` catalog views for metadata (`sys.indexes`, `sys.index_columns`, `sys.objects`, `sys.procedures`, `sys.views`, `sys.parameters`, ...)
- `OBJECT_DEFINITION()` / `sys.sql_modules` for module source
- `sys.extended_properties` for descriptions

## Critical Implementation Notes

### Connection Handling
- Windows Authentication (`-w`) and SQL Authentication (`-u`/`-P`)
- Retry with exponential backoff on connect (`DatabaseConnection`, `max_retries=3`)
- Parallel extraction opens one connection per worker (`--max-workers`); `--no-parallel` uses a single connection
- `--trust-cert` adds `TrustServerCertificate=yes`; otherwise `Encrypt=yes`

### WSL to SQL Server Connection
When testing from WSL with SQL Server on the Windows host, use the host IP, not localhost:
```bash
sqlcmd -S 172.31.208.1,1433 -U sa -P YourPassword -C -d DatabaseName
```

### Error Handling & Exit Codes
Exceptions derive from `SQLExtractError` (`src/utils.py`) and map to exit codes in `cli.py`:
- `0` - Success
- `1` - Connection error
- `2` - Authentication error
- `3` - Database not found
- `4` - Permission denied
- `5` - Invalid arguments
- `10` - Extraction error
- `11` - Output write error
- `99` - Unexpected/internal error (unclassified exception)

### Security Considerations
- Never log passwords in plain text
- Not yet implemented: environment variable substitution for credentials, sanitizing extracted modules for embedded passwords

## Testing Strategy
- **Target**: 80%+ coverage
- **Unit tests**: each module independently with mocked DB connections
- **Integration tests**: real SQL Server, all output formats
- **Deferred**: multi-version (2012–2022, Azure SQL DB/MI) and cross-platform (Windows, Ubuntu, macOS) test runs

## Technology Stack
- **Python 3.9+**, **pyodbc**, **Click**, **rich**
- **pytest** (+ pytest-cov, pytest-mock), **black**, **mypy**, **pylint**, **flake8**
- `jinja2` and `pyyaml` are declared dependencies but are not currently imported anywhere in `src/`

## Development Workflow Requirements

### Code Style
- PEP 8, black with line length 100
- Type hints on all public functions; code must pass mypy

### Test-Driven Development
When implementing features, follow this order:
1. Interface/contract definition
2. **Test creation** (before implementation)
3. Implementation
4. Integration/wiring

### Documentation Requirements
- Docstrings on all public functions
- Update README.md with new features and add usage examples for new CLI options

## Performance Targets
- 100-table database in <10 seconds; 1000 tables in <60 seconds
- 100K rows of seed data in <10 seconds
- Memory <500MB for large databases; support up to 10,000 tables

## Out of Scope for v1.0
Documented in FUTURE.md; do NOT implement:
- Permissions extraction (GRANT/DENY)
- Schema comparison/diff mode
- Linked server extraction
- SQL Agent jobs extraction
- GUI frontend
- Multi-database support (MySQL, PostgreSQL, Oracle)
- Data masking and sampling
- Documentation generation (HTML/Markdown)

## Project Status
- Phases 1–3 and 5–8 complete; Phase 4 (procedures/functions) mostly complete
- Open: Phase 9 (packaging, Docker Hub, CI pipeline — no workflows in `.github/` yet), multi-version/cross-platform testing
- See TODO.md for the detailed checklist and recent updates
