"""Tests for EGS provenance hash-chain ledger."""

from datetime import datetime, timezone

import pytest

from egs.graph import EGS
from egs.agent import Agent
from egs.executor import GraphExecutor
from egs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata
from egs.provenance import ProvenanceGraph, ProvenanceEntry
from egs.transform import TransformRegistry, TransformResult


@pytest.fixture
def meta():
    return NodeMetadata(created_by="test-agent", created_at=datetime.now(timezone.utc))


@pytest.fixture
def edge_meta():
    return EdgeMetadata(created_by="test-agent", created_at=datetime.now(timezone.utc))


@pytest.fixture
def graph():
    return EGS()


@pytest.fixture
def pg(graph):
    return ProvenanceGraph(graph)


def _make_node(node_id, meta, node_type=NodeType.OPERAND, data=None):
    return Node(id=node_id, type=node_type, data=data or {}, metadata=meta)


# --- add_node ---

def test_add_node_creates_ledger_entry(pg, meta):
    node = _make_node("n1", meta)
    pg.add_node(node)

    entries = pg.history()
    assert len(entries) == 1

    e = entries[0]
    assert e.sequence == 0
    assert e.operation == "add_node"
    assert e.agent_id == "test-agent"
    assert e.target_id == "n1"
    assert e.detail["node_type"] == "OPERAND"
    assert e.detail["node_id"] == "n1"
    assert e.previous_hash == ""
    assert len(e.hash) == 64  # SHA-256 hex


# --- remove_node ---

def test_remove_node_creates_entry_and_returns_node(pg, meta):
    node = _make_node("n1", meta)
    pg.add_node(node)

    removed = pg.remove_node("n1", agent_id="admin")
    assert removed is not None
    assert removed.id == "n1"

    entries = pg.history()
    assert len(entries) == 2
    e = entries[1]
    assert e.operation == "remove_node"
    assert e.agent_id == "admin"
    assert e.target_id == "n1"


def test_remove_nonexistent_node_no_entry(pg):
    result = pg.remove_node("ghost")
    assert result is None
    assert pg.ledger_size() == 0


# --- add_edge ---

def test_add_edge_creates_entry(pg, meta, edge_meta):
    pg.add_node(_make_node("a", meta))
    pg.add_node(_make_node("b", meta))

    edge = Edge(source_id="a", target_id="b", relation="FEEDS", metadata=edge_meta)
    pg.add_edge(edge)

    entries = pg.history()
    assert len(entries) == 3  # 2 add_node + 1 add_edge
    e = entries[2]
    assert e.operation == "add_edge"
    assert e.agent_id == "test-agent"
    assert e.target_id == "a->FEEDS->b"
    assert e.detail["source_id"] == "a"
    assert e.detail["target_id"] == "b"
    assert e.detail["relation"] == "FEEDS"


# --- remove_edge ---

def test_remove_edge_creates_entry(pg, meta, edge_meta):
    pg.add_node(_make_node("a", meta))
    pg.add_node(_make_node("b", meta))
    edge = Edge(source_id="a", target_id="b", relation="FEEDS", metadata=edge_meta)
    pg.add_edge(edge)

    removed = pg.remove_edge("a", "b", "FEEDS", agent_id="cleaner")
    assert removed is not None

    entries = pg.history()
    assert len(entries) == 4
    e = entries[3]
    assert e.operation == "remove_edge"
    assert e.agent_id == "cleaner"
    assert e.target_id == "a->FEEDS->b"


def test_remove_nonexistent_edge_no_entry(pg, meta):
    pg.add_node(_make_node("a", meta))
    initial_size = pg.ledger_size()
    result = pg.remove_edge("a", "z", "FEEDS")
    assert result is None
    assert pg.ledger_size() == initial_size


# --- update_node ---

def test_update_node_creates_entry_with_updated_keys(pg, meta):
    pg.add_node(_make_node("n1", meta, data={"value": 10}))
    pg.update_node("n1", {"value": 20, "label": "updated"}, agent_id="editor")

    entries = pg.history()
    assert len(entries) == 2
    e = entries[1]
    assert e.operation == "update_node"
    assert e.agent_id == "editor"
    assert e.target_id == "n1"
    assert sorted(e.detail["updated_keys"]) == ["label", "value"]


def test_update_nonexistent_node_no_entry(pg):
    result = pg.update_node("ghost", {"x": 1})
    assert result is None
    assert pg.ledger_size() == 0


# --- Hash chain ---

def test_hash_chain_links_entries(pg, meta):
    pg.add_node(_make_node("n1", meta))
    pg.add_node(_make_node("n2", meta))
    pg.add_node(_make_node("n3", meta))

    entries = pg.history()
    assert entries[0].previous_hash == ""
    assert entries[1].previous_hash == entries[0].hash
    assert entries[2].previous_hash == entries[1].hash


def test_verify_returns_true_on_valid_chain(pg, meta):
    pg.add_node(_make_node("n1", meta))
    pg.add_node(_make_node("n2", meta))
    assert pg.verify() is True


def test_verify_returns_false_when_tampered(pg, meta):
    pg.add_node(_make_node("n1", meta))
    pg.add_node(_make_node("n2", meta))

    # Tamper with the detail of the first entry
    pg._ledger[0].detail["node_id"] = "TAMPERED"
    assert pg.verify() is False


# --- history / history_for ---

def test_history_returns_all_entries(pg, meta, edge_meta):
    pg.add_node(_make_node("a", meta))
    pg.add_node(_make_node("b", meta))
    pg.add_edge(Edge(source_id="a", target_id="b", relation="FEEDS", metadata=edge_meta))
    pg.update_node("a", {"x": 1}, agent_id="editor")

    assert len(pg.history()) == 4


