"""Command-line interface for SQL Extract."""

import click
import sys
from .connection import ConnectionConfig
from .extractor import DatabaseExtractor
from .utils import setup_logging, get_logger, SQLExtractError, ConnectionError as ConnError

logger = get_logger(__name__)


@click.command()
@click.option('--server', '-s', required=True, help='SQL Server hostname or IP')
@click.option('--port', '-p', default=1433, help='SQL Server port (default: 1433)')
@click.option('--database', '-d', required=True, help='Database name')
@click.option('--user', '-u', help='Username (if not using Windows Auth)')
@click.option('--password', '-P', help='Password')
@click.option('--windows-auth', '-w', is_flag=True, help='Use Windows Authentication')
@click.option('--trust-cert', is_flag=True, help='Trust server certificate (for Azure SQL)')
@click.option('--output', '-o', default='./output', help='Output directory (default: ./output)')
@click.option('--format', 'output_format', type=click.Choice(['single', 'per-object', 'modular']), default='modular', help='Output format (default: modular)')
@click.option('--clean', is_flag=True, help='Delete the output directory before extraction')
@click.option('--omit-ts', is_flag=True, help='Omit the generation timestamp from output headers')
@click.option('--schemas', help='Comma-separated list of schemas to extract')
@click.option('--seed-data', is_flag=True, help='Extract seed data from tables')
@click.option('--tables', help='Comma-separated list of tables for seed data (format: schema.table)')
@click.option('--max-rows', type=int, help='Maximum rows per table for seed data')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Quiet mode (errors only)')
@click.option('--log-file', help='Log to file')
@click.version_option(version='1.0.0')
def main(
    server: str,
    port: int,
    database: str,
    user: str,
    password: str,
    windows_auth: bool,
    trust_cert: bool,
    output: str,
    output_format: str,
    clean: bool,
    omit_ts: bool,
    schemas: str,
    seed_data: bool,
    tables: str,
    max_rows: int,
    verbose: bool,
    quiet: bool,
    log_file: str
):
    """SQL Extract - Universal SQL Server schema extractor.

    Extract complete database schemas, stored procedures, and seed data from SQL Server databases.

    Examples:

        \b
        # Extract complete database schema
        sqlextract -s localhost -d MyDB -u sa -P password -o ./output

        \b
        # Extract only specific schemas
        sqlextract -s localhost -d MyDB --schemas "dbo,MQTT" -o ./output

        \b
        # Extract schema with seed data
        sqlextract -s localhost -d MyDB --seed-data --max-rows 1000 -o ./output

        \b
        # Extract seed data from specific tables
        sqlextract -s localhost -d MyDB --seed-data --tables "dbo.Config,dbo.Status" -o ./output

        \b
        # Use Windows Authentication
        sqlextract -s localhost -d MyDB -w -o ./output

        \b
        # Connect to Azure SQL Database
        sqlextract -s myserver.database.windows.net -d MyDB -u admin -P password --trust-cert -o ./output
    """
    # Setup logging
    setup_logging(verbose=verbose, quiet=quiet, log_file=log_file)

    try:
        # Validate arguments
        if not windows_auth and (not user or not password):
            click.echo("Error: --user and --password required when not using Windows Authentication", err=True)
            sys.exit(5)

        # Parse schema filter
        schema_filter = None
        if schemas:
            schema_filter = [s.strip() for s in schemas.split(',')]

        # Parse seed tables
        seed_tables = None
        if tables:
            seed_tables = [t.strip() for t in tables.split(',')]

        # Create connection config
        config = ConnectionConfig(
            server=server,
            port=port,
            database=database,
            user=user,
            password=password,
            windows_auth=windows_auth,
            trust_cert=trust_cert
        )

        # Create extractor and run
        extractor = DatabaseExtractor(config)
        extractor.extract(
            output_dir=output,
            schema_filter=schema_filter,
            extract_seed_data=seed_data,
            seed_tables=seed_tables,
            max_rows=max_rows,
            output_format=output_format,
            clean=clean,
            omit_ts=omit_ts
        )

        click.echo(f"\n✓ Extraction complete! SQL scripts written to: {output}")
        sys.exit(0)

    except ConnError as e:
        click.echo(f"\n✗ Connection Error: {e}", err=True)
        sys.exit(1)

    except SQLExtractError as e:
        click.echo(f"\n✗ Extraction Error: {e}", err=True)
        sys.exit(10)

    except Exception as e:
        click.echo(f"\n✗ Unexpected Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(11)


if __name__ == '__main__':
    main()
