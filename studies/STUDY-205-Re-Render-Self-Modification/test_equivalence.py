# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-205: cross-condition equivalence and conformance suite.

Verifies the load-bearing claim: Conditions B (wholesale re-render, same file),
C (re-render as new-file emission), and D (hybrid in-place + re-render) each produce a
final graph TOPOLOGY structurally identical to Condition A (in-place mutation baseline),
while the on-disk serialized REPRESENTATION diverges. The materialization strategy moved;
the mechanism (topology-as-program + result-driven edge selection + persisted self-mod)
did not. Equivalence is decided by ``structural_diff`` — a TOPOLOGICAL comparator, never
a byte/file hash — which carries its own anti-tautology negative test.

Also generates ``results.json`` (run ``python test_equivalence.py``); the file is
GENERATED, never hand-authored. Re-running reproduces it byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from baseline_in_place_mutation import (
    SELF_MOD_NODE_ID,
    MaterializingSubstrate,
    canonical_snapshot,
    compute_metrics,
    entry_of,
    load_baseline,
    run_condition_a,
    select_edge,
    serialize_in_place,
    serialize_rerender,
    structural_diff,
    topologically_equal,
    traverse,
)
from rerender_full_emit import run_condition_b
from rerender_new_file import run_condition_c
from hybrid_mixed import mixes_in_place_and_rerender, run_condition_d

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.json"

STUDY_ID = "STUDY-205"
STUDY_TITLE = "Re-Render Self-Modification — Wholesale Re-Rendering vs In-Place Mutation"
STUDY_DATE = "2026-06-18"
# B1 / ADR-002: STUDY-203 landed first (merged) and is the canonical shared baseline;
# STUDY-205 reuses its graph_initial.json byte-identical and conforms to its schema.
BASELINE_AUTHORED_BY = "STUDY-203"

METRIC_KEYS = (
    "topology_determination",
    "result_dependent_routing",
    "self_modification",
    "modification_persistence",
    "functional_equivalence",
    "representation_divergence",
    "node_count_delta",
    "edge_count_delta",
)
BOOLEAN_METRICS = METRIC_KEYS[:5]
EXPECTED_PATH = ["start", "compute", "branch", "grow", "audit", "finalize"]

VENDOR_DENYLIST = (
    "postgres", "postgresql", "redis", "mysql", "mongo", "neo4j", "sqlalchemy",
    "django", "flask", "langchain", "langgraph", "autogen", "crewai", "uipath",
    "qomplx", "oracle", "dynamodb", "cassandra", "node-red", "nodered", "flowise",
    "langflow", "henshin", "groove", "progres", "ehrig",
)

# The final-graph fixture (baseline + the data-driven self-modification) used by the
# serializer/comparator lemmas — schema matches the shared STUDY-203 baseline.
_INJECTED_NODE = {"id": SELF_MOD_NODE_ID, "type": "OPERATION", "op": "record", "data": {}}
_INJECTED_EDGES = [
    {"source_id": "grow", "target_id": SELF_MOD_NODE_ID, "relation": "THEN"},
    {"source_id": SELF_MOD_NODE_ID, "target_id": "finalize", "relation": "THEN"},
]


def _decode(text: str) -> tuple[list, list]:
    g = json.loads(text)
    return g["nodes"], g["edges"]


def _final_graph() -> dict:
    b = load_baseline()
    return {"nodes": list(b["nodes"]) + [_INJECTED_NODE],
            "edges": list(b["edges"]) + _INJECTED_EDGES}


# ---------------------------------------------------------------------------
# Run-all: execute the four conditions against one shared baseline
# ---------------------------------------------------------------------------

