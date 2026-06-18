# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: cross-condition equivalence and conformance suite.

Verifies the load-bearing claim: Conditions B (relational store), C (mediated
access), and D (both) are FUNCTIONALLY EQUIVALENT to Condition A (serialized-file
baseline) — the embodiment (storage / access path) moved, the mechanism did not.

Also generates ``results.json`` (run ``python test_equivalence.py``); the file is
GENERATED, never hand-authored. Re-running reproduces it byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from baseline_file import (
    DictStore,
    FileStore,
    INJECTED_NODE_ID,
    canonical_snapshot,
    compute_metrics,
    entry_id,
    load_baseline,
    run_condition_a,
    select_edge,
    traverse,
    GRAPH_INITIAL_PATH,
)
from persistent_store import SqliteStore, run_condition_b
from mediated_access import GraphMediator, agent_has_storage_handle, run_condition_c, MEDIATOR_INTERFACE
from combined_store_mediated import run_condition_d, composes_b_and_c

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.json"

STUDY_ID = "STUDY-204"
STUDY_TITLE = "Storage-Independent Graph Substrate — Database and Mediated Access"
STUDY_DATE = "2026-06-18"
# ADR-003 / reconciliation (2026-06-18): STUDY-203 landed first and is the authoritative
# author of the shared graph_initial.json; STUDY-204 adopts it byte-identically.
BASELINE_AUTHORED_BY = "STUDY-203"
THE_SEVEN_METRICS = (
    "topology_determination",
    "result_dependent_routing",
    "self_modification",
    "modification_persistence",
    "functional_equivalence",
    "node_count_delta",
    "edge_count_delta",
)
EXPECTED_PATH = ["start", "compute", "branch", "grow", "audit", "finalize"]

# Vendor/product/framework denylist — prose must name none of these (RISK-2).
VENDOR_DENYLIST = (
    "postgres", "postgresql", "redis", "mysql", "mongo", "neo4j", "sqlalchemy",
    "django", "flask", "langchain", "langgraph", "autogen", "qomplx", "oracle",
    "dynamodb", "cassandra",
)


# ---------------------------------------------------------------------------
# Run-all: execute the four conditions against one shared baseline
# ---------------------------------------------------------------------------

def run_all() -> dict:
    """Run A/B/C/D over the shared baseline and return per-condition metrics plus
    access-pattern evidence. Condition A's final state is THE baseline."""
    with tempfile.TemporaryDirectory(prefix="study_204_") as tmp:
        a = run_condition_a(tmp)
        baseline_snapshot = a["snapshot"]
        a_metrics = compute_metrics(a["store"], a["record"], a["initial"], baseline_snapshot)

        b = run_condition_b()
        b_metrics = compute_metrics(b["store"], b["record"], b["initial"], baseline_snapshot)

        c = run_condition_c()
        c_metrics = compute_metrics(c["store"], c["record"], c["initial"], baseline_snapshot)

        d = run_condition_d()
        d_metrics = compute_metrics(d["store"], d["record"], d["initial"], baseline_snapshot)

        evidence = {
            "visited_path": a["record"]["visited"],
            "B_sql_query_count": b["store"].query_count,
            "B_file_parses": b["store"].file_parses,
            "C_agent_has_storage_handle": agent_has_storage_handle(c["store"]),
            "D_agent_has_storage_handle": agent_has_storage_handle(d["store"]),
            "D_composes_b_and_c": composes_b_and_c(d),
            "D_backing_sql_query_count": d["backing"].query_count,
        }
    return {"A": a_metrics, "B": b_metrics, "C": c_metrics, "D": d_metrics, "evidence": evidence}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def results() -> dict:
    return run_all()


@pytest.fixture
def baseline_snapshot(tmp_path) -> dict:
    return run_condition_a(tmp_path)["snapshot"]


# ---------------------------------------------------------------------------
# Functional equivalence — the load-bearing proof (SC-1)
# ---------------------------------------------------------------------------

class TestEquivalence:

    def test_b_equals_baseline(self, baseline_snapshot):
        assert run_condition_b()["snapshot"] == baseline_snapshot

    def test_c_equals_baseline(self, baseline_snapshot):
        assert run_condition_c()["snapshot"] == baseline_snapshot

    def test_d_equals_baseline(self, baseline_snapshot):
        assert run_condition_d()["snapshot"] == baseline_snapshot

    def test_all_three_report_functional_equivalence(self, results):
        for cond in ("B", "C", "D"):
            assert results[cond]["functional_equivalence"] is True, cond


