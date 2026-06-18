"""STUDY-203 Condition A: single-process baseline.

One process performs all three steps -- traversal, execution, and
modification -- operating over the on-disk serialized graph file. The
file IS the program (limitation L1) and traversing it IS executing it
(limitation L3): every step reads the current graph from disk, executes
the current node, persists any self-modification back to disk, and
selects the next edge from the *execution result* evaluated against the
outgoing-edge conditions (not from any coordinating logic).

This module also defines the shared substrate primitives -- op execution,
result-driven edge selection, data-driven self-modification, and atomic
persistence -- that Conditions B and C import. The substrate *semantics*
are therefore identical across all three conditions; only the *embodiment*
(single process vs. decomposed processes vs. external dispatch) differs.
That is the whole point of the study: the mechanism survives the
agent-count embodiment shift.

The graph (topology) lives on disk; the execution state (the accumulator)
lives in the executing agent -- computation occurs in the agent, not in
the graph.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

# Bounded-iteration safety net so a malformed topology can never hang a run.
MAX_STEPS = 100


# ---------------------------------------------------------------------------
# Persisted-file I/O -- the on-disk serialized graph is the shared medium
# ---------------------------------------------------------------------------

def load_graph(path: Path) -> dict:
    """Read the graph from the on-disk serialized file."""
    with Path(path).open("r") as f:
        return json.load(f)


def save_graph_atomic(graph: dict, path: Path) -> None:
    """Persist the graph by an atomic replace.

    Write to a temp file in the same directory, fsync, then os.replace --
    a reader never observes a partial file. This atomic write is the
    write-serialization primitive Condition B's sole-modifier process
    relies on for multi-writer consistency.
    """
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".graph_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(graph, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def init_working_file(initial_path: Path, working_path: Path) -> None:
    """Materialize a fresh working copy of the baseline on disk.

    The committed graph_initial.json is never mutated; each run operates
    on its own on-disk working file.
    """
    save_graph_atomic(load_graph(initial_path), working_path)


# ---------------------------------------------------------------------------
# Topology helpers (generic over the node/edge schema)
# ---------------------------------------------------------------------------

def node_by_id(graph: dict, node_id: str) -> dict:
    for n in graph["nodes"]:
        if n["id"] == node_id:
            return n
    raise KeyError(f"node not found: {node_id}")


def outgoing_edges(graph: dict, node_id: str) -> list[dict]:
    return [e for e in graph["edges"] if e["source_id"] == node_id]


def is_terminal(node: dict) -> bool:
    return node["type"] == "RESULT"


def find_entry(graph: dict) -> str:
    """Entry = the declared 'entry', else the unique node with no in-edge."""
    if graph.get("entry"):
        return graph["entry"]
    targets = {e["target_id"] for e in graph["edges"]}
    roots = [n["id"] for n in graph["nodes"] if n["id"] not in targets]
    return roots[0]


# ---------------------------------------------------------------------------
# Substrate semantics -- shared by ALL conditions (single source of truth)
# ---------------------------------------------------------------------------

def execute_node(node: dict, state: dict) -> str:
    """Deterministically execute a node against the agent's execution state.

    Returns the node's execution result. The result -- NOT any coordinating
    or dispatch logic -- is what later selects the outgoing edge.
    """
    op = node.get("op")
    if op == "init":
        state["acc"] = 0
        return "ok"
    if op == "add":
        state["acc"] = state.get("acc", 0) + node["data"]["value"]
        return "ok"
    if op == "classify":
        return "high" if state.get("acc", 0) >= node["data"]["threshold"] else "low"
    if op == "self_modify":
        return "ok"
    if op == "record":
        return "ok"
    if op == "finalize":
        return "done"
    return "ok"


def modification_for(node: dict) -> Optional[dict]:
    """Return the self-modification spec a node triggers, if any.

    Data-driven: a self_modify node carries the node + edges to add in its
    own 'data', so the modification is deterministic and the engine code
    is content-agnostic.
    """
    if node.get("op") == "self_modify":
        return {
            "add_node": node["data"]["add_node"],
            "add_edges": node["data"]["add_edges"],
        }
    return None


def apply_modification(graph: dict, spec: dict) -> None:
    """Add the spec's node and edges to the graph (idempotent)."""
    existing_nodes = {n["id"] for n in graph["nodes"]}
    add_node = spec["add_node"]
    if add_node["id"] not in existing_nodes:
        graph["nodes"].append(add_node)
    have = {(e["source_id"], e["target_id"], e["relation"]) for e in graph["edges"]}
    for e in spec["add_edges"]:
        key = (e["source_id"], e["target_id"], e["relation"])
        if key not in have:
            graph["edges"].append(e)


def modification_present(graph: dict, spec: dict) -> bool:
    """True iff the spec's node and edges are present in the graph."""
    node_ok = any(n["id"] == spec["add_node"]["id"] for n in graph["nodes"])
    have = {(e["source_id"], e["target_id"], e["relation"]) for e in graph["edges"]}
    edges_ok = all(
        (e["source_id"], e["target_id"], e["relation"]) in have
        for e in spec["add_edges"]
    )
    return node_ok and edges_ok


