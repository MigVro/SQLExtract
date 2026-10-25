# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SQL Extract** is a cross-platform CLI (Python 3.9+, pyodbc, Click, rich) that extracts SQL Server schemas, programmability objects and seed data. It replaces `mssql-scripter` (Python 2.7) and SSMS (Windows-only GUI).

- Dependency-ordered output (tables by FK graph, views by view-to-view references)
- Deterministic output across runs (stable ordering of objects and extended properties)
- Seed data extraction with table and row-count filters
- Four output formats; CI/CD-ready exit codes and logging

## Common Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt   # needs ODBC Driver 17/18 for SQL Server

python sqlextract.py --help
python sqlextract.py -s localhost -d TestDB -u sa -P "..." --trust-cert -o ./output
python sqlextract.py -s localhost -d MyDb -w --schemas "dbo,MQTT" --clean
python sqlextract.py -s localhost -d MyDb -w --seed-data --tables "MQTT.ReceiverConfig" --max-rows 1000
python sqlextract.py -s localhost -d MyDb -w --dry-run

pytest                                          # addopts add -v and coverage
pytest tests/test_formatter.py::TestX::test_y
```

- Use the `quality-check` agent for black/mypy/pylint/flake8/pytest runs.
- Use the `integration-test` agent for real-server tests (Docker test DB, `SQLEXTRACT_TEST_SERVER`, WSL).
- A PostToolUse hook runs black on every edited `.py` file.

## Key Patterns

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

**Catalog Queries:** `sys.*` catalog views for metadata, `OBJECT_DEFINITION()` / `sys.sql_modules` for module source, `sys.extended_properties` for descriptions.

**Connections:** retry with exponential backoff (`DatabaseConnection`, `max_retries=3`); one connection per worker in parallel mode (`--max-workers`, default 8), a single one with `--no-parallel`; `--trust-cert` adds `TrustServerCertificate=yes`, otherwise `Encrypt=yes`.

## Output Formats (`--format`)
1. **single**: one file with section comments
2. **per-object**: one file per object in subdirectories by type
3. **per-object-cons**: per-object, but each table's PK, unique/check constraints, indexes and triggers are bundled into its `Tables/` file; FKs stay separate
4. **modular** (default): numbered deployment files plus deploy scripts:
   `01_CREATE_SCHEMAS`, `02_CREATE_TYPES`, `03_CREATE_SEQUENCES`, `04_CREATE_TABLES`, `05_CREATE_CONSTRAINTS`, `06_CREATE_INDEXES`, `07_CREATE_TRIGGERS`, `08_CREATE_VIEWS`, `09_CREATE_PROCEDURES`, `10_CREATE_FUNCTIONS`, `11_CREATE_DEFERRED_FKS`, `12_SEED_DATA`

## Exit Codes
Exceptions derive from `SQLExtractError` (`src/utils.py`) and map to exit codes in `cli.py`:
`0` success, `1` connection, `2` authentication, `3` database not found, `4` permission denied, `5` invalid arguments, `10` extraction, `11` output write, `99` unexpected/unclassified.

## Security
- Never log passwords in plain text
- Not yet implemented: environment variable substitution for credentials, sanitizing extracted modules for embedded passwords

## Development Workflow
- Black with line length 100; type hints on all public functions, must pass mypy
- TDD order: interface/contract → tests → implementation → wiring
- Docstrings on all public functions
- Update README.md for new features, with usage examples for new CLI options
- Unit tests mock DB connections; coverage target 80%+
- `jinja2` and `pyyaml` are declared dependencies but are not imported anywhere in `src/`

## Out of Scope for v1.0
Documented in FUTURE.md; do NOT implement:
permissions (GRANT/DENY), schema diff, linked servers, SQL Agent jobs, GUI, non-SQL-Server databases, data masking/sampling, documentation generation.

## Project Status
See TODO.md.
