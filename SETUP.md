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
cd /mnt/d/dev2
git clone https://github.com/your-org/sqlextract.git
cd sqlextract
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

# Check code style
black --check src/
mypy src/
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

# Run specific test
pytest tests/test_extractor.py::test_extract_tables

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
black --check src/

# Format specific file
black src/extractor.py
```

### Type Checking
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

---

## Setting Up Test Database

### Option 1: Docker (Recommended)
```bash
# Start SQL Server container
docker run -d \
  --name sqlextract-test \
  -e 'ACCEPT_EULA=Y' \
  -e 'SA_PASSWORD=YourStrong@Passw0rd' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest

# Wait for SQL Server to start (30 seconds)
sleep 30

# Create test database
docker exec sqlextract-test /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' \
  -Q 'CREATE DATABASE TestDB'

# Run test schema script
docker exec -i sqlextract-test /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' -d TestDB \
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
├── pyproject.toml         # Python project config
├── setup.py               # Package setup (alternative)
├── Dockerfile             # Container image
├── docker-compose.yml     # Docker services
│
├── sqlextract.py          # CLI entry point
│
├── src/                   # Source code
│   ├── __init__.py
│   ├── cli.py             # CLI argument parsing
│   ├── connection.py      # Database connectivity
│   ├── extractor.py       # Core extraction orchestration
│   ├── schema.py          # Schema introspection
│   ├── tables.py          # Table extraction
│   ├── constraints.py     # Constraint extraction
│   ├── indexes.py         # Index extraction
│   ├── views.py           # View extraction
│   ├── procedures.py      # Stored procedure extraction
│   ├── functions.py       # Function extraction
│   ├── triggers.py        # Trigger extraction
│   ├── sequences.py       # Sequence extraction
│   ├── seed_data.py       # Data extraction
│   ├── dependency.py      # Dependency analysis
│   ├── formatter.py       # Output formatting
│   └── utils.py           # Utilities and logging
│
├── tests/                 # Tests
│   ├── __init__.py
│   ├── conftest.py        # Pytest configuration
│   ├── test_connection.py
│   ├── test_extractor.py
│   ├── test_tables.py
│   ├── test_constraints.py
│   ├── test_indexes.py
│   ├── test_views.py
│   ├── test_procedures.py
│   ├── test_seed_data.py
│   ├── test_dependency.py
│   ├── test_formatter.py
│   └── fixtures/
│       ├── test_schema.sql      # Test database schema
│       └── sample_database.sql  # Sample database for integration tests
│
├── examples/              # Example scripts
│   ├── extract_prod.sh
│   ├── extract_dev.sh
│   └── compare_schemas.sh
│
└── docs/                  # Additional documentation
    ├── architecture.md
    ├── api_reference.md
    └── contributing.md
```

---

## Configuration Files

### requirements.txt
```txt
pyodbc>=4.0.35
click>=8.1.0
jinja2>=3.1.0
pyyaml>=6.0
rich>=13.0.0
```

### requirements-dev.txt
```txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
black>=23.0.0
mypy>=1.5.0
pylint>=2.17.0
flake8>=6.0.0
types-PyYAML>=6.0.0
```

### pyproject.toml
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sqlextract"
version = "1.0.0"
description = "Universal SQL Server schema extractor"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "pyodbc>=4.0.35",
    "click>=8.1.0",
    "jinja2>=3.1.0",
    "pyyaml>=6.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "black>=23.0.0",
    "mypy>=1.5.0",
    "pylint>=2.17.0",
    "flake8>=6.0.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
sqlextract = "src.cli:main"

[tool.black]
line-length = 100
target-version = ['py39', 'py310', 'py311', 'py312']
include = '\.pyi?$'

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=src --cov-report=term-missing"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "venv/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### .gitignore
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project-specific
output/
*.log
config.yaml
secrets.yaml
```

---

## VS Code Setup

### Recommended Extensions
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Python Test Explorer (littlefoxteam.vscode-python-test-adapter)
- Black Formatter (ms-python.black-formatter)
- autoDocstring (njpwerner.autodocstring)
- GitLens (eamodio.gitlens)

### settings.json
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
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
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    },
    {
      "name": "SQL Extract: Run CLI",
      "type": "python",
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
      "type": "python",
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
```bash
# Start test database
docker-compose up -d

# Run integration tests
pytest tests/integration/

# Stop database
docker-compose down
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

See [docs/contributing.md](docs/contributing.md) for contribution guidelines.

---

## Getting Help

- **Documentation**: README.md, REQUIREMENTS.md
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: dev@sqlextract.dev

---

**Last Updated**: 2025-10-09
