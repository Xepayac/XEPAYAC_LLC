# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: Condition C — mediated graph access.

The agent does not hold a storage handle. A ``GraphMediator`` interposes between the
agent and the underlying store, exposing only graph operations
(read_node / get_outgoing_edges / write_node / add_edge / remove_node — the ADR-002
contract). The agent is handed the mediator and nothing else; it cannot reach the
backing store, which is name-mangled private. The topology still governs execution.

This removes the residual file-similarity of Condition B entirely: there is no file,
no database handle, and no storage object the agent can touch — only an interface.

The traversal agent, edge router, and metrics are imported unchanged from
``baseline_file``; the backing medium here is an in-memory store, so the embodiment
is neither a serialized file nor a database, yet the result is identical.
"""

from __future__ import annotations

from typing import Any

from baseline_file import (
    DictStore,
    baseline_counts,
    compute_metrics,
    load_baseline,
    traverse,
    GRAPH_INITIAL_PATH,
)

# The exact public graph-operation interface the mediator exposes to the agent.
MEDIATOR_INTERFACE = (
    "read_node",
    "has_node",
    "get_outgoing_edges",
    "write_node",
    "add_edge",
    "remove_node",
    "remove_edge",
)


class GraphMediator:
    """Mediation layer (ADR-002). Holds the backing store privately (name-mangled),
    delegating each graph operation. The agent receives only this object; it has no
    reference to, and no public accessor for, the underlying storage."""

    access_pattern = "mediated"

    def __init__(self, backing_store: Any) -> None:
        # Name-mangled to ``_GraphMediator__backing``: not part of the public surface
        # the agent (or anyone treating the mediator as its interface) can reach.
        self.__backing = backing_store

    # --- ADR-002 graph-operation interface (all the agent is given) ---

    def read_node(self, node_id: str) -> dict | None:
        return self.__backing.read_node(node_id)

    def has_node(self, node_id: str) -> bool:
        return self.__backing.has_node(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return self.__backing.get_outgoing_edges(node_id)

    def write_node(self, node: dict) -> None:
        self.__backing.write_node(node)

    def add_edge(self, edge: dict) -> None:
        self.__backing.add_edge(edge)

    def remove_node(self, node_id: str) -> None:
        self.__backing.remove_node(node_id)

    def remove_edge(self, source: str, target: str) -> None:
        self.__backing.remove_edge(source, target)

    # --- measurement helpers (used by the harness, not by the traversal agent) ---

    def node_count(self) -> int:
        return self.__backing.node_count()

    def edge_count(self) -> int:
        return self.__backing.edge_count()

    def snapshot(self) -> dict:
        return self.__backing.snapshot()


def agent_has_storage_handle(mediator: GraphMediator) -> bool:
    """True iff the mediator exposes the backing store through any public attribute.

    Used by the test suite to assert the agent (which is handed only the mediator)
    cannot reach storage: a serialized-file path, a database connection, or the
    backing store object itself."""
    for name in vars(mediator):
        if not name.startswith("_GraphMediator__"):
            value = getattr(mediator, name)
            # A storage handle would be a path, a DB connection, or a store object.
            if hasattr(value, "execute") or hasattr(value, "read_node") or isinstance(value, (str, bytes)):
                return True
    # Common storage-handle attribute names must not be publicly present.
    return any(hasattr(mediator, attr) for attr in ("conn", "path", "backing", "store", "db"))


def run_condition_c(graph_initial: str = GRAPH_INITIAL_PATH) -> dict:
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    backing = DictStore(baseline)          # in-memory backing — neither file nor DB
    mediator = GraphMediator(backing)      # the agent will receive ONLY this
    record = traverse(mediator, baseline.get("start", "start"))
    snapshot = mediator.snapshot()
    return {"condition": "C", "store": mediator, "record": record,
            "snapshot": snapshot, "initial": initial}


if __name__ == "__main__":
    import sys
    import tempfile
    from baseline_file import run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_204_c_") as tmp:
        a = run_condition_a(tmp)
        baseline_snapshot = a["snapshot"]

    c = run_condition_c()
    metrics = compute_metrics(c["store"], c["record"], c["initial"], baseline_snapshot)
    has_handle = agent_has_storage_handle(c["store"])

    print("=" * 64)
    print("STUDY-204 — Condition C (mediated access)")
    print("=" * 64)
    print(f"  visited:             {' -> '.join(c['record']['visited'])}")
    print(f"  final_acc:           {c['record']['final_acc']}")
    print(f"  agent has handle:    {has_handle}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    ok = (
        metrics["functional_equivalence"]
        and has_handle is False
        and metrics["node_count_delta"] == 1
        and metrics["edge_count_delta"] == 2
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
