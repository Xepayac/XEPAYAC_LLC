"""STUDY-208 Backend B — multiple serialized files + cross-file edges.

Implements the substrate contract over a connected set of files: one file per
node under nodes/, and edges grouped by source under edges/. An edge in one
source's file references a target node living in a different file — a cross-file
edge. The store is the union of all files. This backend implements the contract
and nothing more.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from substrate_contract import Modification, SubstrateContract, canonical


class MultiFileBackend(SubstrateContract):

    def __init__(self, initial: dict[str, Any], workdir: Path) -> None:
        self.root = Path(workdir)
        self.ndir = self.root / "nodes"
        self.edir = self.root / "edges"
        self.ndir.mkdir(parents=True, exist_ok=True)
        self.edir.mkdir(parents=True, exist_ok=True)
        self._pending: Modification = {"add_nodes": [], "add_edges": []}
        for node in initial["nodes"]:
            self._write_node(node)
        for edge in initial["edges"]:
            self._append_edge(edge)

    def _write_node(self, node: dict) -> None:
        with (self.ndir / f"{node['id']}.json").open("w", encoding="utf-8") as f:
            json.dump(node, f, indent=2)

    def _append_edge(self, edge: dict) -> None:
        path = self.edir / f"{edge['source']}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        existing.append(edge)
        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

    def read_node(self, node_id: str) -> dict[str, Any]:
        path = self.ndir / f"{node_id}.json"
        if not path.exists():
            raise KeyError(node_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        path = self.edir / f"{node_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def write_modification(self, modification: Modification) -> None:
        self._pending["add_nodes"].extend(modification.get("add_nodes", []))
        self._pending["add_edges"].extend(modification.get("add_edges", []))

    def persist(self) -> None:
        for node in self._pending["add_nodes"]:
            self._write_node(node)
        for edge in self._pending["add_edges"]:
            self._append_edge(edge)
        self._pending = {"add_nodes": [], "add_edges": []}

    def export_canonical(self) -> dict[str, Any]:
        nodes = [json.loads(p.read_text(encoding="utf-8"))
                 for p in self.ndir.glob("*.json")]
        edges: list[dict] = []
        for p in self.edir.glob("*.json"):
            edges.extend(json.loads(p.read_text(encoding="utf-8")))
        return canonical(nodes, edges)
