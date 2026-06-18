# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-205: Re-Render Self-Modification — Condition A (in-place mutation baseline)
and the shared substrate semantics every condition runs.

This module is the single source of the *mechanism*: one ``traverse`` agent, one
``execute_node`` step, one ``select_edge`` router, and the data-driven self-modification,
applied over a ``MaterializingSubstrate`` whose only per-condition variable is HOW a
result-driven modification is written back to the persisted serialization:

  - Condition A (here): in-place mutation — a localized edit that preserves the
    on-disk order/format of untouched elements and splices in the delta.
  - Condition B (``rerender_full_emit``): wholesale re-render — re-serialize the entire
    graph (canonical normal form) and replace the prior file content.
  - Condition C (``rerender_new_file``): re-render as new-file emission — emit the whole
    graph as a NEW file, switch the active substrate to it, leave the prior file intact.
  - Condition D (``hybrid_mixed``): mix in-place and re-render within one traversal.

The load-bearing structure of the proof: the *materialization strategy* moves; the
*mechanism* does not. Across all four conditions the final TOPOLOGY is structurally
identical (compared by ``structural_diff`` — NOT a byte/file hash), while the on-disk
serialized REPRESENTATION diverges (the ``representation_divergence`` metric). That is
the crux of this study: *representation differs, topology does not.*

