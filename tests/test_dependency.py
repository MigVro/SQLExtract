"""Tests for dependency analysis module."""

import pytest
from src.dependency import DependencyGraph, build_dependency_graph, order_tables_by_dependency
from src.constraints import ForeignKeyInfo


class TestDependencyGraph:
    """Test DependencyGraph class."""

    def test_add_table(self):
        """Test adding tables to the graph."""
        graph = DependencyGraph()

        graph.add_table("dbo", "Config")
        graph.add_table("MQTT", "Broker")

        assert "dbo.Config" in graph.all_tables
        assert "MQTT.Broker" in graph.all_tables
        assert len(graph.all_tables) == 2

    def test_add_dependency(self):
        """Test adding dependencies (foreign keys)."""
        graph = DependencyGraph()

        graph.add_dependency("MQTT", "ReceiverConfig", "MQTT", "Broker")

        assert "MQTT.ReceiverConfig" in graph.all_tables
        assert "MQTT.Broker" in graph.all_tables
        assert "MQTT.Broker" in graph.graph["MQTT.ReceiverConfig"]
        assert "MQTT.ReceiverConfig" in graph.reverse_graph["MQTT.Broker"]

    def test_simple_topological_sort(self):
        """Test topological sort without circular dependencies."""
        graph = DependencyGraph()

        # Create simple dependency: Config (no deps) <- Broker <- ReceiverConfig
        graph.add_table("dbo", "Config")
        graph.add_table("MQTT", "Broker")
        graph.add_table("MQTT", "ReceiverConfig")

        # ReceiverConfig depends on Broker
        graph.add_dependency("MQTT", "ReceiverConfig", "MQTT", "Broker")

        sorted_tables, deferred_fks = graph.topological_sort()

        # All tables should be sorted
        assert len(sorted_tables) == 3
        assert len(deferred_fks) == 0

        # Broker should come before ReceiverConfig (ReceiverConfig depends on Broker)
        broker_idx = sorted_tables.index("MQTT.Broker")
        receiver_idx = sorted_tables.index("MQTT.ReceiverConfig")
        assert broker_idx < receiver_idx

    def test_complex_topological_sort(self):
        """Test topological sort with complex dependencies."""
        graph = DependencyGraph()

        # Create dependency chain: A <- B <- C, A <- D
        graph.add_table("dbo", "TableA")
        graph.add_table("dbo", "TableB")
        graph.add_table("dbo", "TableC")
        graph.add_table("dbo", "TableD")

        graph.add_dependency("dbo", "TableB", "dbo", "TableA")
        graph.add_dependency("dbo", "TableC", "dbo", "TableB")
        graph.add_dependency("dbo", "TableD", "dbo", "TableA")

        sorted_tables, deferred_fks = graph.topological_sort()

        # All tables should be present
        assert len(sorted_tables) == 4
        assert "dbo.TableA" in sorted_tables
        assert "dbo.TableB" in sorted_tables
        assert "dbo.TableC" in sorted_tables
        assert "dbo.TableD" in sorted_tables

        # No circular dependencies - all FKs should be preserved
        assert len(deferred_fks) == 0

        # Verify correct dependency ordering
        a_idx = sorted_tables.index("dbo.TableA")
        b_idx = sorted_tables.index("dbo.TableB")
        c_idx = sorted_tables.index("dbo.TableC")
        d_idx = sorted_tables.index("dbo.TableD")

        # TableA comes before TableB (B depends on A)
        assert a_idx < b_idx
        # TableB comes before TableC (C depends on B)
        assert b_idx < c_idx
        # TableA comes before TableD (D depends on A)
        assert a_idx < d_idx

    def test_detect_circular_dependencies(self):
        """Test detection of circular dependencies."""
        graph = DependencyGraph()

        # Create circular dependency: A -> B -> C -> A
        graph.add_table("dbo", "TableA")
        graph.add_table("dbo", "TableB")
        graph.add_table("dbo", "TableC")

        graph.add_dependency("dbo", "TableA", "dbo", "TableB")
        graph.add_dependency("dbo", "TableB", "dbo", "TableC")
        graph.add_dependency("dbo", "TableC", "dbo", "TableA")

        cycles = graph.detect_circular_dependencies()

        assert len(cycles) > 0
        # There should be at least one cycle detected
        assert any("dbo.TableA" in cycle for cycle in cycles)

    def test_topological_sort_with_circular_dependencies(self):
        """Test topological sort handles circular dependencies."""
        graph = DependencyGraph()

        # Create circular dependency: A -> B -> A
        graph.add_table("dbo", "TableA")
        graph.add_table("dbo", "TableB")

        graph.add_dependency("dbo", "TableA", "dbo", "TableB")
        graph.add_dependency("dbo", "TableB", "dbo", "TableA")

        sorted_tables, deferred_fks = graph.topological_sort()

        # All tables should still be in sorted list
        assert len(sorted_tables) == 2
        assert "dbo.TableA" in sorted_tables
        assert "dbo.TableB" in sorted_tables

        # At least one FK should be deferred
        assert len(deferred_fks) > 0

    def test_topological_sort_self_referencing_table(self):
        """Test topological sort with self-referencing table."""
        graph = DependencyGraph()

        # Create self-referencing table (e.g., Employee -> Employee.ManagerID)
        graph.add_table("dbo", "Employee")
        graph.add_dependency("dbo", "Employee", "dbo", "Employee")

        sorted_tables, deferred_fks = graph.topological_sort()

        assert len(sorted_tables) == 1
        assert "dbo.Employee" in sorted_tables

        # Self-reference should be deferred
        assert len(deferred_fks) >= 1
        assert ("dbo.Employee", "dbo.Employee") in deferred_fks

    def test_topological_sort_diamond_dependency(self):
        """Test topological sort with diamond dependency pattern."""
        graph = DependencyGraph()

        #    A
        #   / \
        #  B   C
        #   \ /
        #    D
        graph.add_table("dbo", "TableA")
        graph.add_table("dbo", "TableB")
        graph.add_table("dbo", "TableC")
        graph.add_table("dbo", "TableD")

        graph.add_dependency("dbo", "TableB", "dbo", "TableA")
        graph.add_dependency("dbo", "TableC", "dbo", "TableA")
        graph.add_dependency("dbo", "TableD", "dbo", "TableB")
        graph.add_dependency("dbo", "TableD", "dbo", "TableC")

        sorted_tables, deferred_fks = graph.topological_sort()

        # All tables should be present
        assert len(sorted_tables) == 4
        assert "dbo.TableA" in sorted_tables
        assert "dbo.TableB" in sorted_tables
        assert "dbo.TableC" in sorted_tables
        assert "dbo.TableD" in sorted_tables

        # No circular dependencies - all FKs should be preserved
        assert len(deferred_fks) == 0

        # Verify correct dependency ordering in diamond pattern
        a_idx = sorted_tables.index("dbo.TableA")
        b_idx = sorted_tables.index("dbo.TableB")
        c_idx = sorted_tables.index("dbo.TableC")
        d_idx = sorted_tables.index("dbo.TableD")

        # TableA comes before both B and C (they depend on A)
        assert a_idx < b_idx
        assert a_idx < c_idx
        # Both B and C come before D (D depends on both)
        assert b_idx < d_idx
        assert c_idx < d_idx

    def test_empty_graph(self):
        """Test topological sort on empty graph."""
        graph = DependencyGraph()

        sorted_tables, deferred_fks = graph.topological_sort()

        assert len(sorted_tables) == 0
        assert len(deferred_fks) == 0

    def test_graph_with_isolated_tables(self):
        """Test graph with tables that have no dependencies."""
        graph = DependencyGraph()

        graph.add_table("dbo", "Config")
        graph.add_table("dbo", "Status")
        graph.add_table("dbo", "Settings")

        sorted_tables, deferred_fks = graph.topological_sort()

        # All tables should be in the result
        assert len(sorted_tables) == 3
        assert len(deferred_fks) == 0
        assert "dbo.Config" in sorted_tables
        assert "dbo.Status" in sorted_tables
        assert "dbo.Settings" in sorted_tables


