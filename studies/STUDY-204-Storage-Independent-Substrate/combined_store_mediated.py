# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: Condition D — relational persistent store UNDER a mediation layer.

The combined, maximum-architectural-distance condition: the graph lives in the
Condition-B relational store, and the agent reaches it only through the Condition-C
mediation layer. D is compositional — it imports ``SqliteStore`` from
``persistent_store`` and ``GraphMediator`` from ``mediated_access`` and stacks them.
The agent holds no storage handle AND the medium is a database. Two embodiment
shifts at once; the mechanism is still unchanged.
"""

from __future__ import annotations

from baseline_file import (
    baseline_counts,
    compute_metrics,
    entry_id,
    load_baseline,
    traverse,
    GRAPH_INITIAL_PATH,
)
from persistent_store import SqliteStore       # Condition B
from mediated_access import GraphMediator, agent_has_storage_handle  # Condition C


def run_condition_d(graph_initial: str = GRAPH_INITIAL_PATH, db_path: str = ":memory:") -> dict:
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = SqliteStore(baseline, db_path)     # B: relational store
    mediator = GraphMediator(store)            # C: mediation over it
    record = traverse(mediator, entry_id(baseline))
    snapshot = mediator.snapshot()
    return {"condition": "D", "store": mediator, "backing": store, "record": record,
            "snapshot": snapshot, "initial": initial}


def composes_b_and_c(bundle: dict) -> bool:
    """True iff D is genuinely the composition B∘C: a GraphMediator (C) wrapping a
    SqliteStore (B)."""
    mediator = bundle["store"]
    backing = bundle.get("backing")
    return isinstance(mediator, GraphMediator) and isinstance(backing, SqliteStore)


if __name__ == "__main__":
    import sys
    import tempfile
    from baseline_file import run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_204_d_") as tmp:
        a = run_condition_a(tmp)
        baseline_snapshot = a["snapshot"]

    d = run_condition_d()
    metrics = compute_metrics(d["store"], d["record"], d["initial"], baseline_snapshot)
    has_handle = agent_has_storage_handle(d["store"])

    print("=" * 64)
    print("STUDY-204 — Condition D (relational store + mediation)")
    print("=" * 64)
    print(f"  visited:             {' -> '.join(d['record']['visited'])}")
    print(f"  final_acc:           {d['record']['final_acc']}")
    print(f"  composes B and C:    {composes_b_and_c(d)}")
    print(f"  agent has handle:    {has_handle}")
    print(f"  backing SQL queries: {d['backing'].query_count}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    ok = (
        metrics["functional_equivalence"]
        and composes_b_and_c(d)
        and has_handle is False
        and d["backing"].query_count > 0
        and metrics["node_count_delta"] == 1
        and metrics["edge_count_delta"] == 2
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