def run_all() -> dict:
    """Run A/B/C/D over the shared baseline and return per-condition metrics plus
    materialization evidence. Condition A's final topology + bytes are THE references.
    All metric computation happens INSIDE the tempdir context (stores read live files)."""
    with tempfile.TemporaryDirectory(prefix="study_205_") as tmp:
        a = run_condition_a(tmp)
        base_snap, base_bytes = a["snapshot"], a["bytes"]
        a_m = compute_metrics(a["store"], a["record"], a["initial"], base_snap, base_bytes)

        b = run_condition_b(tmp)
        b_m = compute_metrics(b["store"], b["record"], b["initial"], base_snap, base_bytes)

        c = run_condition_c(tmp)
        c_m = compute_metrics(c["store"], c["record"], c["initial"], base_snap, base_bytes)

        d = run_condition_d(tmp)
        d_m = compute_metrics(d["store"], d["record"], d["initial"], base_snap, base_bytes)

        evidence = {
            "visited_path": a["record"]["visited"],
            "A_materialization": a["store"].materialization_log,
            "B_materialization": b["store"].materialization_log,
            "C_active_path_is_new": c["active_path_is_new"],
            "C_prior_file_intact": c["prior_file_intact"],
            "C_has_superseded_by_edge": c["has_superseded_by_edge"],
            "C_emitted_file_count": c["emitted_file_count"],
            "D_strategies_used": d["strategies_used"],
            "D_mixes_in_place_and_rerender": mixes_in_place_and_rerender(d),
        }
    return {"A": a_m, "B": b_m, "C": c_m, "D": d_m, "evidence": evidence}


@pytest.fixture(scope="module")
def results() -> dict:
    return run_all()


# ---------------------------------------------------------------------------
# Functional (TOPOLOGICAL) equivalence — the load-bearing proof (SC-1)
# ---------------------------------------------------------------------------

class TestTopologicalEquivalence:

    def test_b_topology_equals_a(self, results):
        assert results["B"]["functional_equivalence"] is True

    def test_c_topology_equals_a(self, results):
        assert results["C"]["functional_equivalence"] is True

    def test_d_topology_equals_a(self, results):
        assert results["D"]["functional_equivalence"] is True

    def test_all_three_report_topological_equivalence(self, results):
        for cond in ("B", "C", "D"):
            assert results[cond]["functional_equivalence"] is True, cond


# ---------------------------------------------------------------------------
# Representation divergence — the crux metric (SC-2): bytes differ from A while the
# topology matches. A byte-identical "re-render" would fail this — that is the point.
# ---------------------------------------------------------------------------

class TestRepresentationDivergence:

    def test_bcd_bytes_differ_from_a_while_topology_matches(self, results):
        for cond in ("B", "C", "D"):
            rep = results[cond]["representation_divergence"]
            assert rep["bytes_differ_from_A"] is True, f"{cond}: bytes did NOT diverge (no-op re-render?)"
            assert rep["topology_matches_A"] is True, f"{cond}: topology diverged"

    def test_a_is_the_reference_not_divergent(self, results):
        rep = results["A"]["representation_divergence"]
        assert rep["bytes_differ_from_A"] is False
        assert rep["topology_matches_A"] is True

    def test_serializers_diverge_in_bytes_on_the_final_graph(self):
        """The lemma the study rests on: the same FINAL graph serialized in-place vs
        re-rendered produces DIFFERENT bytes but DECODES to the same topology."""
        graph = _final_graph()
        in_place = serialize_in_place(graph)
        rerendered = serialize_rerender(graph)
        assert in_place != rerendered
        assert topologically_equal(
            canonical_snapshot(*_decode(in_place)),
            canonical_snapshot(*_decode(rerendered)),
        )


# ---------------------------------------------------------------------------
# The comparator is TOPOLOGICAL, not byte — anti-tautology negative test (SC-3, CRITICAL).
# ---------------------------------------------------------------------------

