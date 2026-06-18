# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-206: API-Mediated Self-Modification — Condition D (API over a persistent store).

The API service boundary is composed over a PERSISTENT-STORE backend: the
service writes the agent's requested modifications into a relational store
(stdlib sqlite3, in-memory — definitively not a serialized file), and reads
serve nodes/edges back out of it via queries. This puts the maximum
architectural distance from the direct-write baseline: the write crosses a
service boundary AND lands in a non-file store, yet the agent still decides WHAT
to modify and the modification is still structurally live for the next step.

Condition D is COMPOSITIONAL: it reuses Condition B's WriteMediatedClient (the
agent's accessor; reads in-process via the service, writes as serialized
requests) over a sqlite-backed service that satisfies the same service contract.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import sqlite3


class SqliteWriteService:
    """Sole holder + sole mutator of the substrate, backed by a relational
    persistent store. Satisfies the same read/submit contract as the in-process
    WriteService, so Condition B's client composes over it unchanged. A dumb
    transport: it applies the op named in the serialized request; it never sees
    the execution result or the routing decision."""

    def __init__(self, graph):
        self._conn = sqlite3.connect(":memory:")
        self._conn.execute(
            "CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT, op TEXT, data TEXT)")
        self._conn.execute(
            "CREATE TABLE edges (source_id TEXT, target_id TEXT, "
            "relation TEXT, condition TEXT)")
        for n in graph["nodes"]:
            self._conn.execute(
                "INSERT INTO nodes VALUES (?, ?, ?, ?)",
                (n["id"], n["type"], n.get("op"), json.dumps(n.get("data", {}))))
        for e in graph["edges"]:
            self._conn.execute(
                "INSERT INTO edges VALUES (?, ?, ?, ?)",
                (e["source_id"], e["target_id"], e["relation"],
                 json.dumps(e["condition"]) if e.get("condition") is not None else None))
        self._conn.commit()

    def _row_to_edge(self, row):
        edge = {"source_id": row[0], "target_id": row[1], "relation": row[2]}
        if row[3] is not None:
            edge["condition"] = json.loads(row[3])
        return edge

    # --- read surface (via SQL queries, not file parsing) ---
    def read_node(self, node_id):
        row = self._conn.execute(
            "SELECT id, type, op, data FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "type": row[1], "op": row[2], "data": json.loads(row[3])}

    def read_outgoing_edges(self, node_id):
        rows = self._conn.execute(
            "SELECT source_id, target_id, relation, condition FROM edges "
            "WHERE source_id = ?", (node_id,)).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def snapshot(self):
        nodes = [
            {"id": r[0], "type": r[1], "op": r[2], "data": json.loads(r[3])}
            for r in self._conn.execute("SELECT id, type, op, data FROM nodes")
        ]
        edges = [
            self._row_to_edge(r) for r in self._conn.execute(
                "SELECT source_id, target_id, relation, condition FROM edges")
        ]
        return {"nodes": nodes, "edges": edges}

    def node_count(self):
        return self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def edge_count(self):
        return self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    # --- write surface: ONLY a serialized request crosses here ---
    def submit(self, request_json):
        request = json.loads(request_json)
        op = request.get("op")
        if op == "add_node":
            n = request["node"]
            self._conn.execute("INSERT INTO nodes VALUES (?, ?, ?, ?)",
                               (n["id"], n["type"], n.get("op"), json.dumps(n.get("data", {}))))
        elif op == "add_edge":
            e = request["edge"]
            self._conn.execute("INSERT INTO edges VALUES (?, ?, ?, ?)",
                               (e["source_id"], e["target_id"], e["relation"],
                                json.dumps(e["condition"]) if e.get("condition") is not None else None))
        elif op == "remove_edge":
            self._conn.execute(
                "DELETE FROM edges WHERE source_id = ? AND target_id = ? "
                "AND relation = ?", (request["src"], request["tgt"], request["rel"]))
        else:
            raise ValueError("unknown write op: %r" % op)
        self._conn.commit()
        return {"ack": True}


def run(initial_graph, baseline_state=None):
    """Run Condition D. Returns {condition, metrics, final_state}."""
    from baseline_direct_write import run_agent, compute_metrics
    from api_mediated_write import WriteMediatedClient

    service = SqliteWriteService(initial_graph)
    client = WriteMediatedClient(service)  # compositional reuse of Condition B's client
    init_counts = (client.node_count(), client.edge_count())
    evidence = run_agent(client)
    final_graph = service.snapshot()
    evidence["audit_traversed"] = (
        evidence["audit_traversed"]
        and any(n["id"] == "audit" for n in final_graph["nodes"]))
    metrics, fstate = compute_metrics(final_graph, init_counts,
                                      evidence, baseline_state)
    metrics["persistent_store"] = "relational (sqlite, in-memory)"
    return {"condition": "D", "metrics": metrics, "final_state": fstate}


if __name__ == "__main__":
    import sys
    from baseline_direct_write import load_graph
    from pathlib import Path
    res = run(load_graph(Path(__file__).parent / "graph_initial.json"))
    m = res["metrics"]
    print("STUDY-206 Condition D — API boundary over a persistent store")
    for key, value in m.items():
        if key != "evidence":
            print("  %s: %s" % (key, value))
    ok = (m["decision_locus"] == "agent" and m["self_modification"]
          and (m["node_count_delta"] or m["edge_count_delta"]))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
