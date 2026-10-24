"""Dependency analysis and ordering module."""

from typing import List, Dict, Set, Tuple, Any
from collections import defaultdict, deque
from .constraints import ForeignKeyInfo
from .utils import get_logger

logger = get_logger(__name__)


class DependencyGraph:
    """Build and analyze table dependency graph."""

    def __init__(self):
        """Initialize dependency graph."""
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self.all_tables: Set[str] = set()

    def add_table(self, schema_name: str, table_name: str) -> None:
        """Add a table to the graph.

        Args:
            schema_name: Schema name
            table_name: Table name
        """
        table_key = f"{schema_name}.{table_name}"
        self.all_tables.add(table_key)
        if table_key not in self.graph:
            self.graph[table_key] = set()

    def add_dependency(
        self, from_schema: str, from_table: str, to_schema: str, to_table: str
    ) -> None:
        """Add a dependency (foreign key relationship).

        Args:
            from_schema: Source schema name
            from_table: Source table name
            to_schema: Target schema name
            to_table: Target table name
        """
        from_key = f"{from_schema}.{from_table}"
        to_key = f"{to_schema}.{to_table}"

        self.graph[from_key].add(to_key)
        self.reverse_graph[to_key].add(from_key)
        self.all_tables.add(from_key)
        self.all_tables.add(to_key)

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the graph.

        Returns:
            List of circular dependency chains
        """
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in sorted(self.graph.get(node, [])):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.remove(node)

        for table in sorted(self.all_tables):
            if table not in visited:
                dfs(table, [])

        if cycles:
            logger.warning(f"Found {len(cycles)} circular dependencies")
            for cycle in cycles:
                logger.warning(f"  Cycle: {' -> '.join(cycle)}")

        return cycles

    def topological_sort(self) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Perform topological sort on the dependency graph.

        Returns:
            Tuple of (ordered tables, deferred foreign keys)
            Deferred foreign keys are those that create circular dependencies
        """
        # Calculate in-degree for each node (how many tables each table depends on)
        # In-degree = number of incoming edges = number of dependencies
        in_degree = {table: len(self.graph.get(table, set())) for table in sorted(self.all_tables)}

        # Queue for nodes with no dependencies (in-degree = 0)
        # These tables can be created first
        queue = deque(sorted(table for table, degree in in_degree.items() if degree == 0))
        sorted_tables = []
        deferred_fks = []

        while queue:
            # Process a table with no remaining dependencies
            table = queue.popleft()
            sorted_tables.append(table)

            # For all tables that depend on this table, reduce their in-degree
            # (since this dependency is now satisfied)
            for dependent in sorted(self.reverse_graph.get(table, [])):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # If not all tables are sorted, there are circular dependencies
        if len(sorted_tables) < len(self.all_tables):
            remaining = sorted(set(self.all_tables) - set(sorted_tables))
            logger.warning(f"Circular dependencies detected. {len(remaining)} tables affected.")

            # Add remaining tables and mark their FKs as deferred
            for table in remaining:
                sorted_tables.append(table)
                for dep in sorted(self.graph.get(table, [])):
                    if dep in remaining or dep in sorted_tables:
                        deferred_fks.append((table, dep))

        logger.info(f"Topological sort complete: {len(sorted_tables)} tables ordered")
        if deferred_fks:
            logger.info(f"Deferred {len(deferred_fks)} foreign keys due to circular dependencies")

        return sorted_tables, deferred_fks


def build_dependency_graph(
    tables: List[Tuple[str, str]], foreign_keys: List[ForeignKeyInfo]
) -> DependencyGraph:
    """Build dependency graph from tables and foreign keys.

    Args:
        tables: List of (schema_name, table_name) tuples
        foreign_keys: List of foreign key information

    Returns:
        Dependency graph
    """
    graph = DependencyGraph()

    # Add all tables
    for schema_name, table_name in tables:
        graph.add_table(schema_name, table_name)

    # Add foreign key dependencies
    for fk in foreign_keys:
        graph.add_dependency(
            fk.schema_name, fk.table_name, fk.referenced_schema, fk.referenced_table
        )

    return graph


def order_tables_by_dependency(
    tables: List[Tuple[str, str]], foreign_keys: List[ForeignKeyInfo]
) -> Tuple[List[Tuple[str, str]], List[ForeignKeyInfo]]:
    """Order tables by their dependencies.

    Args:
        tables: List of (schema_name, table_name) tuples
        foreign_keys: List of foreign key information

    Returns:
        Tuple of (ordered tables, deferred foreign keys)
    """
    graph = build_dependency_graph(tables, foreign_keys)

    # Detect circular dependencies
    cycles = graph.detect_circular_dependencies()

    # Perform topological sort
    sorted_table_keys, deferred_fk_keys = graph.topological_sort()

    # Convert back to tuples
    ordered_tables = []
    for table_key in sorted_table_keys:
        schema_name, table_name = table_key.split(".", 1)
        ordered_tables.append((schema_name, table_name))

    # Find deferred foreign keys
    deferred_fks = []
    for fk in foreign_keys:
        from_key = f"{fk.schema_name}.{fk.table_name}"
        to_key = f"{fk.referenced_schema}.{fk.referenced_table}"
        if (from_key, to_key) in deferred_fk_keys:
            deferred_fks.append(fk)

    return ordered_tables, deferred_fks


def order_views_by_dependency(
    views: List[Dict[str, Any]], dependencies: List[Tuple[str, str, str, str]]
) -> List[Dict[str, Any]]:
    """Order views so that a view referenced by another view is created first.

    Args:
        views: List of view dicts with 'schema_name' and 'view_name' keys
        dependencies: List of (schema_name, view_name, referenced_schema_name, referenced_view_name) tuples

    Returns:
        Views ordered so dependencies come before the views that reference them
    """
    view_map = {f"{v['schema_name']}.{v['view_name']}": v for v in views}

    graph = DependencyGraph()
    for view_key in view_map:
        schema_name, view_name = view_key.split(".", 1)
        graph.add_table(schema_name, view_name)

    for schema_name, view_name, ref_schema_name, ref_view_name in dependencies:
        ref_key = f"{ref_schema_name}.{ref_view_name}"
        if ref_key not in view_map:
            # Referenced view was filtered out (e.g. by --schemas) or unresolved; skip
            continue
        graph.add_dependency(schema_name, view_name, ref_schema_name, ref_view_name)

    cycles = graph.detect_circular_dependencies()
    if cycles:
        logger.warning("Circular view dependencies detected; falling back to original order")
        for cycle in cycles:
            logger.warning(f"  Cycle: {' -> '.join(cycle)}")
        return views

    sorted_view_keys, _ = graph.topological_sort()
    return [view_map[key] for key in sorted_view_keys if key in view_map]
