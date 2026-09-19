# SQL Extract - Universal SQL Server Schema Extractor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**A cross-platform command-line tool for extracting complete SQL Server database schemas, stored procedures, and seed data into deployable SQL scripts.**

## Why This Tool?

Microsoft's `mssql-scripter` exists but has limitations:
- Python 2.7 dependency (deprecated)
- No seed data extraction with filtering
- Poor handling of complex dependencies

**SQL Extract** provides:
- ✅ **Complete schema extraction** (schemas, types, sequences, tables, constraints, indexes, views, procedures, functions, triggers, extended properties)
- ✅ **Intelligent dependency ordering** (tables/views ordered by FK and view-to-view dependencies, with circular FKs deferred)
- ✅ **Seed data extraction** with table/row-count filtering
- ✅ **Multiple output formats** (single file, per-object, modular deployment scripts)
- ✅ **Cross-platform** (Windows, Linux, macOS — anywhere the ODBC Driver for SQL Server runs)
- ✅ **CI/CD ready** (documented exit codes, `--quiet`/`--log-file`, `--dry-run`)
- ✅ **Parallel extraction** (concurrent metadata/seed-data queries, each on its own connection)

---

## Quick Start

### Installation
```bash
git clone <this-repository-url>
cd SQLExtract

# Install dependencies
pip install -r requirements.txt

# Or run via Docker
docker build -t sqlextract .
docker run --rm sqlextract --help
```

You'll also need the [ODBC Driver for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) (17 or 18) installed — see [SETUP.md](SETUP.md) for platform-specific instructions.

### Basic Usage
```bash
# Extract complete database schema (SQL auth)
python sqlextract.py --server localhost --database MyDB --user sa --password "P@ssw0rd" --output ./output

# Windows Authentication
python sqlextract.py --server localhost --database MyDB --windows-auth --output ./output

# Azure SQL Database (needs --trust-cert for the default self-signed-friendly ODBC 18 behavior)
python sqlextract.py --server myserver.database.windows.net --database MyDB \
    --user admin --password "P@ssw0rd" --trust-cert --output ./output

# Extract only specific schemas
python sqlextract.py --server localhost --database MyDB --schemas "dbo,MQTT" --output ./output

# Extract schema plus seed data (all tables, capped at 1000 rows each)
python sqlextract.py --server localhost --database MyDB --seed-data --max-rows 1000 --output ./output

# Extract seed data from specific tables only
python sqlextract.py --server localhost --database MyDB --seed-data --tables "dbo.Config,dbo.Status" --output ./output

# Preview what would be extracted without writing any files
python sqlextract.py --server localhost --database MyDB --seed-data --dry-run
```

### Demo

Running against a small schema (default verbosity logs each step; `--quiet` suppresses all of this and just prints the final result):

```
$ python sqlextract.py --server localhost --database MyDB --format modular --output ./schema

INFO     Connecting to database...
INFO     Connection established successfully
INFO     Extracting schema metadata (parallel, 15 queries)...
INFO     Found 2 schemas
INFO     Found 6 tables
...
INFO     Schema metadata extracted in 0.31s
INFO     Analyzing dependencies...
INFO     Topological sort complete: 6 tables ordered
INFO     Generating SQL scripts...
INFO     Extraction complete!
  Extracting metadata ---------------------------------------- 100% 0:00:00

✓ Extraction complete! SQL scripts written to: ./schema
```

---

## Example Output

### Modular Format (Recommended for deployment)

`--format modular` writes numbered, dependency-ordered files plus a generated `deploy.sh` / `deploy.ps1` that runs only the files actually produced (empty sections are skipped):

```
schema/
├── 01_CREATE_SCHEMAS.sql
├── 02_CREATE_TYPES.sql
├── 03_CREATE_SEQUENCES.sql
├── 04_CREATE_TABLES.sql
├── 05_CREATE_CONSTRAINTS.sql
├── 06_CREATE_INDEXES.sql
├── 07_CREATE_TRIGGERS.sql
├── 08_CREATE_VIEWS.sql
├── 09_CREATE_PROCEDURES.sql
├── 10_CREATE_FUNCTIONS.sql
├── 11_CREATE_DEFERRED_FKS.sql   # foreign keys that would form a circular dependency
├── 12_SEED_DATA.sql             # only present with --seed-data
├── deploy.sh
├── deploy.ps1
└── README.md                    # object counts + deployment instructions for this extraction
```