def select_next_edge(graph: dict, node_id: str, result: str) -> Optional[str]:
    """Select the next node by evaluating the execution RESULT against the
    outgoing-edge conditions. THEN edges (no condition) are taken
    unconditionally; conditional edges are taken iff their condition
    matches the result. Deterministic tie-break by target id.

    This function embodies result-driven edge selection -- the as-filed
    carve-out that computation occurs in the agents, with the graph's edge
    conditions (not coordinating logic) selecting the path.
    """
    eligible = []
    for e in outgoing_edges(graph, node_id):
        cond = e.get("condition")
        if cond is None:
            eligible.append(e)
        elif cond.get("result") == result:
            eligible.append(e)
    if not eligible:
        return None
    eligible.sort(key=lambda e: e["target_id"])
    return eligible[0]["target_id"]


# ---------------------------------------------------------------------------
# Equivalence / hashing
# ---------------------------------------------------------------------------

def canonical_graph(graph: dict) -> dict:
    """A canonical, order-independent view of the graph's final STATE used
    for equivalence comparison: nodes by id (id/type/op) and edges as a
    sorted set of (source, target, relation, condition)."""
    nodes = sorted(
        ({"id": n["id"], "type": n["type"], "op": n.get("op")} for n in graph["nodes"]),
        key=lambda n: n["id"],
    )
    edges = sorted(
        (
            {
                "source_id": e["source_id"],
                "target_id": e["target_id"],
                "relation": e["relation"],
                "condition": e.get("condition"),
            }
            for e in graph["edges"]
        ),
        key=lambda e: (e["source_id"], e["target_id"], e["relation"]),
    )
    return {"nodes": nodes, "edges": edges}


def graph_hash(graph: dict) -> str:
    blob = json.dumps(canonical_graph(graph), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Condition A: one process does traversal + execution + modification
# ---------------------------------------------------------------------------

def run(graph_path: Path) -> dict:
    """Traverse + execute + self-modify the on-disk graph in one process.

    Returns a raw-result dict (shared shape across all conditions) that the
    equivalence harness reduces to the 7 study metrics.
    """
    graph_path = Path(graph_path)
    initial = load_graph(graph_path)
    initial_nodes, initial_edges = len(initial["nodes"]), len(initial["edges"])

    state: dict[str, Any] = {}
    visited: list[str] = []
    branch_decision = None
    self_modified = False
    modification_persisted = False

    current: Optional[str] = find_entry(initial)
    steps = 0
    while current is not None and steps < MAX_STEPS:
        steps += 1
        graph = load_graph(graph_path)            # read the program from disk (L1)
        node = node_by_id(graph, current)
        result = execute_node(node, state)        # compute in the agent, not the graph
        visited.append(current)

        spec = modification_for(node)
        if spec is not None:
            apply_modification(graph, spec)
            save_graph_atomic(graph, graph_path)  # persist the modification to disk
            self_modified = True
            modification_persisted = modification_present(load_graph(graph_path), spec)

        if is_terminal(node):
            break

        graph = load_graph(graph_path)            # next step sees the modified+persisted graph
        nxt = select_next_edge(graph, current, result)
        if node["type"] == "BRANCH":
            branch_decision = {
                "node": current,
                "result": result,
                "selected_target": nxt,
            }
        if nxt is None:
            break
        current = nxt

    final = load_graph(graph_path)
    return {
        "condition": "A",
        "embodiment": "single_process",
        "visited": visited,
        "branch_decision": branch_decision,
        "self_modified": self_modified,
        "modification_persisted": modification_persisted,
        "initial_node_count": initial_nodes,
        "initial_edge_count": initial_edges,
        "final_node_count": len(final["nodes"]),
        "final_edge_count": len(final["edges"]),
        "node_count_delta": len(final["nodes"]) - initial_nodes,
        "edge_count_delta": len(final["edges"]) - initial_edges,
        "final_acc": state.get("acc"),
        "final_graph_hash": graph_hash(final),
        "final_graph": canonical_graph(final),
        "metadata": {
            "processes": 1,
            "writer_count": 1,
            "writer_roles": ["single_process"],
            "shared_medium": "on_disk_serialized_file",
            "channel_carries": "n/a (single process)",
            "routing_source": "execution_result_vs_edge_condition",
        },
    }


def run_in_tempdir() -> dict:
    """Standalone entry: copy the baseline to a temp working file and run A."""
    initial_path = Path(__file__).parent / "graph_initial.json"
    with tempfile.TemporaryDirectory(prefix="study_203_A_") as d:
        working = Path(d) / "graph.json"
        init_working_file(initial_path, working)
        return run(working)


if __name__ == "__main__":
    res = run_in_tempdir()
    print("=" * 60)
    print("STUDY-203 Condition A: single-process baseline")
    print("=" * 60)
    print(f"  visited:               {' -> '.join(res['visited'])}")
    print(f"  branch decision:       {res['branch_decision']}")
    print(f"  self modified:         {res['self_modified']}")
    print(f"  modification persisted: {res['modification_persisted']}")
    print(f"  nodes: {res['initial_node_count']} -> {res['final_node_count']} "
          f"(delta {res['node_count_delta']:+d})")
    print(f"  edges: {res['initial_edge_count']} -> {res['final_edge_count']} "
          f"(delta {res['edge_count_delta']:+d})")
    print(f"  final graph hash:      {res['final_graph_hash'][:16]}...")
    expected = ["start", "compute", "branch", "grow", "audit", "finalize"]
    ok = res["visited"] == expected and res["self_modified"] and res["modification_persisted"]
    print("=" * 60)
    print("RESULT:", "OK" if ok else "UNEXPECTED")
    sys.exit(0 if ok else 1)
