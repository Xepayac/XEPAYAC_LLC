# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-205: Condition C — Re-Render as New-File Emission.

The agent emits the modified graph as a **new serialized file**; the active substrate
switches to it; the prior file is left intact and **no** ``superseded_by`` edge is
written. This is *pure* re-render — deliberately the harder dodge: unlike supersede
(STUDY-140 / issue #1329), which preserves topology AND writes a persisted
``superseded_by`` link, pure re-render need preserve neither. The substrate topology
still evolves through execution, and the final active file is structurally equal to the
in-place baseline A.

Only the materialization strategy differs from Conditions A/B; the agent is imported
unchanged from ``baseline_in_place_mutation``.
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


def run_condition_c(workdir: str | Path, graph_initial: str | Path = GRAPH_INITIAL_PATH) -> dict:
    """Run Condition C (re-render as new-file emission)."""
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = MaterializingSubstrate(Path(workdir) / "C", baseline, "rerender_new_file", name="substrate_c")
    record = traverse(store, entry_of(baseline))
    return {
        "condition": "C",
        "store": store,
        "record": record,
        "snapshot": store.snapshot(),
        "bytes": store.active_bytes(),
        "initial": initial,
        # evidence specific to new-file emission
        "active_path_is_new": store.active_path != store.original_path,
        "prior_file_intact": store.prior_file_intact(),
        "has_superseded_by_edge": store.has_superseded_by_edge(),
        "emitted_file_count": len(store.emitted_paths),
    }


if __name__ == "__main__":
    import sys
    import tempfile

    from baseline_in_place_mutation import compute_metrics, run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_205_c_") as tmp:
        a = run_condition_a(tmp)
        c = run_condition_c(tmp)
        metrics = compute_metrics(c["store"], c["record"], c["initial"], a["snapshot"], a["bytes"])

        print("=" * 64)
        print("STUDY-205 — Condition C (re-render as new-file emission)")
        print("=" * 64)
        print(f"  visited:          {' -> '.join(c['record']['visited'])}")
        print(f"  active_path_new:  {c['active_path_is_new']}")
        print(f"  prior_intact:     {c['prior_file_intact']}")
        print(f"  superseded_edge:  {c['has_superseded_by_edge']}")
        print(f"  emitted_files:    {c['emitted_file_count']}")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

        rep = metrics["representation_divergence"]
        ok = (
            metrics["functional_equivalence"]
            and rep["bytes_differ_from_A"]
            and rep["topology_matches_A"]
            and c["active_path_is_new"]                 # active substrate switched to a new file
            and c["prior_file_intact"]                  # prior file left intact
            and not c["has_superseded_by_edge"]         # PURE re-render — no provenance edge
            and metrics["node_count_delta"] == 1
            and metrics["edge_count_delta"] == 2
        )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
