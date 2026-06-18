"""STUDY-209: Networked / Distributed Substrate — Condition A (local baseline) + shared core.

AGPL-3.0 | Patent Pending (app 19/575,491)

This module holds the mechanism that every condition shares unchanged:

  * the node-op interpreter (``execute``),
  * the result-driven edge selector (``select_edge``),
  * the ``Agent`` that traverses a substrate, routes by execution result, and
    performs an in-traversal self-modification — and then continues on the
    persisted-and-modified substrate.

The agent talks to a *store* through a tiny, dumb persistence contract
(``read_node`` / ``get_outgoing_edges`` / ``write_modification`` / ``has_node``
/ ``all_nodes`` / ``all_edges``). The store NEVER routes, executes, or selects
edges — that is the agent's job. This is the load-bearing invariant of the
study: moving the store across a network boundary (Condition B / C) changes
only WHERE the substrate is persisted, never the mechanism. If the store routed,
the study would demonstrate a different mechanism over the wire and the
reduction-to-practice for the networked claim would collapse.

Condition A keeps the agent and the substrate in one process (``LocalStore``) —
the golden reference every other condition is compared against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

GRAPH_INITIAL = Path(__file__).with_name("graph_initial.json")

# The single node the agent adds when it reaches a self-modification trigger.
# It is reachable ONLY via the edges the agent persists during traversal, so a
# subsequent step can visit it iff the modification persisted and is live.
AUDIT_NODE_ID = "audit"


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def make_node(node_id: str, node_type: str, op: str) -> dict:
    return {"id": node_id, "type": node_type, "op": op}


def make_edge(source: str, target: str, relation: str,
              condition: Optional[str]) -> dict:
    return {"source": source, "target": target,
            "relation": relation, "condition": condition}


def load_graph(path: Path = GRAPH_INITIAL) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# The mechanism — execution + result-driven edge selection (the agent's, never
# the store's)
# --------------------------------------------------------------------------- #
def execute(node: dict, acc: int) -> tuple[str, int]:
    """Execute a node's content; return (routing_token, new_accumulator).

    The routing token is the *execution result* the agent uses to choose the
    next edge — control flow is decided by runtime results over the live
    topology, not by a static table.
    """
    op = node["op"]
    if op.startswith("set:"):
        return "next", int(op.split(":", 1)[1])
    if op.startswith("add:"):
        return "next", acc + int(op.split(":", 1)[1])
    if op == "parity":
        return ("odd" if acc % 2 else "even"), acc
    if op == "self_modify":
        # The agent's self-modification produced a new branch; the token routes
        # onto the freshly-persisted edge.
        return "modified", acc
    if op == "finalize":
        return "halt", acc
    raise ValueError(f"unknown op: {op!r}")


def select_edge(edges: list[dict], token: str) -> Optional[dict]:
    """Result-driven edge selection. Prefer an edge whose condition matches the
    execution result; else take an unconditional (default) edge; else stop.

    This is the agent's decision. A store never calls this.
    """
    for edge in edges:
        if edge.get("condition") == token:
            return edge
    for edge in edges:
        if edge.get("condition") is None:
            return edge
    return None


def self_modification() -> dict:
    """The topology modification the agent writes when it hits a self_modify
    trigger: add the ``audit`` node and the edges that carry traversal through
    it (``mutate -> audit`` keyed to the ``modified`` token, and
    ``audit -> end``). Persisting this is what the next step must see."""
    return {
        "add_nodes": [make_node(AUDIT_NODE_ID, "OPERATION", "add:5")],
        "add_edges": [
            make_edge("mutate", AUDIT_NODE_ID, "COND", "modified"),
            make_edge(AUDIT_NODE_ID, "end", "THEN", None),
        ],
    }


class Agent:
    """Traverses a substrate held by an arbitrary store, identically across all
    conditions. The agent owns topology-determined sequencing, result-driven
    edge selection, and the in-traversal self-modification."""

    START = "start"
    _GUARD = 1000

    def traverse(self, store: "Store") -> dict:
        current: Optional[str] = self.START
        acc = 0
        sequence: list[str] = []
        self_mods = 0
        steps = 0
        while current is not None:
            node = store.read_node(current)            # read (over the boundary in B/C)
            sequence.append(current)
            token, acc = execute(node, acc)            # execute — the agent's compute
            if node["op"] == "self_modify" and not store.has_node(AUDIT_NODE_ID):
                store.write_modification(self_modification())   # write (over the boundary)
                self_mods += 1
            # Re-read outgoing edges AFTER any write: the next step operates on
            # the substrate as modified-and-persisted — no recompile/redeploy.
            edges = store.get_outgoing_edges(current)
            nxt = select_edge(edges, token)            # the agent selects, not the store
            current = nxt["target"] if nxt else None
            steps += 1
            if steps > self._GUARD:                    # pragma: no cover
                raise RuntimeError("traversal did not terminate")
        return {"sequence": sequence, "final_acc": acc, "self_mods": self_mods}


# --------------------------------------------------------------------------- #
# Store contract + the local (Condition A) store
# --------------------------------------------------------------------------- #
class Store:
    """The dumb persistence contract every condition's store satisfies. Read /
    write only — no routing, no execution, no edge selection."""

    def read_node(self, node_id: str) -> dict: raise NotImplementedError
    def has_node(self, node_id: str) -> bool: raise NotImplementedError
    def get_outgoing_edges(self, node_id: str) -> list[dict]: raise NotImplementedError
    def write_modification(self, modification: dict) -> None: raise NotImplementedError
    def all_nodes(self) -> list[dict]: raise NotImplementedError
    def all_edges(self) -> list[dict]: raise NotImplementedError


class LocalStore(Store):
    """Condition A: substrate held in-process, in the same address space as the
    agent. The golden reference."""

    def __init__(self, graph: dict) -> None:
        self._nodes: dict[str, dict] = {n["id"]: dict(n) for n in graph["nodes"]}
        self._edges: list[dict] = [dict(e) for e in graph["edges"]]

    def read_node(self, node_id: str) -> dict:
        return dict(self._nodes[node_id])

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return [dict(e) for e in self._edges if e["source"] == node_id]

    def write_modification(self, modification: dict) -> None:
        for node in modification.get("add_nodes", []):
            self._nodes[node["id"]] = dict(node)
        for edge in modification.get("add_edges", []):
            self._edges.append(dict(edge))

    def all_nodes(self) -> list[dict]:
        return [dict(n) for n in self._nodes.values()]

    def all_edges(self) -> list[dict]:
        return [dict(e) for e in self._edges]


# --------------------------------------------------------------------------- #
# Canonical state + metric capture (shared by every condition)
# --------------------------------------------------------------------------- #
def canonical_state(store: Store) -> dict:
    """A normalized, order-independent snapshot of the substrate, for
    structural functional-equivalence comparison across conditions."""
    nodes = sorted([n["id"], n["type"], n["op"]] for n in store.all_nodes())
    edges = sorted(
        [e["source"], e["target"], e["relation"], e.get("condition")]
        for e in store.all_edges()
    )
    return {"nodes": nodes, "edges": edges}


# The deterministic sequence the shared baseline produces (start acc=7 -> odd
# branch -> self-modify -> traverse the freshly-persisted audit node -> end).
EXPECTED_SEQUENCE = ["start", "gate", "odd_branch", "mutate", "audit", "end"]


def metric_block(
    condition: str,
    locus: str,
    n0: int,
    e0: int,
    store: Store,
    trace: dict,
    baseline_state: Optional[dict],
    across_boundary: bool,
) -> dict:
    """Build the per-condition 6-metric block (the issue's measurement set)."""
    n1 = len(store.all_nodes())
    e1 = len(store.all_edges())
    sequence = trace["sequence"]
    state = canonical_state(store)
    audited = AUDIT_NODE_ID in sequence  # the agent visited the persisted-added node

    block: dict[str, Any] = {
        "condition": condition,
        "locus": locus,
        "topology_determination": sequence == EXPECTED_SEQUENCE,
        "result_driven_routing": "odd_branch" in sequence and "even_branch" not in sequence,
        "in_traversal_self_modification": trace["self_mods"],
        "node_count_delta": n1 - n0,
        "edge_count_delta": e1 - e0,
        "persistence_affects_subsequent_traversal": audited,
        "sequence": sequence,
        "final_acc": trace["final_acc"],
    }
    if across_boundary:
        # Structural liveness ACROSS the boundary: the remotely-persisted
        # modification was observed by the next traversal step (the agent read
        # the new edge back over the wire and walked it) with no recompile /
        # redeploy / restart between the remote write and its effect.
        block["structural_liveness_across_boundary"] = bool(audited and trace["self_mods"] > 0)
    else:
        block["structural_liveness_across_boundary"] = "n/a (local baseline)"
    if baseline_state is None:
        block["functional_equivalence_to_A"] = "reference"
    else:
        block["functional_equivalence_to_A"] = (state == baseline_state)
    return block


def run_condition_A() -> tuple[dict, dict]:
    """Run Condition A and return (metric_block, canonical_final_state)."""
    graph = load_graph()
    store = LocalStore(graph)
    n0, e0 = len(store.all_nodes()), len(store.all_edges())
    trace = Agent().traverse(store)
    state = canonical_state(store)
    block = metric_block("A", "local in-process (single address space)",
                         n0, e0, store, trace, baseline_state=None,
                         across_boundary=False)
    return block, state


def _checklist(block: dict) -> list[tuple[str, bool]]:
    return [
        ("topology determines the sequence", block["topology_determination"]),
        ("result-driven routing (odd branch taken for acc=7)", block["result_driven_routing"]),
        ("in-traversal self-modification occurred", block["in_traversal_self_modification"] > 0),
        ("self-mod node visited by the subsequent step",
         block["persistence_affects_subsequent_traversal"]),
        ("node_count_delta nonzero", block["node_count_delta"] != 0),
        ("edge_count_delta nonzero", block["edge_count_delta"] != 0),
    ]


if __name__ == "__main__":
    import sys

    block, state = run_condition_A()
    print("=" * 64)
    print("STUDY-209 — Condition A (local baseline / golden reference)")
    print("=" * 64)
    for k, v in block.items():
        print(f"  {k}: {v}")
    print("-" * 64)
    ok = True
    for label, passed in _checklist(block):
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
        ok = ok and passed
    print("=" * 64)
    print("RESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
