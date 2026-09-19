"""Main extraction orchestration module."""

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any, Callable
from .connection import DatabaseConnection, ConnectionConfig
from .schema import SchemaReader
from .constraints import ConstraintExtractor
from .indexes import IndexExtractor
from .dependency import order_tables_by_dependency, order_views_by_dependency
from .seed_data import SeedDataExtractor
from .formatter import SQLFormatter
from .utils import get_logger, ExtractionError

logger = get_logger(__name__)


class DatabaseExtractor:
    """Main database schema extractor."""

    def __init__(self, config: ConnectionConfig):
        """Initialize database extractor.

        Args:
            config: Connection configuration
        """
        self.config = config
        self.connection: Optional[DatabaseConnection] = None

    def _run_jobs(
        self,
        jobs: Dict[str, Callable[[DatabaseConnection], Any]],
        parallel: bool,
        max_workers: int
    ) -> Dict[str, Any]:
        """Run independent, schema-filtered extraction jobs.

        Each job gets its own DatabaseConnection when run in parallel, since pyodbc
        connections/cursors are not thread-safe and can't be shared across threads.

        Args:
            jobs: Mapping of result key -> callable taking a DatabaseConnection
            parallel: Run concurrently via a thread pool if True, sequentially otherwise
            max_workers: Maximum number of concurrent connections/threads

        Returns:
            Mapping of result key -> job result
        """
        if not jobs:
            return {}

        if not parallel:
            return {name: job(self.connection) for name, job in jobs.items()}

        def run_job(name: str, job: Callable[[DatabaseConnection], Any]) -> Any:
            conn = DatabaseConnection(self.config, label=name)
            conn.connect()
            try:
                return job(conn)
            finally:
                conn.close()

        results: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as executor:
            future_to_name = {executor.submit(run_job, name, job): name for name, job in jobs.items()}
            for future in as_completed(future_to_name):
                results[future_to_name[future]] = future.result()

        return results

    def extract(
        self,
        output_dir: str,
        schema_filter: Optional[List[str]] = None,
        extract_seed_data: bool = False,
        seed_tables: Optional[List[str]] = None,
        max_rows: Optional[int] = None,
        output_format: str = 'modular',
        clean: bool = False,
        omit_ts: bool = False,
        no_header: bool = False,
        parallel: bool = True,
        max_workers: int = 8
    ) -> None:
        """Extract database schema and data.

        Args:
            output_dir: Output directory for SQL scripts
            schema_filter: Optional list of schemas to include
            extract_seed_data: Whether to extract seed data
            seed_tables: Optional list of tables for seed data (format: schema.table)
            max_rows: Maximum rows per table for seed data
            output_format: Output format - 'single', 'per-object', or 'modular'
            clean: Delete the output directory before extraction
            omit_ts: Omit the generation timestamp from output headers
            no_header: Omit the header comment block from output files entirely
            parallel: Run independent metadata/seed-data extraction queries concurrently,
                each on its own database connection
            max_workers: Maximum number of concurrent connections when parallel is True
        """
        try:
            # Connect to database
            logger.info("Connecting to database...")
            self.connection = DatabaseConnection(self.config)
            self.connection.connect()

            formatter = SQLFormatter(output_dir, omit_ts=omit_ts, no_header=no_header)

            # Extract all independent, schema-filtered metadata in parallel (each job
            # opens its own connection - sequences are extracted before tables since a
            # column's DEFAULT may reference one via NEXT VALUE FOR; user-defined types
            # before tables since a column's data type may reference one)
            metadata_jobs: Dict[str, Callable[[DatabaseConnection], Any]] = {
                'schemas': lambda conn: SchemaReader(conn).get_schemas(schema_filter),
                'user_defined_types': lambda conn: SchemaReader(conn).get_user_defined_types(schema_filter),
                'sequences': lambda conn: SchemaReader(conn).get_sequences(schema_filter),
                'tables': lambda conn: SchemaReader(conn).get_tables(schema_filter),
                'extended_properties': lambda conn: SchemaReader(conn).get_extended_properties(schema_filter),
                'primary_keys': lambda conn: ConstraintExtractor(conn).get_primary_keys(schema_filter),
                'foreign_keys': lambda conn: ConstraintExtractor(conn).get_foreign_keys(schema_filter),
                'unique_constraints': lambda conn: ConstraintExtractor(conn).get_unique_constraints(schema_filter),
                'check_constraints': lambda conn: ConstraintExtractor(conn).get_check_constraints(schema_filter),
                'indexes': lambda conn: IndexExtractor(conn).get_indexes(schema_filter),
                'views': lambda conn: SchemaReader(conn).get_views(schema_filter),
                'view_dependencies': lambda conn: SchemaReader(conn).get_view_dependencies(schema_filter),
                'procedures': lambda conn: SchemaReader(conn).get_stored_procedures(schema_filter),
                'functions': lambda conn: SchemaReader(conn).get_functions(schema_filter),
                'triggers': lambda conn: SchemaReader(conn).get_triggers(schema_filter),
            }

            logger.info(f"Extracting schema metadata ({'parallel' if parallel else 'sequential'}, {len(metadata_jobs)} queries)...")
            start = time.monotonic()
            results = self._run_jobs(metadata_jobs, parallel=parallel, max_workers=max_workers)
            logger.info(f"Schema metadata extracted in {time.monotonic() - start:.2f}s")

            schemas = results['schemas']
            user_defined_types = results['user_defined_types']
            sequences = results['sequences']
            tables = results['tables']
            extended_properties = results['extended_properties']
            primary_keys = results['primary_keys']
            foreign_keys = results['foreign_keys']
            unique_constraints = results['unique_constraints']
            check_constraints = results['check_constraints']
            indexes = results['indexes']
            views = results['views']
            view_dependencies = results['view_dependencies']
            procedures = results['procedures']
            functions = results['functions']
            triggers = results['triggers']

            # Order tables by dependency
            logger.info("Analyzing dependencies...")
            table_tuples = [(t.schema_name, t.table_name) for t in tables]
            ordered_table_tuples, deferred_fks = order_tables_by_dependency(table_tuples, foreign_keys)

            # Reorder tables list
            table_map = {(t.schema_name, t.table_name): t for t in tables}
            ordered_tables = [table_map[t] for t in ordered_table_tuples if t in table_map]

            # Order views by dependency (a view referencing another view must be
            # created after the view it references)
            views = order_views_by_dependency(views, view_dependencies)

            # Extract seed data if requested
            seed_data = []
            seed_data_by_table: Dict[str, List[str]] = {}
            if extract_seed_data:
                # Determine which tables to extract data from
                data_tables = []
                if seed_tables:
                    # Parse seed_tables list (format: schema.table)
                    for table_spec in seed_tables:
                        parts = table_spec.split('.')
                        if len(parts) == 2:
                            schema_name, table_name = parts
                            matching_table = next(
                                (t for t in ordered_tables if t.schema_name == schema_name and t.table_name == table_name),
                                None
                            )
                            if matching_table:
                                data_tables.append(matching_table)
                            else:
                                logger.warning(f"Table {table_spec} not found")
                        else:
                            logger.warning(f"Invalid table specification: {table_spec}")
                else:
                    # Extract from all tables
                    data_tables = ordered_tables

                logger.info(f"Extracting seed data from {len(data_tables)} table(s)...")
                seed_jobs: Dict[str, Callable[[DatabaseConnection], List[str]]] = {
                    f"{table.schema_name}.{table.table_name}": (
                        lambda conn, t=table: SeedDataExtractor(conn).extract_table_data(
                            t.schema_name, t.table_name, t.columns, max_rows=max_rows
                        )
                    )
                    for table in data_tables
                }
                seed_results = self._run_jobs(seed_jobs, parallel=parallel, max_workers=max_workers)

                # Reassemble in dependency order (not completion order)
                for table in data_tables:
                    key = f"{table.schema_name}.{table.table_name}"
                    table_data = seed_results[key]
                    seed_data.extend(table_data)
                    seed_data_by_table[key] = table_data

            # Generate SQL scripts
            if clean and os.path.exists(output_dir):
                logger.info(f"Cleaning output directory: {output_dir}")
                shutil.rmtree(output_dir)

            logger.info("Generating SQL scripts...")
            if output_format == 'single':
                formatter.write_single_file(
                    schemas=schemas,
                    user_defined_types=user_defined_types,
                    sequences=sequences,
                    tables=ordered_tables,
                    extended_properties=extended_properties,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys,
                    deferred_foreign_keys=deferred_fks,
                    unique_constraints=unique_constraints,
                    check_constraints=check_constraints,
                    indexes=indexes,
                    views=views,
                    procedures=procedures,
                    functions=functions,
                    triggers=triggers,
                    seed_data=seed_data
                )
            elif output_format == 'per-object':
                formatter.write_per_object_format(
                    schemas=schemas,
                    user_defined_types=user_defined_types,
                    sequences=sequences,
                    tables=ordered_tables,
                    extended_properties=extended_properties,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys,
                    deferred_foreign_keys=deferred_fks,
                    unique_constraints=unique_constraints,
                    check_constraints=check_constraints,
                    indexes=indexes,
                    views=views,
                    procedures=procedures,
                    functions=functions,
                    triggers=triggers,
                    seed_data_by_table=seed_data_by_table
                )
            else:
                formatter.write_modular_format(
                    schemas=schemas,
                    user_defined_types=user_defined_types,
                    sequences=sequences,
                    tables=ordered_tables,
                    extended_properties=extended_properties,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys,
                    deferred_foreign_keys=deferred_fks,
                    unique_constraints=unique_constraints,
                    check_constraints=check_constraints,
                    indexes=indexes,
                    views=views,
                    procedures=procedures,
                    functions=functions,
                    triggers=triggers,
                    seed_data=seed_data
                )

            formatter.write_readme(
                output_format=output_format,
                schemas=schemas,
                user_defined_types=user_defined_types,
                sequences=sequences,
                tables=ordered_tables,
                views=views,
                procedures=procedures,
                functions=functions,
                triggers=triggers,
                indexes=indexes,
                deferred_foreign_keys=deferred_fks,
                has_seed_data=bool(seed_data)
            )

            logger.info("Extraction complete!")

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise ExtractionError(f"Extraction failed: {e}")

        finally:
            if self.connection:
                self.connection.close()
