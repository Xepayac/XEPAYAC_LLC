# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: Storage-Independent Graph Substrate — Condition A (serialized-file baseline)
and the shared substrate semantics every condition runs.

This module is the single source of the *mechanism*: one ``traverse`` agent, one
``execute`` step, one ``select_edge`` router, applied over a pluggable ``store``.
Conditions B/C/D import this same agent and supply only a different store, so any
behavioural difference between conditions would be a difference of *storage*, never
of *mechanism*. That is the load-bearing structure of the proof: the embodiment
(where/how the graph is stored or accessed) moves; the mechanism does not.

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
from typing import Any

GRAPH_INITIAL_PATH = Path(__file__).resolve().parent / "graph_initial.json"

# The node the agent injects into the substrate during execution. It does not
# exist in the baseline graph; the 'grow' node creates it (and its edges) live.
INJECTED_NODE_ID = "injected"


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline(path: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Load the shared baseline graph (nodes + edges + start marker)."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def baseline_counts(baseline: dict) -> dict[str, int]:
    return {"nodes": len(baseline["nodes"]), "edges": len(baseline["edges"])}


# ---------------------------------------------------------------------------
# Canonical snapshot — the structure-only view used for cross-condition equality
# ---------------------------------------------------------------------------

def canonical_node(node: dict) -> dict:
    return {"id": node["id"], "type": node["type"], "content": node["content"]}


def canonical_edge(edge: dict) -> dict:
    return {
        "source": edge["source"],
        "target": edge["target"],
        "relation": edge["relation"],
        "condition": edge.get("condition", {"when": "always"}),
    }


def canonical_snapshot(nodes: list[dict], edges: list[dict]) -> dict:
    """A storage-independent, order-independent view of the graph's final state.

    Two conditions are *functionally equivalent* iff their canonical snapshots are
    deep-equal. Sorting removes any storage-imposed ordering so the comparison is
    over structure alone.
    """
    snap_nodes = sorted((canonical_node(n) for n in nodes), key=lambda n: n["id"])
    snap_edges = sorted(
        (canonical_edge(e) for e in edges),
        key=lambda e: (e["source"], e["target"], e["relation"]),
    )
    return {"nodes": snap_nodes, "edges": snap_edges}


# ---------------------------------------------------------------------------
# The agent: traversal IS execution. Storage-agnostic — operates on any ``store``
# implementing read_node / has_node / get_outgoing_edges / write_node / add_edge.
# ---------------------------------------------------------------------------

def _condition_satisfied(condition: dict, result: int) -> bool:
    when = condition.get("when", "always")
    if when == "always":
        return True
    if when == "result_gte":
        return result >= condition["value"]
    if when == "result_lt":
        return result < condition["value"]
    return False


def select_edge(edges: list[dict], result: int) -> dict | None:
    """Result-driven edge selection: return the first outgoing edge whose condition
    property is satisfied by the execution result. The result — not a static
    dispatch table — decides control flow over the live topology."""
    for edge in edges:
        if _condition_satisfied(edge.get("condition", {"when": "always"}), result):
            return edge
    return None


def execute(node: dict, acc: int, store: Any) -> tuple[int, bool]:
    """Execute a node's content against the accumulator, returning (new_acc, did_self_modify).

    The 'grow' node self-modifies the substrate *during execution*: it writes a new
    node and the edges that continue the path. Because the store is live, the very
    next ``get_outgoing_edges`` call in the traversal loop sees the new edge — there
    is no compile/parse/deploy boundary between the write and its effect.
    """
    content = node.get("content", {})
    op = content.get("op", "noop")
    if op == "add":
        acc = acc + int(content.get("value", 0))
    elif op == "noop":
        pass
    else:
        raise ValueError(f"unknown op: {op!r}")

    did_self_modify = False
    if node["id"] == "grow" and not store.has_node(INJECTED_NODE_ID):
        store.write_node(
            {
                "id": INJECTED_NODE_ID,
                "type": "OPERATION",
                "content": {"op": "add", "value": 100, "label": "node injected during execution"},
            }
        )
        # The continuation that did not exist until the agent created it, live:
        store.add_edge(
            {"source": "grow", "target": INJECTED_NODE_ID, "relation": "THEN", "condition": {"when": "always"}}
        )
        store.add_edge(
            {"source": INJECTED_NODE_ID, "target": "finalize", "relation": "THEN", "condition": {"when": "always"}}
        )
        did_self_modify = True
    return acc, did_self_modify


def traverse(store: Any, start_id: str = "start", max_steps: int = 1000) -> dict:
    """Traverse-and-execute the substrate held by ``store``. Returns an execution
    record (final accumulator, visited order, routing decisions, self-mod flag)."""
    acc = 0
    current: str | None = start_id
    visited: list[str] = []
    routing: list[dict] = []
    self_modified = False
    steps = 0

    while current is not None and steps < max_steps:
        steps += 1
        node = store.read_node(current)  # live read from the store
        if node is None:
            break
        acc, did_mod = execute(node, acc, store)  # may self-modify the store
        self_modified = self_modified or did_mod
        visited.append(current)

        edges = store.get_outgoing_edges(current)  # live re-read — sees any self-mod
        chosen = select_edge(edges, acc)
        if chosen is None:
            break
        routing.append(
            {
                "from": current,
                "to": chosen["target"],
                "condition": chosen.get("condition", {}).get("when", "always"),
                "result": acc,
                "candidates": len(edges),
            }
        )
        current = chosen["target"]

    return {
        "final_acc": acc,
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
        "result_dependent_routing": any(r["condition"] != "always" for r in routing),
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
        return [dict(e) for e in self._edges if e["source"] == node_id]

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
        self._edges = [e for e in self._edges if not (e["source"] == source and e["target"] == target)]

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
        return [e for e in self._load()["edges"] if e["source"] == node_id]

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
        graph["edges"] = [e for e in graph["edges"] if not (e["source"] == source and e["target"] == target)]
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
    record = traverse(store, baseline.get("start", "start"))
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
        rec["visited"] == ["start", "branch", "grow", "injected", "finalize"]
        and metrics["self_modification"]
        and metrics["modification_persistence"]
        and metrics["node_count_delta"] == 1
        and metrics["edge_count_delta"] == 2
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
