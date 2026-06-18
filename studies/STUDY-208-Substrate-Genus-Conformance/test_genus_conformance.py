"""STUDY-208: Substrate-Genus Conformance — genus-conformance harness + tests.

AGPL-3.0 | Patent Pending (app 19/575,491)

Runs the ONE conformance corpus against every persistent-store backend (A
serialized file, B multi-file, C relational, D key-value, E in-memory) and
asserts:
  * each backend passes all 7 conformance metrics (incl. nonzero deltas),
  * every backend's final substrate state is structurally equivalent to the
    file baseline A (B==A, C==A, D==A, E==A),
  * the mechanism touches storage ONLY through the substrate contract
    (embodiment-only — the load-bearing invariant; a violation invalidates the
    reduction-to-practice),
  * the relational backend reads via query and the in-memory backend satisfies
    persist semantics within the run,
  * the workload is deterministic so equivalence is a decidable structural diff.

`python -m pytest test_genus_conformance.py`  -> runs the test suite.
`python test_genus_conformance.py`            -> runs the demo + writes results.json.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend_file import FileBackend
from backend_inmemory import InMemoryBackend
from backend_kv import KeyValueBackend
from backend_multifile import MultiFileBackend
from backend_relational import RelationalBackend
from conformance_corpus import EXPECTED_PATH, run_corpus
from substrate_contract import (
    fingerprint,
    load_initial,
    make_edge,
    SubstrateContract,
)

GRAPH_INITIAL = Path(__file__).resolve().parent / "graph_initial.json"
BASELINE_AUTHORED_BY = "STUDY-208"  # siblings STUDY-203/204 unbuilt at authoring (B1)
STUDY_DATE = "2026-06-18"

METRIC_KEYS = [
    "topology_determination",
    "result_dependent_routing",
    "self_modification",
    "modification_persistence",
    "functional_equivalence",
    "node_count_delta",
    "edge_count_delta",
]

# (key, store description, adapter class) — the representative genus spread.
BACKENDS = [
    ("A", "serialized file", FileBackend),
    ("B", "multi-file", MultiFileBackend),
    ("C", "relational store", RelationalBackend),
    ("D", "key-value store", KeyValueBackend),
    ("E", "in-memory store", InMemoryBackend),
]


def _build(key: str, cls, base: Path) -> SubstrateContract:
    wd = base / f"backend_{key}"
    wd.mkdir(parents=True, exist_ok=True)
    return cls(load_initial(GRAPH_INITIAL), wd)


def run_all(base: Path) -> tuple[dict[str, Any], str]:
    """Run the corpus against every backend; fill functional_equivalence vs A."""
    results: dict[str, Any] = {}
    baseline_fp = ""
    for key, store, cls in BACKENDS:
        backend = _build(key, cls, base)
        run = run_corpus(backend)
        run["store"] = store
        run["fingerprint"] = fingerprint(run["final_state"])
        results[key] = run
        if key == "A":
            baseline_fp = run["fingerprint"]
    for key in results:
        results[key]["metrics"]["functional_equivalence"] = (
            results[key]["fingerprint"] == baseline_fp
        )
    return results, baseline_fp


@pytest.fixture(scope="module")
def genus(tmp_path_factory) -> dict[str, Any]:
    base = tmp_path_factory.mktemp("genus")
    results, baseline_fp = run_all(base)
    return {"results": results, "baseline_fp": baseline_fp}


# --- The study's reason to exist: cross-backend functional equivalence -------

class TestEquivalence:

    @pytest.mark.parametrize("key", ["B", "C", "D", "E"])
    def test_backend_equivalent_to_file_baseline(self, genus, key):
        results = genus["results"]
        assert results[key]["fingerprint"] == results["A"]["fingerprint"], (
            f"backend {key} final state differs from the file baseline A"
        )

    def test_all_backends_share_one_state(self, genus):
        fps = {k: v["fingerprint"] for k, v in genus["results"].items()}
        assert len(set(fps.values())) == 1, f"backends diverged: {fps}"


# --- 7 metrics per backend, incl. nonzero deltas ----------------------------

class TestMetrics:

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_all_seven_metrics_present(self, genus, key):
        m = genus["results"][key]["metrics"]
        for mk in METRIC_KEYS:
            assert mk in m, f"backend {key} missing metric {mk}"

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_count_deltas_present_and_nonzero(self, genus, key):
        m = genus["results"][key]["metrics"]
        assert isinstance(m["node_count_delta"], int)
        assert isinstance(m["edge_count_delta"], int)
        assert m["node_count_delta"] != 0 or m["edge_count_delta"] != 0, (
            f"backend {key} has all-zero deltas — no self-modification recorded"
        )

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_functional_equivalence_true(self, genus, key):
        assert genus["results"][key]["metrics"]["functional_equivalence"] is True


# --- Substrate governs execution, per backend -------------------------------

class TestSubstrateGoverns:

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_topology_determines_sequence(self, genus, key):
        run = genus["results"][key]
        assert run["metrics"]["topology_determination"] is True
        assert run["visited"] == EXPECTED_PATH, (
            f"backend {key} visited {run['visited']}, expected {EXPECTED_PATH}"
        )

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_result_driven_routing(self, genus, key):
        # gate (odd vs even), mutate (audit vs done), supersede (v2 vs v1).
        assert genus["results"][key]["metrics"]["result_dependent_routing"] == 3

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_self_modification_and_supersede(self, genus, key):
        run = genus["results"][key]
        assert run["metrics"]["self_modification"] == 2  # self-mod + supersede
        assert "compute_v2" in run["visited"]            # superseding node is live

    @pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
    def test_modification_persists_and_is_live(self, genus, key):
        run = genus["results"][key]
        assert run["metrics"]["modification_persistence"] is True
        assert "audit" in run["visited"]  # the self-mod-added node was traversed


# --- Embodiment-only: the deepest correctness invariant (B3, CRITICAL) ------

class _ContractSpy:
    """Records every method the corpus calls on the contract."""

    ALLOWED = {"read_node", "get_outgoing_edges", "write_modification",
               "persist", "export_canonical"}

    def __init__(self, inner: SubstrateContract) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "calls", [])

    def __getattr__(self, name: str):
        inner = object.__getattribute__(self, "_inner")
        attr = getattr(inner, name)
        if callable(attr):
            calls = object.__getattribute__(self, "calls")

            def wrapper(*a, **k):
                calls.append(name)
                return attr(*a, **k)

            return wrapper
        return attr


class TestEmbodimentOnly:

    def test_corpus_touches_storage_only_via_contract(self, tmp_path):
        backend = _build("A", FileBackend, tmp_path)
        spy = _ContractSpy(backend)
        run_corpus(spy)
        called = set(spy.calls)
        assert called <= _ContractSpy.ALLOWED, (
            f"corpus called non-contract methods: {called - _ContractSpy.ALLOWED}"
        )
        # The mechanism really did read, write, and persist via the contract.
        assert {"read_node", "get_outgoing_edges",
                "write_modification", "persist"} <= called

    def test_corpus_does_not_import_any_backend(self):
        src = (Path(__file__).resolve().parent / "conformance_corpus.py").read_text(
            encoding="utf-8"
        )
        assert "import backend_" not in src
        assert "from backend_" not in src

    @pytest.mark.parametrize("key,cls", [
        ("A", FileBackend), ("B", MultiFileBackend), ("C", RelationalBackend),
        ("D", KeyValueBackend), ("E", InMemoryBackend),
    ])
    def test_backend_is_a_contract(self, key, cls):
        assert issubclass(cls, SubstrateContract)


# --- Access patterns: relational query + in-memory persist semantics --------

class TestAccessPattern:

    def test_relational_reads_via_query(self, tmp_path):
        backend = _build("C", RelationalBackend, tmp_path)
        run_corpus(backend)
        assert backend.reads_via_query > 0  # the read path issued SQL, not file parse

    def test_inmemory_persist_semantics_within_run(self, tmp_path):
        backend = InMemoryBackend(load_initial(GRAPH_INITIAL))
        before = backend.get_outgoing_edges("mutate")
        backend.write_modification(
            {"add_nodes": [], "add_edges": [make_edge("mutate", "audit", "COND", "audit")]}
        )
        # Not yet persisted -> not visible to traversal.
        assert backend.get_outgoing_edges("mutate") == before
        backend.persist()
        # Persisted -> immediately live (governs subsequent traversal).
        after = backend.get_outgoing_edges("mutate")
        assert len(after) == len(before) + 1


# --- Determinism so equivalence is decidable (B6) ---------------------------

class TestDeterminism:

    def test_repeated_run_is_identical(self, tmp_path):
        b1 = _build("A", FileBackend, tmp_path / "r1")
        b2 = _build("A", FileBackend, tmp_path / "r2")
        fp1 = fingerprint(run_corpus(b1)["final_state"])
        fp2 = fingerprint(run_corpus(b2)["final_state"])
        assert fp1 == fp2


# --- Cross-study baseline authoring record (B1 / ADR-003) -------------------

class TestCrossStudy:

    def test_baseline_authoring_recorded(self):
        # Siblings STUDY-203/204 are unbuilt; STUDY-208 authors the canonical
        # baseline. The byte-compare is deferred (B1); the authoring record is not.
        assert BASELINE_AUTHORED_BY == "STUDY-208"


# --- No vendor/product/framework names in the published prose ---------------

class TestNoVendorNames:

    def test_readme_is_vendor_name_free(self):
        readme = Path(__file__).resolve().parent / "README.md"
        if not readme.exists():
            pytest.skip("README.md not yet written")
        text = readme.read_text(encoding="utf-8").lower()
        denylist = [
            "postgres", "redis", "mysql", "mongo", "neo4j", "sqlalchemy",
            "django", "flask", "langchain", "langgraph", "autogen", "oracle",
            "dynamodb", "cassandra", "rocksdb", "leveldb", "memcached",
        ]
        hits = [name for name in denylist if name in text]
        assert not hits, f"vendor names found in README prose: {hits}"


# ---------------------------------------------------------------------------
# Demo + results.json writer
# ---------------------------------------------------------------------------

def _build_results_doc(results: dict[str, Any]) -> dict[str, Any]:
    backends_block: dict[str, Any] = {}
    for key, store, _ in BACKENDS:
        m = results[key]["metrics"]
        passed = (
            m["functional_equivalence"] is True
            and m["topology_determination"] is True
            and m["modification_persistence"] is True
            and (m["node_count_delta"] != 0 or m["edge_count_delta"] != 0)
        )
        backends_block[key] = {
            "store": store,
            "result": "PASS" if passed else "FAIL",
            "topology_determination": m["topology_determination"],
            "result_dependent_routing": m["result_dependent_routing"],
            "self_modification": m["self_modification"],
            "modification_persistence": m["modification_persistence"],
            "functional_equivalence": m["functional_equivalence"],
            "node_count_delta": m["node_count_delta"],
            "edge_count_delta": m["edge_count_delta"],
        }
    return backends_block


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="study_208_") as tmp:
        results, _ = run_all(Path(tmp))

    backends_block = _build_results_doc(results)

    checks: list[tuple[str, bool]] = []
    for key in ["B", "C", "D", "E"]:
        checks.append((f"Backend {key} final state == file baseline A",
                       results[key]["fingerprint"] == results["A"]["fingerprint"]))
    for key, _, _ in BACKENDS:
        m = results[key]["metrics"]
        checks.append((f"Backend {key} 7 metrics present",
                       all(mk in m for mk in METRIC_KEYS)))
        checks.append((f"Backend {key} deltas nonzero",
                       m["node_count_delta"] != 0 or m["edge_count_delta"] != 0))
        checks.append((f"Backend {key} topology determines sequence",
                       m["topology_determination"] is True))
        checks.append((f"Backend {key} result-driven routing (==3)",
                       m["result_dependent_routing"] == 3))
        checks.append((f"Backend {key} self-modification + supersede (==2)",
                       m["self_modification"] == 2))
        checks.append((f"Backend {key} modification persists + live",
                       m["modification_persistence"] is True))

    passed = sum(1 for _, ok in checks if ok)
    failed = sum(1 for _, ok in checks if not ok)
    status = "PASS" if failed == 0 else "FAIL"

    doc = {
        "study_id": "STUDY-208",
        "title": "Substrate-Genus Conformance",
        "date": STUDY_DATE,
        "status": status,
        "tests_run": len(checks),
        "tests_passed": passed,
        "tests_failed": failed,
        "baseline_authored_by": BASELINE_AUTHORED_BY,
        "backends": backends_block,
        "key_findings": [
            "One substrate contract (read_node / get_outgoing_edges / "
            "write_modification / persist) suffices for the whole persistent-store "
            "genus: serialized file, multi-file, relational, key-value, in-memory.",
            "The identical self-superseding mechanism and the identical conformance "
            "corpus run UNCHANGED across all five backends.",
            "Every backend's final substrate state is structurally equivalent to the "
            "file baseline (B==A, C==A, D==A, E==A) — the mechanism does the work, "
            "the storage does not.",
            "All three never-broadened mechanism properties hold per backend: "
            "topology-as-program, result-driven edge selection, and structural-"
            "liveness (an in-traversal persisted self-modification incl. a supersede "
            "step is immediately live).",
            "The networked/distributed species is NOT reduced to practice here "
            "(owed to STUDY-209); this artifact is a dated RTP of the genus, not the "
            "patent's enabling disclosure.",
        ],
    }

    out = Path(__file__).resolve().parent / "results.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")

    print("=" * 64)
    print("STUDY-208: Substrate-Genus Conformance")
    print("=" * 64)
    for key, store, _ in BACKENDS:
        b = backends_block[key]
        print(f"  Backend {key} ({store}): {b['result']} | "
              f"equiv={b['functional_equivalence']} "
              f"Δnodes={b['node_count_delta']} Δedges={b['edge_count_delta']}")
    print("-" * 64)
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print("=" * 64)
    print(f"RESULT: {status} ({passed}/{len(checks)} checks) -> wrote {out.name}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
