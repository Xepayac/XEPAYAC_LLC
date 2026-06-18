"""STUDY-203 equivalence / conformance harness.

Runs Conditions A (single process), B (three decomposed processes), and C
(external dispatch) from the one shared baseline graph, captures the seven
study metrics per condition, and asserts the acceptance gate: the decomposed
and externally-dispatched embodiments produce a final graph state
*functionally equivalent* to the single-process baseline (B == A and C == A),
while every mechanism-axis property survives the embodiment shift.

Also generates results.json (run `python test_equivalence.py`); the output is
deterministic so it can be regenerated and diffed in CI.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baseline_single_process as cond_a
import decomposed_agents as cond_b
import external_dispatch as cond_c
from baseline_single_process import (
    init_working_file,
    load_graph,
    canonical_graph,
    select_next_edge,
)

HERE = Path(__file__).resolve().parent
INITIAL = HERE / "graph_initial.json"

EXPECTED_VISITED = ["start", "compute", "branch", "grow", "audit", "finalize"]
SEVEN_METRICS = [
    "topology_determination",
    "result_dependent_routing",
    "self_modification",
    "modification_persistence",
    "functional_equivalence",
    "node_count_delta",
    "edge_count_delta",
]


# ---------------------------------------------------------------------------
# Metric reduction
# ---------------------------------------------------------------------------

def seven_metrics(raw: dict, baseline_hash: str) -> dict:
    """Reduce a condition's raw result to the seven study metrics."""
    fg = raw["final_graph"]  # canonical {nodes, edges}
    visited = raw["visited"]
    edgeset = {(e["source_id"], e["target_id"]) for e in fg["edges"]}
    topo = len(visited) >= 2 and all(
        (visited[i], visited[i + 1]) in edgeset for i in range(len(visited) - 1)
    )

    bd = raw["branch_decision"]
    routing = False
    if bd is not None:
        # The selected edge must be exactly the one the execution result picks
        # against the on-disk edge conditions -- routing is the substrate's.
        recomputed = select_next_edge(
            {"nodes": fg["nodes"], "edges": fg["edges"]}, bd["node"], bd["result"]
        )
        routing = bd["selected_target"] is not None and bd["selected_target"] == recomputed

    return {
        "topology_determination": bool(topo),
        "result_dependent_routing": bool(routing),
        "self_modification": bool(raw["self_modified"]),
        "modification_persistence": bool(raw["modification_persisted"]),
        "functional_equivalence": raw["final_graph_hash"] == baseline_hash,
        "node_count_delta": raw["node_count_delta"],
        "edge_count_delta": raw["edge_count_delta"],
    }


# ---------------------------------------------------------------------------
# Run helpers
# ---------------------------------------------------------------------------

def run_all() -> dict:
    """Run A, B, C from the shared baseline; return raw results keyed A/B/C."""
    return {"A": cond_a.run_in_tempdir(),
            "B": cond_b.run_in_tempdir(),
            "C": cond_c.run_in_tempdir()}


@pytest.fixture(scope="module")
def raws():
    return run_all()


@pytest.fixture(scope="module")
def baseline_hash(raws):
    return raws["A"]["final_graph_hash"]


# ---------------------------------------------------------------------------
# Target 1.1 -- per-condition substrate governance (topology/routing/self-mod/persist)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cond", ["A", "B", "C"])
def test_condition_substrate_governance(cond, raws, baseline_hash):
    m = seven_metrics(raws[cond], baseline_hash)
    assert raws[cond]["visited"] == EXPECTED_VISITED
    assert m["topology_determination"] is True
    assert m["result_dependent_routing"] is True
    assert m["self_modification"] is True
    assert m["modification_persistence"] is True


# ---------------------------------------------------------------------------
# Target 1.2 / SC-2 -- all seven metrics captured for every condition
# ---------------------------------------------------------------------------

def test_seven_metrics_captured_each_condition(raws, baseline_hash):
    for cond in ("A", "B", "C"):
        m = seven_metrics(raws[cond], baseline_hash)
        missing = [k for k in SEVEN_METRICS if k not in m]
        assert not missing, f"{cond} missing metrics: {missing}"


# ---------------------------------------------------------------------------
# Target 1.3 / SC-1 -- functional-equivalence acceptance gate (B==A, C==A)
# ---------------------------------------------------------------------------

def test_equivalence_B_equals_A(raws):
    assert raws["B"]["final_graph"] == raws["A"]["final_graph"]
    assert raws["B"]["final_graph_hash"] == raws["A"]["final_graph_hash"]