class TestComparatorIsStructural:

    def test_byte_divergent_but_topologically_equal_compares_equal(self):
        baseline = load_baseline()
        graph = {"nodes": baseline["nodes"], "edges": baseline["edges"]}
        in_place = serialize_in_place(graph)
        rerendered = serialize_rerender(graph)
        assert in_place != rerendered
        snap_a = canonical_snapshot(*_decode(in_place))
        snap_b = canonical_snapshot(*_decode(rerendered))
        assert topologically_equal(snap_a, snap_b)
        assert not any(structural_diff(snap_a, snap_b).values())

    def test_topologically_different_compares_unequal(self):
        baseline = load_baseline()
        snap_a = canonical_snapshot(baseline["nodes"], baseline["edges"])
        more_nodes = list(baseline["nodes"]) + [{"id": "extra", "type": "OPERATION", "op": "noop"}]
        snap_b = canonical_snapshot(more_nodes, baseline["edges"])
        assert not topologically_equal(snap_a, snap_b)
        assert "extra" in structural_diff(snap_a, snap_b)["nodes_only_in_b"]

    def test_edge_difference_compares_unequal(self):
        baseline = load_baseline()
        snap_a = canonical_snapshot(baseline["nodes"], baseline["edges"])
        more_edges = list(baseline["edges"]) + [
            {"source_id": "start", "target_id": "finalize", "relation": "THEN"}
        ]
        snap_b = canonical_snapshot(baseline["nodes"], more_edges)
        assert not topologically_equal(snap_a, snap_b)
        assert structural_diff(snap_a, snap_b)["edges_only_in_b"]

    def test_comparator_self_equality(self):
        baseline = load_baseline()
        snap = canonical_snapshot(baseline["nodes"], baseline["edges"])
        assert topologically_equal(snap, snap)


# ---------------------------------------------------------------------------
# Metrics — all 7 present, typed, and deltas nonzero per condition (SC-5)
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_seven_metrics_present_per_condition(self, results):
        for cond in ("A", "B", "C", "D"):
            for metric in METRIC_KEYS:
                assert metric in results[cond], f"{cond} missing {metric}"

    def test_metric_types(self, results):
        for cond in ("A", "B", "C", "D"):
            block = results[cond]
            for boolean in BOOLEAN_METRICS:
                assert isinstance(block[boolean], bool), f"{cond}.{boolean}"
            assert type(block["node_count_delta"]) is int, cond
            assert type(block["edge_count_delta"]) is int, cond
            rep = block["representation_divergence"]
            assert isinstance(rep, dict) and set(rep) == {"bytes_differ_from_A", "topology_matches_A"}, cond

    def test_count_deltas_present_and_nonzero(self, results):
        for cond in ("A", "B", "C", "D"):
            block = results[cond]
            assert block["node_count_delta"] != 0 or block["edge_count_delta"] != 0, f"{cond} all-zero"
            assert block["node_count_delta"] == 1, cond
            assert block["edge_count_delta"] == 2, cond


# ---------------------------------------------------------------------------
# Substrate governs execution — properties hold DURING execution, not just at end
# ---------------------------------------------------------------------------

class TestSubstrateGoverns:

    def test_topology_determines_sequence(self, results):
        assert results["evidence"]["visited_path"] == EXPECTED_PATH
        for cond in ("A", "B", "C", "D"):
            assert results[cond]["topology_determination"] is True, cond

    def test_result_determines_edge(self):
        """An execution result — not a static dispatch table — selects the edge."""
        edges = [
            {"source_id": "branch", "target_id": "grow", "relation": "BRANCH",
             "condition": {"result": "high"}},
            {"source_id": "branch", "target_id": "finalize", "relation": "BRANCH",
             "condition": {"result": "low"}},
        ]
        assert select_edge(edges, "high")["target_id"] == "grow"
        assert select_edge(edges, "low")["target_id"] == "finalize"

    def test_self_modification_occurs_during_execution(self, tmp_path):
        baseline = load_baseline()
        store = MaterializingSubstrate(tmp_path, baseline, "in_place", name="probe")
        assert store.has_node(SELF_MOD_NODE_ID) is False
        record = traverse(store, entry_of(baseline))
        assert store.has_node(SELF_MOD_NODE_ID) is True
        assert SELF_MOD_NODE_ID in record["visited"]
        assert record["visited"].index("grow") < record["visited"].index(SELF_MOD_NODE_ID)

    def test_modification_persists_and_affects_subsequent_traversal(self, results):
        for cond in ("A", "B", "C", "D"):
            assert results[cond]["self_modification"] is True, cond
            assert results[cond]["modification_persistence"] is True, cond