def test_history_for_filters_by_target_id(pg, meta):
    pg.add_node(_make_node("n1", meta))
    pg.add_node(_make_node("n2", meta))
    pg.update_node("n1", {"x": 1})

    h = pg.history_for("n1")
    assert len(h) == 2
    assert all(e.target_id == "n1" for e in h)


# --- who_created ---

def test_who_created_returns_correct_agent(pg, meta):
    pg.add_node(_make_node("n1", meta))
    assert pg.who_created("n1") == "test-agent"


def test_who_created_returns_none_for_unknown(pg):
    assert pg.who_created("ghost") is None


# --- ledger_size ---

def test_ledger_size_tracks_count(pg, meta):
    assert pg.ledger_size() == 0
    pg.add_node(_make_node("n1", meta))
    assert pg.ledger_size() == 1
    pg.add_node(_make_node("n2", meta))
    assert pg.ledger_size() == 2
    pg.remove_node("n1")
    assert pg.ledger_size() == 3


# --- Read operations don't create entries ---

def test_read_operations_no_entries(pg, meta, edge_meta):
    pg.add_node(_make_node("a", meta))
    pg.add_node(_make_node("b", meta))
    pg.add_edge(Edge(source_id="a", target_id="b", relation="FEEDS", metadata=edge_meta))
    initial = pg.ledger_size()

    pg.get_node("a")
    pg.find_nodes(node_type=NodeType.OPERAND)
    pg.find_edges(from_id="a")
    pg.get_neighbors("a")
    _ = pg.nodes
    _ = pg.edges
    pg.to_dict()
    pg.get_summary()

    assert pg.ledger_size() == initial


# --- Multiple operations build correct chain ---

def test_multiple_operations_chain(pg, meta, edge_meta):
    pg.add_node(_make_node("a", meta))
    pg.add_node(_make_node("b", meta))
    pg.add_edge(Edge(source_id="a", target_id="b", relation="FEEDS", metadata=edge_meta))
    pg.update_node("a", {"v": 1})
    pg.remove_edge("a", "b", "FEEDS")
    pg.remove_node("b")

    entries = pg.history()
    assert len(entries) == 6

    # Verify chain links
    for i in range(1, len(entries)):
        assert entries[i].previous_hash == entries[i - 1].hash

    # Verify overall integrity
    assert pg.verify() is True

    # Verify sequence numbers
    for i, e in enumerate(entries):
        assert e.sequence == i


# --- Integration: Agent writes through ProvenanceGraph ---

def test_agent_writes_through_provenance(meta):
    graph = EGS()
    pg = ProvenanceGraph(graph)
    agent = Agent("agent-alpha", pg, [NodeType.OPERAND, NodeType.CONCEPT])

    node = Node(
        id="op1",
        type=NodeType.OPERAND,
        data={"value": 42},
        metadata=NodeMetadata(created_by="placeholder", created_at=datetime.now(timezone.utc)),
    )
    agent.add_node(node)

    # Agent stamps created_by with its own id
    entries = pg.history()
    assert len(entries) == 1
    assert entries[0].operation == "add_node"
    assert entries[0].agent_id == "agent-alpha"
    assert entries[0].target_id == "op1"

    # Verify the node in the underlying graph has agent's id
    stored = graph.get_node("op1")
    assert stored.metadata.created_by == "agent-alpha"


# --- Integration: GraphExecutor + TransformRegistry ---

def test_executor_transform_through_provenance():
    graph = EGS()
    pg = ProvenanceGraph(graph)

    # Register a transform that creates a new node
    registry = TransformRegistry()

    @registry.register("make_result")
    def make_result(inputs, config):
        values = list(inputs.values())
        total = sum(v for v in values if isinstance(v, (int, float)))
        result_node = Node(
            id="result_from_transform",
            type=NodeType.OPERAND,
            data={"value": total},
            metadata=NodeMetadata(
                created_by="placeholder",
                created_at=datetime.now(timezone.utc),
            ),
        )
        return TransformResult(nodes=[result_node])

    # Build a small graph: OPERAND -> TRANSFORM
    meta = NodeMetadata(created_by="setup", created_at=datetime.now(timezone.utc))
    edge_meta = EdgeMetadata(created_by="setup", created_at=datetime.now(timezone.utc))

    pg.add_node(Node(id="input1", type=NodeType.OPERAND, data={"value": 10}, metadata=meta))
    pg.add_node(Node(
        id="t1",
        type=NodeType.TRANSFORM,
        data={"transform_fn": "make_result"},
        metadata=meta,
    ))
    pg.add_edge(Edge(source_id="input1", target_id="t1", relation="FEEDS", metadata=edge_meta))

    initial_size = pg.ledger_size()

    # Execute — the executor calls pg.add_node for transform output
    executor = GraphExecutor(pg, transforms=registry)
    trace = executor.execute()

    assert trace.success is True

    # The transform should have created a new node via pg.add_node
    assert pg.ledger_size() > initial_size

    # Find the add_node entry for the transform-created node
    new_entries = [e for e in pg.history() if e.sequence >= initial_size]
    add_entries = [e for e in new_entries if e.operation == "add_node"]
    assert len(add_entries) >= 1
    assert any(e.target_id == "result_from_transform" for e in add_entries)

    # The created node exists in the graph
    created = pg.get_node("result_from_transform")
    assert created is not None
    assert created.data["value"] == 10

    # Chain is still valid
    assert pg.verify() is True
