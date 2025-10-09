# SQL Extract - Universal SQL Server Schema Extractor

**A robust, cross-platform command-line tool for extracting complete SQL Server database schemas, stored procedures, and seed data.**

## Why This Tool?

Microsoft's `mssql-scripter` exists but has limitations:
- Python 2.7 dependency (deprecated)
- Limited customization options
- No seed data extraction with filtering
- Poor handling of complex dependencies

**SQL Extract** provides:
- ✅ **Complete schema extraction** (tables, views, procedures, functions, triggers)
- ✅ **Intelligent dependency ordering** (respects FK relationships)
- ✅ **Seed data extraction** with configurable filters
- ✅ **Multiple output formats** (single file, per-object, modular)
- ✅ **Cross-platform** (Windows, Linux, macOS)
- ✅ **Modern tech stack** (Python 3.9+, pyodbc)
- ✅ **CI/CD ready** (scriptable, exit codes, logging)

---

## Quick Start

### Installation
```bash
# Clone repository
cd /mnt/d/dev2/sqlextract

# Install dependencies
pip install -r requirements.txt

# Or use Docker
docker build -t sqlextract .
docker run sqlextract --help
```

### Basic Usage
```bash
# Extract complete database schema
./sqlextract.py \
    --server "mbox-eastasia.database.windows.net,1433" \
    --database "MqttBridge" \
    --user "mbox-admin" \
    --password "PASSWORD" \
    --output ./output

# Extract only stored procedures
./sqlextract.py --server localhost --database MyDb --objects procedures --output ./procs

# Extract seed data from specific tables
./sqlextract.py --server localhost --database MyDb --seed-data --tables "MQTT.ReceiverConfig,MQTT.SourceConfig"

# Extract to modular files (numbered, deployable)
./sqlextract.py --server localhost --database MyDb --format modular --output ./deploy
```

---

## Features

### 1. Complete Schema Extraction
Extracts all database objects with proper dependency ordering:
- Schemas
- Tables (with all constraints, defaults, computed columns)
- Primary Keys, Foreign Keys, Unique Constraints, Check Constraints
- Indexes (clustered, non-clustered, unique, filtered)
- Views
- Stored Procedures
- Functions (scalar, table-valued, inline)
- Triggers
- Sequences
- User-Defined Types

### 2. Seed Data Extraction
Intelligently extracts configuration/lookup data:
- Configurable table filters (whitelist/blacklist)
- Row count limits (e.g., extract only first 100 rows)
- WHERE clause filters (e.g., `Status = 'Active'`)
- Identity column handling
- NULL value handling
- Proper escaping for special characters

### 3. Output Formats

**Single File** (`--format single`)
```
01_database_schema.sql  # Everything in one file
```

**Per-Object** (`--format per-object`)
```
schemas/MQTT.sql
tables/MQTT.ReceiverConfig.sql
procedures/dbo.GetPendingMessages.sql
indexes/IX_ReceiverConfig_Enabled.sql
```

**Modular** (`--format modular` - **Recommended for deployment**)
```
01_CREATE_SCHEMAS.sql
02_CREATE_TABLES.sql
03_CREATE_CONSTRAINTS.sql
04_CREATE_INDEXES.sql
05_CREATE_VIEWS.sql
06_CREATE_PROCEDURES.sql
07_CREATE_FUNCTIONS.sql
08_CREATE_TRIGGERS.sql
09_SEED_DATA.sql
```

### 4. Dependency Analysis
- Detects foreign key relationships
- Orders table creation to respect dependencies
- Groups related objects
- Generates dependency graph (optional)

### 5. Filtering & Customization
```bash
# Extract only specific schemas
--schemas "MQTT,Logging"

# Exclude certain object types
--exclude "triggers,sequences"

# Extract only objects matching pattern
--pattern "*Config*"

# Skip seed data for large tables
--seed-data --exclude-tables "dbo.AuditLog,dbo.EventHistory"
```

---

## Use Cases

### 1. Database Migration
```bash
# Extract from on-premises SQL Server
./sqlextract.py --server localhost --database ProdDB --output ./migration

# Deploy to Azure SQL Database
sqlcmd -S azure.database.windows.net -d NewDB -i ./migration/*.sql
```

### 2. Version Control
```bash
# Extract schema to Git repository
./sqlextract.py --server prod --database MyApp --format per-object --output ./db-schema
cd db-schema
git add .
git commit -m "Schema snapshot 2025-10-09"
```

### 3. CI/CD Pipeline
```bash
# GitHub Actions / Azure DevOps
- name: Extract Database Schema
  run: |
    ./sqlextract.py --server ${{ secrets.DB_SERVER }} \
                    --database ${{ secrets.DB_NAME }} \
                    --format modular \
                    --output ./schema

- name: Compare Schema Changes
  run: |
    diff -r ./schema-previous ./schema
```