**Sample Table Output** (`04_CREATE_TABLES.sql`):
```sql
CREATE TABLE [MQTT].[ReceiverConfig] (
    [ReceiverConfigID] int IDENTITY(1,1) NOT NULL,
    [BrokerID] int NOT NULL,
    [Topic] nvarchar(255) NOT NULL,
    [QoS] tinyint NOT NULL DEFAULT ((0)),
    [IsEnabled] bit NOT NULL DEFAULT ((1)),
    [CreatedDate] datetime2(3) NOT NULL DEFAULT (getutcdate())
)
GO
```

**Sample Seed Data** (`12_SEED_DATA.sql`):
```sql
SET IDENTITY_INSERT [MQTT].[ReceiverConfig] ON
GO
INSERT INTO [MQTT].[ReceiverConfig] ([ReceiverConfigID], [BrokerID], [Topic], [QoS], [IsEnabled]) VALUES (1, 1, N'sensors/temperature', 1, 1)
INSERT INTO [MQTT].[ReceiverConfig] ([ReceiverConfigID], [BrokerID], [Topic], [QoS], [IsEnabled]) VALUES (2, 1, N'sensors/humidity', 0, 1)
GO
SET IDENTITY_INSERT [MQTT].[ReceiverConfig] OFF
GO
```

Deploy with:
```bash
./deploy.sh <server> <database> [user] [password]      # Linux/macOS
.\deploy.ps1 -Server <server> -Database <database>      # Windows
```

---

## Features

### 1. Complete Schema Extraction
- Schemas
- User-defined types (alias types, table types; CLR types as a metadata comment)
- Sequences
- Tables (columns, computed columns, identity columns, defaults)
- Primary keys, foreign keys, unique constraints, check constraints
- Indexes (clustered, non-clustered, unique, filtered, included columns)
- Triggers (AFTER/INSTEAD OF table triggers, including disabled state)
- Views (in view-to-view dependency order)
- Stored procedures and functions (scalar, inline table-valued, multi-statement table-valued)
- Extended properties (`MS_Description` on tables/columns, restored via `sp_addextendedproperty`)

### 2. Seed Data Extraction
- `--seed-data` to enable, `--tables` to whitelist specific tables (`schema.table` format)
- `--max-rows` to cap rows per table
- Identity columns wrapped in `SET IDENTITY_INSERT ON/OFF`
- NULLs, `BIT` values, and special characters (quotes, backslashes) handled correctly
- Data inserted in FK dependency order, one `INSERT` statement per row

### 3. Output Formats

**Single file** (`--format single`) — everything in one `schema.sql`.

**Per-object** (`--format per-object`) — one file per object, grouped into subdirectories
(`Tables/`, `Views/`, `Procedures/`, `Constraints/01_PrimaryKeys/`, etc. — see the generated
`README.md` for the full list and deployment order).

