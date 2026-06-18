"""STUDY-208 Backend C — relational store (stdlib sqlite3).

Implements the substrate contract over a relational store: a node table and an
edge table. Nodes and edges are read via SELECT and written via INSERT; persist()
commits the transaction. This is a genuinely different ACCESS PATTERN from parsing
a serialized graph file — the answer to "a relational store is technically still
a file" is the access pattern (rows via query), not the storage medium. No live
external database server: sqlite3 is embedded stdlib. This backend implements the
contract and nothing more.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from substrate_contract import Modification, SubstrateContract, canonical


class RelationalBackend(SubstrateContract):

    def __init__(self, initial: dict[str, Any], workdir: Path) -> None:
        self.conn = sqlite3.connect(str(Path(workdir) / "substrate.db"))
        self.reads_via_query = 0  # evidence the read path issues SQL, not file parsing
        self._pending: Modification = {"add_nodes": [], "add_edges": []}
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT, op TEXT)")
        cur.execute(
            "CREATE TABLE edges (eid INTEGER PRIMARY KEY AUTOINCREMENT, "
            "source TEXT, target TEXT, relation TEXT, condition TEXT)"
        )
        cur.executemany(
            "INSERT INTO nodes (id, type, op) VALUES (?, ?, ?)",
            [(n["id"], n["type"], n["op"]) for n in initial["nodes"]],
        )
        cur.executemany(
            "INSERT INTO edges (source, target, relation, condition) VALUES (?, ?, ?, ?)",
            [(e["source"], e["target"], e["relation"], e.get("condition"))
             for e in initial["edges"]],
        )
        self.conn.commit()

    def read_node(self, node_id: str) -> dict[str, Any]:
        self.reads_via_query += 1
        row = self.conn.execute(
            "SELECT id, type, op FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            raise KeyError(node_id)
        return {"id": row[0], "type": row[1], "op": row[2]}

    def get_outgoing_edges(self, node_id: str) -> list[dict[str, Any]]:
        self.reads_via_query += 1
        rows = self.conn.execute(
            "SELECT source, target, relation, condition FROM edges WHERE source = ?",
            (node_id,),
        ).fetchall()
        return [{"source": r[0], "target": r[1], "relation": r[2], "condition": r[3]}
                for r in rows]

    def write_modification(self, modification: Modification) -> None:
        self._pending["add_nodes"].extend(modification.get("add_nodes", []))
        self._pending["add_edges"].extend(modification.get("add_edges", []))

    def persist(self) -> None:
        cur = self.conn.cursor()
        for n in self._pending["add_nodes"]:
            cur.execute(
                "INSERT OR REPLACE INTO nodes (id, type, op) VALUES (?, ?, ?)",
                (n["id"], n["type"], n["op"]),
            )
        for e in self._pending["add_edges"]:
            cur.execute(
                "INSERT INTO edges (source, target, relation, condition) "
                "VALUES (?, ?, ?, ?)",
                (e["source"], e["target"], e["relation"], e.get("condition")),
            )
        self.conn.commit()
        self._pending = {"add_nodes": [], "add_edges": []}

    def export_canonical(self) -> dict[str, Any]:
        nodes = [{"id": r[0], "type": r[1], "op": r[2]}
                 for r in self.conn.execute("SELECT id, type, op FROM nodes")]
        edges = [{"source": r[0], "target": r[1], "relation": r[2], "condition": r[3]}
                 for r in self.conn.execute(
                     "SELECT source, target, relation, condition FROM edges")]
        return canonical(nodes, edges)