class TestBuildDependencyGraph:
    """Test build_dependency_graph function."""

    def test_build_graph_simple(self):
        """Test building graph from tables and foreign keys."""
        tables = [
            ("dbo", "Config"),
            ("MQTT", "Broker"),
            ("MQTT", "ReceiverConfig")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_ReceiverConfig_Broker",
                schema_name="MQTT",
                table_name="ReceiverConfig",
                columns=["BrokerID"],
                referenced_schema="MQTT",
                referenced_table="Broker",
                referenced_columns=["BrokerID"],
                delete_action="CASCADE",
                update_action="NO_ACTION"
            )
        ]

        graph = build_dependency_graph(tables, foreign_keys)

        assert len(graph.all_tables) == 3
        assert "MQTT.Broker" in graph.graph["MQTT.ReceiverConfig"]

    def test_build_graph_no_foreign_keys(self):
        """Test building graph with no foreign keys."""
        tables = [
            ("dbo", "Config"),
            ("dbo", "Status")
        ]

        foreign_keys = []

        graph = build_dependency_graph(tables, foreign_keys)

        assert len(graph.all_tables) == 2
        assert len(graph.graph["dbo.Config"]) == 0
        assert len(graph.graph["dbo.Status"]) == 0

    def test_build_graph_multi_column_fk(self):
        """Test building graph with multi-column foreign keys."""
        tables = [
            ("dbo", "Parent"),
            ("dbo", "Child")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_Child_Parent",
                schema_name="dbo",
                table_name="Child",
                columns=["ParentKey1", "ParentKey2"],
                referenced_schema="dbo",
                referenced_table="Parent",
                referenced_columns=["Key1", "Key2"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            )
        ]

        graph = build_dependency_graph(tables, foreign_keys)

        assert "dbo.Parent" in graph.graph["dbo.Child"]
        assert "dbo.Child" in graph.reverse_graph["dbo.Parent"]


