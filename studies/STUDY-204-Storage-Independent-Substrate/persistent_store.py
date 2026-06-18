# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-204: Condition B — relational persistent store.

The graph substrate is held in a relational store: nodes as rows in a node table,
edges as rows in an edge table. The agent reads the current node and its outgoing
edges via SQL ``SELECT`` and writes the self-modification via ``INSERT`` — never by
parsing a serialized graph file. The baseline is loaded into the store once at
setup; every traversal-time access is a query.

This is the answer to the "SQLite is technically a file" objection on the
*access-pattern* ground: the agent issues SQL against rows, it does not deserialize
a JSON document. (Condition C removes even the residual file-similarity entirely.)

The traversal agent, edge router, metrics, and equivalence comparison are imported
unchanged from ``baseline_file`` — only the store differs. Rows carry the shared
schema (node ``op``/``data``; edge ``source_id``/``target_id``/``relation``/``condition``).
"""

from __future__ import annotations

import json
import sqlite3

from baseline_file import (
    baseline_counts,
    canonical_snapshot,
    compute_metrics,
    entry_id,
    load_baseline,
    traverse,
    GRAPH_INITIAL_PATH,
)


class SqliteStore:
    """Relational store: nodes/edges as table rows; reads via SELECT, writes via
    INSERT/UPDATE/DELETE. ``query_count`` records that traversal is query-driven;
    ``file_parses`` stays 0 — the graph is never re-parsed from a file at run time."""

    access_pattern = "relational_sql"

    def __init__(self, baseline: dict, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.query_count = 0
        self.file_parses = 0  # invariant: 0 — no graph-file parsing during traversal
        self._init_schema()
        self._load_baseline(baseline)

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE nodes (
                id    TEXT PRIMARY KEY,
                type  TEXT NOT NULL,
                op    TEXT,
                data  TEXT NOT NULL,
                ord   INTEGER NOT NULL
            );
            CREATE TABLE edges (
                rowid     INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation  TEXT NOT NULL,
                condition TEXT,
                ord       INTEGER NOT NULL
            );
            """
        )
        self.conn.commit()

    def _load_baseline(self, baseline: dict) -> None:
        for i, n in enumerate(baseline["nodes"]):
            self.conn.execute(
                "INSERT INTO nodes (id, type, op, data, ord) VALUES (?, ?, ?, ?, ?)",
                (n["id"], n["type"], n.get("op"), json.dumps(n.get("data", {})), i),
            )
        for i, e in enumerate(baseline["edges"]):
            self.conn.execute(
                "INSERT INTO edges (source_id, target_id, relation, condition, ord) VALUES (?, ?, ?, ?, ?)",
                (e["source_id"], e["target_id"], e["relation"], json.dumps(e.get("condition")), i),
            )
        self.conn.commit()

    # --- reads: SQL SELECT, not file parsing ---

    def read_node(self, node_id: str) -> dict | None:
        self.query_count += 1
        row = self.conn.execute(
            "SELECT id, type, op, data FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "type": row[1], "op": row[2], "data": json.loads(row[3])}

    def has_node(self, node_id: str) -> bool:
        self.query_count += 1
        return self.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (node_id,)
        ).fetchone() is not None

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        self.query_count += 1
        rows = self.conn.execute(
            "SELECT source_id, target_id, relation, condition FROM edges WHERE source_id = ? ORDER BY ord, rowid",
            (node_id,),
        ).fetchall()
        return [
            {"source_id": r[0], "target_id": r[1], "relation": r[2], "condition": json.loads(r[3])}
            for r in rows
        ]

    # --- writes: SQL INSERT/UPDATE/DELETE ---

    def write_node(self, node: dict) -> None:
        self.query_count += 1
        exists = self.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (node["id"],)
        ).fetchone() is not None
        if exists:
            self.conn.execute(
                "UPDATE nodes SET type = ?, op = ?, data = ? WHERE id = ?",
                (node["type"], node.get("op"), json.dumps(node.get("data", {})), node["id"]),
            )
        else:
            next_ord = self.conn.execute(
                "SELECT COALESCE(MAX(ord), -1) + 1 FROM nodes"
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO nodes (id, type, op, data, ord) VALUES (?, ?, ?, ?, ?)",
                (node["id"], node["type"], node.get("op"), json.dumps(node.get("data", {})), next_ord),
            )
        self.conn.commit()

    def add_edge(self, edge: dict) -> None:
        self.query_count += 1
        next_ord = self.conn.execute(
            "SELECT COALESCE(MAX(ord), -1) + 1 FROM edges"
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO edges (source_id, target_id, relation, condition, ord) VALUES (?, ?, ?, ?, ?)",
            (edge["source_id"], edge["target_id"], edge["relation"],
             json.dumps(edge.get("condition")), next_ord),
        )
        self.conn.commit()

    def remove_node(self, node_id: str) -> None:
        self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.conn.commit()

    def remove_edge(self, source: str, target: str) -> None:
        self.conn.execute("DELETE FROM edges WHERE source_id = ? AND target_id = ?", (source, target))
        self.conn.commit()

    def node_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def edge_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    def snapshot(self) -> dict:
        node_rows = self.conn.execute("SELECT id, type, op, data FROM nodes").fetchall()
        edge_rows = self.conn.execute(
            "SELECT source_id, target_id, relation, condition FROM edges"
        ).fetchall()
        nodes = [{"id": r[0], "type": r[1], "op": r[2], "data": json.loads(r[3])} for r in node_rows]
        edges = [
            {"source_id": r[0], "target_id": r[1], "relation": r[2], "condition": json.loads(r[3])}
            for r in edge_rows
        ]
        return canonical_snapshot(nodes, edges)


def run_condition_b(graph_initial: str = GRAPH_INITIAL_PATH, db_path: str = ":memory:") -> dict:
    baseline = load_baseline(graph_initial)
    initial = baseline_counts(baseline)
    store = SqliteStore(baseline, db_path)
    record = traverse(store, entry_id(baseline))
    snapshot = store.snapshot()
    return {"condition": "B", "store": store, "record": record,
            "snapshot": snapshot, "initial": initial}


if __name__ == "__main__":
    import sys

    # Condition A baseline to compare against.
    import tempfile
    from baseline_file import run_condition_a

    with tempfile.TemporaryDirectory(prefix="study_204_b_") as tmp:
        a = run_condition_a(tmp)
        baseline_snapshot = a["snapshot"]

    b = run_condition_b()
    metrics = compute_metrics(b["store"], b["record"], b["initial"], baseline_snapshot)

    print("=" * 64)
    print("STUDY-204 — Condition B (relational persistent store)")
    print("=" * 64)
    print(f"  visited:        {' -> '.join(b['record']['visited'])}")
    print(f"  final_acc:      {b['record']['final_acc']}")
    print(f"  SQL queries:    {b['store'].query_count}")
    print(f"  file parses:    {b['store'].file_parses}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    ok = (
        metrics["functional_equivalence"]
        and b["store"].query_count > 0
        and b["store"].file_parses == 0
        and metrics["node_count_delta"] == 1
        and metrics["edge_count_delta"] == 2
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
