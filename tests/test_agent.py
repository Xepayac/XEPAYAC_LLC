"""Tests for EGS multi-agent coordination."""

from datetime import datetime, timezone

import pytest

from egs.graph import EGS
from egs.agent import Agent, AccessError, CoordinationSession
from egs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata


@pytest.fixture
def meta():
    return NodeMetadata(created_by="test", created_at=datetime.now(timezone.utc))


@pytest.fixture
def edge_meta():
    return EdgeMetadata(created_by="test", created_at=datetime.now(timezone.utc))


@pytest.fixture
def graph():
    return EGS()


@pytest.fixture
def agent_a(graph):
    """Agent allowed OPERAND and CONCEPT."""
    return Agent("agent-a", graph, [NodeType.OPERAND, NodeType.CONCEPT])


@pytest.fixture
def agent_b(graph):
    """Agent allowed OPERAND and RESULT."""
    return Agent("agent-b", graph, [NodeType.OPERAND, NodeType.RESULT])


# --- add_node ---

def test_add_node_allowed_type(agent_a, meta):
    node = Node(id="n1", type=NodeType.OPERAND, data={"v": 1}, metadata=meta)
    agent_a.add_node(node)
    assert agent_a.graph.get_node("n1") is not None


def test_add_node_disallowed_type_raises(agent_a, meta):
    node = Node(id="n1", type=NodeType.RESULT, data={}, metadata=meta)
    with pytest.raises(AccessError):
        agent_a.add_node(node)


# --- get_node ---

def test_get_node_disallowed_type_returns_none(agent_a, graph, meta):
    """Agent sees None for a node whose type is outside its allowed set."""
    node = Node(id="n1", type=NodeType.RESULT, data={}, metadata=meta)
    graph.add_node(node)
    assert agent_a.get_node("n1") is None


def test_get_node_nonexistent_returns_none(agent_a):
    assert agent_a.get_node("does-not-exist") is None


# --- find_nodes ---

def test_find_nodes_filters_to_allowed_types(agent_a, graph, meta):
    graph.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    graph.add_node(Node(id="n2", type=NodeType.RESULT, data={}, metadata=meta))
    results = agent_a.find_nodes()
    assert len(results) == 1
    assert results[0].id == "n1"


# --- visible_nodes ---

def test_visible_nodes_filters(agent_a, graph, meta):
    graph.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    graph.add_node(Node(id="n2", type=NodeType.RESULT, data={}, metadata=meta))
    graph.add_node(Node(id="n3", type=NodeType.CONCEPT, data={}, metadata=meta))
    visible = agent_a.visible_nodes()
    assert set(visible.keys()) == {"n1", "n3"}


# --- add_edge ---

def test_add_edge_both_visible(agent_a, meta, edge_meta):
    agent_a.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    agent_a.add_node(Node(id="n2", type=NodeType.CONCEPT, data={}, metadata=meta))
    edge = Edge(source_id="n1", target_id="n2", relation="LINKS", metadata=edge_meta)
    agent_a.add_edge(edge)
    assert len(agent_a.graph.edges) == 1


def test_add_edge_source_not_visible_raises(agent_a, graph, meta, edge_meta):
    graph.add_node(Node(id="n1", type=NodeType.RESULT, data={}, metadata=meta))
    agent_a.add_node(Node(id="n2", type=NodeType.OPERAND, data={}, metadata=meta))
    edge = Edge(source_id="n1", target_id="n2", relation="LINKS", metadata=edge_meta)
    with pytest.raises(AccessError):
        agent_a.add_edge(edge)


def test_add_edge_target_not_visible_raises(agent_a, graph, meta, edge_meta):
    agent_a.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    graph.add_node(Node(id="n2", type=NodeType.RESULT, data={}, metadata=meta))
    edge = Edge(source_id="n1", target_id="n2", relation="LINKS", metadata=edge_meta)
    with pytest.raises(AccessError):
        agent_a.add_edge(edge)


# --- get_edges ---

def test_get_edges_filters_by_visibility(agent_a, graph, meta, edge_meta):
    graph.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    graph.add_node(Node(id="n2", type=NodeType.RESULT, data={}, metadata=meta))
    graph.add_node(Node(id="n3", type=NodeType.CONCEPT, data={}, metadata=meta))
    graph.add_edge(Edge(source_id="n1", target_id="n2", relation="A", metadata=edge_meta))
    graph.add_edge(Edge(source_id="n2", target_id="n3", relation="B", metadata=edge_meta))
    # agent_a sees OPERAND + CONCEPT, so:
    # edge A: n1(OPERAND) visible -> included
    # edge B: n3(CONCEPT) visible -> included
    edges = agent_a.get_edges()
    assert len(edges) == 2


# --- shared graph ---

def test_two_agents_shared_type(graph, meta):
    """Two agents share OPERAND. One writes, the other reads."""
    a = Agent("a", graph, [NodeType.OPERAND])
    b = Agent("b", graph, [NodeType.OPERAND])
    a.add_node(Node(id="n1", type=NodeType.OPERAND, data={"x": 1}, metadata=meta))
    assert b.get_node("n1") is not None
    assert b.get_node("n1").data["x"] == 1


def test_two_agents_exclusive_types(graph, meta):
    """Exclusive types are invisible to the other agent."""
    a = Agent("a", graph, [NodeType.CONCEPT])
    b = Agent("b", graph, [NodeType.RESULT])
    a.add_node(Node(id="n1", type=NodeType.CONCEPT, data={}, metadata=meta))
    b.add_node(Node(id="n2", type=NodeType.RESULT, data={}, metadata=meta))
    assert b.get_node("n1") is None
    assert a.get_node("n2") is None


# --- auto-stamp created_by ---

def test_auto_stamp_node_created_by(agent_a, meta):
    node = Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta)
    agent_a.add_node(node)
    stored = agent_a.graph.get_node("n1")
    assert stored.metadata.created_by == "agent-a"


def test_auto_stamp_edge_created_by(agent_a, meta, edge_meta):
    agent_a.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    agent_a.add_node(Node(id="n2", type=NodeType.CONCEPT, data={}, metadata=meta))
    edge = Edge(source_id="n1", target_id="n2", relation="LINKS", metadata=edge_meta)
    agent_a.add_edge(edge)
    stored = agent_a.graph.edges[0]
    assert stored.metadata.created_by == "agent-a"


# --- CoordinationSession ---

def test_coordination_session_summary(graph, meta):
    a = Agent("a", graph, [NodeType.OPERAND])
    b = Agent("b", graph, [NodeType.RESULT])
    session = CoordinationSession(graph)
    session.add_agent(a)
    session.add_agent(b)
    a.add_node(Node(id="n1", type=NodeType.OPERAND, data={}, metadata=meta))
    a.add_node(Node(id="n2", type=NodeType.OPERAND, data={}, metadata=meta))
    b.add_node(Node(id="n3", type=NodeType.RESULT, data={}, metadata=meta))
    summary = session.summary()
    assert summary == {"a": 2, "b": 1}
    assert len(session.agents) == 2
