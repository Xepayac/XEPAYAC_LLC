"""Tests for STUDY-140: Supersede Operation.

Eight tests proving the supersede primitive: atomic self-replacement,
edge redirection, chain traversability, type safety, rollback on failure,
provenance, concurrent-conflict detection, and LLM-directed application
from a recorded structured JSON proposal (no live model call — the
property under test is that the graph validates and applies the
proposal, which a recorded document proves).

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json

import pytest

from graph import ACTIVE, STALE, SUPERSEDED_BY, Edge, Graph, Node, Schema
from supersede import (
    CommitValidationError,
    ConcurrentConflict,
    SupersedeError,
    TypeViolation,
    apply_llm_proposal,
    supersede,
)


def make_graph() -> Graph:
    """A small substrate: one PROCESS under test plus callers."""
    schema = Schema(
        allowed_types=["PROCESS", "RECORD", "AGENT"],
        required_properties={"PROCESS": ["name"]},
    )
    g = Graph(schema)
    g.add_node(Node("proc_a", "PROCESS", {"name": "alpha"}))
    g.add_node(Node("caller_1", "AGENT", {"name": "one"}))
    g.add_node(Node("caller_2", "AGENT", {"name": "two"}))
    g.add_node(Node("caller_3", "AGENT", {"name": "three"}))
    g.add_edge(Edge("caller_1", "proc_a", "INVOKES"))
    g.add_edge(Edge("caller_2", "proc_a", "INVOKES"))
    g.add_edge(Edge("caller_3", "proc_a", "READS"))
    return g


# A recorded LLM-authored supersede proposal (structured JSON document).
RECORDED_LLM_PROPOSAL = json.dumps(
    {
        "operation": "supersede",
        "original_id": "proc_a",
        "replacement": {
            "id": "proc_a_v2",
            "type": "PROCESS",
            "properties": {"name": "alpha-v2", "authored_by": "llm"},
        },
    }
)


def test_simple_supersede():
    """B1: the original goes stale and the replacement goes active in one
    committed step — no state has both active."""
    g = make_graph()
    result = supersede(g, "proc_a", Node("proc_b", "PROCESS", {"name": "beta"}))
    assert g.get_node("proc_a").status == STALE
    assert g.get_node("proc_b").status == ACTIVE
    both_active = (
        g.get_node("proc_a").status == ACTIVE
        and g.get_node("proc_b").status == ACTIVE
    )
    assert not both_active
    assert result.replacement_id == "proc_b"
    assert g.get_node("proc_a").id not in [n.id for n in g.active_nodes()]


def test_chain_supersede():
    """B3: chain A -> B -> C stays traversable and current(A) == C."""
    g = make_graph()
    supersede(g, "proc_a", Node("proc_b", "PROCESS", {"name": "beta"}))
    supersede(g, "proc_b", Node("proc_c", "PROCESS", {"name": "gamma"}))
    assert g.supersede_chain("proc_a") == ["proc_a", "proc_b", "proc_c"]
    assert g.current("proc_a").id == "proc_c"
    assert g.current("proc_a").status == ACTIVE
    assert g.get_node("proc_a").status == STALE
    assert g.get_node("proc_b").status == STALE


def test_edge_redirection():
    """B2: every incoming edge of the original redirects to the
    replacement (3 incoming -> all 3 redirect)."""
    g = make_graph()
    assert len(g.incoming_edges("proc_a")) == 3
    result = supersede(g, "proc_a", Node("proc_b", "PROCESS", {"name": "beta"}))
    assert result.redirected_edges == 3
    functional = [
        e for e in g.incoming_edges("proc_b") if e.relation != SUPERSEDED_BY
    ]
    assert len(functional) == 3
    assert g.incoming_edges("proc_a") == []  # only outgoing lineage remains


def test_type_safety():
    """B4: a replacement whose type the schema forbids is rejected and
    the graph is unchanged."""
    g = make_graph()
    before = g.snapshot()
    with pytest.raises(TypeViolation):
        supersede(g, "proc_a", Node("bad", "UNKNOWN_TYPE", {"name": "x"}))
    assert g.snapshot() == before


def test_rollback():
    """B1/rollback: a failure during commit (replacement missing a
    schema-required property) restores the exact pre-operation state."""
    g = make_graph()
    before = g.snapshot()
    with pytest.raises(CommitValidationError):
        supersede(g, "proc_a", Node("proc_b", "PROCESS", {}))  # no 'name'
    assert g.snapshot() == before
    assert g.get_node("proc_a").status == ACTIVE
    assert "proc_b" not in g.nodes


def test_provenance():
    """Each committed supersede appends one reconstructable provenance
    record; the chain history is auditable after the fact."""
    g = make_graph()
    supersede(g, "proc_a", Node("proc_b", "PROCESS", {"name": "beta"}))
    supersede(g, "proc_b", Node("proc_c", "PROCESS", {"name": "gamma"}))
    ops = [p for p in g.provenance if p["operation"] == "supersede"]
    assert len(ops) == 2
    assert ops[0]["original_id"] == "proc_a"
    assert ops[0]["replacement_id"] == "proc_b"
    assert ops[1]["original_id"] == "proc_b"
    assert ops[1]["replacement_id"] == "proc_c"
    assert ops[0]["graph_version"] < ops[1]["graph_version"]


def test_concurrent_conflict():
    """B6: two agents read the same version; the first write wins, the
    second is detected as a conflict and applies nothing."""
    g = make_graph()
    seen_by_agent_1 = g.version
    seen_by_agent_2 = g.version
    supersede(
        g,
        "proc_a",
        Node("proc_b", "PROCESS", {"name": "beta"}),
        expected_version=seen_by_agent_1,
    )
    before = g.snapshot()
    with pytest.raises(ConcurrentConflict):
        supersede(
            g,
            "proc_a",
            Node("proc_x", "PROCESS", {"name": "chi"}),
            expected_version=seen_by_agent_2,
        )
    assert g.snapshot() == before
    assert "proc_x" not in g.nodes


def test_llm_directed():
    """Scenario 4: the graph validates and applies a supersede proposal
    authored by an LLM, supplied as a recorded structured JSON document."""
    g = make_graph()
    result = apply_llm_proposal(g, RECORDED_LLM_PROPOSAL)
    assert result.original_id == "proc_a"
    assert result.replacement_id == "proc_a_v2"
    assert g.get_node("proc_a").status == STALE
    assert g.get_node("proc_a_v2").status == ACTIVE
    assert g.get_node("proc_a_v2").properties["authored_by"] == "llm"
    assert g.current("proc_a").id == "proc_a_v2"
    # malformed proposals are rejected before touching the graph
    before = g.snapshot()
    with pytest.raises(SupersedeError):
        apply_llm_proposal(g, json.dumps({"operation": "delete_everything"}))
    assert g.snapshot() == before