The substrate semantics here are byte-for-byte the same baseline graph STUDY-203 (#1438)
authored and merged (``baseline_authored_by = STUDY-203``), and the execution model
(op-based accumulator, result-driven edge selection over edge ``condition`` properties,
data-driven self-modification) matches STUDY-203's so the final topology is identical
across the studies — the shared-baseline combined-prior-art premise.

HONESTY (read REJECTING the over-claim). This is a *materialization-strategy-equivalence*
study, NOT a *mechanism-fully-survives* study. Wholesale re-render is, by definition, a
generation/transformation step; it **surrenders L5 / structural-liveness** (the as-filed
spec's no-compile floor). The mechanism axis this study demonstrates surviving the
materialization shift is *topology-as-program* (the final topology governs subsequent
traversal) and *result-driven edge selection* (a result selects the modification and the
next edge), plus persistence. It does **not** claim re-render preserves structural
liveness. See README "Honesty and Claim Mapping".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

GRAPH_INITIAL_PATH = Path(__file__).resolve().parent / "graph_initial.json"

# The node the data-driven self-modification injects during execution (carried in the
# 'grow' node's own ``data`` in the shared baseline). It does not exist at start.
SELF_MOD_NODE_ID = "audit"

# Bounded-iteration safety net — never a cap on the study domain (the path is 6 steps).
MAX_STEPS = 100


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline(path: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Load the shared baseline graph (nodes + edges + entry marker)."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def baseline_counts(baseline: dict) -> dict[str, int]:
    return {"nodes": len(baseline["nodes"]), "edges": len(baseline["edges"])}


def entry_of(baseline: dict) -> str:
    return baseline.get("entry") or baseline.get("start") or "start"


# ---------------------------------------------------------------------------
# Canonical snapshot + structural diff — the TOPOLOGICAL comparator (ADR-001).
# Equivalence is decided over STRUCTURE, never over serialized bytes: re-render
# legitimately changes the bytes, so a byte/hash comparison would spuriously fail
# every re-render condition. Schema matches STUDY-203's (id/type/op nodes;
# source_id/target_id/relation/condition edges) so cross-study equality holds.
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
    """A serialization-independent, order-independent view of the graph's structure:
    node identities + op, and the directed edge set + edge conditions."""
    snap_nodes = sorted((canonical_node(n) for n in nodes), key=lambda n: n["id"])
    snap_edges = sorted(
        (canonical_edge(e) for e in edges),
        key=lambda e: (e["source_id"], e["target_id"], e["relation"]),
    )
    return {"nodes": snap_nodes, "edges": snap_edges}


def structural_diff(snap_a: dict, snap_b: dict) -> dict:
    """Return the TOPOLOGICAL difference between two canonical snapshots.

    An empty diff (all lists empty) means the two graphs are structurally identical —
    regardless of how either was serialized on disk. This is the comparator the
    equivalence gate uses; it is deliberately NOT a byte/file hash.
    """
    def edge_key(e: dict) -> tuple:
        return (e["source_id"], e["target_id"], e["relation"],
                json.dumps(e["condition"], sort_keys=True))

    a_nodes = {n["id"]: n for n in snap_a["nodes"]}
    b_nodes = {n["id"]: n for n in snap_b["nodes"]}
    a_edges = {edge_key(e) for e in snap_a["edges"]}
    b_edges = {edge_key(e) for e in snap_b["edges"]}

    return {
        "nodes_only_in_a": sorted(set(a_nodes) - set(b_nodes)),
        "nodes_only_in_b": sorted(set(b_nodes) - set(a_nodes)),
        "nodes_differing": sorted(k for k in (set(a_nodes) & set(b_nodes)) if a_nodes[k] != b_nodes[k]),
        "edges_only_in_a": sorted(str(k) for k in (a_edges - b_edges)),
        "edges_only_in_b": sorted(str(k) for k in (b_edges - a_edges)),
    }


def topologically_equal(snap_a: dict, snap_b: dict) -> bool:
    """True iff the structural diff is empty — the load-bearing equivalence predicate."""
    return not any(structural_diff(snap_a, snap_b).values())


# ---------------------------------------------------------------------------
# The two materialization serializers — the only thing that differs between an
# in-place edit and a wholesale re-render. Both encode the SAME graph; they differ
# in BYTES. That byte divergence at equal topology is what ``representation_divergence``
# measures, and it is the whole point of the study.
# ---------------------------------------------------------------------------

def serialize_in_place(graph: dict) -> str:
    """Layout-preserving serialization (the in-place edit).

    Preserves document order (nodes/edges in their existing positions) and each
    object's key order, appending only the delta. Untouched elements keep their
    on-disk byte layout; only the spliced-in elements are new.
    """
    return json.dumps({"nodes": graph["nodes"], "edges": graph["edges"]}, indent=2) + "\n"


def serialize_rerender(graph: dict) -> str:
    """Wholesale re-render serialization (the regenerated artifact).

    Regenerates the ENTIRE serialized form in a canonical normal form: nodes sorted by
    id, edges sorted by (source_id, target_id, relation), and ``sort_keys`` normalizing
    every object's key order. Independent of any prior on-disk layout — exactly what a
    generation step produces. Byte-divergent from ``serialize_in_place`` whenever the
    id-order differs from document order (it does here).
    """
    nodes = sorted((dict(n) for n in graph["nodes"]), key=lambda n: n["id"])
    edges = sorted(
        (dict(e) for e in graph["edges"]),
        key=lambda e: (e["source_id"], e["target_id"], e["relation"]),
    )
    return json.dumps({"nodes": nodes, "edges": edges}, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Substrate semantics — shared by ALL conditions (matches STUDY-203's model so the
# final topology is cross-study identical).
# ---------------------------------------------------------------------------

def execute_node(node: dict, state: dict) -> str:
    """Deterministically execute a node against the agent's accumulator state.

    Returns the node's execution result. The result — NOT any dispatch table — is what
    later selects the outgoing edge. Computation occurs in the agent; the graph is the
    program."""
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
    """The self-modification a node triggers, if any. Data-driven: a ``self_modify`` node
    carries the node + edges to add in its own ``data`` (deterministic, content-agnostic
    engine)."""
    if node.get("op") == "self_modify":
        return {"add_node": node["data"]["add_node"], "add_edges": node["data"]["add_edges"]}
    return None


def select_edge(edges: list[dict], result: str) -> Optional[dict]:
    """Result-driven edge selection. An unconditioned edge is always eligible; a
    conditioned edge is eligible iff its ``condition.result`` matches the execution
    result. Deterministic tie-break by target id. The result — not coordinating logic —
    selects the path over the live topology."""
    eligible = []
    for e in edges:
        cond = e.get("condition")
        if cond is None or cond.get("result") == result:
            eligible.append(e)
    if not eligible:
        return None
    eligible.sort(key=lambda e: e["target_id"])
    return eligible[0]


def is_terminal(node: dict) -> bool:
    return node["type"] == "RESULT"


def traverse(store: Any, entry_id: str, max_steps: int = MAX_STEPS) -> dict:
    """Traverse-and-execute the substrate held by ``store``. Executes each node, applies
    any data-driven self-modification through the store (which materializes it per its
    strategy), and selects the next edge by the execution result. Reads are live, so the
    self-modification affects the very next step in every condition."""
    state: dict[str, Any] = {}
    current: Optional[str] = entry_id
    visited: list[str] = []
    routing: list[dict] = []
    self_modified = False
    steps = 0

    while current is not None and steps < max_steps:
        steps += 1
        node = store.read_node(current)  # live read from the active substrate
        if node is None:
            break
        result = execute_node(node, state)  # compute in the agent
        visited.append(current)

        spec = modification_for(node)
        if spec is not None and not store.has_node(spec["add_node"]["id"]):
            # data-driven self-modification, materialized by the store's strategy
            store.write_node(spec["add_node"])
            for e in spec["add_edges"]:
                store.add_edge(e)
            self_modified = True

        if is_terminal(node):
            break

        edges = store.get_outgoing_edges(current)  # live re-read — sees any self-mod
        chosen = select_edge(edges, result)
        if chosen is None:
            break
        routing.append({
            "from": current,
            "to": chosen["target_id"],
            "result": result,
            "conditional": chosen.get("condition") is not None,
            "candidates": len(edges),
        })
        current = chosen["target_id"]

    return {
        "final_acc": state.get("acc"),
        "visited": visited,
        "routing": routing,
        "self_modified": self_modified,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# The materializing substrate: a file-backed graph whose self-modifications are
# written back by one of four strategies. Reads always parse the ACTIVE file (live),
# so persistence affects subsequent traversal in every condition.
# ---------------------------------------------------------------------------

class MaterializingSubstrate:
    """A file-backed graph substrate parameterized by a materialization strategy.

    strategy ∈ {"in_place", "rerender", "rerender_new_file", "hybrid"}:
      - in_place:          localized edit, layout-preserving, same file.
      - rerender:          wholesale re-render, canonical form, same file.
      - rerender_new_file: wholesale re-render emitted to a NEW file; active substrate
                           switches to it; prior file left intact; no superseded_by edge.
      - hybrid:            first modification in-place, the rest by re-render.

    The initial "as-handed-over" representation is written identically for every
    condition (``serialize_in_place`` of the baseline graph), so any byte divergence at
    the end is attributable solely to how the self-modification was materialized.
    """

    def __init__(self, workdir: str | Path, baseline: dict, strategy: str, name: str = "substrate") -> None:
        self.dir = Path(workdir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.strategy = strategy
        self.name = name
        self.materialization_log: list[str] = []
        self.emitted_paths: list[Path] = []
        self._emit_count = 0
        self.original_path = self.dir / f"{name}.json"
        self.active_path = self.original_path
        graph = {
            "nodes": [dict(n) for n in baseline["nodes"]],
            "edges": [dict(e) for e in baseline["edges"]],
        }
        self.original_path.write_text(serialize_in_place(graph), encoding="utf-8")
        self.original_initial_bytes = self.original_path.read_bytes()
        self.emitted_paths.append(self.original_path)

    # --- live reads (parse the ACTIVE file) ---
    def _load(self) -> dict:
        return json.loads(self.active_path.read_text(encoding="utf-8"))

    def read_node(self, node_id: str) -> dict | None:
        for n in self._load()["nodes"]:
            if n["id"] == node_id:
                return n
        return None

    def has_node(self, node_id: str) -> bool:
        return any(n["id"] == node_id for n in self._load()["nodes"])

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return [e for e in self._load()["edges"] if e["source_id"] == node_id]

    def node_count(self) -> int:
        return len(self._load()["nodes"])

    def edge_count(self) -> int:
        return len(self._load()["edges"])

    def snapshot(self) -> dict:
        g = self._load()
        return canonical_snapshot(g["nodes"], g["edges"])

    def active_bytes(self) -> bytes:
        return self.active_path.read_bytes()

    def has_superseded_by_edge(self) -> bool:
        """Pure re-render writes NO provenance link (ADR-004) — distinct from supersede."""
        g = self._load()
        for e in g["edges"]:
            if e.get("relation") in ("SUPERSEDES", "SUPERSEDED_BY") or "superseded_by" in e:
                return True
        return any("superseded_by" in n for n in g["nodes"])

    def prior_file_intact(self) -> bool:
        """True iff the original substrate file still exists with its initial bytes
        (Condition C leaves the prior file intact)."""
        if not self.original_path.exists():
            return False
        return self.original_path.read_bytes() == self.original_initial_bytes

    # --- writes (mutate the in-memory graph, then materialize via the strategy) ---
    def write_node(self, node: dict) -> None:
        g = self._load()
        g["nodes"] = [n for n in g["nodes"] if n["id"] != node["id"]] + [node]
        self._materialize(g)

    def add_edge(self, edge: dict) -> None:
        g = self._load()
        g["edges"].append(edge)
        self._materialize(g)

    def remove_node(self, node_id: str) -> None:
        g = self._load()
        g["nodes"] = [n for n in g["nodes"] if n["id"] != node_id]
        self._materialize(g)

    def _next_strategy(self) -> str:
        if self.strategy != "hybrid":
            return self.strategy
        return "in_place" if len(self.materialization_log) == 0 else "rerender"

    def _materialize(self, graph: dict) -> None:
        strat = self._next_strategy()
        self.materialization_log.append(strat)
        if strat == "in_place":
            self.active_path.write_text(serialize_in_place(graph), encoding="utf-8")
        elif strat == "rerender":
            self.active_path.write_text(serialize_rerender(graph), encoding="utf-8")
        elif strat == "rerender_new_file":
            self._emit_count += 1
            new_path = self.dir / f"{self.name}.v{self._emit_count}.json"
            new_path.write_text(serialize_rerender(graph), encoding="utf-8")
            self.active_path = new_path
            self.emitted_paths.append(new_path)
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown strategy: {strat!r}")

    def strategies_used(self) -> set[str]:
        return set(self.materialization_log)


# ---------------------------------------------------------------------------
# The seven metrics, computed identically for every condition
# ---------------------------------------------------------------------------

def compute_metrics(store: MaterializingSubstrate, record: dict, initial: dict[str, int],
                    baseline_snapshot: dict, baseline_bytes: bytes) -> dict:
    """Compute the 7 study metrics. ``baseline_snapshot`` / ``baseline_bytes`` are
    Condition A's final TOPOLOGY and final on-disk BYTES. ``functional_equivalence``
    (topological) and ``representation_divergence`` (bytes differ from A while topology
    matches) are the two load-bearing metrics."""
    snap = store.snapshot()
    visited = record["visited"]
    routing = record["routing"]
    final_bytes = store.active_bytes()
    return {
        "topology_determination": len(visited) > 1 and len(routing) == len(visited) - 1,
        "result_dependent_routing": any(r["conditional"] for r in routing),
        "self_modification": bool(record["self_modified"]),
        "modification_persistence": store.has_node(SELF_MOD_NODE_ID) and SELF_MOD_NODE_ID in visited,
        "functional_equivalence": topologically_equal(snap, baseline_snapshot),
        "representation_divergence": {
            "bytes_differ_from_A": final_bytes != baseline_bytes,
            "topology_matches_A": topologically_equal(snap, baseline_snapshot),
        },
        "node_count_delta": store.node_count() - initial["nodes"],
        "edge_count_delta": store.edge_count() - initial["edges"],
    }


# ---------------------------------------------------------------------------
# Condition A runner — produces THE baseline topology + bytes every other condition
# is compared against.
# ---------------------------------------------------------------------------

def run_condition_a(workdir: str | Path, graph_initial: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Run Condition A (in-place mutation baseline)."""
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = MaterializingSubstrate(Path(workdir) / "A", baseline, "in_place", name="substrate_a")
    record = traverse(store, entry_of(baseline))
    return {
        "condition": "A",
        "store": store,
        "record": record,
        "snapshot": store.snapshot(),
        "bytes": store.active_bytes(),
        "initial": initial,
    }


if __name__ == "__main__":
    import sys
    import tempfile

    with tempfile.TemporaryDirectory(prefix="study_205_a_") as tmp:
        bundle = run_condition_a(tmp)
        rec = bundle["record"]
        metrics = compute_metrics(bundle["store"], rec, bundle["initial"], bundle["snapshot"], bundle["bytes"])

        print("=" * 64)
        print("STUDY-205 — Condition A (in-place mutation baseline)")
        print("=" * 64)
        print(f"  visited:    {' -> '.join(rec['visited'])}")
        print(f"  final_acc:  {rec['final_acc']}")
        print(f"  materialization: {bundle['store'].materialization_log}")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

        ok = (
            rec["visited"] == ["start", "compute", "branch", "grow", "audit", "finalize"]
            and metrics["self_modification"]
            and metrics["modification_persistence"]
            and metrics["node_count_delta"] == 1
            and metrics["edge_count_delta"] == 2
            and set(bundle["store"].materialization_log) == {"in_place"}
        )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
