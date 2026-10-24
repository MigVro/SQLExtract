# Contributing to SQL Extract

First off, thank you for considering contributing to SQL Extract! It's people like you that make SQL Extract such a great tool.

## 🎯 Ways to Contribute

- 🐛 **Report bugs** - Found a bug? Let us know!
- 💡 **Suggest features** - Have an idea? We'd love to hear it!
- 📖 **Improve documentation** - Help others understand the tool better
- 🔧 **Submit pull requests** - Fix bugs or add features
- ⭐ **Star the repo** - Show your support!

## 🐛 Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected behavior** vs. **actual behavior**
- **Environment details** (OS, Python version, SQL Server version)
- **Error messages** or logs
- **Sample database schema** (if applicable and not sensitive)

### Bug Report Template

```markdown
**Description**
A clear description of the bug.

**To Reproduce**
Steps to reproduce:
1. Run command '...'
2. With database '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04, Windows 11]
- Python version: [e.g., 3.11.2]
- SQL Server version: [e.g., SQL Server 2022, Azure SQL]
- SQL Extract version: [e.g., 1.0.0]

**Additional context**
Add any other context about the problem.
```

## 💡 Suggesting Features

We love feature requests! Before submitting:

1. **Check existing issues** to see if it's already been suggested
2. **Be specific** about the feature and its use case
3. **Explain why** this feature would be useful to most users

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Any alternative solutions or features you've considered.

**Use case**
Explain how this feature would be used in practice.

**Additional context**
Add any other context or screenshots about the feature request.
```

## 🔧 Development Setup

### Prerequisites

- Python 3.9 or later
- Git
- ODBC Driver for SQL Server 18
- SQL Server instance for testing (Docker recommended)

### Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/SQLExtract.git
cd SQLExtract

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Start test database (Docker)
docker-compose up -d

# Wait for SQL Server to start
sleep 30

# Create test database
docker exec sqlextract-test-db /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" -C \
    -Q "CREATE DATABASE SQLExtractTest"

# Load test schema
docker exec -i sqlextract-test-db /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" -d SQLExtractTest -C \
    < tests/fixtures/test_schema.sql
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_extractor.py -v

# Integration tests (need a SQL Server reachable with Windows Authentication, sqlcmd on PATH)
SQLEXTRACT_TEST_SERVER="<server[\instance]>" pytest tests/test_integration.py
```

CI (GitHub Actions) runs `pytest` on Python 3.9–3.12 and `black --check` on every push and
pull request; integration tests are skipped there.

### Code Quality

```bash
# Format code (CI fails if this would change anything)
black src/ tests/ sqlextract.py

# Type checking
mypy src/

# Linting
pylint src/
flake8 src/
```

## 📝 Pull Request Process

1. **Fork the repository** and create your branch from `master`
2. **Follow the coding standards** (see below)
3. **Add tests** for any new functionality
4. **Update documentation** if needed
5. **Ensure all tests pass**
6. **Write a clear commit message**
7. **Submit the pull request**

### Coding Standards

- Follow **PEP 8** style guidelines
- Use **type hints** for all functions
- Write **docstrings** for all public functions
- Keep line length to **100 characters** (black formatter)
- Write **meaningful variable names**
- Add **comments** for complex logic
- Target **80%+ test coverage**

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting (no functional changes)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: Add support for Azure AD authentication

Adds --azure-ad flag to use Azure Active Directory authentication
instead of SQL authentication. Requires azure-identity package.

Closes #123
```

```
fix: Handle NULL values in VARBINARY columns

VARBINARY columns with NULL values were causing extraction to fail.
Now properly handles NULL by checking value before calling .hex().

Fixes #456
```

## 🧪 Testing Guidelines

### Unit Tests

- Test each module independently
- Mock database connections
- Test edge cases and error conditions
- Use descriptive test names

### Integration Tests

- Test against real SQL Server
- Use test database with known schema
- Verify extracted SQL is valid
- Test all output formats

### Test Naming

```python
def test_extract_tables_with_identity_columns():
    """Test that tables with identity columns are extracted correctly."""
    pass

def test_connection_retry_on_failure():
    """Test that connection retries 3 times before failing."""
    pass
```

## 📚 Documentation

When adding features, update:

- **README.md** - User-facing documentation
- **REQUIREMENTS.md** - Technical specifications
- **SETUP.md** - Development setup (if changed)
- **Docstrings** - In-code documentation
- **CLAUDE.md** - AI-assisted development notes (if relevant)

## 🎨 Design Principles

1. **Simplicity** - Keep the CLI simple and intuitive
2. **Reliability** - Handle errors gracefully
3. **Performance** - Optimize for large databases
4. **Compatibility** - Support SQL Server 2012+
5. **Modularity** - Keep code organized and maintainable
6. **Testability** - Write testable code

## ❓ Questions?

- **Open an issue** for general questions
- **Check existing issues** first
- **Be respectful** and constructive

## 📜 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in all interactions.

### Our Standards

**Positive behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior:**
- Harassment, trolling, or insulting comments
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## 🙏 Recognition

Contributors will be recognized in:
- GitHub contributors page
- Release notes for significant contributions
- README acknowledgments (for major features)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to SQL Extract! 🎉
