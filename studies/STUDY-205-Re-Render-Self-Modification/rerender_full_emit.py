# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-205: Condition B — Wholesale Re-Render, same file.

The agent computes the SAME result-driven modification as Condition A, but instead of
an in-place edit it **re-serializes the entire graph** (canonical normal form) and
replaces the prior file content — no in-place delta is written. The change persists in
the same file and affects subsequent traversal.

Only the materialization strategy differs from Condition A; the traversal agent, the
router, and the self-modification are imported unchanged from ``baseline_in_place_mutation``.
The final TOPOLOGY is structurally identical to A; the on-disk REPRESENTATION diverges
(every node re-emitted in canonical order/format, not just the appended delta).
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


def run_condition_b(workdir: str | Path, graph_initial: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Run Condition B (wholesale re-render to the same file)."""
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = MaterializingSubstrate(Path(workdir) / "B", baseline, "rerender", name="substrate_b")
    record = traverse(store, entry_of(baseline))
    return {
        "condition": "B",
        "store": store,
        "record": record,
        "snapshot": store.snapshot(),
        "bytes": store.active_bytes(),
        "initial": initial,
    }


if __name__ == "__main__":
    import sys
    import tempfile

    from baseline_in_place_mutation import compute_metrics, run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_205_b_") as tmp:
        a = run_condition_a(tmp)
        b = run_condition_b(tmp)
        metrics = compute_metrics(b["store"], b["record"], b["initial"], a["snapshot"], a["bytes"])

        print("=" * 64)
        print("STUDY-205 — Condition B (wholesale re-render, same file)")
        print("=" * 64)
        print(f"  visited:         {' -> '.join(b['record']['visited'])}")
        print(f"  materialization: {b['store'].materialization_log}")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

        rep = metrics["representation_divergence"]
        ok = (
            metrics["functional_equivalence"]            # topology matches A
            and rep["bytes_differ_from_A"]               # but the bytes diverge
            and rep["topology_matches_A"]
            and set(b["store"].materialization_log) == {"rerender"}
            and metrics["node_count_delta"] == 1
            and metrics["edge_count_delta"] == 2
        )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
