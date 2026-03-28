"""Tests for EGS self-modification via TransformRegistry.

Covers: registry CRUD, built-in transforms (duplicate, summarize),
executor integration, backward compatibility, and metadata provenance.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from datetime import datetime, timezone

import pytest

from egs.graph import EGS
from egs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata
from egs.executor import GraphExecutor
from egs.transform import TransformRegistry, TransformResult, default_registry


def _meta(created_by: str = "test") -> NodeMetadata:
    return NodeMetadata(created_by=created_by, created_at=datetime.now(timezone.utc))


def _edge_meta(created_by: str = "test") -> EdgeMetadata:
    return EdgeMetadata(created_by=created_by, created_at=datetime.now(timezone.utc))


# ── TransformRegistry ──────────────────────────────────────────────


class TestTransformRegistry:
    def test_register_and_get(self):
        registry = TransformRegistry()

        @registry.register("noop")
        def noop(inputs, config):
            return TransformResult()

        assert registry.get("noop") is noop

    def test_get_unregistered_returns_none(self):
        registry = TransformRegistry()
        assert registry.get("nonexistent") is None

    def test_register_multiple(self):
        registry = TransformRegistry()

        @registry.register("a")
        def fn_a(inputs, config):
            return TransformResult()

        @registry.register("b")
        def fn_b(inputs, config):
            return TransformResult()

        assert registry.get("a") is fn_a
        assert registry.get("b") is fn_b


# ── Built-in: duplicate ────────────────────────────────────────────


class TestDuplicate:
    def test_creates_copies(self):
        fn = default_registry.get("duplicate")
        assert fn is not None

        result = fn({"op1": 42, "op2": 99}, {})
        assert len(result.nodes) == 2

        ids = {n.id for n in result.nodes}
        assert "op1_copy" in ids
        assert "op2_copy" in ids

    def test_copy_values_match(self):
        fn = default_registry.get("duplicate")
        result = fn({"x": 7}, {})
        assert result.nodes[0].data["value"] == 7

    def test_copy_type_is_operand(self):
        fn = default_registry.get("duplicate")
        result = fn({"x": 1}, {})
        assert result.nodes[0].type == NodeType.OPERAND

    def test_copy_metadata_created_by(self):
        fn = default_registry.get("duplicate")
        result = fn({"x": 1}, {})
        assert result.nodes[0].metadata.created_by == "builtin:duplicate"


# ── Built-in: summarize ────────────────────────────────────────────


class TestSummarize:
    def test_creates_summary_node(self):
        fn = default_registry.get("summarize")
        assert fn is not None

        result = fn({"a": 10, "b": 20, "c": 30}, {})
        assert len(result.nodes) == 1
        assert result.nodes[0].id == "summary"

    def test_correct_stats(self):
        fn = default_registry.get("summarize")
        result = fn({"a": 10, "b": 20, "c": 30}, {})
        data = result.nodes[0].data

        assert data["count"] == 3
        assert data["sum"] == 60
        assert data["avg"] == 20.0
        assert data["min"] == 10
        assert data["max"] == 30

    def test_custom_output_id(self):
        fn = default_registry.get("summarize")
        result = fn({"a": 5}, {"output_id": "my_summary"})
        assert result.nodes[0].id == "my_summary"

    def test_summary_type_is_concept(self):
        fn = default_registry.get("summarize")
        result = fn({"a": 1}, {})
        assert result.nodes[0].type == NodeType.CONCEPT

    def test_summary_metadata_created_by(self):
        fn = default_registry.get("summarize")
        result = fn({"a": 1}, {})
        assert result.nodes[0].metadata.created_by == "builtin:summarize"

    def test_empty_inputs(self):
        fn = default_registry.get("summarize")
        result = fn({}, {})
        assert result.nodes[0].data["count"] == 0


# ── Executor integration ───────────────────────────────────────────


def _build_transform_graph(transform_fn: str = "summarize"):
    """Build a graph with 3 operands feeding a TRANSFORM node."""
    graph = EGS()
    for i, val in enumerate([10, 20, 30]):
        graph.add_node(Node(
            id=f"op{i}",
            type=NodeType.OPERAND,
            data={"value": val},
            metadata=_meta(),
        ))
    graph.add_node(Node(
        id="transform_1",
        type=NodeType.TRANSFORM,
        data={"transform_fn": transform_fn},
        metadata=_meta(),
    ))
    for i in range(3):
        graph.add_edge(Edge(
            source_id=f"op{i}",
            target_id="transform_1",
            relation="FEEDS",
            metadata=_edge_meta(),
        ))
    return graph


class TestExecutorWithTransforms:
    def test_transform_creates_nodes(self):
        graph = _build_transform_graph("summarize")
        initial_count = len(graph.nodes)

        executor = GraphExecutor(graph, transforms=default_registry)
        trace = executor.execute()

        assert trace.success
        assert len(graph.nodes) > initial_count

    def test_graph_has_more_nodes_after(self):
        graph = _build_transform_graph("summarize")
        executor = GraphExecutor(graph, transforms=default_registry)
        executor.execute()

        # 3 operands + 1 transform + 1 summary = 5
        assert len(graph.nodes) == 5

    def test_new_nodes_have_transform_created_by(self):
        graph = _build_transform_graph("summarize")
        executor = GraphExecutor(graph, transforms=default_registry)
        executor.execute()

        summary = graph.get_node("summary")
        assert summary is not None
        assert summary.metadata.created_by == "transform:transform_1"

    def test_transform_output_is_created_ids(self):
        graph = _build_transform_graph("summarize")
        executor = GraphExecutor(graph, transforms=default_registry)
        trace = executor.execute()

        # Find the TRANSFORM step
        transform_step = [s for s in trace.steps if s.node_type == "TRANSFORM"][0]
        assert "summary" in transform_step.output

    def test_duplicate_transform_integration(self):
        graph = _build_transform_graph("duplicate")
        executor = GraphExecutor(graph, transforms=default_registry)
        trace = executor.execute()

        assert trace.success
        # 3 operands + 1 transform + 3 copies = 7
        assert len(graph.nodes) == 7

    def test_duplicate_copies_have_correct_metadata(self):
        graph = _build_transform_graph("duplicate")
        executor = GraphExecutor(graph, transforms=default_registry)
        executor.execute()

        copy = graph.get_node("op0_copy")
        assert copy is not None
        assert copy.metadata.created_by == "transform:transform_1"


class TestExecutorBackwardCompat:
    def test_no_registry_passthrough(self):
        """Without a registry, TRANSFORM is passthrough (backward compatible)."""
        graph = _build_transform_graph("summarize")
        initial_count = len(graph.nodes)

        executor = GraphExecutor(graph)
        trace = executor.execute()

        assert trace.success
        # No new nodes created
        assert len(graph.nodes) == initial_count

    def test_unknown_transform_passthrough(self):
        """Unknown transform_fn is treated as passthrough."""
        graph = _build_transform_graph("nonexistent_fn")
        initial_count = len(graph.nodes)

        executor = GraphExecutor(graph, transforms=default_registry)
        trace = executor.execute()

        assert trace.success
        assert len(graph.nodes) == initial_count

    def test_no_transform_fn_in_data_passthrough(self):
        """TRANSFORM node without transform_fn key is passthrough."""
        graph = EGS()
        graph.add_node(Node(
            id="t1",
            type=NodeType.TRANSFORM,
            data={},
            metadata=_meta(),
        ))
        executor = GraphExecutor(graph, transforms=default_registry)
        trace = executor.execute()

        assert trace.success
        assert len(graph.nodes) == 1