### 4. Documentation Generation
```bash
# Extract with documentation metadata
./sqlextract.py --server localhost --database MyDb --include-comments --output-format markdown

# Output: schema_documentation.md with table descriptions, column comments, etc.
```

---

## Architecture

```
sqlextract/
├── sqlextract.py           # Main CLI entry point
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container image
├── README.md              # This file
├── REQUIREMENTS.md        # Detailed requirements
├── TODO.md                # Implementation checklist
├── SETUP.md               # Development setup
├── FUTURE.md              # Future enhancements
│
├── src/                   # Source code
│   ├── __init__.py
│   ├── cli.py             # Argument parsing
│   ├── extractor.py       # Core extraction logic
│   ├── connection.py      # Database connectivity
│   ├── schema.py          # Schema introspection
│   ├── tables.py          # Table extraction
│   ├── procedures.py      # Stored procedure extraction
│   ├── indexes.py         # Index extraction
│   ├── constraints.py     # Constraint extraction
│   ├── seed_data.py       # Data extraction
│   ├── formatter.py       # Output formatting
│   ├── dependency.py      # Dependency resolution
│   └── utils.py           # Utilities
│
├── tests/                 # Unit tests
│   ├── test_extractor.py
│   ├── test_formatter.py
│   └── fixtures/
│
└── examples/              # Example usage scripts
    ├── extract_prod.sh
    └── compare_schemas.sh
```

---

## Technology Stack

- **Python 3.9+** - Core language
- **pyodbc** - SQL Server connectivity (supports Azure SQL, Windows Auth, SQL Auth)
- **Click** - CLI framework
- **SQLAlchemy** (optional) - Advanced schema introspection
- **Jinja2** - Template engine for SQL generation
- **pytest** - Testing framework
- **Docker** - Containerization

---

## Command Reference

### Basic Options
```
--server, -s          SQL Server hostname/IP (required)
--port, -p            Port (default: 1433)
--database, -d        Database name (required)
--user, -u            Username (if not using Windows Auth)
--password, -P        Password
--windows-auth, -w    Use Windows Authentication
--trust-cert          Trust self-signed certificates (Azure SQL)
--output, -o          Output directory (default: ./output)
```

### Extraction Options
```
--objects             Object types to extract: all, schemas, tables, views,
                      procedures, functions, triggers, indexes (default: all)
--schemas             Schema filter (comma-separated)
--exclude             Exclude object types
--pattern             Name pattern filter (wildcards supported)
--seed-data           Extract data from tables
--tables              Table filter for seed data (comma-separated)
--exclude-tables      Tables to exclude from seed data
--where               WHERE clause for seed data
--max-rows            Max rows per table (default: unlimited)
```

### Output Options
```
--format              Output format: single, per-object, modular (default: modular)
--script-drops        Include DROP statements
--script-permissions  Include permissions (GRANT/DENY)
--include-comments    Include extended properties as comments
--no-identity-insert  Don't wrap seed data in SET IDENTITY_INSERT
--batch-separator     Batch separator (default: GO)
```

### Advanced Options
```
--dependency-graph    Generate dependency visualization (requires graphviz)
--compare-with        Compare with another database
--encrypt-passwords   Encrypt extracted passwords
--parallel            Extract objects in parallel (faster for large DBs)
--verbose, -v         Verbose logging
--quiet, -q           Suppress output
--log-file            Log to file
```

---

## Exit Codes

- `0` - Success
- `1` - Connection error
- `2` - Authentication error
- `3` - Database not found
- `4` - Permission denied
- `5` - Invalid arguments
- `10` - Extraction error
- `11` - Output write error

---

## Comparison with Alternatives

| Feature | sqlextract | mssql-scripter | SSMS Generate Scripts | sqlpackage (dacpac) |
|---------|-----------|----------------|----------------------|---------------------|
| Cross-platform | ✅ | ⚠️ (Python 2.7) | ❌ (Windows only) | ✅ |
| Azure SQL support | ✅ | ✅ | ✅ | ✅ |
| Seed data extraction | ✅ | ❌ | ⚠️ (limited) | ❌ |
| Modular output | ✅ | ❌ | ❌ | ❌ |
| CI/CD friendly | ✅ | ⚠️ | ❌ | ✅ |
| Dependency ordering | ✅ | ⚠️ | ⚠️ | ✅ |
| Customizable filters | ✅ | ⚠️ | ⚠️ | ❌ |
| Lightweight | ✅ | ✅ | ❌ (GUI required) | ⚠️ (.NET required) |

---

## License

MIT License - See LICENSE file

---

## Contributing

See [REQUIREMENTS.md](REQUIREMENTS.md) for detailed specifications and [TODO.md](TODO.md) for implementation tasks.

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@sqlextract.dev (to be set up)

---

**Built with ❤️ for database engineers who automate**
