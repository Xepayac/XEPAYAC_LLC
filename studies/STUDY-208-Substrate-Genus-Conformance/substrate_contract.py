"""STUDY-208: Substrate-Genus Conformance — the ONE substrate contract.

AGPL-3.0 | Patent Pending (app 19/575,491)

This is the keystone of the study. Every persistent-store backend implements
exactly this minimal interface and nothing more:

    read_node(node_id)        -> the node record
    get_outgoing_edges(id)    -> the outgoing edges of a node
    write_modification(mod)   -> stage an in-traversal self-modification
    persist()                 -> commit staged modifications (immediately live)

The conformance corpus (the self-superseding workload + traversal/execution/
routing logic) runs ENTIRELY against this contract — never against a backend
directly. That is what lets the study prove the mechanism does the work and the
storage does not: the same mechanism, run over a serialized file, a multi-file
set, a relational store, a key-value store, or an in-memory store, produces a
structurally-equivalent final substrate. No routing, traversal, execution, or
edge-selection logic lives in any backend — it lives above the contract.

`export_canonical()` is a measurement affordance used by the harness AFTER a run
to compare final states; it is NOT part of the execution mechanism and the
corpus does not use it during traversal.
"""

from __future__ import annotations

import copy
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Primitive vocabulary — deterministic, vendor-name-free node/edge constructors
# ---------------------------------------------------------------------------

def make_node(node_id: str, node_type: str, op: str) -> dict[str, Any]:
    """A substrate node: an id, a type, and a deterministic operation string.

    No wall-clock metadata: the substrate is deterministic so that functional
    equivalence across backends is a decidable structural diff.
    """
    return {"id": node_id, "type": node_type, "op": op}


def make_edge(source: str, target: str, relation: str,
              condition: str | None = None) -> dict[str, Any]:
    """A directional substrate edge.

    `relation` is a primitive ("THEN" sequence, "COND" result-conditioned,
    "SUPERSEDES" structural). `condition`, when set, is the execution-result
    token that selects this edge — result-driven edge selection.
    """
    return {"source": source, "target": target,
            "relation": relation, "condition": condition}


def load_initial(path: Path) -> dict[str, Any]:
    """Load the shared starting substrate (nodes + edges)."""
    with Path(path).open("r", encoding="utf-8") as f:
        graph = json.load(f)
    return {"nodes": copy.deepcopy(graph["nodes"]),
            "edges": copy.deepcopy(graph["edges"])}


def canonical(nodes: list[dict], edges: list[dict]) -> dict[str, Any]:
    """A deterministic, order-insensitive view of substrate state.

    Sorts nodes by id and edges by (source, target, relation, condition) so two
    backends that reached the same logical state compare equal regardless of the
    order their store happened to return rows/keys/lines in.
    """
    snodes = sorted(({"id": n["id"], "type": n["type"], "op": n["op"]}
                     for n in nodes), key=lambda n: n["id"])
    sedges = sorted(({"source": e["source"], "target": e["target"],
                      "relation": e["relation"],
                      "condition": e.get("condition")} for e in edges),
                    key=lambda e: (e["source"], e["target"],
                                   e["relation"], e["condition"] or ""))
    return {"nodes": snodes, "edges": sedges}


def fingerprint(state: dict[str, Any]) -> str:
    """A stable string fingerprint of a canonical state, for equality checks."""
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


# A modification is purely additive in this study: it adds nodes and edges.
Modification = dict[str, list[dict[str, Any]]]  # {"add_nodes": [...], "add_edges": [...]}


# ---------------------------------------------------------------------------
# The contract — the ONLY surface the mechanism (corpus) is allowed to touch
# ---------------------------------------------------------------------------

class SubstrateContract(ABC):
    """The uniform substrate interface every backend implements.

    Exactly four mechanism methods. A backend is a STORAGE adapter: it decides
    where nodes and edges live and how they are read and written — nothing else.
    """

    @abstractmethod
    def read_node(self, node_id: str) -> dict[str, Any]:
        """Return the node record for `node_id` from the store."""

    @abstractmethod
    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        """Return the outgoing edges whose source is `node_id`, from the store."""

    @abstractmethod
    def write_modification(self, modification: Modification) -> None:
        """Stage an additive self-modification (new nodes and/or edges)."""

    @abstractmethod
    def persist(self) -> None:
        """Commit staged modifications so subsequent reads observe them.

        After persist() returns, the modification is immediately structurally
        live: there is no parse/compile/deploy/restart step between the write
        and its effect on subsequent traversal.
        """

    @abstractmethod
    def export_canonical(self) -> dict[str, Any]:
        """Measurement affordance (NOT mechanism): a canonical view of the full
        current substrate state, used by the harness to compare final states."""
