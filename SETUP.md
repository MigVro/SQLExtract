# SQL Extract - Development Setup Guide

This guide helps developers set up their environment for contributing to SQL Extract.

---

## Prerequisites

### Required Software
- **Python 3.9 or later** - [Download](https://www.python.org/downloads/)
- **Git** - [Download](https://git-scm.com/downloads/)
- **ODBC Driver for SQL Server 17 or 18** - [Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- **SQL Server instance** - For testing (Docker, local, or Azure)

### Optional Software
- **Docker Desktop** - For running SQL Server in containers
- **VS Code** - Recommended IDE with Python extension
- **Azure Data Studio** or **SSMS** - For database management

---

## Initial Setup

### 1. Clone Repository
```bash
git clone https://github.com/MigVro/SQLExtract.git
cd SQLExtract
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Verify activation (should show venv path)
which python
```

### 3. Install Dependencies
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Or install in editable mode
pip install -e .
```

### 4. Verify Installation
```bash
# Test CLI
python sqlextract.py --help

# Run tests
pytest

# Check code style (same check CI runs)
black --check src tests sqlextract.py
```

---

## Development Workflow

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_extractor.py

# Run specific test class or test
pytest tests/test_extractor.py::TestDryRun

# Run in verbose mode
pytest -v

# Run with output
pytest -s
```

### Code Formatting
```bash
# Format all code
black src/ tests/

# Check formatting without changes
black --check src tests sqlextract.py

# Format specific file
black src/extractor.py
```

black is pinned to 26.10.1 in `requirements-dev.txt` (Python 3.10+ only) so local and CI
formatting agree.

### Type Checking
mypy is not yet clean (see TODO.md Phase 9) and is not a CI gate.
```bash
# Check all code
mypy src/

# Check specific file
mypy src/extractor.py

# Ignore missing imports
mypy src/ --ignore-missing-imports
```

### Linting
```bash
# Run pylint
pylint src/

# Run flake8
flake8 src/
```

### Continuous Integration
`.github/workflows/ci.yml` runs on every push to `master` and on pull requests: `pytest` on
Python 3.9–3.12 and `black --check` on 3.12. Integration tests are skipped in CI (they need
Windows Authentication). Gitea Actions are disabled via an empty `.gitea/workflows/`.

---

## Setting Up Test Database

### Option 1: Docker
`docker-compose.yml` defines container `sqlextract-test-db` (SQL Server 2022, `sa` /
`Test@Password123!`). Useful for manual extraction runs; the automated integration tests
need Windows Authentication instead (see Option 2).
```bash
docker-compose up -d

docker exec sqlextract-test-db /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "Test@Password123!" -C \
  -Q "CREATE DATABASE SQLExtractTest"

docker exec -i sqlextract-test-db /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "Test@Password123!" -d SQLExtractTest -C \
  < tests/fixtures/test_schema.sql
```

### Option 2: Local SQL Server
```bash
# Create test database
sqlcmd -S localhost -E -Q "CREATE DATABASE TestDB"

# Run test schema
sqlcmd -S localhost -E -d TestDB -i tests/fixtures/test_schema.sql
```

### Option 3: Azure SQL Database
```bash
# Create database using Azure CLI
az sql db create \
  --resource-group myResourceGroup \
  --server myserver \
  --name TestDB \
  --service-objective S0

# Get connection string
az sql db show-connection-string \
  --client sqlcmd \
  --name TestDB

# Run test schema
sqlcmd -S myserver.database.windows.net \
  -U myuser -P mypassword -d TestDB \
  -i tests/fixtures/test_schema.sql
```

---

## Project Structure

```
sqlextract/
├── README.md              # Project overview
├── REQUIREMENTS.md        # Detailed requirements
├── TODO.md                # Implementation checklist
├── SETUP.md               # This file
├── FUTURE.md              # Future enhancements
├── LICENSE                # MIT License
├── .gitignore             # Git ignore patterns
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── CONTRIBUTING.md        # Contribution guidelines
├── CLAUDE.md              # Guidance for Claude Code
├── pyproject.toml         # Python project config
├── Dockerfile             # Container image
├── docker-compose.yml     # Test SQL Server container
├── test-extraction.sh     # Docker-based manual extraction smoke test
├── .github/workflows/     # CI (GitHub Actions)
├── .gitea/workflows/      # Empty on purpose: disables Gitea Actions
├── .claude/settings.json  # Claude Code hook: black on edited .py files
│
├── sqlextract.py          # CLI entry point
│
├── src/                   # Source code
│   ├── __init__.py
│   ├── cli.py             # CLI argument parsing, exit codes
│   ├── connection.py      # Database connectivity, retries
│   ├── extractor.py       # Extraction orchestration, parallel jobs
│   ├── schema.py          # Introspection: tables, columns, views, procedures, functions,
│   │                      #   triggers, sequences, types, extended properties
│   ├── constraints.py     # Constraint extraction
│   ├── indexes.py         # Index extraction
│   ├── seed_data.py       # Data extraction
│   ├── dependency.py      # Dependency analysis
│   ├── formatter.py       # SQL generation and output formats
│   └── utils.py           # Utilities, logging, exceptions
│
└── tests/                 # Tests
    ├── __init__.py
    ├── conftest.py        # Pytest configuration
    ├── test_cli.py
    ├── test_connection.py
    ├── test_constraints.py
    ├── test_dependency.py
    ├── test_extractor.py
    ├── test_formatter.py
    ├── test_indexes.py
    ├── test_integration.py  # Real-server tests (SQLEXTRACT_TEST_SERVER)
    ├── test_schema.py
    ├── test_seed_data.py
    ├── test_utils.py
    └── fixtures/
        └── test_schema.sql  # Test database schema
```

---

## Configuration Files

- `requirements.txt` / `requirements-dev.txt`: runtime and development dependencies
- `pyproject.toml`: package metadata, the `sqlextract` console script, and black, mypy,
  pytest and coverage settings (black line length 100; pytest adds `-v` and coverage by default)
- `.gitignore`: Python, test, IDE and OS artifacts

See the files themselves for current contents.

---

## VS Code Setup

### Recommended Extensions
- Python (ms-python.python) — includes test discovery
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- Pylint (ms-python.pylint)
- Flake8 (ms-python.flake8)
- Mypy Type Checker (ms-python.mypy-type-checker)
- autoDocstring (njpwerner.autodocstring)
- GitLens (eamodio.gitlens)

### settings.json
Linting and formatting are configured through their own extensions; the old
`python.linting.*` and `python.formatting.provider` settings are no longer supported.
On Windows use `venv/Scripts/python.exe` as the interpreter path.
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  }
}
```

---

## Debugging

### VS Code Launch Configuration (.vscode/launch.json)
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    },
    {
      "name": "SQL Extract: Run CLI",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/sqlextract.py",
      "args": [
        "--server", "localhost",
        "--database", "TestDB",
        "--user", "sa",
        "--password", "YourStrong@Passw0rd",
        "--output", "./output"
      ],
      "console": "integratedTerminal"
    },
    {
      "name": "Python: pytest",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["-v"],
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Common Tasks

### Create New Module
```bash
# Create file
touch src/my_module.py

# Add to __init__.py
echo "from .my_module import MyClass" >> src/__init__.py

# Create test file
touch tests/test_my_module.py
```

### Run Integration Tests
Integration tests are skipped unless `SQLEXTRACT_TEST_SERVER` is set. They connect with
Windows Authentication, recreate scratch databases from `tests/fixtures/test_schema.sql` via
`sqlcmd -E -C` (so `sqlcmd` must be on PATH), and redeploy the modular output with `deploy.ps1`.
```powershell
$env:SQLEXTRACT_TEST_SERVER = "localhost"
pytest tests/test_integration.py
```

### Build Distribution
```bash
# Build wheel and source distribution
python -m build

# Check distribution
twine check dist/*

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

### Build Docker Image
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

---

## Troubleshooting

### pyodbc Install Fails
**Problem**: `error: Microsoft Visual C++ 14.0 is required`

**Solution** (Windows):
- Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

**Solution** (Linux):
```bash
sudo apt-get install unixodbc-dev
pip install pyodbc
```

**Solution** (macOS):
```bash
brew install unixodbc
pip install pyodbc
```

### ODBC Driver Not Found
**Problem**: `[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server'`

**Solution** (Linux):
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

**Solution** (macOS):
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18
```

### Connection to Azure SQL Fails
**Problem**: SSL certificate verification failed

**Solution**: Add `TrustServerCertificate=yes` or use `--trust-cert` flag
```bash
sqlextract --server myserver.database.windows.net --trust-cert ...
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## Getting Help

- **Documentation**: README.md, REQUIREMENTS.md
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: dev@sqlextract.dev

---

**Last Updated**: 2026-10-24
