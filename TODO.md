# SQL Extract - Implementation Checklist

## Phase 1: Foundation (Week 1)

### Project Setup
- [ ] Initialize Git repository
- [ ] Create Python virtual environment
- [ ] Create `pyproject.toml` or `setup.py`
- [ ] Add `.gitignore` (Python, IDE files)
- [ ] Create `requirements.txt` and `requirements-dev.txt`
- [ ] Set up pre-commit hooks (black, mypy, pytest)
- [ ] Create initial directory structure

### Core Infrastructure
- [ ] Database connection module (`src/connection.py`)
  - [ ] Connection string parsing
  - [ ] Connection pooling
  - [ ] Retry logic with exponential backoff
  - [ ] Connection validation
  - [ ] Support for Windows Auth, SQL Auth, connection strings
- [ ] Logging setup (`src/utils.py`)
  - [ ] Structured logging with levels
  - [ ] File and console output
  - [ ] Progress indicators
- [ ] CLI framework (`src/cli.py`)
  - [ ] Argument parsing with Click
  - [ ] Help text and examples
  - [ ] Version display
  - [ ] Config file loading (YAML/JSON)

### Schema Introspection
- [ ] Schema reader module (`src/schema.py`)
  - [ ] List all schemas
  - [ ] List all tables with columns
  - [ ] List all constraints
  - [ ] List all indexes
  - [ ] List all views, procedures, functions
  - [ ] Filter by schema/pattern

### Testing Infrastructure
- [ ] Set up pytest configuration
- [ ] Create test fixtures (sample database schema)
- [ ] Set up Docker Compose with SQL Server for integration tests
- [ ] Add test coverage reporting
- [ ] Create sample test database script

---

## Phase 2: Table Extraction (Week 2)

### Table Definition Extraction
- [ ] Extract table columns (`src/tables.py`)
  - [ ] Column names, data types, precision, scale
  - [ ] Nullability
  - [ ] Default constraints
  - [ ] Computed columns (persisted/non-persisted)
  - [ ] Identity columns (seed, increment)
- [ ] Generate `CREATE TABLE` statements
  - [ ] Use Jinja2 templates
  - [ ] Include IF EXISTS checks
  - [ ] Proper formatting and indentation

### Constraint Extraction
- [ ] Extract primary keys (`src/constraints.py`)
  - [ ] Single and composite PKs
  - [ ] Named constraints
- [ ] Extract foreign keys
  - [ ] Referenced table/column
  - [ ] ON DELETE/UPDATE actions
  - [ ] Named constraints
- [ ] Extract unique constraints
- [ ] Extract check constraints
  - [ ] Constraint expressions
  - [ ] Enabled/disabled state
- [ ] Extract default constraints

### Dependency Ordering
- [ ] Build dependency graph (`src/dependency.py`)
  - [ ] Parse FK relationships
  - [ ] Topological sort
  - [ ] Detect circular dependencies
- [ ] Order table creation scripts
- [ ] Handle circular FKs (create tables first, add FKs later)

### Testing
- [ ] Unit tests for table extraction
- [ ] Unit tests for constraint extraction
- [ ] Unit tests for dependency ordering
- [ ] Integration test: extract and re-deploy sample database tables

---

## Phase 3: Index and View Extraction (Week 3)

### Index Extraction
- [ ] Extract all indexes (`src/indexes.py`)
  - [ ] Clustered/non-clustered
  - [ ] Unique indexes
  - [ ] Filtered indexes (WHERE clause)
  - [ ] Included columns
  - [ ] Index options (FILLFACTOR, PAD_INDEX, etc.)
- [ ] Exclude PK/unique constraint indexes (already scripted)
- [ ] Generate `CREATE INDEX` statements

### View Extraction
- [ ] Extract view definitions (`src/views.py`)
  - [ ] Use `OBJECT_DEFINITION()` or `sys.sql_modules`
  - [ ] Handle SCHEMABINDING
  - [ ] Handle indexed views
- [ ] Order views by dependencies
- [ ] Generate `CREATE VIEW` statements

### Testing
- [ ] Unit tests for index extraction
- [ ] Unit tests for view extraction
- [ ] Integration test: extract and re-deploy indexes and views

---

## Phase 4: Stored Procedures and Functions (Week 4)

### Stored Procedure Extraction
- [ ] Extract procedure definitions (`src/procedures.py`)
  - [ ] Use `OBJECT_DEFINITION()`
  - [ ] Handle encrypted procedures (warn and skip)
  - [ ] Preserve parameters
- [ ] Generate `CREATE PROCEDURE` statements
- [ ] Handle procedure dependencies (if needed)

