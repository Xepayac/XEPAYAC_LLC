"""STUDY-208 Backend A — single serialized file (the EGS-979 L1 anchor).

Implements the substrate contract over ONE JSON file. The file is the store:
reads load it, persist() writes it. A's final state is the baseline every other
backend is compared against. This backend implements the contract and nothing
more — no traversal, routing, or execution logic lives here.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from substrate_contract import Modification, SubstrateContract, canonical


class FileBackend(SubstrateContract):

    def __init__(self, initial: dict[str, Any], workdir: Path) -> None:
        self.path = Path(workdir) / "substrate.json"
        self._pending: Modification = {"add_nodes": [], "add_edges": []}
        self._dump(initial["nodes"], initial["edges"])

    def _dump(self, nodes: list[dict], edges: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

    def _load(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def read_node(self, node_id: str) -> dict[str, Any]:
        for n in self._load()["nodes"]:
            if n["id"] == node_id:
                return n
        raise KeyError(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        return [e for e in self._load()["edges"] if e["source"] == node_id]

    def write_modification(self, modification: Modification) -> None:
        self._pending["add_nodes"].extend(modification.get("add_nodes", []))
        self._pending["add_edges"].extend(modification.get("add_edges", []))

    def persist(self) -> None:
        data = self._load()
        data["nodes"].extend(self._pending["add_nodes"])
        data["edges"].extend(self._pending["add_edges"])
        self._dump(data["nodes"], data["edges"])
        self._pending = {"add_nodes": [], "add_edges": []}

    def export_canonical(self) -> dict[str, Any]:
        data = self._load()
        return canonical(data["nodes"], data["edges"])
