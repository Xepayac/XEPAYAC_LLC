# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: Storage-Independent Graph Substrate — Condition A (serialized-file baseline)
and the shared substrate semantics every condition runs.

This module is the single source of the *mechanism*: one ``traverse`` agent, one
``execute`` step, one ``select_edge`` router, applied over a pluggable ``store``.
Conditions B/C/D import this same agent and supply only a different store, so any
behavioural difference between conditions would be a difference of *storage*, never
of *mechanism*. That is the load-bearing structure of the proof: the embodiment
(where/how the graph is stored or accessed) moves; the mechanism does not.

Baseline schema (shared with STUDY-203 — the authoritative author of the fixture):
every node carries ``{id, type, op, data}``; every edge carries
``{source_id, target_id, relation}`` with an optional ``condition`` (``{"result": ...}``).
Execution state (the accumulator) lives in the agent; the topology lives in the store.

The mechanism axis demonstrated here (and held fixed across all conditions):
  - topology-as-program: traversal IS execution; the edges determine the sequence.
  - result-driven edge selection: an execution result chooses the outgoing edge.
  - structural liveness / in-traversal self-modification: a node written during
    execution is immediately live and is traversed on the very next step, with no
    compile/parse/deploy boundary between the write and its effect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

GRAPH_INITIAL_PATH = Path(__file__).resolve().parent / "graph_initial.json"

