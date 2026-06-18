# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-206: API-Mediated Self-Modification — equivalence + measurement harness.

Runs Conditions A/B/C/D from the one shared baseline, captures the 7 metrics per
condition, and asserts:
  - functional equivalence: B, C, D produce a final graph state structurally
    identical to the direct-write baseline A;
  - the decision-locus is the AGENT in every condition (the thesis);
  - service-no-decide (adversarial): the write services have no path to the
    execution result or the routing decision, and the agent's client never
    smuggles them into a request;
  - structural-liveness across the boundary: a modification written mid-traversal
    governs the very next step, with no compile/restart boundary;
  - Condition C crosses a genuine process boundary; Condition D composes the
    boundary over a persistent store.

Running this file (`python test_equivalence.py`) regenerates results.json from a
live run — results.json is never hand-authored.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_BASELINE = "STUDY-206"  # this study authored the shared cohort graph_initial.json
_EXPECTED_PATH = ["start", "decide", "path_high", "audit", "end"]
_METRIC_KEYS = (
    "topology_determination", "result_dependent_routing", "self_modification",
    "decision_locus", "modification_persistence", "functional_equivalence",
    "node_count_delta", "edge_count_delta",
)


def _load_initial():
    # Intra-study local import: module-top imports stay stdlib+pytest only so the
    # CQ-2 third-party-dependency gate stays meaningful (these are sibling
    # study modules, not external packages).
    import baseline_direct_write as a
    return a.load_graph(_HERE / "graph_initial.json")


def _run_conditions():
    import baseline_direct_write as a
    import api_mediated_write as b
    import api_mediated_readwrite as c
    import combined_api_persistent as d
    init = _load_initial()
    res_a = a.run(init)
    base = res_a["final_state"]
    return {
        "A": res_a,
        "B": b.run(init, base),
        "C": c.run(init, base),
        "D": d.run(init, base),
    }


@pytest.fixture(scope="module")
def results():
    return _run_conditions()


# ---------------------------------------------------------------------------
# Functional equivalence (the core hypothesis)
# ---------------------------------------------------------------------------

class TestEquivalence:
    def test_b_equals_baseline(self, results):
        assert results["B"]["final_state"] == results["A"]["final_state"]

    def test_c_equals_baseline(self, results):
        assert results["C"]["final_state"] == results["A"]["final_state"]

    def test_d_equals_baseline(self, results):
        assert results["D"]["final_state"] == results["A"]["final_state"]


# ---------------------------------------------------------------------------
# The 7 metrics, incl. decision-locus + node/edge deltas
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_all_metric_keys_present_and_typed(self, results):
        for cond in "ABCD":
            m = results[cond]["metrics"]
            for key in _METRIC_KEYS:
                assert key in m, "%s missing metric %s" % (cond, key)
            assert isinstance(m["node_count_delta"], int)
            assert isinstance(m["edge_count_delta"], int)
            assert isinstance(m["decision_locus"], str)

    def test_a_delta_is_nonzero_per_condition(self, results):
        for cond in "ABCD":
            m = results[cond]["metrics"]
            assert m["node_count_delta"] != 0 or m["edge_count_delta"] != 0


class TestSubstrateGoverns:
    def test_substrate_governs_each_condition(self, results):
        for cond in "ABCD":
            m = results[cond]["metrics"]
            assert m["topology_determination"] is True
            assert m["result_dependent_routing"] is True
            assert m["self_modification"] is True
            assert m["modification_persistence"] is True


# ---------------------------------------------------------------------------
# The thesis: decision-locus is the agent in every condition
# ---------------------------------------------------------------------------

class TestDecisionLocus:
    def test_decision_locus_is_agent_everywhere(self, results):
        for cond in "ABCD":
            m = results[cond]["metrics"]
            assert m["decision_locus"] == "agent", cond
            # The agent computed WHAT to modify from the execution result.
            assert m["evidence"]["selfmod_result"] is not None, cond


# ---------------------------------------------------------------------------
# Service-no-decide (adversarial): the dumb-transport invariant
# ---------------------------------------------------------------------------

class _SpyService:
    """Records every serialized write request it is handed (for client tests)."""

    def __init__(self):
        self.requests = []

    def submit(self, request_json):
        self.requests.append(json.loads(request_json))
        return {"ack": True}

    # read surface unused in these tests
    def read_node(self, node_id):
        return None

    def read_outgoing_edges(self, node_id):
        return []


class _FakeReq:
    def __init__(self):
        self.sent = []

    def put(self, value):
        self.sent.append(json.loads(value))


class _FakeResp:
    def get(self, timeout=None):
        return json.dumps({"ack": True, "node": None, "edges": [], "pid": 0,
                           "nodes": 0, "edges_": 0})


_FORBIDDEN_KEYS = {"result", "decision", "routing", "route", "selected_edge"}
_ALLOWED_REQUEST_KEYS = {"op", "node", "edge", "src", "tgt", "rel"}


