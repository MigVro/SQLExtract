# SQL Extract - Detailed Requirements

## 1. Project Overview

**Problem Statement:**
Database schema extraction is a common task in software development, but existing tools have limitations:
- `mssql-scripter` requires Python 2.7 (deprecated)
- SSMS "Generate Scripts" is Windows-only and GUI-based
- `sqlpackage` (dacpac) doesn't extract seed data and requires .NET
- Custom scripts are fragile and hard to maintain

**Solution:**
Build a modern, cross-platform CLI tool that extracts complete SQL Server database schemas with intelligent dependency ordering, seed data extraction, and flexible output formats.

**Target Users:**
- DevOps engineers automating database deployments
- Database administrators managing schema versioning
- Development teams migrating between environments
- CI/CD pipelines requiring schema validation

---

## 2. Functional Requirements

### 2.1 Database Object Extraction

#### 2.1.1 Schemas
- **FR-SCH-001**: Extract all schemas from database
- **FR-SCH-002**: Generate `CREATE SCHEMA` statements
- **FR-SCH-003**: Support schema filtering by name pattern

#### 2.1.2 Tables
- **FR-TBL-001**: Extract all table definitions including:
  - Column names, data types, precision, scale
  - Nullability
  - Default constraints
  - Computed columns (persisted and non-persisted)
  - Identity columns (seed, increment)
- **FR-TBL-002**: Order tables by foreign key dependencies
- **FR-TBL-003**: Support extracting table subsets by schema or pattern
- **FR-TBL-004**: Handle temporal tables (system-versioned)
- **FR-TBL-005**: Extract table extended properties (descriptions)

#### 2.1.3 Constraints
- **FR-CON-001**: Extract Primary Key constraints
- **FR-CON-002**: Extract Foreign Key constraints with:
  - Referenced table/column
  - ON DELETE/ON UPDATE actions
  - Named constraints
- **FR-CON-003**: Extract Unique constraints
- **FR-CON-004**: Extract Check constraints with:
  - Constraint expressions
  - Enabled/disabled state
- **FR-CON-005**: Extract Default constraints
- **FR-CON-006**: Generate constraints after table creation (to handle circular FKs)

#### 2.1.4 Indexes
- **FR-IDX-001**: Extract all indexes including:
  - Clustered/non-clustered
  - Unique indexes
  - Filtered indexes (WHERE clause)
  - Included columns
  - Index options (PAD_INDEX, FILLFACTOR, etc.)
- **FR-IDX-002**: Exclude primary key indexes (already scripted with PKs)
- **FR-IDX-003**: Generate indexes after constraints for performance

#### 2.1.5 Views
- **FR-VIW-001**: Extract all views with complete definitions
- **FR-VIW-002**: Handle view dependencies (order by dependency chain)
- **FR-VIW-003**: Extract indexed views (with SCHEMABINDING)
- **FR-VIW-004**: Extract view extended properties

#### 2.1.6 Stored Procedures
- **FR-PRC-001**: Extract all stored procedures using `OBJECT_DEFINITION()`
- **FR-PRC-002**: Preserve procedure parameters (names, types, defaults)
- **FR-PRC-003**: Extract procedure extended properties
- **FR-PRC-004**: Handle encrypted procedures (warn user)

#### 2.1.7 Functions
- **FR-FNC-001**: Extract scalar functions
- **FR-FNC-002**: Extract table-valued functions (inline and multi-statement)
- **FR-FNC-003**: Extract CLR functions (metadata only)
- **FR-FNC-004**: Handle function dependencies

#### 2.1.8 Triggers
- **FR-TRG-001**: Extract table triggers (AFTER, INSTEAD OF)
- **FR-TRG-002**: Extract database triggers
- **FR-TRG-003**: Preserve trigger order (if multiple triggers on same table)
- **FR-TRG-004**: Extract trigger enabled/disabled state

#### 2.1.9 Sequences
- **FR-SEQ-001**: Extract sequences (SQL Server 2012+)
- **FR-SEQ-002**: Preserve START WITH, INCREMENT BY, MIN/MAX values

#### 2.1.10 User-Defined Types
- **FR-UDT-001**: Extract user-defined table types
- **FR-UDT-002**: Extract alias types
- **FR-UDT-003**: Extract CLR types (metadata only)

### 2.2 Seed Data Extraction

- **FR-DAT-001**: Extract data from specified tables as INSERT statements
- **FR-DAT-002**: Support table filtering (whitelist/blacklist)
- **FR-DAT-003**: Support WHERE clause filters (e.g., `Status = 'Active'`)
- **FR-DAT-004**: Support row count limits (e.g., extract first 1000 rows)
- **FR-DAT-005**: Handle identity columns with `SET IDENTITY_INSERT`
- **FR-DAT-006**: Handle NULL values correctly
- **FR-DAT-007**: Escape special characters (quotes, backslashes)
- **FR-DAT-008**: Support batching (e.g., 100 INSERT statements per batch)
- **FR-DAT-009**: Generate data in dependency order (respect FKs)
- **FR-DAT-010**: Support excluding large binary columns (VARBINARY(MAX))

