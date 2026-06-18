"""Tests for STUDY-207: Multi-File Substrate Mutation — Cross-File Graph
Self-Modification.

Nine tests, one per design-doc matrix row. Each runs on copies of the committed
fixtures in a pytest ``tmp_path`` — the committed ``fixtures/`` files are never
mutated. The conformance criterion throughout is cross-file atomicity: both
files reflect a mutation, or neither does.

Stdlib + pytest only.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import pytest

from cross_file_mutation import (
    ConcurrentConflict,
    DanglingEdgeError,
    add_cross_file_edge,
    mutate_cross_file,
    supersede_cross_file,
)
from discovery import discover_substrate, reachable
from substrate import (
    DEPENDS_ON,
    FEEDS,
    SUPERSEDED_BY,
    Substrate,
    copy_fixtures,
    make_node,
    ref,
)
from transaction import FailureInjected


@pytest.fixture
def workdir(tmp_path):
    copy_fixtures(tmp_path)
    return tmp_path


@pytest.fixture
def sub(workdir):
    return Substrate.from_dir(workdir)


# --- 1. cross-file node creation (Scenario 1: STAGE-3 -> RESULT in File B) ---

def test_cross_file_node_creation(sub, workdir):
    """Execution in File A spawns a RESULT node in File B and writes a FEEDS
    edge in File A pointing at it. The edge is specifically of type FEEDS."""
    result_node = make_node(
        "result_stage3", "RESULT", {"value": 42}, created_by="pipeline_runner"
    )
    res = mutate_cross_file(
        sub, "file_a.json", "file_b.json", "stage_3", result_node, relation=FEEDS
    )

    # RESULT node now exists in File B (File B was modified in place)
    assert sub.get_node("file_b.json", "result_stage3") is not None
    # a FEEDS edge in File A points at the cross-file result reference
    feeds = [
        e for e in sub.edges_in("file_a.json")
        if e["relation"] == FEEDS
        and e["target_id"] == "file_b.json:result_stage3"
    ]
    assert len(feeds) == 1, "exactly one FEEDS edge, not a generic edge"
    assert res["feeds_edge_present"] is True


# --- 2. cross-file edge connects A<->B, both files reflect it ----------------

def test_cross_file_edge(sub):
    """A cross-file edge connects a node in File A to a node in File B; both
    files reflect it (the edge in A, the resolvable target in B)."""
    add_cross_file_edge(
        sub, "file_a.json", "stage_1", ref("file_b.json", "results_root"), DEPENDS_ON
    )
    edge = [
        e for e in sub.edges_in("file_a.json")
        if e["target_id"] == "file_b.json:results_root"
        and e["relation"] == DEPENDS_ON
        and e["source_id"] == "stage_1"
    ]
    assert len(edge) == 1
    # File B reflects the edge: its target resolves to a real node
    assert sub.resolve("file_b.json:results_root", "file_a.json") is not None
    assert sub.dangling_cross_file_edges() == []


# --- 3. cross-file supersede (File B modified in place; v1->v2 audit trail) --

def test_cross_file_supersede(sub, workdir):
    """Supersede REPORT v1 in File B: v1 marked stale, v2 created active, a
    SUPERSEDED_BY lineage edge added (the v1->v2 audit trail is traversable),
    and File A's reference redirected to v2 — all in one transaction. File B's
    content is genuinely modified (the load-bearing delta over STUDY-202)."""
    before_b = (workdir / "file_b.json").read_bytes()

    replacement = make_node("report_v2", "REPORT", {"title": "summary", "rev": 2})
    res = supersede_cross_file(
        sub, "file_a.json", "file_b.json", "report_v1", replacement
    )

    # v1 stale, v2 active (File B's report node was replaced in place)
    assert sub.get_node("file_b.json", "report_v1")["metadata"]["status"] == "stale"
    assert sub.get_node("file_b.json", "report_v2")["metadata"]["status"] == "active"

    # SUPERSEDED_BY lineage edge present and the v1->v2 audit trail traverses
    lineage = [
        e for e in sub.edges_in("file_b.json")
        if e["relation"] == SUPERSEDED_BY
        and e["source_id"] == "report_v1"
        and e["target_id"] == "report_v2"
    ]
    assert len(lineage) == 1, "SUPERSEDED_BY audit-trail edge v1->v2"
    audit_trail = reachable(sub, "file_b.json", "report_v1")
    assert "file_b.json:report_v2" in audit_trail

    # File A's cross-file reference was redirected to v2
    assert res["source_refs_redirected"] >= 1
    assert any(
        e["target_id"] == "file_b.json:report_v2"
        for e in sub.edges_in("file_a.json")
    )
    # File B's on-disk content actually changed (in-place modification)
    assert (workdir / "file_b.json").read_bytes() != before_b


# --- 4. atomic rollback: a mid-transaction failure leaves both files intact --

def test_atomic_rollback(sub, workdir):
    """An injected failure between the File-B temp write and commit rolls both
    files back: each is byte-identical, with no dangling edge and no partial
    node (deterministic via the ADR-004 fail_after hook)."""
    before_a = (workdir / "file_a.json").read_bytes()
    before_b = (workdir / "file_b.json").read_bytes()

    result_node = make_node("result_stage3", "RESULT", {"value": 42})
    with pytest.raises(FailureInjected):
        mutate_cross_file(
            sub, "file_a.json", "file_b.json", "stage_3", result_node,
            relation=FEEDS, fail_after="target_temp_write",
        )

    # both files byte-unchanged
    assert (workdir / "file_a.json").read_bytes() == before_a
    assert (workdir / "file_b.json").read_bytes() == before_b
    # no partial node, no dangling edge
    sub.reload()
    assert sub.get_node("file_b.json", "result_stage3") is None
    assert sub.dangling_cross_file_edges() == []


# --- 5. substrate discovery by edge-following, no manifest -------------------

def test_substrate_discovery(sub, workdir):
    """Starting from File A, follow cross-file edges transitively (A->B->C) to
    discover all three files. No manifest is read."""
    res = discover_substrate(workdir / "file_a.json")
    assert res["count"] == 3
    assert set(res["files_discovered"]) == {"file_a.json", "file_b.json", "file_c.json"}
    assert res["manifest_used"] is False


# --- 6. traversal after a cross-file mutation is immediately live ------------

def test_traversal_after_mutation(sub):
    """A cross-file mutation is immediately live for traversal across the file
    boundary — no parse/compile/deploy step (structural liveness)."""
    result_node = make_node("result_stage3", "RESULT", {"value": 42})
    mutate_cross_file(
        sub, "file_a.json", "file_b.json", "stage_3", result_node, relation=FEEDS
    )
    reach = reachable(sub, "file_a.json", "stage_3")
    assert "file_b.json:result_stage3" in reach


# --- 7. multi-agent cross-file provenance ------------------------------------

def test_multi_agent_cross_file(sub):
    """Agent 1 writes into Agent 2's file; the created node carries provenance
    naming Agent 1."""
    node = make_node("agent1_result", "RESULT", {"value": 1}, created_by="agent_one")
    mutate_cross_file(
        sub, "file_a.json", "file_b.json", "stage_3", node, relation=FEEDS
    )
    created = sub.get_node("file_b.json", "agent1_result")
    assert created["metadata"]["created_by"] == "agent_one"


# --- 8. dangling-edge prevention (referential integrity) ---------------------

def test_dangling_edge_prevention(sub):
    """A cross-file edge to a non-existent target node is rejected and leaves
    no dangling edge behind."""
    with pytest.raises(DanglingEdgeError):
        add_cross_file_edge(
            sub, "file_a.json", "stage_1",
            ref("file_b.json", "does_not_exist"), DEPENDS_ON,
        )
    sub.reload()
    assert sub.dangling_cross_file_edges() == []


# --- 9. concurrent cross-file writers: one succeeds, one conflicts -----------

def test_concurrent_cross_file(sub):
    """Two writers read File B at the same version and both attempt to supersede
    the same node; optimistic versioning lets exactly one succeed and the other
    conflict."""
    version_at_read = sub.version_of("file_b.json")

    # Writer 1 commits.
    supersede_cross_file(
        sub, "file_a.json", "file_b.json", "report_v1",
        make_node("report_v2a", "REPORT", {"rev": 2, "writer": 1}),
        expected_version=version_at_read,
    )

    # Writer 2 read the same (now stale) version -> must conflict.
    succeeded, conflicted = 1, 0
    try:
        supersede_cross_file(
            sub, "file_a.json", "file_b.json", "report_v1",
            make_node("report_v2b", "REPORT", {"rev": 2, "writer": 2}),
            expected_version=version_at_read,
        )
        succeeded += 1
    except ConcurrentConflict:
        conflicted += 1

    assert succeeded == 1
    assert conflicted == 1
