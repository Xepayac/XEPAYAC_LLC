"""STUDY-140: Supersede Operation — the supersede primitive.

A node spawns a replacement during execution: the replacement is added,
the original is marked stale, every incoming edge is redirected to the
replacement, and a SUPERSEDED_BY edge records lineage — atomically. The
operation validates the replacement against the graph schema, restores
the pre-operation state on any failure, and detects concurrent supersede
attempts on the same node via optimistic versioning.

This file demonstrates WHAT the substrate can do (the capability), not
how any production system implements it.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from graph import ACTIVE, STALE, SUPERSEDED_BY, Edge, Graph, Node


class SupersedeError(Exception):
    """The operation was rejected or failed; the graph is unchanged."""


class TypeViolation(SupersedeError):
    """Replacement node type is not allowed by the schema."""


class ConcurrentConflict(SupersedeError):
    """Another writer mutated the graph after this writer read it."""


class CommitValidationError(SupersedeError):
    """Replacement failed commit-time validation; state was restored."""


@dataclass
class SupersedeResult:
    """Outcome of a committed supersede."""

    original_id: str
    replacement_id: str
    redirected_edges: int
    graph_version: int


def supersede(
    graph: Graph,
    original_id: str,
    replacement: Node,
    expected_version: Optional[int] = None,
) -> SupersedeResult:
    """Atomically replace `original_id` with `replacement` in `graph`.

    Steps (all-or-nothing):
      1. conflict check  — if `expected_version` is given and the graph has
         moved past it, raise ConcurrentConflict (nothing applied);
      2. precondition    — original must exist and be active; replacement id
         must be free; replacement type must satisfy the schema (else
         TypeViolation, nothing applied);
      3. apply           — add replacement (active), mark original stale,
         redirect every incoming edge of the original to the replacement,
         add the SUPERSEDED_BY lineage edge;
      4. commit-validate — replacement must carry every schema-required
         property; on failure the pre-operation state is restored
         (CommitValidationError) and the graph is byte-identical to before;
      5. record          — append one provenance record; bump version.

    There is no observable state in which both nodes are active: the stale
    mark and the replacement's activation commit together or not at all.
    """
    # 1. optimistic concurrency
    if expected_version is not None and expected_version != graph.version:
        raise ConcurrentConflict(
            f"graph moved from version {expected_version} "
            f"to {graph.version} since read"
        )

    # 2. preconditions (graph untouched on failure)
    if original_id not in graph.nodes:
        raise SupersedeError(f"unknown node: {original_id}")
    original = graph.nodes[original_id]
    if original.status != ACTIVE:
        raise SupersedeError(f"node already superseded: {original_id}")
    if replacement.id in graph.nodes:
        raise SupersedeError(f"replacement id taken: {replacement.id}")
    if not graph.schema.type_allowed(replacement.type):
        raise TypeViolation(
            f"replacement type not allowed by schema: {replacement.type}"
        )

    # 3. apply against a snapshot boundary
    snap = graph.snapshot()
    try:
        graph.nodes[replacement.id] = replacement
        replacement.status = ACTIVE
        original.status = STALE
        redirected = 0
        for edge in graph.edges:
            if edge.to_id == original_id and edge.relation != SUPERSEDED_BY:
                edge.to_id = replacement.id
                redirected += 1
        graph.edges.append(Edge(original_id, replacement.id, SUPERSEDED_BY))

        # 4. commit-time validation
        missing = graph.schema.missing_properties(replacement)
        if missing:
            raise CommitValidationError(
                f"replacement missing required properties: {missing}"
            )
    except Exception:
        graph.restore(snap)
        raise

    # 5. provenance + version
    graph.version += 1
    graph.provenance.append(
        {
            "operation": "supersede",
            "original_id": original_id,
            "replacement_id": replacement.id,
            "redirected_edges": redirected,
            "graph_version": graph.version,
        }
    )
    return SupersedeResult(
        original_id=original_id,
        replacement_id=replacement.id,
        redirected_edges=redirected,
        graph_version=graph.version,
    )


def apply_llm_proposal(graph: Graph, proposal_json: str) -> SupersedeResult:
    """Validate and apply a supersede proposal authored by an LLM.

    The proposal is a structured JSON document (recorded; no live model
    call is required to prove the property — see ADR-003 of AAA #1329):

        {
          "operation": "supersede",
          "original_id": "...",
          "replacement": {"id": "...", "type": "...", "properties": {...}},
          "expected_version": <int, optional>
        }

    The graph validates the proposal shape, then applies it through the
    same atomic `supersede` path as any other writer.
    """
    try:
        proposal = json.loads(proposal_json)
    except json.JSONDecodeError as exc:
        raise SupersedeError(f"proposal is not valid JSON: {exc}") from exc

    if proposal.get("operation") != "supersede":
        raise SupersedeError("proposal operation must be 'supersede'")
    for key in ("original_id", "replacement"):
        if key not in proposal:
            raise SupersedeError(f"proposal missing field: {key}")
    spec: Dict[str, Any] = proposal["replacement"]
    for key in ("id", "type"):
        if key not in spec:
            raise SupersedeError(f"proposal replacement missing field: {key}")

    replacement = Node(
        id=spec["id"],
        type=spec["type"],
        properties=dict(spec.get("properties", {})),
    )
    return supersede(
        graph,
        proposal["original_id"],
        replacement,
        expected_version=proposal.get("expected_version"),
    )