class TestOrderTablesByDependency:
    """Test order_tables_by_dependency function."""

    def test_order_simple_dependency(self):
        """Test ordering tables with simple dependency."""
        tables = [
            ("MQTT", "ReceiverConfig"),
            ("MQTT", "Broker"),
            ("dbo", "Config")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_ReceiverConfig_Broker",
                schema_name="MQTT",
                table_name="ReceiverConfig",
                columns=["BrokerID"],
                referenced_schema="MQTT",
                referenced_table="Broker",
                referenced_columns=["BrokerID"],
                delete_action="CASCADE",
                update_action="NO_ACTION"
            )
        ]

        ordered_tables, deferred_fks = order_tables_by_dependency(tables, foreign_keys)

        assert len(ordered_tables) == 3
        assert len(deferred_fks) == 0

        # Broker should come before ReceiverConfig (ReceiverConfig depends on Broker)
        broker_idx = ordered_tables.index(("MQTT", "Broker"))
        receiver_idx = ordered_tables.index(("MQTT", "ReceiverConfig"))
        assert broker_idx < receiver_idx

    def test_order_circular_dependency(self):
        """Test ordering tables with circular dependency."""
        tables = [
            ("dbo", "TableA"),
            ("dbo", "TableB")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_A_B",
                schema_name="dbo",
                table_name="TableA",
                columns=["BID"],
                referenced_schema="dbo",
                referenced_table="TableB",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            ),
            ForeignKeyInfo(
                constraint_name="FK_B_A",
                schema_name="dbo",
                table_name="TableB",
                columns=["AID"],
                referenced_schema="dbo",
                referenced_table="TableA",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            )
        ]

        ordered_tables, deferred_fks = order_tables_by_dependency(tables, foreign_keys)

        # All tables should be ordered
        assert len(ordered_tables) == 2

        # At least one FK should be deferred
        assert len(deferred_fks) >= 1

        # Deferred FK should be one of the circular FKs
        deferred_names = [fk.constraint_name for fk in deferred_fks]
        assert any(name in ["FK_A_B", "FK_B_A"] for name in deferred_names)

    def test_order_no_dependencies(self):
        """Test ordering tables with no dependencies."""
        tables = [
            ("dbo", "Config"),
            ("dbo", "Status"),
            ("dbo", "Settings")
        ]

        foreign_keys = []

        ordered_tables, deferred_fks = order_tables_by_dependency(tables, foreign_keys)

        assert len(ordered_tables) == 3
        assert len(deferred_fks) == 0

    def test_order_complex_dependency_chain(self):
        """Test ordering tables with complex dependency chain."""
        tables = [
            ("dbo", "Level1"),
            ("dbo", "Level2A"),
            ("dbo", "Level2B"),
            ("dbo", "Level3")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_Level2A_Level1",
                schema_name="dbo",
                table_name="Level2A",
                columns=["Level1ID"],
                referenced_schema="dbo",
                referenced_table="Level1",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            ),
            ForeignKeyInfo(
                constraint_name="FK_Level2B_Level1",
                schema_name="dbo",
                table_name="Level2B",
                columns=["Level1ID"],
                referenced_schema="dbo",
                referenced_table="Level1",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            ),
            ForeignKeyInfo(
                constraint_name="FK_Level3_Level2A",
                schema_name="dbo",
                table_name="Level3",
                columns=["Level2AID"],
                referenced_schema="dbo",
                referenced_table="Level2A",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            ),
            ForeignKeyInfo(
                constraint_name="FK_Level3_Level2B",
                schema_name="dbo",
                table_name="Level3",
                columns=["Level2BID"],
                referenced_schema="dbo",
                referenced_table="Level2B",
                referenced_columns=["ID"],
                delete_action="NO_ACTION",
                update_action="NO_ACTION"
            )
        ]

        ordered_tables, deferred_fks = order_tables_by_dependency(tables, foreign_keys)

        # All tables should be present
        assert len(ordered_tables) == 4
        assert ("dbo", "Level1") in ordered_tables
        assert ("dbo", "Level2A") in ordered_tables
        assert ("dbo", "Level2B") in ordered_tables
        assert ("dbo", "Level3") in ordered_tables

        # No circular dependencies - all FKs should be preserved
        assert len(deferred_fks) == 0

        # Verify correct dependency ordering
        level1_idx = ordered_tables.index(("dbo", "Level1"))
        level2a_idx = ordered_tables.index(("dbo", "Level2A"))
        level2b_idx = ordered_tables.index(("dbo", "Level2B"))
        level3_idx = ordered_tables.index(("dbo", "Level3"))

        # Level1 comes before Level2A and Level2B
        assert level1_idx < level2a_idx
        assert level1_idx < level2b_idx
        # Both Level2A and Level2B come before Level3
        assert level2a_idx < level3_idx
        assert level2b_idx < level3_idx

    def test_order_preserves_table_tuples(self):
        """Test that ordering preserves (schema, table) tuple format."""
        tables = [
            ("MQTT", "ReceiverConfig"),
            ("MQTT", "Broker")
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constraint_name="FK_ReceiverConfig_Broker",
                schema_name="MQTT",
                table_name="ReceiverConfig",
                columns=["BrokerID"],
                referenced_schema="MQTT",
                referenced_table="Broker",
                referenced_columns=["BrokerID"],
                delete_action="CASCADE",
                update_action="NO_ACTION"
            )
        ]

        ordered_tables, deferred_fks = order_tables_by_dependency(tables, foreign_keys)

        # Verify all results are tuples
        assert all(isinstance(t, tuple) and len(t) == 2 for t in ordered_tables)

        # Verify tuples contain strings
        for schema, table in ordered_tables:
            assert isinstance(schema, str)
            assert isinstance(table, str)