# ---------------------------------------------------------------------------
# Condition C — pure re-render-as-new-file (ADR-004)
# ---------------------------------------------------------------------------

class TestNewFileEmission:

    def test_c_emits_new_file_and_switches_active_substrate(self, results):
        assert results["evidence"]["C_active_path_is_new"] is True
        assert results["evidence"]["C_emitted_file_count"] > 1

    def test_c_leaves_prior_file_intact(self, results):
        assert results["evidence"]["C_prior_file_intact"] is True

    def test_c_is_pure_rerender_no_superseded_by_edge(self, results):
        assert results["evidence"]["C_has_superseded_by_edge"] is False


# ---------------------------------------------------------------------------
# Condition D — hybrid is compositional and uses BOTH strategies (SC-4)
# ---------------------------------------------------------------------------

class TestHybrid:

    def test_d_uses_both_materialization_strategies(self, results):
        assert results["evidence"]["D_mixes_in_place_and_rerender"] is True
        assert set(results["evidence"]["D_strategies_used"]) >= {"in_place", "rerender"}

    def test_d_topology_equals_a(self, results):
        assert results["D"]["functional_equivalence"] is True


# ---------------------------------------------------------------------------
# Cross-study baseline (CG-2) — conforms to STUDY-203's merged canonical baseline
# ---------------------------------------------------------------------------

class TestCrossStudy:

    def _sibling_baseline(self) -> Path | None:
        # STUDY-203 is the merged canonical (landed first); prefer it. STUDY-204 fallback.
        for pattern in ("STUDY-203*/graph_initial.json", "STUDY-204*/graph_initial.json"):
            for candidate in sorted(HERE.parent.glob(pattern)):
                if candidate.resolve() != (HERE / "graph_initial.json").resolve():
                    return candidate
        return None

    def test_condition_a_equals_sibling_baseline(self):
        other = self._sibling_baseline()
        if other is None:
            pytest.skip(
                "B1/ADR-002: no sibling STUDY-203/204 baseline present in this checkout. "
                "STUDY-205 reuses STUDY-203's merged canonical graph_initial.json "
                "byte-identical (baseline_authored_by=STUDY-203)."
            )
        ours = load_baseline()
        theirs = load_baseline(other)
        assert topologically_equal(
            canonical_snapshot(ours["nodes"], ours["edges"]),
            canonical_snapshot(theirs["nodes"], theirs["edges"]),
        )

    def test_baseline_authoring_is_recorded(self):
        assert BASELINE_AUTHORED_BY in ("STUDY-203", "STUDY-204", "STUDY-205")
        if RESULTS_PATH.exists():
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            assert data.get("baseline_authored_by") in ("STUDY-203", "STUDY-204", "STUDY-205")


# ---------------------------------------------------------------------------
# No vendor names in prose (CQ-3)
# ---------------------------------------------------------------------------

def test_no_vendor_names_in_readme():
    readme = HERE / "README.md"
    assert readme.exists(), "README.md must exist"
    prose = readme.read_text(encoding="utf-8").lower()
    hits = [name for name in VENDOR_DENYLIST if name in prose]
    assert not hits, f"vendor name(s) in README prose: {hits}"


# ---------------------------------------------------------------------------
# results.json generation
# ---------------------------------------------------------------------------