### Function Extraction
- [ ] Extract function definitions (`src/functions.py`)
  - [ ] Scalar functions
  - [ ] Inline table-valued functions
  - [ ] Multi-statement table-valued functions
  - [ ] CLR functions (metadata only)
- [ ] Generate `CREATE FUNCTION` statements

### Trigger Extraction
- [ ] Extract trigger definitions (`src/triggers.py`)
  - [ ] Table triggers (AFTER, INSTEAD OF)
  - [ ] Database triggers
  - [ ] Trigger order
  - [ ] Enabled/disabled state
- [ ] Generate `CREATE TRIGGER` statements

### Testing
- [ ] Unit tests for procedure extraction
- [ ] Unit tests for function extraction
- [ ] Unit tests for trigger extraction
- [ ] Integration test: extract and re-deploy all programmability objects

---

## Phase 5: Seed Data Extraction (Week 5)

### Data Extraction
- [ ] Extract table data (`src/seed_data.py`)
  - [ ] SELECT data from tables
  - [ ] Handle NULL values
  - [ ] Handle identity columns
  - [ ] Escape special characters (quotes, backslashes)
  - [ ] Handle binary data (warn and skip or convert to hex)
- [ ] Generate `INSERT` statements
  - [ ] Batching (e.g., 100 rows per batch)
  - [ ] `SET IDENTITY_INSERT ON/OFF`
  - [ ] Proper formatting
- [ ] Support filtering
  - [ ] Table whitelist/blacklist
  - [ ] WHERE clause filters
  - [ ] Row count limits

### Dependency Ordering for Data
- [ ] Order data insertion by FK dependencies
- [ ] Disable FK constraints during data load (optional)
- [ ] Re-enable FK constraints after load

### Testing
- [ ] Unit tests for data extraction
- [ ] Unit tests for INSERT generation
- [ ] Integration test: extract and re-deploy seed data, verify row counts

---

## Phase 6: Output Formatting (Week 6)

### Single File Format
- [ ] Implement single file output (`src/formatter.py`)
  - [ ] Combine all objects into one file
  - [ ] Add section comments
  - [ ] Add batch separators (GO)

### Per-Object Format
- [ ] Implement per-object file output
  - [ ] Create subdirectories (tables/, procedures/, etc.)
  - [ ] Generate filenames from schema and object name
  - [ ] Write each object to separate file

### Modular Format
- [ ] Implement modular file output
  - [ ] Generate numbered files (01_, 02_, etc.)
  - [ ] Group objects by type
  - [ ] Create deployment script (deploy.sh, deploy.ps1)

### Documentation Generation
- [ ] Generate README.md for extracted schema
  - [ ] List of objects
  - [ ] Deployment instructions
  - [ ] Dependencies

### Testing
- [ ] Unit tests for each output format
- [ ] Integration test: extract with each format, verify file structure
- [ ] Integration test: deploy from each format

---

## Phase 7: Advanced Features (Week 7)

### Sequence Extraction
- [ ] Extract sequences (`src/sequences.py`)
  - [ ] START WITH, INCREMENT BY
  - [ ] MIN/MAX values
  - [ ] CYCLE option
- [ ] Generate `CREATE SEQUENCE` statements

### User-Defined Type Extraction
- [ ] Extract user-defined table types
- [ ] Extract alias types
- [ ] Extract CLR types (metadata only)

### Extended Properties
- [ ] Extract table descriptions
- [ ] Extract column descriptions
- [ ] Include as SQL comments in output

### Parallel Extraction (Optional)
- [ ] Extract objects in parallel using threading/multiprocessing
- [ ] Benchmark performance improvement

### Testing
- [ ] Unit tests for all advanced features
- [ ] Integration tests

---

## Phase 8: Error Handling and Polish (Week 8)

### Error Handling
- [ ] Connection error handling with retries
- [ ] Permission error handling (clear messages)
- [ ] Invalid argument validation
- [ ] SQL syntax validation (dry-run mode)
- [ ] Detailed error messages with troubleshooting hints

### Logging and Progress
- [ ] Progress bars for long operations (using `tqdm` or `rich`)
- [ ] Verbose mode for debugging
- [ ] Quiet mode for CI/CD
- [ ] Log file output

### Exit Codes
- [ ] Define exit codes for different error types
- [ ] Return appropriate exit codes

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

### Milestone 1: Unit Test Coverage
- [ ] Achieve 80%+ test coverage
- [ ] All core modules have unit tests
- [ ] All edge cases covered

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

### Milestone 1: Basic Documentation
- [x] README.md with quick start
- [x] REQUIREMENTS.md with detailed specs
- [x] TODO.md with implementation checklist
- [ ] SETUP.md with development guide

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

**Last Updated**: 2025-10-09
**Status**: Not Started
**Estimated Completion**: 10 weeks from start