# ---------------------------------------------------------------------------
# Metrics — all 7 present, typed, and deltas nonzero per condition (SC-5)
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_seven_metrics_present_per_condition(self, results):
        for cond in ("A", "B", "C", "D"):
            block = results[cond]
            for metric in THE_SEVEN_METRICS:
                assert metric in block, f"{cond} missing {metric}"

    def test_metric_types(self, results):
        for cond in ("A", "B", "C", "D"):
            block = results[cond]
            for boolean in THE_SEVEN_METRICS[:5]:
                assert isinstance(block[boolean], bool), f"{cond}.{boolean}"
            assert type(block["node_count_delta"]) is int, cond
            assert type(block["edge_count_delta"]) is int, cond

    def test_count_deltas_present_and_nonzero(self, results):
        """The shared baseline carries one self-modification (one node + two edges),
        so every condition that executes it must show a real, nonzero delta — this
        proves the deltas are computed per condition, not merely key-present."""
        for cond in ("A", "B", "C", "D"):
            block = results[cond]
            assert block["node_count_delta"] != 0, f"{cond} node delta is zero"
            assert block["edge_count_delta"] != 0, f"{cond} edge delta is zero"
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
            # The routing-metric VALUE is load-bearing, not just the mechanism: the
            # result-driven conditional edge at 'branch' must actually be exercised
            # (a run that never routed via a condition would leave this False).
            assert results[cond]["result_dependent_routing"] is True, cond

    def test_result_determines_edge(self):
        """An execution result — not a static dispatch table — selects the edge."""
        edges = [
            {"source_id": "branch", "target_id": "grow", "relation": "BRANCH",
             "condition": {"result": "high"}},
            {"source_id": "branch", "target_id": "finalize", "relation": "BRANCH",
             "condition": {"result": "low"}},
        ]
        assert select_edge(edges, "high")["target_id"] == "grow"      # result "high"
        assert select_edge(edges, "low")["target_id"] == "finalize"   # result "low" -> different edge

    def test_self_modification_occurs_during_execution(self, tmp_path):
        """The injected node does not exist at start; it is created mid-traversal and
        then traversed (it affected subsequent traversal — structural liveness)."""
        baseline = load_baseline()
        store = DictStore(baseline)
        assert store.has_node(INJECTED_NODE_ID) is False  # absent in the baseline
        record = traverse(store, entry_id(baseline))
        assert store.has_node(INJECTED_NODE_ID) is True            # created live
        assert INJECTED_NODE_ID in record["visited"]               # and traversed
        # 'grow' is reached before 'injected' exists — the agent built its own path.
        assert record["visited"].index("grow") < record["visited"].index(INJECTED_NODE_ID)

    def test_modification_persists_and_affects_subsequent_traversal(self, results):
        for cond in ("A", "B", "C", "D"):
            assert results[cond]["self_modification"] is True, cond
            assert results[cond]["modification_persistence"] is True, cond


# ---------------------------------------------------------------------------
# Access-pattern distinctions (SC-3 / B2 / RISK-1)
# ---------------------------------------------------------------------------

class TestAccessPattern:

    def test_b_reads_via_query_not_file_parse(self, results):
        ev = results["evidence"]
        assert ev["B_sql_query_count"] > 0       # the agent issued SQL
        assert ev["B_file_parses"] == 0          # and never parsed a graph file

    def test_b_store_is_row_based(self):
        baseline = load_baseline()
        store = SqliteStore(baseline)
        # The substrate lives in rows: node and edge tables exist and are populated.
        tables = {r[0] for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"nodes", "edges"} <= tables
        assert store.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == len(baseline["nodes"])

    def test_c_agent_has_no_storage_handle(self, results):
        assert results["evidence"]["C_agent_has_storage_handle"] is False

    def test_c_mediator_exposes_only_the_interface(self):
        baseline = load_baseline()
        mediator = GraphMediator(DictStore(baseline))
        # The backing store is name-mangled private; no public storage handle exists.
        assert not hasattr(mediator, "conn")
        assert not hasattr(mediator, "path")
        assert not hasattr(mediator, "backing")
        for method in MEDIATOR_INTERFACE:
            assert callable(getattr(mediator, method)), method


# ---------------------------------------------------------------------------
# Condition D is compositional (SC-4)
# ---------------------------------------------------------------------------