### 2.3 Output Formatting

#### 2.3.1 Single File Format
- **FR-OUT-001**: Generate single SQL file with all objects
- **FR-OUT-002**: Add section comments (e.g., `-- TABLES --`)
- **FR-OUT-003**: Include batch separators (`GO`)

#### 2.3.2 Per-Object Format
- **FR-OUT-004**: Generate separate file for each object
- **FR-OUT-005**: Organize files in subdirectories by type (tables/, procedures/, etc.)
- **FR-OUT-006**: Use object schema and name in filename (e.g., `MQTT.ReceiverConfig.sql`)

#### 2.3.3 Modular Format
- **FR-OUT-007**: Generate numbered files for deployment order:
  - `01_CREATE_SCHEMAS.sql`
  - `02_CREATE_TABLES.sql`
  - `03_CREATE_CONSTRAINTS.sql`
  - `04_CREATE_INDEXES.sql`
  - `05_CREATE_VIEWS.sql`
  - `06_CREATE_PROCEDURES.sql`
  - `07_CREATE_FUNCTIONS.sql`
  - `08_CREATE_TRIGGERS.sql`
  - `09_SEED_DATA.sql`
- **FR-OUT-008**: Include deployment script (`deploy.sh` or `deploy.ps1`)

### 2.4 Dependency Analysis

- **FR-DEP-001**: Detect foreign key dependencies between tables
- **FR-DEP-002**: Detect view dependencies on tables/views
- **FR-DEP-003**: Detect procedure dependencies on tables/views
- **FR-DEP-004**: Generate dependency graph (optional, requires graphviz)
- **FR-DEP-005**: Order objects to respect dependencies
- **FR-DEP-006**: Handle circular dependencies gracefully (warn user)

### 2.5 CLI Interface

- **FR-CLI-001**: Support connection via command-line arguments
- **FR-CLI-002**: Support connection string as alternative to individual args
- **FR-CLI-003**: Support reading connection details from config file (JSON/YAML)
- **FR-CLI-004**: Support interactive mode (prompt for password if not provided)
- **FR-CLI-005**: Support --help and --version flags
- **FR-CLI-006**: Return appropriate exit codes for CI/CD integration

---

## 3. Non-Functional Requirements

### 3.1 Performance

