"""STUDY-207: cross-file mutation operations.

The load-bearing delta over STUDY-202 (spawn-and-supersede, File A read-only):
here an agent executing in the *source* file reaches into the *target* file and
modifies the target file's contents in place — a RESULT node is created, an
edge is added/redirected, a node is superseded — with both files committed
atomically (transaction.py) or neither.

  * ``mutate_cross_file``  — execution in the source file spawns a RESULT node
    into the target file and writes a FEEDS edge in the source file pointing at
    it; both files commit together.
  * ``add_cross_file_edge`` — add only a cross-file edge, guarded by referential
    integrity (a dangling edge to a non-existent target is refused).
  * ``supersede_cross_file`` — supersede a node in the target file in place
    (mark v1 stale, create v2 active, add a SUPERSEDED_BY lineage edge, redirect
    incoming edges, redirect the source file's cross-file reference to v2), with
    optimistic-versioning conflict detection for concurrent writers.

This file demonstrates WHAT the substrate can do, not how a production system
implements it.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import copy
from typing import Optional

from substrate import (
    ACTIVE,
    FEEDS,
    STALE,
    SUPERSEDED_BY,
    Substrate,
    make_edge,
    ref,
    split_ref,
)
from transaction import CrossFileTransaction


class MutationError(Exception):
    """A cross-file mutation was rejected; the substrate is unchanged."""


class DanglingEdgeError(MutationError):
    """A cross-file edge would point at a non-existent target node."""


class ConcurrentConflict(MutationError):
    """Another writer advanced the target file after this writer read it."""


def _graph_copy(substrate: Substrate, fname: str) -> dict:
    return copy.deepcopy(substrate.graphs[fname])


def _bump(graph: dict) -> None:
    graph["version"] = int(graph.get("version", 1)) + 1


def mutate_cross_file(
    substrate: Substrate,
    source_file: str,
    target_file: str,
    source_node_id: str,
    new_node: dict,
    relation: str = FEEDS,
    fail_after: Optional[str] = None,
) -> dict:
    """Execution in ``source_file`` spawns ``new_node`` into ``target_file`` and
    writes a cross-file ``relation`` edge in ``source_file`` pointing at it.

    Both files commit atomically. The edge's target is the node created in the
    same transaction, so it can never dangle.
    """
    if substrate.get_node(source_file, source_node_id) is None:
        raise MutationError(
            f"source node not found: {source_file}:{source_node_id}"
        )
    if substrate.get_node(target_file, new_node["id"]) is not None:
        raise MutationError(
            f"target node id taken: {target_file}:{new_node['id']}"
        )

    src = _graph_copy(substrate, source_file)
    tgt = _graph_copy(substrate, target_file)

    tgt.setdefault("nodes", []).append(new_node)
    _bump(tgt)

    target_ref = ref(target_file, new_node["id"])
    src.setdefault("edges", []).append(
        make_edge(source_node_id, target_ref, relation)
    )
    _bump(src)

    # referential integrity: the edge target must resolve post-commit.
    fname, nid = split_ref(target_ref)
    if fname != target_file or not any(n["id"] == nid for n in tgt["nodes"]):
        raise DanglingEdgeError(f"cross-file edge target missing: {target_ref}")

    txn = CrossFileTransaction(substrate.base_dir, fail_after=fail_after)
    txn.stage(substrate.files[source_file], src, label="source")
    txn.stage(substrate.files[target_file], tgt, label="target")
    result = txn.commit()
    substrate.reload()

    feeds_present = any(
        e["relation"] == relation and e["target_id"] == target_ref
        for e in substrate.edges_in(source_file)
    )
    return {
        "source_file": source_file,
        "target_file": target_file,
        "new_node_id": new_node["id"],
        "relation": relation,
        "feeds_edge_present": feeds_present,
        "committed": result.files_committed,
        "nodes_in_target_after": len(substrate.nodes_in(target_file)),
    }


def add_cross_file_edge(
    substrate: Substrate,
    source_file: str,
    source_node_id: str,
    target_ref: str,
    relation: str,
    fail_after: Optional[str] = None,
) -> dict:
    """Add only a cross-file edge. Refused (no write) if the target node does
    not exist — the referential-integrity guard that prevents dangling edges.
    """
    if substrate.get_node(source_file, source_node_id) is None:
        raise MutationError(
            f"source node not found: {source_file}:{source_node_id}"
        )
    fname, nid = split_ref(target_ref)
    if fname is None:
        raise MutationError(f"not a cross-file reference: {target_ref}")
    if fname not in substrate.graphs or substrate.get_node(fname, nid) is None:
        raise DanglingEdgeError(f"refusing dangling cross-file edge: {target_ref}")

    src = _graph_copy(substrate, source_file)
    src.setdefault("edges", []).append(
        make_edge(source_node_id, target_ref, relation)
    )
    _bump(src)
    txn = CrossFileTransaction(substrate.base_dir, fail_after=fail_after)
    txn.stage(substrate.files[source_file], src, label="source")
    txn.commit()
    substrate.reload()
    return {"added": target_ref, "relation": relation}


def supersede_cross_file(
    substrate: Substrate,
    source_file: str,
    target_file: str,
    original_id: str,
    replacement: dict,
    expected_version: Optional[int] = None,
    fail_after: Optional[str] = None,
) -> dict:
    """Supersede ``target_file:original_id`` in place with ``replacement``.

    Marks the original stale, adds the replacement active, redirects every
    incoming within-file edge, adds a SUPERSEDED_BY lineage edge (so the
    v1->v2 audit trail is traversable), and redirects any cross-file reference
    in ``source_file`` to point at the replacement — all atomically.

    Optimistic versioning: pass the ``expected_version`` read earlier; if the
    target file has advanced since, ``ConcurrentConflict`` is raised and nothing
    is applied.
    """
    if (
        expected_version is not None
        and substrate.version_of(target_file) != expected_version
    ):
        raise ConcurrentConflict(
            f"{target_file} moved from v{expected_version} "
            f"to v{substrate.version_of(target_file)} since read"
        )

    original = substrate.get_node(target_file, original_id)
    if original is None:
        raise MutationError(f"unknown node: {target_file}:{original_id}")
    if original["metadata"].get("status") != ACTIVE:
        raise MutationError(f"node already superseded: {original_id}")
    if substrate.get_node(target_file, replacement["id"]) is not None:
        raise MutationError(f"replacement id taken: {replacement['id']}")

    tgt = _graph_copy(substrate, target_file)
    replacement = copy.deepcopy(replacement)
    replacement.setdefault("metadata", {})["status"] = ACTIVE

    for node in tgt["nodes"]:
        if node["id"] == original_id:
            node["metadata"]["status"] = STALE
    tgt["nodes"].append(replacement)

    redirected = 0
    for edge in tgt["edges"]:
        if edge["target_id"] == original_id and edge["relation"] != SUPERSEDED_BY:
            edge["target_id"] = replacement["id"]
            redirected += 1
    tgt["edges"].append(make_edge(original_id, replacement["id"], SUPERSEDED_BY))
    _bump(tgt)

    src = _graph_copy(substrate, source_file)
    old_ref = ref(target_file, original_id)
    new_ref = ref(target_file, replacement["id"])
    src_redirected = 0
    for edge in src["edges"]:
        if edge["target_id"] == old_ref:
            edge["target_id"] = new_ref
            src_redirected += 1
    _bump(src)

    txn = CrossFileTransaction(substrate.base_dir, fail_after=fail_after)
    txn.stage(substrate.files[source_file], src, label="source")
    txn.stage(substrate.files[target_file], tgt, label="target")
    txn.commit()
    substrate.reload()

    return {
        "original_id": original_id,
        "replacement_id": replacement["id"],
        "redirected_edges": redirected,
        "source_refs_redirected": src_redirected,
        "target_version": substrate.version_of(target_file),
    }
