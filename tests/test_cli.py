"""Tests for the CLI's exit-code mapping (see CLAUDE.md for the documented scheme)."""

import sys
import pytest
from unittest.mock import patch
from click.testing import CliRunner
from src.cli import _run, main
from src.utils import (
    ConnectionError as ConnError,
    AuthenticationError,
    DatabaseAccessError,
    PermissionDeniedError,
    ExtractionError,
    OutputError,
)

BASE_ARGS = ['--server', 'localhost', '--database', 'TestDB', '--user', 'sa', '--password', 'x']


@pytest.mark.parametrize('exc,expected_code', [
    (AuthenticationError("bad login"), 2),
    (DatabaseAccessError("no db"), 3),
    (PermissionDeniedError("denied"), 4),
    (ConnError("conn failed"), 1),
    (OutputError("write failed"), 11),
    (ExtractionError("extract failed"), 10),
    (ValueError("bad value"), 5),
    (RuntimeError("boom"), 99),
])
def test_exit_code_for_exception(exc, expected_code):
    """Each exception type raised by DatabaseExtractor.extract() must map to its
    documented exit code."""
    runner = CliRunner()
    with patch('src.cli.DatabaseExtractor') as MockExtractor:
        MockExtractor.return_value.extract.side_effect = exc
        result = runner.invoke(_run, BASE_ARGS)
    assert result.exit_code == expected_code


def test_success_exits_0(tmp_path):
    runner = CliRunner()
    with patch('src.cli.DatabaseExtractor') as MockExtractor:
        MockExtractor.return_value.extract.return_value = None
        result = runner.invoke(_run, BASE_ARGS + ['--output', str(tmp_path)])
    assert result.exit_code == 0


def test_missing_credentials_exits_5():
    """--user/--password required without --windows-auth is checked before any DB work."""
    runner = CliRunner()
    result = runner.invoke(_run, ['--server', 'localhost', '--database', 'TestDB'])
    assert result.exit_code == 5


@pytest.mark.parametrize('extra_args', [
    ['--port', '0'],
    ['--port', '70000'],
    ['--max-rows', '0'],
    ['--max-rows', '-5'],
    ['--max-workers', '0'],
])
def test_invalid_numeric_argument_exits_5(extra_args):
    """Out-of-range --port/--max-rows/--max-workers are rejected before any DB work."""
    runner = CliRunner()
    result = runner.invoke(_run, BASE_ARGS + extra_args)
    assert result.exit_code == 5


def test_click_usage_error_remapped_to_5(monkeypatch):
    """Click's own argument validation (e.g. missing --server/--database) normally
    exits with Click's default code 2 - the main() wrapper remaps that to 5."""
    monkeypatch.setattr(sys, 'argv', ['sqlextract'])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 5
