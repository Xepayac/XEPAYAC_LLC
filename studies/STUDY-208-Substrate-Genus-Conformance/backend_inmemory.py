"""STUDY-208 Backend E — in-memory store.

Implements the substrate contract over in-process structures (no file, no
external service). Reads come from the committed state; write_modification stages
changes; persist() commits them. The answer to "in-memory is technically still
ephemeral" is persist SEMANTICS WITHIN THE RUN: a modification is not visible to
subsequent traversal until persist() commits it, and once committed it governs
the modified topology — exactly the structural-liveness the contract requires.
This backend implements the contract and nothing more.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from substrate_contract import Modification, SubstrateContract, canonical


class InMemoryBackend(SubstrateContract):

    def __init__(self, initial: dict[str, Any], workdir: Path | None = None) -> None:
        self._nodes: dict[str, dict] = {n["id"]: dict(n) for n in initial["nodes"]}
        self._edges: list[dict] = [dict(e) for e in initial["edges"]]
        self._pending: Modification = {"add_nodes": [], "add_edges": []}

    def read_node(self, node_id: str) -> dict[str, Any]:
        return dict(self._nodes[node_id])

    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        return [dict(e) for e in self._edges if e["source"] == node_id]

    def write_modification(self, modification: Modification) -> None:
        self._pending["add_nodes"].extend(modification.get("add_nodes", []))
        self._pending["add_edges"].extend(modification.get("add_edges", []))

    def persist(self) -> None:
        for n in self._pending["add_nodes"]:
            self._nodes[n["id"]] = dict(n)
        for e in self._pending["add_edges"]:
            self._edges.append(dict(e))
        self._pending = {"add_nodes": [], "add_edges": []}

    def export_canonical(self) -> dict[str, Any]:
        return canonical(list(self._nodes.values()), self._edges)