class TestCombined:

    def test_d_composes_b_and_c(self, results):
        assert results["evidence"]["D_composes_b_and_c"] is True
        assert results["evidence"]["D_backing_sql_query_count"] > 0
        assert results["evidence"]["D_agent_has_storage_handle"] is False

    def test_d_uses_both_modules(self):
        bundle = run_condition_d()
        assert isinstance(bundle["store"], GraphMediator)   # from mediated_access (C)
        assert isinstance(bundle["backing"], SqliteStore)   # from persistent_store (B)


# ---------------------------------------------------------------------------
# Cross-study baseline (SC-7 / CG-2) — B1-gated skip + non-skippable authoring record
# ---------------------------------------------------------------------------

class TestCrossStudy:

    def _study_203_baseline(self) -> Path | None:
        for candidate in sorted(HERE.parent.glob("STUDY-203*/graph_initial.json")):
            return candidate
        return None

    def test_condition_a_equals_study_203_baseline(self):
        other = self._study_203_baseline()
        if other is None:
            pytest.skip(
                "STUDY-203 baseline directory not present in this checkout. STUDY-203 is "
                "the authoritative author of the shared graph_initial.json; STUDY-204 "
                "adopts it byte-identically."
            )
        ours = load_baseline()
        theirs = load_baseline(other)
        assert canonical_snapshot(ours["nodes"], ours["edges"]) == \
            canonical_snapshot(theirs["nodes"], theirs["edges"])

    def test_baseline_authoring_is_recorded(self):
        """NON-skippable (CG-2): which study authored the shared baseline must be
        recorded so ADR-003's combined-evidence claim is auditable."""
        assert BASELINE_AUTHORED_BY in ("STUDY-204", "STUDY-203")
        if RESULTS_PATH.exists():
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            assert data.get("baseline_authored_by") in ("STUDY-204", "STUDY-203")


# ---------------------------------------------------------------------------
# No vendor names in prose (CQ-3 / RISK-2)
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
    conditions = {k: {m: results[k][m] for m in THE_SEVEN_METRICS} for k in ("A", "B", "C", "D")}
    equivalent = all(conditions[c]["functional_equivalence"] for c in ("B", "C", "D"))
    status = "PASS" if (equivalent and checks_passed == checks_total) else "FAIL"
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
        "access_evidence": results["evidence"],
        "key_findings": [
            "A graph substrate stored in a relational store (B), accessed through a "
            "mediation layer (C), or both (D) produces a final state structurally "
            "identical to the serialized-file baseline (A).",
            "The agent reads the relational store via SQL queries, not by parsing a "
            "serialized file; the mediated agent holds no storage handle at all.",
            "Topology-as-program, result-driven edge selection, and in-traversal "
            "self-modification (no compile/deploy boundary) are preserved unchanged "
            "across every storage/access embodiment.",
            "The self-modification adds one node and two edges live during execution "
            "and the new topology is traversed on the next step (nonzero deltas in "
            "every condition).",
            "Storage format and access path are deployment details; the substrate "
            "mechanism is storage-independent.",
        ],
    }


def validation_checklist(results: dict) -> list[tuple[str, bool]]:
    ev = results["evidence"]
    checks: list[tuple[str, bool]] = [
        ("Condition A traversed the expected path", ev["visited_path"] == EXPECTED_PATH),
        ("B final-state == A baseline", results["B"]["functional_equivalence"]),
        ("C final-state == A baseline", results["C"]["functional_equivalence"]),
        ("D final-state == A baseline", results["D"]["functional_equivalence"]),
        ("B reads via SQL (queries > 0)", ev["B_sql_query_count"] > 0),
        ("B never parses a graph file (parses == 0)", ev["B_file_parses"] == 0),
        ("C agent holds no storage handle", ev["C_agent_has_storage_handle"] is False),
        ("D composes B (store) and C (mediation)", ev["D_composes_b_and_c"]),
        ("D agent holds no storage handle", ev["D_agent_has_storage_handle"] is False),
    ]
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
    print("\nMetrics by condition (A=file, B=relational, C=mediated, D=both):")
    for cond in ("A", "B", "C", "D"):
        block = results[cond]
        print(f"  {cond}: equiv={block['functional_equivalence']!s:<5} "
              f"node_delta={block['node_count_delta']} edge_delta={block['edge_count_delta']}")

    print("\nVALIDATION")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok

    payload = build_results(results, total, passed)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH.name}: status={payload['status']} "
          f"({passed}/{total} checks)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
