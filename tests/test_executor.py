"""Tests for the EGS topological executor."""

from datetime import datetime, timezone

import pytest

from egs import EGS, Node, NodeType, Edge, EdgeMetadata, NodeMetadata
from egs.executor import GraphExecutor, CycleError, ExecutionTrace


def _meta(agent: str = "test") -> NodeMetadata:
    return NodeMetadata(created_by=agent, created_at=datetime.now(timezone.utc))


def _edge_meta() -> EdgeMetadata:
    return EdgeMetadata(created_by="test", created_at=datetime.now(timezone.utc))


def _operand(id: str, value) -> Node:
    return Node(id=id, type=NodeType.OPERAND, data={"value": value}, metadata=_meta())


def _operation(id: str, op: str, **extra) -> Node:
    data = {"operation": op, **extra}
    return Node(id=id, type=NodeType.OPERATION, data=data, metadata=_meta())


def _result(id: str, op: str = "identity") -> Node:
    return Node(id=id, type=NodeType.RESULT, data={"operation": op}, metadata=_meta())


def _feeds(src: str, tgt: str) -> Edge:
    return Edge(source_id=src, target_id=tgt, relation="FEEDS", metadata=_edge_meta())


def _requires(src: str, tgt: str) -> Edge:
    return Edge(source_id=src, target_id=tgt, relation="REQUIRES", metadata=_edge_meta())


class TestEmptyGraph:
    def test_empty_graph_returns_success(self):
        graph = EGS()
        trace = GraphExecutor(graph).execute()
        assert trace.success is True
        assert trace.result is None
        assert trace.steps == []

    def test_graph_with_no_executable_nodes(self):
        graph = EGS()
        graph.add_node(Node(id="c1", type=NodeType.CONCEPT, data={}, metadata=_meta()))
        trace = GraphExecutor(graph).execute()
        assert trace.success is True
        assert trace.steps == []