# The node the agent injects into the substrate during execution. It does not exist
# in the baseline graph; the 'grow' (self_modify) node creates it (and its edges)
# live, data-driven from the grow node's own ``data``. In the shared STUDY-203
# baseline this is the 'audit' node.
INJECTED_NODE_ID = "audit"


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline(path: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Load the shared baseline graph (nodes + edges + entry marker)."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def baseline_counts(baseline: dict) -> dict[str, int]:
    return {"nodes": len(baseline["nodes"]), "edges": len(baseline["edges"])}


def entry_id(baseline: dict) -> str:
    """The traversal entry node: the declared ``entry`` (the shared schema's key)."""
    return baseline.get("entry", baseline.get("start", "start"))


# ---------------------------------------------------------------------------
# Canonical snapshot — the structure-only view used for cross-condition equality
# ---------------------------------------------------------------------------

def canonical_node(node: dict) -> dict:
    return {"id": node["id"], "type": node["type"], "op": node.get("op")}


def canonical_edge(edge: dict) -> dict:
    return {
        "source_id": edge["source_id"],
        "target_id": edge["target_id"],
        "relation": edge["relation"],
        "condition": edge.get("condition"),
    }


def canonical_snapshot(nodes: list[dict], edges: list[dict]) -> dict:
    """A storage-independent, order-independent view of the graph's final state.

    Two conditions are *functionally equivalent* iff their canonical snapshots are
    deep-equal. Sorting removes any storage-imposed ordering so the comparison is
    over structure alone (node id/type/op and edge source/target/relation/condition).
    """
    snap_nodes = sorted((canonical_node(n) for n in nodes), key=lambda n: n["id"])
    snap_edges = sorted(
        (canonical_edge(e) for e in edges),
        key=lambda e: (e["source_id"], e["target_id"], e["relation"]),
    )
    return {"nodes": snap_nodes, "edges": snap_edges}


# ---------------------------------------------------------------------------
# The agent: traversal IS execution. Storage-agnostic — operates on any ``store``
# implementing read_node / has_node / get_outgoing_edges / write_node / add_edge.
# ---------------------------------------------------------------------------

def select_edge(edges: list[dict], result: str) -> dict | None:
    """Result-driven edge selection: an unconditional (THEN) edge is always eligible;
    a conditional edge is eligible iff its ``condition.result`` equals the execution
    result. The result — not a static dispatch table — decides control flow over the
    live topology. Deterministic tie-break by target id."""
    eligible = []
    for edge in edges:
        cond = edge.get("condition")
        if cond is None:
            eligible.append(edge)
        elif cond.get("result") == result:
            eligible.append(edge)
    if not eligible:
        return None
    eligible.sort(key=lambda e: e["target_id"])
    return eligible[0]


def modification_for(node: dict) -> Optional[dict]:
    """The self-modification a node triggers, if any. Data-driven: a ``self_modify``
    node carries the node + edges to add in its own ``data``, so the engine is
    content-agnostic and the modification is deterministic."""
    if node.get("op") == "self_modify":
        data = node.get("data", {})
        return {"add_node": data["add_node"], "add_edges": data["add_edges"]}
    return None


def execute(node: dict, state: dict, store: Any) -> tuple[str, bool]:
    """Execute a node against the agent's execution state; return (result, did_self_modify).

    The execution *result* (a string) is what later selects the outgoing edge. A
    ``self_modify`` node modifies the substrate *during execution*: it writes a new
    node and the edges that continue the path, data-driven from its own ``data``.
    Because the store is live, the very next ``get_outgoing_edges`` call in the
    traversal loop sees the new edge — there is no compile/parse/deploy boundary
    between the write and its effect.
    """
    op = node.get("op")
    if op == "init":
        state["acc"] = 0
        result = "ok"
    elif op == "add":
        state["acc"] = state.get("acc", 0) + int(node.get("data", {}).get("value", 0))
        result = "ok"
    elif op == "classify":
        result = "high" if state.get("acc", 0) >= node["data"]["threshold"] else "low"
    elif op == "self_modify":
        result = "ok"
    elif op == "record":
        result = "ok"
    elif op == "finalize":
        result = "done"
    else:
        result = "ok"

    did_self_modify = False
    spec = modification_for(node)
    if spec is not None and not store.has_node(spec["add_node"]["id"]):
        store.write_node(spec["add_node"])
        # The continuation that did not exist until the agent created it, live:
        for e in spec["add_edges"]:
            store.add_edge(e)
        did_self_modify = True
    return result, did_self_modify


def traverse(store: Any, start: str = "start", max_steps: int = 1000) -> dict:
    """Traverse-and-execute the substrate held by ``store``. Returns an execution
    record (final accumulator, visited order, routing decisions, self-mod flag)."""
    state: dict[str, Any] = {}
    current: str | None = start
    visited: list[str] = []
    routing: list[dict] = []
    self_modified = False
    steps = 0

    while current is not None and steps < max_steps:
        steps += 1
        node = store.read_node(current)  # live read from the store
        if node is None:
            break
        result, did_mod = execute(node, state, store)  # may self-modify the store
        self_modified = self_modified or did_mod
        visited.append(current)

        if node.get("type") == "RESULT":
            break

        edges = store.get_outgoing_edges(current)  # live re-read — sees any self-mod
        chosen = select_edge(edges, result)
        if chosen is None:
            break
        routing.append(
            {
                "from": current,
                "to": chosen["target_id"],
                "conditional": chosen.get("condition") is not None,
                "result": result,
                "candidates": len(edges),
            }
        )
        current = chosen["target_id"]

    return {
        "final_acc": state.get("acc"),
        "visited": visited,
        "routing": routing,
        "self_modified": self_modified,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# The seven metrics, computed identically for every condition
# ---------------------------------------------------------------------------

def compute_metrics(store: Any, record: dict, initial: dict[str, int],
                    baseline_snapshot: dict) -> dict:
    """Compute the 7 study metrics for a finished condition run.

    ``baseline_snapshot`` is Condition A's final snapshot; for A itself it is A's
    own snapshot (self-equal). ``functional_equivalence`` is the load-bearing one.
    """
    snap = store.snapshot()
    visited = record["visited"]
    routing = record["routing"]
    return {
        # 1. topology determination: the visited sequence was induced by edges
        #    (one routing decision per step except the terminal), not hardcoded.
        "topology_determination": len(visited) > 1 and len(routing) == len(visited) - 1,
        # 2. result-dependent routing: at least one edge was chosen by evaluating a
        #    non-trivial condition against the execution result.
        "result_dependent_routing": any(r["conditional"] for r in routing),
        # 3. self-modification during execution.
        "self_modification": bool(record["self_modified"]),
        # 4. modification persistence: the injected node persisted in the store AND
        #    was traversed after its creation (it affected subsequent traversal).
        "modification_persistence": store.has_node(INJECTED_NODE_ID) and INJECTED_NODE_ID in visited,
        # 5. functional equivalence to the serialized-file baseline (Condition A).
        "functional_equivalence": snap == baseline_snapshot,
        # 6 & 7. structural deltas produced during execution.
        "node_count_delta": store.node_count() - initial["nodes"],
        "edge_count_delta": store.edge_count() - initial["edges"],
    }


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------

class DictStore:
    """In-memory reference store. The mediation layer (Condition C) wraps one of
    these so its underlying medium is neither a file nor a database."""

    access_pattern = "in_memory"

    def __init__(self, baseline: dict) -> None:
        self._nodes: dict[str, dict] = {n["id"]: dict(n) for n in baseline["nodes"]}
        self._node_order: list[str] = [n["id"] for n in baseline["nodes"]]
        self._edges: list[dict] = [dict(e) for e in baseline["edges"]]

    def read_node(self, node_id: str) -> dict | None:
        node = self._nodes.get(node_id)
        return dict(node) if node is not None else None

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return [dict(e) for e in self._edges if e["source_id"] == node_id]

    def write_node(self, node: dict) -> None:
        if node["id"] not in self._nodes:
            self._node_order.append(node["id"])
        self._nodes[node["id"]] = dict(node)

    def add_edge(self, edge: dict) -> None:
        self._edges.append(dict(edge))

    def remove_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)
        self._node_order = [n for n in self._node_order if n != node_id]

    def remove_edge(self, source: str, target: str) -> None:
        self._edges = [e for e in self._edges if not (e["source_id"] == source and e["target_id"] == target)]

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def snapshot(self) -> dict:
        return canonical_snapshot(
            [self._nodes[nid] for nid in self._node_order], self._edges
        )


class FileStore:
    """Condition A: the serialized-file baseline (the EGS-979 L1 anchor).

    The substrate IS a JSON file on disk. Reads parse the file; writes serialize the
    whole graph back in place. This is the file access pattern that Conditions B and
    C are measured *against*.
    """

    access_pattern = "serialized_file"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.file_reads = 0
        self.file_writes = 0

    @classmethod
    def from_baseline(cls, baseline: dict, path: str | Path) -> "FileStore":
        store = cls(path)
        with store.path.open("w", encoding="utf-8") as f:
            json.dump({"nodes": baseline["nodes"], "edges": baseline["edges"]}, f, indent=2)
        store.file_writes += 1
        return store

    def _load(self) -> dict:
        self.file_reads += 1
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, graph: dict) -> None:
        self.file_writes += 1
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2)

    def read_node(self, node_id: str) -> dict | None:
        for n in self._load()["nodes"]:
            if n["id"] == node_id:
                return n
        return None

    def has_node(self, node_id: str) -> bool:
        return any(n["id"] == node_id for n in self._load()["nodes"])

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return [e for e in self._load()["edges"] if e["source_id"] == node_id]

    def write_node(self, node: dict) -> None:
        graph = self._load()
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node["id"]] + [node]
        self._save(graph)

    def add_edge(self, edge: dict) -> None:
        graph = self._load()
        graph["edges"].append(edge)
        self._save(graph)

    def remove_node(self, node_id: str) -> None:
        graph = self._load()
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node_id]
        self._save(graph)

    def remove_edge(self, source: str, target: str) -> None:
        graph = self._load()
        graph["edges"] = [e for e in graph["edges"] if not (e["source_id"] == source and e["target_id"] == target)]
        self._save(graph)

    def node_count(self) -> int:
        return len(self._load()["nodes"])

    def edge_count(self) -> int:
        return len(self._load()["edges"])

    def snapshot(self) -> dict:
        graph = self._load()
        return canonical_snapshot(graph["nodes"], graph["edges"])