- **NFR-PER-001**: Extract schema from 1000-table database in <60 seconds
- **NFR-PER-002**: Extract seed data from 100,000-row table in <10 seconds
- **NFR-PER-003**: Support parallel extraction for large databases (optional)
- **NFR-PER-004**: Use connection pooling for efficiency
- **NFR-PER-005**: Stream large result sets (don't load entire DB into memory)

### 3.2 Compatibility

- **NFR-COM-001**: Support SQL Server 2012 and later
- **NFR-COM-002**: Support Azure SQL Database
- **NFR-COM-003**: Support Azure SQL Managed Instance
- **NFR-COM-004**: Support Windows Authentication (Windows only)
- **NFR-COM-005**: Support SQL Authentication (all platforms)
- **NFR-COM-006**: Support Azure AD Authentication (future)
- **NFR-COM-007**: Run on Windows, Linux, macOS
- **NFR-COM-008**: Require Python 3.9 or later

### 3.3 Reliability

- **NFR-REL-001**: Handle connection failures gracefully with retries
- **NFR-REL-002**: Validate all extracted SQL for syntax errors
- **NFR-REL-003**: Provide detailed error messages with troubleshooting hints
- **NFR-REL-004**: Log all operations for debugging
- **NFR-REL-005**: Support dry-run mode (validate without writing files)

### 3.4 Security

- **NFR-SEC-001**: Never log passwords in plain text
- **NFR-SEC-002**: Support password encryption in config files
- **NFR-SEC-003**: Warn if connection is not encrypted (TrustServerCertificate=False)
- **NFR-SEC-004**: Sanitize extracted stored procedures for embedded passwords
- **NFR-SEC-005**: Support environment variable substitution for credentials

### 3.5 Usability

- **NFR-USA-001**: Provide clear, actionable error messages
- **NFR-USA-002**: Include progress indicators for long operations
- **NFR-USA-003**: Support verbose mode for debugging
- **NFR-USA-004**: Support quiet mode for CI/CD pipelines
- **NFR-USA-005**: Include examples in documentation

### 3.6 Maintainability

- **NFR-MNT-001**: Use modular architecture (separate concerns)
- **NFR-MNT-002**: Achieve 80%+ test coverage
- **NFR-MNT-003**: Follow PEP 8 style guidelines
- **NFR-MNT-004**: Use type hints for all public functions
- **NFR-MNT-005**: Include inline documentation (docstrings)

---

## 4. Technical Requirements

### 4.1 Technology Stack

- **Python 3.9+** - Core language
- **pyodbc** - SQL Server driver (ODBC-based)
- **Click** - CLI framework
- **Jinja2** - SQL template engine
- **pytest** - Testing framework
- **black** - Code formatter
- **mypy** - Static type checker

### 4.2 Database Queries

Use `INFORMATION_SCHEMA` views and system catalog views:
- `INFORMATION_SCHEMA.TABLES`
- `INFORMATION_SCHEMA.COLUMNS`
- `INFORMATION_SCHEMA.TABLE_CONSTRAINTS`
- `INFORMATION_SCHEMA.KEY_COLUMN_USAGE`
- `INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS`
- `sys.indexes`, `sys.index_columns`
- `sys.objects`, `sys.procedures`, `sys.views`
- `OBJECT_DEFINITION()` for procedure/view definitions
- `sys.extended_properties` for descriptions

### 4.3 SQL Generation

- Use Jinja2 templates for SQL generation
- Support SQL Server 2012+ syntax
- Include comments with extraction metadata (date, tool version)
- Add `IF EXISTS` checks for DROP statements
- Use qualified names (`[schema].[object]`)
- Preserve original casing and object names

---

## 5. Acceptance Criteria

### 5.1 Schema Extraction

- [ ] Extract complete schema from sample database (50+ tables, 100+ procedures)
- [ ] Re-deploy extracted schema to new database without errors
- [ ] Verify all constraints, indexes, and defaults are present
- [ ] Verify all stored procedures execute successfully
- [ ] Verify data in seed tables matches source

### 5.2 Output Formats

- [ ] Single file output is valid SQL
- [ ] Per-object files are organized correctly
- [ ] Modular files deploy in correct order without errors
- [ ] Deployment script works on Windows and Linux

### 5.3 Performance

- [ ] Extract 1000-table database in <60 seconds
- [ ] Extract 100K rows of seed data in <10 seconds
- [ ] Memory usage <500MB for large databases

### 5.4 Compatibility

- [ ] Works with SQL Server 2012, 2016, 2019, 2022
- [ ] Works with Azure SQL Database (single database)
- [ ] Works with Azure SQL Managed Instance
- [ ] Works on Windows 10/11, Ubuntu 20.04+, macOS 12+

### 5.5 Error Handling

- [ ] Graceful handling of connection failures
- [ ] Clear error messages for missing permissions
- [ ] Validation of all command-line arguments
- [ ] Non-zero exit codes for failures

---

## 6. Out of Scope (Future Enhancements)

See [FUTURE.md](FUTURE.md) for:
- Permissions extraction (GRANT/DENY)
- Linked server extraction
- SQL Agent jobs extraction
- Database mail configuration
- Full-text indexes
- XML indexes
- Spatial indexes
- Comparison mode (diff two databases)
- GUI frontend
- Web API
- Database documentation generation (HTML/Markdown)

---

## 7. Dependencies

### 7.1 Python Packages
- `pyodbc >= 4.0.35` - SQL Server connectivity
- `click >= 8.1.0` - CLI framework
- `jinja2 >= 3.1.0` - Template engine
- `pyyaml >= 6.0` - Config file parsing
- `pytest >= 7.4.0` - Testing
- `pytest-cov >= 4.1.0` - Coverage
- `black >= 23.0.0` - Formatting
- `mypy >= 1.5.0` - Type checking

### 7.2 System Dependencies
- **ODBC Driver for SQL Server 17/18** - Database connectivity
  - Windows: Included with Windows
  - Linux: `apt-get install msodbcsql18` or `yum install msodbcsql18`
  - macOS: `brew install msodbcsql18`

---

## 8. Testing Strategy

### 8.1 Unit Tests
- Test each extraction module independently
- Mock database connections
- Validate SQL generation
- Test dependency ordering algorithms

### 8.2 Integration Tests
- Test against real SQL Server instance (Docker)
- Extract and re-deploy sample database
- Verify extracted SQL matches source

### 8.3 End-to-End Tests
- Full extraction workflows
- All output formats
- Error scenarios (connection failures, permission errors)

### 8.4 Performance Tests
- Benchmark extraction times for various database sizes
- Memory profiling

---

## 9. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Complex circular FK dependencies | High | Medium | Disable FKs during deploy, re-enable after |
| Encrypted stored procedures | Medium | Low | Warn user, skip encrypted objects |
| Very large seed data tables | Medium | Medium | Support row limits, WHERE filters |
| ODBC driver not installed | High | Medium | Clear error message with installation instructions |
| Azure SQL firewall blocking connection | Medium | High | Validate connection before extraction, suggest firewall rule |

---

## 10. Success Metrics

- **Adoption**: 100+ stars on GitHub in first 6 months
- **Reliability**: <5 bug reports per month after v1.0
- **Performance**: Extract 90% of databases in <60 seconds
- **Compatibility**: Works on 95%+ SQL Server instances without modifications
- **User Satisfaction**: 4.5+ star rating (surveys, GitHub)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-09
**Author**: Development Team