class TestSimpleArithmetic:
    def test_add_two_operands(self):
        graph = EGS()
        graph.add_node(_operand("a", 3))
        graph.add_node(_operand("b", 5))
        graph.add_node(_result("r", "add"))
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.success is True
        assert trace.result == 8

    def test_multiply_two_operands(self):
        graph = EGS()
        graph.add_node(_operand("a", 6))
        graph.add_node(_operand("b", 7))
        graph.add_node(_result("r", "multiply"))
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 42

    def test_subtract(self):
        graph = EGS()
        graph.add_node(_operand("a", 10))
        graph.add_node(_operand("b", 3))
        graph.add_node(_result("r", "subtract"))
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 7

    def test_chained_operations(self):
        """3 + 5 = 8, then 8 * 2 = 16."""
        graph = EGS()
        graph.add_node(_operand("a", 3))
        graph.add_node(_operand("b", 5))
        graph.add_node(_operation("add", "add"))
        graph.add_node(_operand("c", 2))
        graph.add_node(_result("r", "multiply"))
        graph.add_edge(_feeds("a", "add"))
        graph.add_edge(_feeds("b", "add"))
        graph.add_edge(_feeds("add", "r"))
        graph.add_edge(_feeds("c", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 16


class TestCompare:
    def test_equal_true(self):
        graph = EGS()
        graph.add_node(_operand("a", 5))
        graph.add_node(_operand("b", 5))
        graph.add_node(_result("r", "compare"))
        graph.add_node.__wrapped__ if hasattr(graph.add_node, '__wrapped__') else None
        graph._nodes["r"].data["comparator"] = "eq"
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result is True

    def test_less_than(self):
        graph = EGS()
        graph.add_node(_operand("a", 3))
        graph.add_node(_operand("b", 7))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "compare", "comparator": "lt"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result is True

    def test_greater_than_false(self):
        graph = EGS()
        graph.add_node(_operand("a", 3))
        graph.add_node(_operand("b", 7))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "compare", "comparator": "gt"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result is False


class TestFilter:
    def test_filter_positive_passes(self):
        graph = EGS()
        graph.add_node(_operand("a", 5))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "filter", "condition": "positive"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 5

    def test_filter_positive_rejects(self):
        graph = EGS()
        graph.add_node(_operand("a", -3))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "filter", "condition": "positive"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result is None


class TestAggregate:
    def test_aggregate_sum(self):
        graph = EGS()
        graph.add_node(_operand("a", 1))
        graph.add_node(_operand("b", 2))
        graph.add_node(_operand("c", 3))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "aggregate", "method": "sum"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))
        graph.add_edge(_feeds("c", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 6

    def test_aggregate_avg(self):
        graph = EGS()
        graph.add_node(_operand("a", 10))
        graph.add_node(_operand("b", 20))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "aggregate", "method": "avg"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 15.0

    def test_aggregate_min_max(self):
        graph = EGS()
        graph.add_node(_operand("a", 5))
        graph.add_node(_operand("b", 2))
        graph.add_node(_operand("c", 8))
        node_min = Node(id="rmin", type=NodeType.RESULT, data={"operation": "aggregate", "method": "min"}, metadata=_meta())
        node_max = Node(id="rmax", type=NodeType.OPERATION, data={"operation": "aggregate", "method": "max"}, metadata=_meta())
        graph.add_node(node_min)
        graph.add_node(node_max)
        graph.add_edge(_feeds("a", "rmin"))
        graph.add_edge(_feeds("b", "rmin"))
        graph.add_edge(_feeds("c", "rmin"))
        graph.add_edge(_feeds("a", "rmax"))
        graph.add_edge(_feeds("b", "rmax"))
        graph.add_edge(_feeds("c", "rmax"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 2  # RESULT node is rmin

        # Check rmax output from trace steps
        max_step = next(s for s in trace.steps if s.node_id == "rmax")
        assert max_step.output == 8

    def test_aggregate_count(self):
        graph = EGS()
        graph.add_node(_operand("a", 10))
        graph.add_node(_operand("b", 20))
        graph.add_node(_operand("c", 30))
        node = Node(id="r", type=NodeType.RESULT, data={"operation": "aggregate", "method": "count"}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))
        graph.add_edge(_feeds("c", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 3


class TestIdentity:
    def test_identity_passthrough(self):
        graph = EGS()
        graph.add_node(_operand("a", 42))
        graph.add_node(_result("r", "identity"))
        graph.add_edge(_feeds("a", "r"))

        trace = GraphExecutor(graph).execute()
        assert trace.result == 42


class TestBranch:
    def test_branch_true(self):
        graph = EGS()
        graph.add_node(_operand("cond", True))
        node = Node(id="br", type=NodeType.BRANCH, data={}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("cond", "br"))

        trace = GraphExecutor(graph).execute()
        br_step = next(s for s in trace.steps if s.node_id == "br")
        assert br_step.output["condition"] is True

    def test_branch_false(self):
        graph = EGS()
        graph.add_node(_operand("cond", False))
        node = Node(id="br", type=NodeType.BRANCH, data={}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("cond", "br"))

        trace = GraphExecutor(graph).execute()
        br_step = next(s for s in trace.steps if s.node_id == "br")
        assert br_step.output["condition"] is False


class TestMerge:
    def test_merge_collects_inputs(self):
        graph = EGS()
        graph.add_node(_operand("a", 1))
        graph.add_node(_operand("b", 2))
        graph.add_node(_operand("c", 3))
        node = Node(id="m", type=NodeType.MERGE, data={}, metadata=_meta())
        graph.add_node(node)
        graph.add_edge(_feeds("a", "m"))
        graph.add_edge(_feeds("b", "m"))
        graph.add_edge(_feeds("c", "m"))

        trace = GraphExecutor(graph).execute()
        merge_step = next(s for s in trace.steps if s.node_id == "m")
        assert sorted(merge_step.output) == [1, 2, 3]


class TestCycleDetection:
    def test_simple_cycle_raises(self):
        graph = EGS()
        graph.add_node(_operation("a", "add"))
        graph.add_node(_operation("b", "add"))
        graph.add_edge(_feeds("a", "b"))
        graph.add_edge(_feeds("b", "a"))

        trace = GraphExecutor(graph).execute()
        assert trace.success is False
        assert "Cycle detected" in trace.error

    def test_three_node_cycle(self):
        graph = EGS()
        graph.add_node(_operation("a", "add"))
        graph.add_node(_operation("b", "add"))
        graph.add_node(_operation("c", "add"))
        graph.add_edge(_feeds("a", "b"))
        graph.add_edge(_feeds("b", "c"))
        graph.add_edge(_feeds("c", "a"))

        trace = GraphExecutor(graph).execute()
        assert trace.success is False
        assert "Cycle detected" in trace.error


class TestExecutionTrace:
    def test_trace_records_all_steps(self):
        graph = EGS()
        graph.add_node(_operand("a", 3))
        graph.add_node(_operand("b", 5))
        graph.add_node(_result("r", "add"))
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_feeds("b", "r"))

        trace = GraphExecutor(graph).execute()
        assert len(trace.steps) == 3
        assert trace.steps[0].node_type == "OPERAND"
        assert trace.steps[1].node_type == "OPERAND"
        assert trace.steps[2].node_type == "RESULT"
        assert trace.steps[2].output == 8

    def test_trace_step_order_is_sequential(self):
        graph = EGS()
        graph.add_node(_operand("a", 1))
        graph.add_node(_operand("b", 2))
        graph.add_node(_operation("op", "add"))
        graph.add_node(_result("r", "identity"))
        graph.add_edge(_feeds("a", "op"))
        graph.add_edge(_feeds("b", "op"))
        graph.add_edge(_feeds("op", "r"))

        trace = GraphExecutor(graph).execute()
        orders = [s.order for s in trace.steps]
        assert orders == [0, 1, 2, 3]

    def test_requires_edge_enforces_order(self):
        """REQUIRES edges enforce ordering without carrying data."""
        graph = EGS()
        graph.add_node(_operand("a", 10))
        graph.add_node(_operand("b", 20))
        graph.add_node(_result("r", "identity"))
        graph.add_edge(_feeds("a", "r"))
        graph.add_edge(_requires("b", "r"))  # b must run before r but doesn't feed data

        trace = GraphExecutor(graph).execute()
        assert trace.success is True
        # r only gets data from a (via FEEDS), not from b (REQUIRES)
        assert trace.result == 10


class TestComplexGraph:
    def test_diamond_dependency(self):
        """a → op1, a → op2, op1 → r, op2 → r."""
        graph = EGS()
        graph.add_node(_operand("a", 5))
        graph.add_node(_operation("op1", "multiply"))
        graph.add_node(_operation("op2", "add"))
        graph.add_node(_operand("two", 2))
        graph.add_node(_operand("ten", 10))
        graph.add_node(_result("r", "add"))
        graph.add_edge(_feeds("a", "op1"))
        graph.add_edge(_feeds("two", "op1"))    # 5 * 2 = 10
        graph.add_edge(_feeds("a", "op2"))
        graph.add_edge(_feeds("ten", "op2"))    # 5 + 10 = 15
        graph.add_edge(_feeds("op1", "r"))
        graph.add_edge(_feeds("op2", "r"))      # 10 + 15 = 25

        trace = GraphExecutor(graph).execute()
        assert trace.result == 25
