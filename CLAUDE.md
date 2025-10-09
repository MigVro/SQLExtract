# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SQL Extract** is a modern, cross-platform CLI tool for extracting complete SQL Server database schemas, stored procedures, and seed data. It addresses limitations in existing tools like `mssql-scripter` (Python 2.7 dependency) and SSMS (Windows-only GUI).

**Core Value Proposition:**
- Intelligent dependency ordering for schema objects
- Flexible seed data extraction with configurable filters
- Multiple output formats (single file, per-object, modular)
- CI/CD ready with proper exit codes and logging

**Target Users:** DevOps engineers, DBAs, development teams managing schema versioning and database migrations.

## Development Setup

### Prerequisites
- **Python 3.9+** required
- **ODBC Driver for SQL Server 17 or 18** - Platform-specific installation:
  - Linux: `sudo apt-get install msodbcsql18`
  - macOS: `brew install msodbcsql18`
  - Windows: Included with Windows
- **SQL Server instance** for testing (Docker recommended)

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies (when available)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Or install in editable mode
pip install -e .
```

### Test Database Setup (Docker - Recommended)
```bash
# Start SQL Server container
docker run -d \
  --name sqlextract-test \
  -e 'ACCEPT_EULA=Y' \
  -e 'SA_PASSWORD=YourStrong@Passw0rd' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest

# Wait for startup (30 seconds)
sleep 30

# Create test database
docker exec sqlextract-test /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' \
  -Q 'CREATE DATABASE TestDB'

# Run test schema (when available)
docker exec -i sqlextract-test /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' -d TestDB \
  < tests/fixtures/test_schema.sql
```

## Common Commands

### Running the CLI
```bash
# Display help
python sqlextract.py --help

# Basic extraction (when implemented)
./sqlextract.py \
    --server localhost \
    --database TestDB \
    --user sa \
    --password "YourStrong@Passw0rd" \
    --output ./output

# Extract only stored procedures
./sqlextract.py --server localhost --database MyDb --objects procedures --output ./procs

# Extract seed data from specific tables
./sqlextract.py --server localhost --database MyDb --seed-data --tables "MQTT.ReceiverConfig,MQTT.SourceConfig"

# Extract to modular files (recommended for deployment)
./sqlextract.py --server localhost --database MyDb --format modular --output ./deploy
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_extractor.py

# Run specific test
pytest tests/test_extractor.py::test_extract_tables

# Run in verbose mode
pytest -v
```

### Code Quality
```bash
# Format all code
black src/ tests/

# Check formatting without changes
black --check src/

# Type checking
mypy src/

# Linting
pylint src/
flake8 src/
```

### Docker Operations
```bash
# Build image
docker build -t sqlextract:latest .

# Run container
docker run --rm sqlextract:latest --help

# Test with local database
docker run --rm --network host \
  sqlextract:latest \
  --server localhost \
  --database TestDB \
  --user sa \
  --password YourStrong@Passw0rd \
  --output /output
```

## Architecture Overview

### Planned Module Structure
```
sqlextract/
├── sqlextract.py           # CLI entry point
├── src/
│   ├── cli.py              # Argument parsing (Click framework)
│   ├── connection.py       # Database connectivity (pyodbc)
│   ├── extractor.py        # Core extraction orchestration
│   ├── schema.py           # Schema introspection
│   ├── tables.py           # Table extraction
│   ├── constraints.py      # Constraint extraction (PK, FK, unique, check, default)
│   ├── indexes.py          # Index extraction
│   ├── views.py            # View extraction
│   ├── procedures.py       # Stored procedure extraction
│   ├── functions.py        # Function extraction (scalar, table-valued)
│   ├── triggers.py         # Trigger extraction
│   ├── sequences.py        # Sequence extraction
│   ├── seed_data.py        # Data extraction with filtering
│   ├── dependency.py       # Dependency analysis & topological sort
│   ├── formatter.py        # Output formatting (single/per-object/modular)
│   └── utils.py            # Utilities and logging
└── tests/
    ├── conftest.py         # Pytest configuration
    ├── test_*.py           # Unit tests per module
    └── fixtures/
        └── test_schema.sql # Test database schema