def build_results(results: dict, checks_total: int, checks_passed: int) -> dict:
    conditions = {k: {m: results[k][m] for m in METRIC_KEYS} for k in ("A", "B", "C", "D")}
    equivalent = all(conditions[c]["functional_equivalence"] for c in ("B", "C", "D"))
    divergent = all(conditions[c]["representation_divergence"]["bytes_differ_from_A"] for c in ("B", "C", "D"))
    status = "PASS" if (equivalent and divergent and checks_passed == checks_total) else "FAIL"
    return {
        "study_id": STUDY_ID,
        "title": STUDY_TITLE,
        "date": STUDY_DATE,
        "status": status,
        "tests_run": checks_total,
        "tests_passed": checks_passed,
        "tests_failed": checks_total - checks_passed,
        "baseline_authored_by": BASELINE_AUTHORED_BY,
        "conditions": conditions,
        "materialization_evidence": results["evidence"],
        "key_findings": [
            "A graph substrate self-modified by wholesale re-render to the same file (B), "
            "by re-render as a new-file emission (C), or by a hybrid of in-place edit and "
            "re-render (D) produces a final graph TOPOLOGY structurally identical to the "
            "in-place mutation baseline (A).",
            "Across B, C, and D the on-disk serialized REPRESENTATION diverges from A "
            "(the bytes differ) while the topology matches — proving the re-render is a "
            "real re-emit, not a no-op: representation differs, topology does not.",
            "Equivalence is decided by a topological structural diff, never a byte/file "
            "hash; the comparator carries an anti-tautology negative test.",
            "Result-driven edge selection and in-traversal self-modification (one node + "
            "two edges, live) drive the same topology evolution in every condition; the "
            "modified, persisted topology governs the subsequent traversal.",
            "HONEST SCOPE: this proves materialization-strategy-equivalence, NOT that "
            "re-render preserves structural-liveness. Wholesale re-render is a generation "
            "step and surrenders the L5/no-compile distinction; the study rests its weight "
            "on topology-as-program + result-driven edge selection + persistence only.",
            "Shared baseline reused byte-identical from STUDY-203 (the merged canonical), "
            "so materialization-independence (205) and agent-decomposition (203) are "
            "proven against the same baseline.",
        ],
    }


def validation_checklist(results: dict) -> list[tuple[str, bool]]:
    ev = results["evidence"]
    checks: list[tuple[str, bool]] = [
        ("Condition A traversed the expected path", ev["visited_path"] == EXPECTED_PATH),
        ("A materialized only in-place", set(ev["A_materialization"]) == {"in_place"}),
        ("B materialized only by re-render", set(ev["B_materialization"]) == {"rerender"}),
        ("C emitted a new file + switched active substrate", ev["C_active_path_is_new"]),
        ("C left the prior file intact", ev["C_prior_file_intact"]),
        ("C wrote NO superseded_by edge (pure re-render)", ev["C_has_superseded_by_edge"] is False),
        ("D mixed in-place AND re-render in one traversal", ev["D_mixes_in_place_and_rerender"]),
    ]
    for cond in ("B", "C", "D"):
        block = results[cond]
        rep = block["representation_divergence"]
        checks.append((f"{cond}: topology == A", block["functional_equivalence"]))
        checks.append((f"{cond}: bytes diverge from A while topology matches",
                       rep["bytes_differ_from_A"] and rep["topology_matches_A"]))
    for cond in ("A", "B", "C", "D"):
        checks.append((f"{cond}: node delta == 1, edge delta == 2",
                       results[cond]["node_count_delta"] == 1 and results[cond]["edge_count_delta"] == 2))
        checks.append((f"{cond}: result-dependent routing + persisted self-mod",
                       results[cond]["result_dependent_routing"] and results[cond]["modification_persistence"]))
    return checks


def main() -> int:
    results = run_all()
    checks = validation_checklist(results)
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)

    print("=" * 64)
    print(f"{STUDY_ID}: {STUDY_TITLE}")
    print("=" * 64)
    print("\nMetrics by condition "
          "(A=in-place, B=re-render same-file, C=re-render new-file, D=hybrid):")
    for cond in ("A", "B", "C", "D"):
        block = results[cond]
        rep = block["representation_divergence"]
        print(f"  {cond}: topo_equiv={block['functional_equivalence']!s:<5} "
              f"bytes_differ={rep['bytes_differ_from_A']!s:<5} "
              f"node_delta={block['node_count_delta']} edge_delta={block['edge_count_delta']}")

    print("\nVALIDATION")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok

    payload = build_results(results, total, passed)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH.name}: status={payload['status']} ({passed}/{total} checks)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
