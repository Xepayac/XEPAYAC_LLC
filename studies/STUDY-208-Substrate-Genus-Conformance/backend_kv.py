"""STUDY-208 Backend D — key-value store.

Implements the substrate contract over a key-value store: each node lives under
the key `node:<id>`, and each node's outgoing edges live under `edges:<source>`.
Access is by point key lookup — the backend never loads or parses "the graph",
only the value at a key. The store is persisted to a single key->value file as
its durability medium; reads come from the committed key space. This backend
implements the contract and nothing more.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from substrate_contract import Modification, SubstrateContract, canonical


class KeyValueBackend(SubstrateContract):

    def __init__(self, initial: dict[str, Any], workdir: Path) -> None:
        self.path = Path(workdir) / "substrate.kv.json"
        self._store: dict[str, Any] = {}          # committed key space
        self._pending: Modification = {"add_nodes": [], "add_edges": []}
        self._index_key = "index:node_ids"
        node_ids: list[str] = []
        for n in initial["nodes"]:
            self._store[f"node:{n['id']}"] = n
            node_ids.append(n["id"])
        for e in initial["edges"]:
            self._store.setdefault(f"edges:{e['source']}", []).append(e)
        self._store[self._index_key] = node_ids
        self._flush()

    def _flush(self) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2)

    def read_node(self, node_id: str) -> dict[str, Any]:
        value = self._store.get(f"node:{node_id}")
        if value is None:
            raise KeyError(node_id)
        return value

    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        return list(self._store.get(f"edges:{node_id}", []))

    def write_modification(self, modification: Modification) -> None:
        self._pending["add_nodes"].extend(modification.get("add_nodes", []))
        self._pending["add_edges"].extend(modification.get("add_edges", []))

    def persist(self) -> None:
        node_ids = list(self._store[self._index_key])
        for n in self._pending["add_nodes"]:
            self._store[f"node:{n['id']}"] = n
            if n["id"] not in node_ids:
                node_ids.append(n["id"])
        for e in self._pending["add_edges"]:
            self._store.setdefault(f"edges:{e['source']}", []).append(e)
        self._store[self._index_key] = node_ids
        self._flush()
        self._pending = {"add_nodes": [], "add_edges": []}

    def export_canonical(self) -> dict[str, Any]:
        nodes = [self._store[f"node:{nid}"] for nid in self._store[self._index_key]]
        edges: list[dict] = []
        for key, value in self._store.items():
            if key.startswith("edges:"):
                edges.extend(value)
        return canonical(nodes, edges)