**Per-object, consolidated** (`--format per-object-cons`) — same as per-object, but each table's
primary key, unique/check constraints, indexes, and triggers are bundled into its `Tables/` file
instead of separate `Constraints/`/`Indexes/`/`Triggers/` files (like SSMS's "Script Table as
CREATE To"). Foreign keys still get their own file under `Constraints/03_ForeignKeys/`, since
bundling them would make per-table deploys order-dependent (or circular) across tables.

**Modular** (`--format modular`, default) — numbered deployment files plus `deploy.sh`/`deploy.ps1`, as shown above.

### 4. Dry Run
`--dry-run` connects, runs the same metadata queries as a real extraction, and prints object
counts (schemas, tables, views, procedures, functions, triggers, indexes, constraints, and how
many tables seed data would be pulled from) — without writing any output files or reading a
single seed-data row. Use it to validate connectivity/permissions and sanity-check scope before
a real run against an unfamiliar or production database.

### 5. Parallel Extraction
Independent metadata queries (and, with `--seed-data`, each table's data pull) run concurrently
by default, each on its own database connection — `--no-parallel` falls back to a single
sequential connection, `--max-workers` (default 8) caps concurrency.

### 6. Dependency Ordering
- Table creation ordered by foreign-key relationships; a circular FK is deferred to
  `11_CREATE_DEFERRED_FKS.sql` instead of blocking the whole extraction
- Views ordered so a view referencing another view is created after it
- Types and sequences extracted before tables, since a column may reference either

---

## Use Cases

### Database Migration
```bash
python sqlextract.py --server localhost --database ProdDB --output ./migration
sqlcmd -S azure.database.windows.net -d NewDB -C -i ./migration/deploy.sh   # or run deploy.sh/deploy.ps1 directly
```

### Version Control / Schema Snapshots
```bash
python sqlextract.py --server prod --database MyApp --format per-object --output ./db-schema
cd db-schema
git add .
git commit -m "Schema snapshot $(date +%F)"
```

### CI/CD Pipeline
```yaml
# GitHub Actions
- name: Validate database connectivity
  run: python sqlextract.py --server ${{ secrets.DB_SERVER }} --database ${{ secrets.DB_NAME }} \
       --user ${{ secrets.DB_USER }} --password ${{ secrets.DB_PASSWORD }} --dry-run --quiet

- name: Extract database schema
  run: python sqlextract.py --server ${{ secrets.DB_SERVER }} --database ${{ secrets.DB_NAME }} \
       --user ${{ secrets.DB_USER }} --password ${{ secrets.DB_PASSWORD }} \
       --format modular --output ./schema --quiet
```
The tool exits with a specific non-zero code on failure (see **Exit Codes** below), so a CI step
can distinguish "can't connect" from "bad credentials" from "disk full" without parsing output.

---

## Architecture

```
SQLExtract/
├── sqlextract.py           # CLI entry point
├── requirements.txt        # Runtime dependencies
├── Dockerfile              # Container image
├── README.md               # This file
├── REQUIREMENTS.md         # Detailed requirements
├── TODO.md                 # Implementation checklist
├── SETUP.md                # Development setup
├── FUTURE.md                # Deliberately out-of-scope features
│
├── src/
│   ├── cli.py               # Argument parsing, exit codes (Click)
│   ├── extractor.py         # Extraction orchestration (DatabaseExtractor)
│   ├── connection.py        # Database connectivity (pyodbc), retries
│   ├── schema.py            # Schema introspection (tables, views, procs, functions,
│   │                        #   triggers, sequences, types, extended properties)
│   ├── constraints.py       # PK/FK/unique/check constraint extraction
│   ├── indexes.py           # Index extraction
│   ├── seed_data.py         # Seed data extraction and INSERT generation
│   ├── formatter.py         # Output formatting (single/per-object/modular, deploy scripts, README)
│   ├── dependency.py        # Topological sort for tables and views
│   └── utils.py             # Logging, progress bars, exception hierarchy
│
└── tests/
    ├── test_*.py             # Unit tests (mocked DB connections)
    ├── test_integration.py   # Integration tests against a real SQL Server (see below)
    └── fixtures/test_schema.sql
```

---

## Technology Stack

- **Python 3.9+**
- **pyodbc** — SQL Server connectivity (Windows Auth, SQL Auth, Azure SQL)
- **Click** — CLI framework
- **Jinja2** — SQL template engine
- **rich** — logging and progress bars
- **pytest** — testing framework

---

## Command Reference

### Connection Options
```
--server, -s          SQL Server hostname or IP (required)
--port, -p            Port (default: 1433)
--database, -d        Database name (required)
--user, -u            Username (required unless --windows-auth)
--password, -P        Password (required unless --windows-auth)
--windows-auth, -w    Use Windows Authentication
--trust-cert          Trust server certificate (needed for Azure SQL / self-signed certs
                      with ODBC Driver 18, which defaults to encrypting and validating)
```

### Extraction Options
```
--schemas             Comma-separated schema filter (e.g. "dbo,MQTT")
--seed-data           Extract seed data from tables
--tables              Comma-separated table filter for seed data (format: schema.table) —
                      an entry that doesn't match a table logs a warning and is skipped,
                      the rest of the extraction still succeeds
--max-rows            Maximum rows per table for seed data (must be positive)
--dry-run             Connect and report what would be extracted; write nothing
--no-parallel         Disable parallel extraction (use a single database connection)
--max-workers         Maximum concurrent connections when running in parallel (default: 8)
```

### Output Options
```
--output, -o          Output directory (default: ./output)
--format              Output format: single, per-object, per-object-cons, modular
                      (default: modular)
--clean               Delete the output directory before extraction
--omit-ts             Omit the generation timestamp from output headers (avoids
                      spurious diffs when re-extracting an unchanged schema)
--no-header           Omit the header comment block from output files entirely
```

### Logging Options
```
--verbose, -v         Verbose (DEBUG) logging
--quiet, -q           Errors only; also suppresses the progress bar
--log-file            Also write logs to this file
```

### Other
```
--version             Show version and exit
--help                Show help and exit
```

---

## Exit Codes

CI/CD pipelines can branch on these without parsing stdout:

| Code | Meaning              | Typical cause |
|------|----------------------|---------------|
| `0`  | Success              | — |
| `1`  | Connection error     | Wrong `--server`/`--port`, firewall, instance not accepting remote TCP |
| `2`  | Authentication error | Wrong `--user`/`--password`, or SQL Auth not enabled on the server |
| `3`  | Database not found   | Wrong `--database`, or the login has no access to it (SQL Server reports both cases identically) |
| `4`  | Permission denied    | Login lacks `SELECT`/`EXECUTE` on a specific object |
| `5`  | Invalid arguments    | Missing/out-of-range CLI options (e.g. `--port` outside 1-65535) |
| `10` | Extraction error     | Unclassified failure while reading schema/seed data |
| `11` | Output write error   | Can't write to `--output` (permissions, disk full, path in use) |
| `99` | Unexpected error     | Anything not covered above — rerun with `--verbose` and report it |

---

## Troubleshooting

Every error `sqlextract` prints includes a one-line `Hint:` pointing at the likely cause. Some
common ones in more detail:

**"Connection Error" (exit 1)**
Check `--server`/`--port` are correct, the SQL Server instance has TCP/IP enabled (SQL Server
Configuration Manager → Protocols) and accepts remote connections, and no firewall is blocking
the port. For a named instance (e.g. `SERVER\INSTANCENAME`), the SQL Server Browser service must
be running unless you connect on a fixed port.

**"Authentication Error" (exit 2)**
Verify `--user`/`--password`. If you're sure they're correct, confirm the server has "SQL Server
and Windows Authentication mode" enabled — a server in Windows-only mode rejects all SQL logins
regardless of credentials.

**"Database Not Found" (exit 3)**
SQL Server returns the same "Cannot open database" error whether the database doesn't exist or
the login simply has no access to it (by design, so an unauthorized login can't tell which).
Double-check both the spelling of `--database` and that the login has been granted access.

**Azure SQL / self-signed certificate errors**
Pass `--trust-cert`. ODBC Driver 18 encrypts connections and validates the server certificate by
default; `--trust-cert` matches ODBC 17's more permissive default and is required for Azure SQL
and most self-signed/on-prem setups.

**Extraction is slower than expected on a large database**
Extraction is parallel by default (`--max-workers 8`). Try raising `--max-workers` if the server
has headroom, or add `--verbose` to see per-object timing and find which stage is slow.

**Not sure what a run against an unfamiliar database will actually do**
Use `--dry-run` first — it connects and reports object counts without writing anything.

## FAQ

**Does this support MySQL/PostgreSQL/Oracle?**
No — SQL Server only, including Azure SQL Database (via `--trust-cert`). See [FUTURE.md](FUTURE.md).

**Does it extract permissions (GRANT/DENY) or SQL Agent jobs?**
No, both are explicitly out of scope for v1.0 — see [FUTURE.md](FUTURE.md).

**Can I extract only some object types (e.g. just stored procedures)?**
Not selectively by object type today — `--schemas` filters by schema, and `--tables` filters
seed data by table, but there's no flag to skip e.g. views or triggers while keeping everything
else. Extract to `--format per-object` and take only the files you need if you require this.

**Will re-running extraction against an unchanged database produce an identical diff?**
Use `--omit-ts` to drop the generation timestamp from file headers — without it, every run
changes the timestamp line even if nothing else did, adding noise to a diff.

**What happens to circular foreign keys?**
Tables are still created; the FKs that would form a cycle are deferred to a separate
`11_CREATE_DEFERRED_FKS.sql` (modular format) so table creation never deadlocks on a cycle.

**What SQL Server versions and platforms is this tested against?**
Automated integration tests run against a local SQL Server 2017 instance on Windows. It has not
yet been verified against SQL Server 2012/2016/2019/2022, Azure SQL Managed Instance, or on
Linux/macOS — see [TODO.md](TODO.md) Phase 8 for the current testing status.

---

## Running the Tests

```bash
pytest                        # unit tests only (no database required)
pytest --cov=src --cov-report=html   # with coverage

# Integration tests (deploys the fixture schema to scratch databases and redeploys it) —
# require a real SQL Server reachable with Windows Authentication:
SQLEXTRACT_TEST_SERVER="<server[\instance]>" pytest tests/test_integration.py
```

---

## Comparison with Alternatives

| Feature | sqlextract | mssql-scripter | SSMS Generate Scripts |
|---------|-----------|----------------|----------------------|
| Cross-platform | ✅ | ⚠️ (Python 2.7) | ❌ (Windows only) |
| Azure SQL support | ✅ | ✅ | ✅ |
| Seed data extraction | ✅ | ❌ | ⚠️ (limited) |
| Modular, deployable output | ✅ | ❌ | ❌ |
| CI/CD friendly (exit codes, `--quiet`, `--dry-run`) | ✅ | ⚠️ | ❌ |
| Dependency ordering (tables + views) | ✅ | ⚠️ | ⚠️ |
| Parallel extraction | ✅ | ❌ | N/A |

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Contributing

See [REQUIREMENTS.md](REQUIREMENTS.md) for detailed specifications, [TODO.md](TODO.md) for the
implementation checklist, and [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process.

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
