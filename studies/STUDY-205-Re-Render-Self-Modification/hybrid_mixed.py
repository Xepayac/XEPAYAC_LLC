# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-205: Condition D — Hybrid Mixed (in-place + re-render in one traversal).

Within a single traversal, some modifications are applied in place and others by
wholesale re-render. This proves the two materialization strategies are interchangeable:
the final TOPOLOGY is still structurally equal to the in-place baseline A, and the
on-disk REPRESENTATION still diverges from A. The mix is recorded in the substrate's
``materialization_log`` (both strategies appear), so the audit can confirm D actually
exercised both, not just one.

Compositional reuse: the agent and the substrate are imported unchanged from
``baseline_in_place_mutation``; D differs only in the ``hybrid`` strategy (first
modification in-place, the rest by re-render).
"""

from __future__ import annotations

from pathlib import Path

from baseline_in_place_mutation import (
    GRAPH_INITIAL_PATH,
    MaterializingSubstrate,
    baseline_counts,
    entry_of,
    load_baseline,
    traverse,
)


def run_condition_d(workdir: str | Path, graph_initial: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Run Condition D (hybrid mixed in-place + re-render)."""
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = MaterializingSubstrate(Path(workdir) / "D", baseline, "hybrid", name="substrate_d")
    record = traverse(store, entry_of(baseline))
    return {
        "condition": "D",
        "store": store,
        "record": record,
        "snapshot": store.snapshot(),
        "bytes": store.active_bytes(),
        "initial": initial,
        "strategies_used": sorted(store.strategies_used()),
    }


def mixes_in_place_and_rerender(bundle: dict) -> bool:
    """True iff Condition D used BOTH materialization strategies within one traversal."""
    return {"in_place", "rerender"} <= set(bundle["strategies_used"])


if __name__ == "__main__":
    import sys
    import tempfile

    from baseline_in_place_mutation import compute_metrics, run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_205_d_") as tmp:
        a = run_condition_a(tmp)
        d = run_condition_d(tmp)
        metrics = compute_metrics(d["store"], d["record"], d["initial"], a["snapshot"], a["bytes"])

        print("=" * 64)
        print("STUDY-205 — Condition D (hybrid mixed in-place + re-render)")
        print("=" * 64)
        print(f"  visited:          {' -> '.join(d['record']['visited'])}")
        print(f"  materialization:  {d['store'].materialization_log}")
        print(f"  strategies_used:  {d['strategies_used']}")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

        rep = metrics["representation_divergence"]
        ok = (
            metrics["functional_equivalence"]
            and rep["bytes_differ_from_A"]
            and rep["topology_matches_A"]
            and mixes_in_place_and_rerender(d)          # BOTH strategies used in one traversal
            and metrics["node_count_delta"] == 1
            and metrics["edge_count_delta"] == 2
        )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
