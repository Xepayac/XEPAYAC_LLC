# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-206: API-Mediated Self-Modification — Condition A (direct-write baseline).

Condition A is the EGS-979 base case: a single agent traverses the graph by
topology, executes node content, routes by the execution result, and writes the
result-driven self-modification DIRECTLY to the persisted serialized substrate.

This module also holds the SHARED primitives reused by Conditions B/C/D: the
graph helpers, the canonical-state normaliser, and — critically — the single
shared agent (`run_agent`). The agent's decision logic is identical in every
condition; only the accessor it is handed determines WHERE a write physically
executes. That is the whole point of the study: the decision-locus is the agent
regardless of where the write runs.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared graph primitives (stdlib only; primitive vocabulary, no vendor names)
# ---------------------------------------------------------------------------

def make_node(node_id, node_type, data):
    return {"id": node_id, "type": node_type, "data": data}


def make_edge(source, target, relation, condition=None):
    edge = {"source_id": source, "target_id": target, "relation": relation}
    if condition is not None:
        edge["condition"] = condition
    return edge


def save_graph(graph, path):
    with Path(path).open("w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2)


def load_graph(path):
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def deep(graph):
    """Deep copy via serialisation round-trip (avoids a non-stdlib-allowlisted
    `copy` import; the substrate is plain JSON-shaped data anyway)."""
    return json.loads(json.dumps(graph))


def canonical_state(graph):
    """Structural normal form for cross-condition equivalence comparison:
    node identity + type + content, and the edge topology. Volatile or
    embodiment-specific fields (storage layout, edge `condition` strings) are
    excluded so equality means 'same final substrate', not 'same storage'."""
    nodes = sorted(
        (n["id"], n["type"], json.dumps(n.get("data", {}), sort_keys=True))
        for n in graph["nodes"]
    )
    edges = sorted(
        (e["source_id"], e["target_id"], e["relation"]) for e in graph["edges"]
    )
    return {"nodes": nodes, "edges": edges}


def execute_node(node, state):
    """Execute a node against the agent's execution state; return the string
    result that selects the outgoing edge. Op-driven over the shared STUDY-203
    baseline schema ({id, type, op, data}); the accumulator lives in the agent,
    not the graph (computation occurs in the agent)."""
    op = node.get("op")
    if op == "init":
        state["acc"] = 0
        return "ok"
    if op == "add":
        state["acc"] = state.get("acc", 0) + int(node.get("data", {}).get("value", 0))
        return "ok"
    if op == "classify":
        return "high" if state.get("acc", 0) >= node["data"]["threshold"] else "low"
    if op == "finalize":
        return "done"
    # self_modify, record, and any other op are pure (no accumulator effect).
    return "ok"


def modification_for(node):
    """The self-modification a node triggers, if any. Data-driven: a `self_modify`
    node carries the node + edges to add in its own `data`, so the agent decides
    WHAT to write from the substrate content (not the transport)."""
    if node.get("op") == "self_modify":
        data = node.get("data", {})
        return {"add_node": data["add_node"], "add_edges": data["add_edges"]}
    return None


def select_edge(edges, result):
    """Result-dependent edge selection: choose the first conditioned edge whose
    `condition.result` equals the execution result; else the first unconditioned
    (THEN) edge. The result — not a static dispatch table — decides the path."""
    for edge in edges:
        cond = edge.get("condition")
        if cond is not None and cond.get("result") == result:
            return edge
    for edge in edges:
        if edge.get("condition") is None:
            return edge
    raise RuntimeError("no outgoing edge satisfied for result=%r" % result)


def is_edge_walk(path, graph):
    """True iff every consecutive pair in the traversal path is a real edge —
    evidence that the topology, not an external script, determined the sequence."""
    pairs = {(e["source_id"], e["target_id"]) for e in graph["edges"]}
    return all((path[i], path[i + 1]) in pairs for i in range(len(path) - 1))


# ---------------------------------------------------------------------------
# The shared agent — identical across all four conditions
# ---------------------------------------------------------------------------

def run_agent(sub):
    """Traverse, execute, route by result, and self-modify — through the accessor
    `sub`. The accessor exposes get_node / outgoing_edges / add_node / add_edge /
    remove_edge and decides only WHERE a write executes (directly, or across a
    service / process / store boundary). The agent decides WHAT to modify — the
    data-driven self-modification carried by the `self_modify` node (here, the
    `grow` node, which adds an `audit` node and its continuation) — entirely
    agent-side, BEFORE handing fully-specified writes to the accessor.
    """
    state = {}
    path = []
    routing_result = None
    selfmod_result = None
    routed_via_condition = False
    self_modified = False
    current = "start"
    for _ in range(1000):
        node = sub.get_node(current)
        path.append(current)
        result = execute_node(node, state)
        spec = modification_for(node)
        if spec is not None and not self_modified:
            # Agent-side decision: WHAT to write comes from the substrate content;
            # the accessor only transports/applies the requested writes.
            selfmod_result = result
            sub.add_node(spec["add_node"])
            for edge in spec["add_edges"]:
                sub.add_edge(edge)
            self_modified = True
        if node.get("type") == "RESULT":
            break
        edges = sub.outgoing_edges(current)
        if not edges:
            break
        chosen = select_edge(edges, result)
        if chosen.get("condition") is not None:
            routing_result = result
            routed_via_condition = True
        current = chosen["target_id"]
    else:
        raise RuntimeError("traversal did not terminate")
    return {
        "path": path,
        "routing_result": routing_result,
        "routed_via_condition": routed_via_condition,
        "selfmod_result": selfmod_result,
        "self_modified": self_modified,
        "audit_traversed": "audit" in path,
        "decision_locus": "agent",
    }


def compute_metrics(final_graph, init_counts, evidence, baseline_state):
    """Assemble the 7-metric block for one condition. Returns (metrics, state)."""
    fstate = canonical_state(final_graph)
    nodes_now = len(final_graph["nodes"])
    edges_now = len(final_graph["edges"])
    audit_present = any(n["id"] == "audit" for n in final_graph["nodes"])
    metrics = {
        "topology_determination": is_edge_walk(evidence["path"], final_graph),
        "result_dependent_routing": (evidence["routing_result"] is not None
                                      and evidence["routed_via_condition"]),
        "self_modification": evidence["self_modified"],
        "decision_locus": evidence["decision_locus"],
        "modification_persistence": evidence["audit_traversed"] and audit_present,
        "functional_equivalence": (True if baseline_state is None
                                   else fstate == baseline_state),
        "node_count_delta": nodes_now - init_counts[0],
        "edge_count_delta": edges_now - init_counts[1],
        "evidence": {
            "path": evidence["path"],
            "routing_result": evidence["routing_result"],
            "selfmod_result": evidence["selfmod_result"],
        },
    }
    return metrics, fstate


# ---------------------------------------------------------------------------
# Condition A: direct write to the persisted serialized substrate
# ---------------------------------------------------------------------------

class DirectSubstrate:
    """The agent holds the substrate directly and writes to it in place,
    persisting to the serialized file. This is the EGS-979 base case."""

    def __init__(self, path):
        self.path = Path(path)
        self.graph = load_graph(self.path)

    def _persist(self):
        save_graph(self.graph, self.path)

    def get_node(self, node_id):
        return next(n for n in self.graph["nodes"] if n["id"] == node_id)

    def outgoing_edges(self, node_id):
        return [e for e in self.graph["edges"] if e["source_id"] == node_id]

    def add_node(self, node):
        self.graph["nodes"].append(node)
        self._persist()

    def add_edge(self, edge):
        self.graph["edges"].append(edge)
        self._persist()

    def remove_edge(self, source, target, relation):
        self.graph["edges"] = [
            e for e in self.graph["edges"]
            if not (e["source_id"] == source and e["target_id"] == target
                    and e["relation"] == relation)
        ]
        self._persist()

    def node_count(self):
        return len(self.graph["nodes"])

    def edge_count(self):
        return len(self.graph["edges"])

    def snapshot(self):
        return self.graph


def run(initial_graph, baseline_state=None):
    """Run Condition A. Returns {condition, metrics, final_state}."""
    with tempfile.TemporaryDirectory(prefix="study206_A_") as tmp:
        path = Path(tmp) / "substrate.json"
        save_graph(deep(initial_graph), path)
        sub = DirectSubstrate(path)
        init_counts = (sub.node_count(), sub.edge_count())
        evidence = run_agent(sub)
        # Persistence across the serialized file: reload from disk and confirm
        # the modification survived (it governs any subsequent traversal).
        reloaded = load_graph(path)
        persisted = any(n["id"] == "audit" for n in reloaded["nodes"])
        evidence["audit_traversed"] = evidence["audit_traversed"] and persisted
        metrics, fstate = compute_metrics(sub.snapshot(), init_counts,
                                          evidence, baseline_state)
    return {"condition": "A", "metrics": metrics, "final_state": fstate}


if __name__ == "__main__":
    init = load_graph(Path(__file__).parent / "graph_initial.json")
    res = run(init)
    m = res["metrics"]
    print("STUDY-206 Condition A — direct-write baseline")
    for key, value in m.items():
        if key != "evidence":
            print("  %s: %s" % (key, value))
    print("  path: %s" % " -> ".join(m["evidence"]["path"]))
    ok = (m["functional_equivalence"] and m["decision_locus"] == "agent"
          and m["self_modification"]
          and (m["node_count_delta"] or m["edge_count_delta"]))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