def test_equivalence_C_equals_A(raws):
    assert raws["C"]["final_graph"] == raws["A"]["final_graph"]
    assert raws["C"]["final_graph_hash"] == raws["A"]["final_graph_hash"]


# ---------------------------------------------------------------------------
# SC-3 -- result-dependent routing is the substrate's (every condition)
# ---------------------------------------------------------------------------

def test_result_dependent_routing_each_condition(raws, baseline_hash):
    for cond in ("A", "B", "C"):
        bd = raws[cond]["branch_decision"]
        assert bd is not None, f"{cond}: no branch decision recorded"
        assert bd["result"] == "high"        # acc == 5 >= threshold 5
        assert bd["selected_target"] == "grow"
        m = seven_metrics(raws[cond], baseline_hash)
        assert m["result_dependent_routing"] is True


# ---------------------------------------------------------------------------
# SC-4 / Target 1.5 -- the dispatcher does NOT route from its own logic
# ---------------------------------------------------------------------------

def test_dispatcher_does_not_route_from_own_logic(raws):
    c = raws["C"]
    meta = c["metadata"]
    assert meta["dispatcher_evaluated_edges"] is False
    assert meta["routing_source"] == "execution_result_vs_edge_condition"
    # The dispatcher-followed route equals the substrate's result-vs-condition
    # selection -- so routing came from the result, not the orchestrator.
    fg = c["final_graph"]
    bd = c["branch_decision"]
    recomputed = select_next_edge(
        {"nodes": fg["nodes"], "edges": fg["edges"]}, bd["node"], bd["result"]
    )
    assert bd["selected_target"] == recomputed == "grow"


# ---------------------------------------------------------------------------
# SC-5 / Target 1.4 -- multi-writer consistency under decomposition
# ---------------------------------------------------------------------------

def test_multi_writer_consistency_repeated_runs_deterministic(baseline_hash):
    """Run Condition B repeatedly; every run must yield the identical final
    state (and equal the baseline). Bit-for-bit determinism across runs is the
    empirical proof that the three writers' access is serialized through the
    sole modifier rather than racing."""
    hashes = []
    for _ in range(5):
        res = cond_b.run_in_tempdir()
        hashes.append(res["final_graph_hash"])
        assert res["metadata"]["sole_modifier"] is True
        assert res["metadata"]["distinct_writer_processes"] <= 1
        assert res["metadata"]["processes"] == 3
    assert len(set(hashes)) == 1, f"non-deterministic final states: {set(hashes)}"
    assert hashes[0] == baseline_hash


# ---------------------------------------------------------------------------
# SC-6 / Target 1.9 / TE-5 -- the persisted on-disk file is the shared medium
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", [cond_a, cond_b, cond_c], ids=["A", "B", "C"])
def test_persisted_file_is_the_shared_medium(module):
    """Each condition reads/writes the same on-disk serialized file; the file
    (not an in-memory object) carries the substrate and its modification."""
    with tempfile.TemporaryDirectory(prefix="study_203_persist_") as d:
        working = Path(d) / "graph.json"
        init_working_file(INITIAL, working)
        before = working.read_text()

        res = module.run(working)

        assert working.exists()                       # the file is the medium
        after = working.read_text()
        assert after != before                        # it was modified on disk
        on_disk = load_graph(working)
        # The persisted file carries the self-modification (added node + edges).
        node_ids = {n["id"] for n in on_disk["nodes"]}
        assert "audit" in node_ids
        edgeset = {(e["source_id"], e["target_id"]) for e in on_disk["edges"]}
        assert ("grow", "audit") in edgeset
        assert ("audit", "finalize") in edgeset
        # The file IS the final state the condition reported.
        assert canonical_graph(on_disk) == res["final_graph"]


# ---------------------------------------------------------------------------
# Self-modification persisted (per condition)
# ---------------------------------------------------------------------------

def test_self_modification_persisted_each_condition(raws):
    for cond in ("A", "B", "C"):
        r = raws[cond]
        assert r["self_modified"] is True
        assert r["modification_persisted"] is True
        assert r["node_count_delta"] == 1     # +audit
        assert r["edge_count_delta"] == 2     # +grow->audit, +audit->finalize


# ---------------------------------------------------------------------------
# TE-3 / BC-2 -- the baseline is reusable by STUDY-204 (generic loader)
# ---------------------------------------------------------------------------