# ---------------------------------------------------------------------------
# Condition A runner
# ---------------------------------------------------------------------------

def run_condition_a(workdir: str | Path, graph_initial: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Run Condition A (serialized-file baseline). Returns the run bundle whose
    snapshot is THE baseline every other condition is compared against."""
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    work_path = Path(workdir) / "substrate_a.json"
    store = FileStore.from_baseline(baseline, work_path)
    record = traverse(store, entry_id(baseline))
    snapshot = store.snapshot()
    return {"condition": "A", "store": store, "record": record,
            "snapshot": snapshot, "initial": initial}


if __name__ == "__main__":
    import sys
    import tempfile

    with tempfile.TemporaryDirectory(prefix="study_204_a_") as tmp:
        bundle = run_condition_a(tmp)
        rec = bundle["record"]
        # Compute metrics while the FileStore's backing file still exists.
        metrics = compute_metrics(bundle["store"], rec, bundle["initial"], bundle["snapshot"])

    print("=" * 64)
    print("STUDY-204 — Condition A (serialized-file baseline)")
    print("=" * 64)
    print(f"  visited:    {' -> '.join(rec['visited'])}")
    print(f"  final_acc:  {rec['final_acc']}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    ok = (
        rec["visited"] == ["start", "compute", "branch", "grow", "audit", "finalize"]
        and metrics["self_modification"]
        and metrics["modification_persistence"]
        and metrics["node_count_delta"] == 1
        and metrics["edge_count_delta"] == 2
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