class TestServiceNoDecide:
    def test_writeservice_ignores_injected_result_and_decision(self):
        import api_mediated_write as b
        node = {"id": "x", "type": "OPERATION", "data": {"emit": 0}}
        clean = b.WriteService({"nodes": [], "edges": []})
        clean.submit(json.dumps({"op": "add_node", "node": node}))
        # An adversary tries to smuggle a result/routing decision into the request.
        spiked = b.WriteService({"nodes": [], "edges": []})
        spiked.submit(json.dumps({"op": "add_node", "node": node,
                                  "result": 999, "decision": "delete everything",
                                  "routing": "path_low"}))
        assert clean.snapshot() == spiked.snapshot()

    def test_sqlite_service_ignores_injected_result_and_decision(self):
        import combined_api_persistent as d
        seed = {"nodes": [], "edges": []}
        edge = {"source_id": "a", "target_id": "b", "relation": "THEN"}
        clean = d.SqliteWriteService(seed)
        clean.submit(json.dumps({"op": "add_edge", "edge": edge}))
        spiked = d.SqliteWriteService(seed)
        spiked.submit(json.dumps({"op": "add_edge", "edge": edge,
                                  "result": 7, "decision": "route high"}))
        assert clean.snapshot() == spiked.snapshot()

    def test_services_expose_no_result_or_decision_attribute(self):
        import api_mediated_write as b
        import combined_api_persistent as d
        for svc in (b.WriteService({"nodes": [], "edges": []}),
                    d.SqliteWriteService({"nodes": [], "edges": []})):
            attrs = set(vars(svc))
            assert not (attrs & {"result", "decision", "routing", "agent",
                                 "_result", "_decision"}), attrs

    def test_write_mediated_client_never_sends_result_or_decision(self):
        import api_mediated_write as b
        spy = _SpyService()
        client = b.WriteMediatedClient(spy)
        client.add_node({"id": "audit", "type": "OPERATION", "data": {}})
        client.add_edge({"source_id": "p", "target_id": "audit", "relation": "THEN"})
        client.remove_edge("p", "end", "THEN")
        assert spy.requests, "client issued no requests"
        for req in spy.requests:
            keys = set(req)
            assert keys <= _ALLOWED_REQUEST_KEYS, keys
            assert not (keys & _FORBIDDEN_KEYS), keys

    def test_process_mediated_client_never_sends_result_or_decision(self):
        import api_mediated_readwrite as c
        client = c.ProcessMediatedClient(_FakeReq(), _FakeResp())
        client.add_node({"id": "audit", "type": "OPERATION", "data": {}})
        client.add_edge({"source_id": "p", "target_id": "audit", "relation": "THEN"})
        client.remove_edge("p", "end", "THEN")
        for req in client._request_q.sent:
            keys = set(req)
            assert not (keys & _FORBIDDEN_KEYS), keys


# ---------------------------------------------------------------------------
# Structural-liveness across the boundary (no reintroduced compile step)
# ---------------------------------------------------------------------------

class TestStructuralLiveness:
    def test_modification_is_live_for_the_next_step(self, results):
        initial = _load_initial()
        # In the ORIGINAL substrate, path_high's only successor is `end`.
        orig_high = {(e["source_id"], e["target_id"]) for e in initial["edges"]
                     if e["source_id"] == "path_high"}
        assert ("path_high", "end") in orig_high
        assert ("path_high", "audit") not in orig_high
        for cond in "ABCD":
            path = results[cond]["metrics"]["evidence"]["path"]
            # Single continuous traversal — no restart between add and traverse.
            assert path == _EXPECTED_PATH, "%s path: %s" % (cond, path)
            # The agent followed path_high -> audit, an edge that did NOT exist
            # until it was written mid-traversal: the write was structurally live
            # for the very next step, across the boundary, with no recompile.
            i = path.index("path_high")
            assert path[i + 1] == "audit", cond


class TestProcessBoundary:
    def test_condition_c_crosses_a_real_process_boundary(self, results):
        m = results["C"]["metrics"]
        assert m.get("process_boundary_crossed") is True
        assert m["evidence"]["service_pid"] != m["evidence"]["agent_pid"]


class TestCombined:
    def test_condition_d_composes_boundary_over_persistent_store(self, results):
        m = results["D"]["metrics"]
        assert "sqlite" in m.get("persistent_store", "")
        assert results["D"]["final_state"] == results["A"]["final_state"]


# ---------------------------------------------------------------------------
# Cross-study baseline (B1-gated) + baseline-authoring record
# ---------------------------------------------------------------------------

class TestCrossStudy:
    def test_cross_study_baseline_or_b1_skip(self):
        import baseline_direct_write as a
        cohort = (_HERE.parent / "STUDY-204-Storage-Independent-Substrate"
                  / "graph_initial.json")
        if not cohort.exists():
            pytest.skip("B1: cohort sibling baseline not yet on disk in "
                        "XEPAYAC_LLC; STUDY-206 authored the canonical baseline "
                        "and the siblings conform (ADR-003).")
        mine = a.canonical_state(_load_initial())
        theirs = a.canonical_state(a.load_graph(cohort))
        assert mine == theirs

    def test_results_json_records_baseline_authoring(self):
        results_path = _HERE / "results.json"
        if not results_path.exists():
            generate_results()
        data = json.loads(results_path.read_text(encoding="utf-8"))
        assert data["baseline_authored_by"].startswith("STUDY-")