def test_baseline_reusable_by_study_204():
    """graph_initial.json must parse with a generic graph loader -- no
    STUDY-203-only key may be required to read it -- so STUDY-204 can reuse
    the same fixture."""
    g = json.loads(INITIAL.read_text())          # generic JSON load
    assert "nodes" in g and "edges" in g
    assert g["nodes"] and g["edges"]
    # Generic node/edge contract only (id/type ; source_id/target_id/relation).
    for n in g["nodes"]:
        assert "id" in n and "type" in n
    for e in g["edges"]:
        assert "source_id" in e and "target_id" in e and "relation" in e
    # A generic loader that knows nothing of 'op'/'condition' can still build
    # the topology adjacency.
    adjacency = {}
    for e in g["edges"]:
        adjacency.setdefault(e["source_id"], []).append(e["target_id"])
    assert adjacency["start"] == ["compute"]
    assert g.get("entry") == "start"


# ---------------------------------------------------------------------------
# results.json generation (deterministic) -- run as a script
# ---------------------------------------------------------------------------

def build_results() -> dict:
    raws = run_all()
    baseline_hash = raws["A"]["final_graph_hash"]
    conditions = {}
    for cond in ("A", "B", "C"):
        m = seven_metrics(raws[cond], baseline_hash)
        conditions[cond] = {
            "embodiment": raws[cond]["embodiment"],
            **m,
            "visited": raws[cond]["visited"],
            "final_graph_hash": raws[cond]["final_graph_hash"],
        }
    b_eq_a = raws["B"]["final_graph_hash"] == baseline_hash
    c_eq_a = raws["C"]["final_graph_hash"] == baseline_hash
    tests_total = len([n for n in globals() if n.startswith("test_")])
    status = "PASS" if (b_eq_a and c_eq_a) else "FAIL"
    return {
        "study_id": "STUDY-203",
        "title": "Decomposed Agent Systems - Multi-Process Graph Substrate Execution",
        "date": "2026-06-18",
        "status": status,
        "patent": "19/575,491",
        "broadening": "CIP Broadening #2 (multi-process / decomposed agents)",
        "tests": {"functions": tests_total},
        "acceptance": {
            "baseline_condition": "A",
            "baseline_graph_hash": baseline_hash,
            "B_equals_A": b_eq_a,
            "C_equals_A": c_eq_a,
        },
        "conditions": conditions,
        "key_findings": [
            "A graph substrate governs traversal, result-dependent routing, and "
            "in-execution self-modification identically whether one process, three "
            "decomposed processes, or an externally-dispatched agent performs the work.",
            "Conditions B and C produce a final graph state functionally equivalent to "
            "the single-process baseline A (identical canonical graph and hash).",
            "In every condition the on-disk serialized graph file is the shared executed "
            "medium; the IPC/dispatch channels carry coordination messages only, never the "
            "substrate as an in-memory object (limitation L1/L3 survive the decomposition).",
            "Condition B routes every write through a single sole-modifier process with an "
            "atomic replace; repeated runs are bit-for-bit deterministic, demonstrating the "
            "multi-writer-consistency discipline (not merely that B happened to equal A).",
            "In Condition C the external dispatcher schedules WHO/WHEN but never evaluates an "
            "edge condition; the execution result against the substrate's edge conditions "
            "selects the next node.",
        ],
    }


def write_results(path: Path) -> dict:
    results = build_results()
    with Path(path).open("w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")
    return results


if __name__ == "__main__":
    results = write_results(HERE / "results.json")
    print("=" * 64)
    print("STUDY-203: Decomposed Agent Systems - equivalence harness")
    print("=" * 64)
    print(f"  status: {results['status']}")
    print(f"  baseline hash: {results['acceptance']['baseline_graph_hash'][:16]}...")
    print(f"  B == A: {results['acceptance']['B_equals_A']}   "
          f"C == A: {results['acceptance']['C_equals_A']}")
    for cond in ("A", "B", "C"):
        c = results["conditions"][cond]
        print(f"  [{cond}] {c['embodiment']:<18} "
              f"eq={c['functional_equivalence']} "
              f"route={c['result_dependent_routing']} "
              f"selfmod={c['self_modification']} "
              f"persist={c['modification_persistence']} "
              f"dN={c['node_count_delta']:+d} dE={c['edge_count_delta']:+d}")
    print("=" * 64)
    sys.exit(0 if results["status"] == "PASS" else 1)
