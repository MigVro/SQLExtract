"""Main extraction orchestration module."""

import os
import shutil
from typing import List, Optional, Dict, Any
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
        no_header: bool = False
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
        """
        try:
            # Connect to database
            logger.info("Connecting to database...")
            self.connection = DatabaseConnection(self.config)
            self.connection.connect()

            # Initialize components
            schema_reader = SchemaReader(self.connection)
            constraint_extractor = ConstraintExtractor(self.connection)
            index_extractor = IndexExtractor(self.connection)
            seed_data_extractor = SeedDataExtractor(self.connection)
            formatter = SQLFormatter(output_dir, omit_ts=omit_ts, no_header=no_header)

            # Extract schemas
            logger.info("Extracting schemas...")
            schemas = schema_reader.get_schemas(schema_filter)

            # Extract sequences (extracted before tables, since a column's DEFAULT
            # may reference a sequence via NEXT VALUE FOR)
            logger.info("Extracting sequences...")
            sequences = schema_reader.get_sequences(schema_filter)

            # Extract tables
            logger.info("Extracting tables...")
            tables = schema_reader.get_tables(schema_filter)

            # Extract extended properties (table/column descriptions)
            logger.info("Extracting extended properties...")
            extended_properties = schema_reader.get_extended_properties(schema_filter)

            # Extract constraints
            logger.info("Extracting constraints...")
            primary_keys = constraint_extractor.get_primary_keys(schema_filter)
            foreign_keys = constraint_extractor.get_foreign_keys(schema_filter)
            unique_constraints = constraint_extractor.get_unique_constraints(schema_filter)
            check_constraints = constraint_extractor.get_check_constraints(schema_filter)

            # Order tables by dependency
            logger.info("Analyzing dependencies...")
            table_tuples = [(t.schema_name, t.table_name) for t in tables]
            ordered_table_tuples, deferred_fks = order_tables_by_dependency(table_tuples, foreign_keys)

            # Reorder tables list
            table_map = {(t.schema_name, t.table_name): t for t in tables}
            ordered_tables = [table_map[t] for t in ordered_table_tuples if t in table_map]

            # Extract indexes
            logger.info("Extracting indexes...")
            indexes = index_extractor.get_indexes(schema_filter)

            # Extract views and order them by dependency (a view referencing
            # another view must be created after the view it references)
            logger.info("Extracting views...")
            views = schema_reader.get_views(schema_filter)
            view_dependencies = schema_reader.get_view_dependencies(schema_filter)
            views = order_views_by_dependency(views, view_dependencies)

            # Extract stored procedures
            logger.info("Extracting stored procedures...")
            procedures = schema_reader.get_stored_procedures(schema_filter)

            # Extract functions
            logger.info("Extracting functions...")
            functions = schema_reader.get_functions(schema_filter)

            # Extract triggers
            logger.info("Extracting triggers...")
            triggers = schema_reader.get_triggers(schema_filter)

            # Extract seed data if requested
            seed_data = []
            seed_data_by_table: Dict[str, List[str]] = {}
            if extract_seed_data:
                logger.info("Extracting seed data...")

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

                # Extract data in dependency order
                for table in data_tables:
                    logger.info(f"Extracting data from {table.schema_name}.{table.table_name}...")
                    table_data = seed_data_extractor.extract_table_data(
                        table.schema_name,
                        table.table_name,
                        table.columns,
                        max_rows=max_rows
                    )
                    seed_data.extend(table_data)
                    seed_data_by_table[f"{table.schema_name}.{table.table_name}"] = table_data

            # Generate SQL scripts
            if clean and os.path.exists(output_dir):
                logger.info(f"Cleaning output directory: {output_dir}")
                shutil.rmtree(output_dir)

            logger.info("Generating SQL scripts...")
            if output_format == 'single':
                formatter.write_single_file(
                    schemas=schemas,
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