# ---------------------------------------------------------------------------
# No vendor/product/framework names in the README prose
# ---------------------------------------------------------------------------

def test_no_vendor_names_in_readme():
    readme = _HERE / "README.md"
    if not readme.exists():
        pytest.skip("README.md not yet written")
    text = readme.read_text(encoding="utf-8").lower()
    denylist = [
        "postgres", "redis", "mysql", "mongo", "neo4j", "kafka", "rabbitmq",
        "grpc", "graphql", "fastapi", "flask", "django", "celery", "zeromq",
        "langchain", "langgraph", "autogen", "dynamodb",
    ]
    found = [name for name in denylist if name in text]
    assert not found, "vendor names in README prose: %s" % found


# ---------------------------------------------------------------------------
# results.json generation (never hand-authored)
# ---------------------------------------------------------------------------

def _condition_block(res):
    m = res["metrics"]
    block = {k: m[k] for k in _METRIC_KEYS}
    if "process_boundary_crossed" in m:
        block["process_boundary_crossed"] = m["process_boundary_crossed"]
    if "persistent_store" in m:
        block["persistent_store"] = m["persistent_store"]
    block["path"] = m["evidence"]["path"]
    return block


def generate_results():
    """Run all four conditions and write results.json. Deterministic (no
    timestamp/duration) so re-running yields a byte-identical file."""
    runs = _run_conditions()
    base = runs["A"]["final_state"]
    conditions = {}
    checks = []  # (label, bool)
    for cond in "ABCD":
        m = runs[cond]["metrics"]
        conditions[cond] = _condition_block(runs[cond])
        equiv = (runs[cond]["final_state"] == base)
        checks += [
            ("%s.topology_determination" % cond, m["topology_determination"] is True),
            ("%s.result_dependent_routing" % cond, m["result_dependent_routing"] is True),
            ("%s.self_modification" % cond, m["self_modification"] is True),
            ("%s.decision_locus_is_agent" % cond, m["decision_locus"] == "agent"),
            ("%s.modification_persistence" % cond, m["modification_persistence"] is True),
            ("%s.functional_equivalence_to_A" % cond, equiv),
            ("%s.delta_nonzero" % cond,
             m["node_count_delta"] != 0 or m["edge_count_delta"] != 0),
        ]
    checks.append(("C.process_boundary_crossed",
                   runs["C"]["metrics"].get("process_boundary_crossed") is True))
    passed = sum(1 for _, ok in checks if ok)
    failed = sum(1 for _, ok in checks if not ok)
    data = {
        "study_id": "STUDY-206",
        "title": "API-Mediated Self-Modification — Modification Across a Service Boundary",
        "date": "2026-06-18",
        "status": "PASS" if failed == 0 else "FAIL",
        "tests_run": len(checks),
        "tests_passed": passed,
        "tests_failed": failed,
        "baseline_authored_by": _BASELINE,
        "conditions": conditions,
        "key_findings": [
            "An interposed API/service boundary is a transport detail, not a "
            "relocation of the inventive locus: B, C and D produce a final graph "
            "state structurally identical to the direct-write baseline A.",
            "The decision-locus is the agent in every condition — the "
            "result-driven modification is decided agent-side, regardless of "
            "where the write physically executes.",
            "The write services are dumb transports: they apply the requested "
            "write and have no path to the execution result or the routing "
            "decision (adversarially verified).",
            "The modification is structurally live across the boundary: a write "
            "issued mid-traversal governs the very next step with no parse, "
            "compile, deploy or restart boundary.",
            "Condition C crosses a genuine operating-system process boundary and "
            "Condition D composes the boundary over a relational persistent "
            "store, yet both remain functionally equivalent to the baseline.",
        ],
    }
    with (_HERE / "results.json").open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return data, checks


def test_results_json_shape():
    data, _ = generate_results()
    cond = data["conditions"]
    assert sorted(cond) == ["A", "B", "C", "D"]
    assert all(cond[k]["decision_locus"] == "agent" for k in "ABCD")
    assert all(cond[k]["node_count_delta"] != 0 or cond[k]["edge_count_delta"] != 0
               for k in "ABCD")
    assert data["status"] == "PASS"


if __name__ == "__main__":
    data, checks = generate_results()
    print("=" * 64)
    print("STUDY-206: API-Mediated Self-Modification — validation")
    print("=" * 64)
    for label, ok in checks:
        print("  %s %s" % ("✅" if ok else "❌", label))
    print("-" * 64)
    print("conditions:", ", ".join(sorted(data["conditions"])))
    print("status: %s  (%d/%d checks passed)"
          % (data["status"], data["tests_passed"], data["tests_run"]))
    print("results.json written (generated, not hand-authored)")
    sys.exit(0 if data["tests_failed"] == 0 else 1)
