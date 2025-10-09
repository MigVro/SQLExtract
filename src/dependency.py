"""Dependency analysis and ordering module."""

from typing import List, Dict, Set, Tuple
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

    def add_dependency(self, from_schema: str, from_table: str, to_schema: str, to_table: str) -> None:
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

            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.remove(node)

        for table in self.all_tables:
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
        # Calculate in-degree for each node
        in_degree = {table: 0 for table in self.all_tables}
        for table in self.all_tables:
            for dep in self.graph.get(table, []):
                if dep in in_degree:
                    in_degree[dep] += 1

        # Queue for nodes with no dependencies
        queue = deque([table for table, degree in in_degree.items() if degree == 0])
        sorted_tables = []
        deferred_fks = []

        while queue:
            table = queue.popleft()
            sorted_tables.append(table)

            # Reduce in-degree for dependent tables
            for dependent in self.reverse_graph.get(table, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # If not all tables are sorted, there are circular dependencies
        if len(sorted_tables) < len(self.all_tables):
            remaining = set(self.all_tables) - set(sorted_tables)
            logger.warning(f"Circular dependencies detected. {len(remaining)} tables affected.")

            # Add remaining tables and mark their FKs as deferred
            for table in remaining:
                sorted_tables.append(table)
                for dep in self.graph.get(table, []):
                    if dep in remaining or dep in sorted_tables:
                        deferred_fks.append((table, dep))

        logger.info(f"Topological sort complete: {len(sorted_tables)} tables ordered")
        if deferred_fks:
            logger.info(f"Deferred {len(deferred_fks)} foreign keys due to circular dependencies")

        return sorted_tables, deferred_fks


def build_dependency_graph(tables: List[Tuple[str, str]], foreign_keys: List[ForeignKeyInfo]) -> DependencyGraph:
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
            fk.schema_name,
            fk.table_name,
            fk.referenced_schema,
            fk.referenced_table
        )

    return graph


def order_tables_by_dependency(tables: List[Tuple[str, str]], foreign_keys: List[ForeignKeyInfo]) -> Tuple[List[Tuple[str, str]], List[ForeignKeyInfo]]:
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
        schema_name, table_name = table_key.split('.', 1)
        ordered_tables.append((schema_name, table_name))

    # Find deferred foreign keys
    deferred_fks = []
    for fk in foreign_keys:
        from_key = f"{fk.schema_name}.{fk.table_name}"
        to_key = f"{fk.referenced_schema}.{fk.referenced_table}"
        if (from_key, to_key) in deferred_fk_keys:
            deferred_fks.append(fk)

    return ordered_tables, deferred_fks
