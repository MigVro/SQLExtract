"""Utility functions and logging setup."""

import logging
import sys
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Shared with create_progress() so logging and progress bars render through the
# same Rich console instead of two independent ones fighting over the terminal.
console = Console()


def setup_logging(verbose: bool = False, quiet: bool = False, log_file: Optional[str] = None):
    """Configure logging with rich formatting.

    Args:
        verbose: Enable verbose (DEBUG) logging
        quiet: Suppress console output
        log_file: Optional log file path
    """
    level = logging.DEBUG if verbose else logging.INFO
    if quiet:
        level = logging.ERROR

    handlers = []

    if not quiet:
        handlers.append(RichHandler(console=console, rich_tracebacks=True, show_time=False, show_path=False))

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger
    """
    return logging.getLogger(name)


def create_progress() -> Progress:
    """Create a rich progress bar.

    Returns:
        Configured Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def escape_sql_identifier(identifier: str) -> str:
    """Escape SQL Server identifier with square brackets.

    Args:
        identifier: SQL identifier (table name, column name, etc.)

    Returns:
        Escaped identifier in square brackets
    """
    # Remove existing brackets if present
    identifier = identifier.strip('[]')
    # Escape any existing closing brackets
    identifier = identifier.replace(']', ']]')
    return f"[{identifier}]"


def escape_sql_string(value: str) -> str:
    """Escape a string value for SQL.

    Args:
        value: String value to escape

    Returns:
        Escaped string with single quotes escaped
    """
    # Escape single quotes by doubling them
    return value.replace("'", "''")


class SQLExtractError(Exception):
    """Base exception for SQL Extract."""
    pass


class ConnectionError(SQLExtractError):
    """Database connection error."""
    pass


class AuthenticationError(ConnectionError):
    """Login/authentication failure."""
    pass


class DatabaseAccessError(ConnectionError):
    """Database does not exist, or the login has no access to it.

    SQL Server reports both cases with the identical "Cannot open database"
    message (error 4060) by design, to avoid leaking which one it is to an
    unauthorized login - so the two can't be told apart here, and the raised
    message says so explicitly rather than guessing. Not raised for
    permission failures on objects *within* an already-open database (see
    PermissionDeniedError).
    """
    pass


class PermissionDeniedError(ConnectionError):
    """Insufficient permissions to access a database object."""
    pass


class ExtractionError(SQLExtractError):
    """Error during schema extraction."""
    pass


class OutputError(SQLExtractError):
    """Error writing output files."""
    pass