```

### Key Architectural Patterns

**Dependency Ordering:**
- Build directed graph from FK relationships
- Topological sort for creation order
- Handle circular dependencies by creating tables first, adding FKs later

**SQL Generation:**
- Use Jinja2 templates for SQL statement generation
- Support SQL Server 2012+ syntax
- Include metadata comments (extraction date, tool version)
- Always use qualified names (`[schema].[object]`)

**Data Extraction:**
- Stream large result sets (don't load entire DB into memory)
- Handle identity columns with `SET IDENTITY_INSERT ON/OFF`
- Escape special characters in string values
- Support batching (e.g., 100 INSERT statements per batch)

**Output Formats:**
1. **Single File**: All objects in one file with section comments
2. **Per-Object**: Separate files organized in subdirectories by type
3. **Modular**: Numbered deployment files (01_CREATE_SCHEMAS.sql, 02_CREATE_TABLES.sql, etc.)

### Database Queries Strategy
Use system catalog views for metadata extraction:
- `INFORMATION_SCHEMA.*` for standard objects
- `sys.indexes`, `sys.index_columns` for index details
- `sys.objects`, `sys.procedures`, `sys.views` for programmability objects
- `OBJECT_DEFINITION()` for procedure/view source code
- `sys.extended_properties` for descriptions

## Critical Implementation Notes

### Connection Handling
- Support Windows Authentication (Windows only) and SQL Authentication (all platforms)
- Implement retry logic with exponential backoff for connection failures
- Use connection pooling for efficiency
- For Azure SQL: always use `TrustServerCertificate=yes` or `--trust-cert` flag to handle SSL certificates

### WSL to SQL Server Connection
When testing from WSL with SQL Server on Windows host:
```bash
# Use WSL host IP, not localhost
Server: 172.31.208.1,1433
sqlcmd -S 172.31.208.1,1433 -U sa -P YourPassword -C -d DatabaseName
```

### Error Handling & Exit Codes
Return specific exit codes for CI/CD integration:
- `0` - Success
- `1` - Connection error
- `2` - Authentication error
- `3` - Database not found
- `4` - Permission denied
- `5` - Invalid arguments
- `10` - Extraction error
- `11` - Output write error

### Security Considerations
- Never log passwords in plain text
- Support environment variable substitution for credentials
- Sanitize extracted stored procedures for embedded passwords
- Warn if connection is not encrypted

## Testing Strategy

### Test Coverage Requirements
- **Target**: 80%+ test coverage
- **Unit Tests**: Test each extraction module independently with mocked DB connections
- **Integration Tests**: Test against real SQL Server instance (Docker)
- **End-to-End Tests**: Full extraction workflows with all output formats

### Testing Milestones
1. **Cross-Platform**: Test on Windows 10/11, Ubuntu 20.04+, macOS 12+
2. **SQL Server Versions**: Test on SQL Server 2012, 2016, 2019, 2022, Azure SQL Database, Azure SQL Managed Instance
3. **Performance**: Extract 1000-table database in <60 seconds, 100K rows in <10 seconds

## Technology Stack

- **Python 3.9+** - Core language
- **pyodbc** - SQL Server connectivity (ODBC-based)
- **Click** - CLI framework
- **Jinja2** - SQL template engine
- **pytest** - Testing framework
- **black** - Code formatter
- **mypy** - Static type checker
- **rich** - Terminal formatting and progress bars

## Development Workflow Requirements

### Code Style
- Follow PEP 8 style guidelines
- Use type hints for all public functions
- Achieve 80%+ test coverage
- Format with black (line length: 100)
- All code must pass mypy type checking

### Test-Driven Development
When implementing features, follow this order:
1. Interface/contract definition
2. **Test creation** (before implementation)
3. Implementation
4. Integration/wiring

### Documentation Requirements
- Include docstrings for all public functions
- Maintain inline documentation for complex logic
- Update README.md with new features
- Add usage examples for new CLI options

## Performance Targets

- Extract 100-table database in <10 seconds
- Extract 1000-table database in <60 seconds
- Extract 100K rows of seed data in <10 seconds
- Memory usage <500MB for large databases
- Support databases up to 10,000 tables

## Out of Scope for v1.0

The following features are documented in FUTURE.md and should NOT be implemented in the initial version:
- Permissions extraction (GRANT/DENY)
- Schema comparison/diff mode
- Linked server extraction
- SQL Agent jobs extraction
- GUI frontend
- Multi-database support (MySQL, PostgreSQL, Oracle)
- Data masking and sampling
- Documentation generation (HTML/Markdown)

## Project Status

**Current Status**: Planning/Design Phase - No implementation yet
**Next Phase**: Phase 1 - Foundation (Project Setup, Core Infrastructure, Schema Introspection)

Refer to TODO.md for the complete 10-phase implementation checklist.
