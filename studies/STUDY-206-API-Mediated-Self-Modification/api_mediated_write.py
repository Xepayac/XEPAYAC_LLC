# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-206: API-Mediated Self-Modification — Condition B (API-mediated write).

The agent computes the result-driven modification and ISSUES IT AS A SERIALIZED
REQUEST across a service boundary; a separate WriteService — the sole holder of
the substrate and the sole component that mutates it — performs the write. The
agent never mutates the substrate directly; its only write capability is to
submit a request. Reads are local (in-process) in this condition; only writes
cross the boundary.

The WriteService is a DUMB TRANSPORT: it applies the operation named in the
request and nothing more. It has no reference to the agent, the execution
result, or the routing decision — so the decision-locus cannot move off the
agent. (Adversarially verified in test_equivalence.py::TestServiceNoDecide.)

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json


class WriteService:
    """Sole holder + sole mutator of the substrate. The write surface accepts
    only a serialized request (operation + payload); there is no surface through
    which the execution result or routing decision could reach the service."""

    # The complete set of keys a write request may carry. The execution result
    # and the routing decision are deliberately NOT among them.
    _ALLOWED_REQUEST_KEYS = {"op", "node", "edge", "src", "tgt", "rel"}

    def __init__(self, graph):
        # The service's own copy of the substrate is the only mutable store.
        self._graph = json.loads(json.dumps(graph))

    # --- read surface (in-process; used directly by the client in Condition B) ---
    def read_node(self, node_id):
        return next((n for n in self._graph["nodes"] if n["id"] == node_id), None)

    def read_outgoing_edges(self, node_id):
        return [e for e in self._graph["edges"] if e["source_id"] == node_id]

    def snapshot(self):
        return json.loads(json.dumps(self._graph))

    def node_count(self):
        return len(self._graph["nodes"])

    def edge_count(self):
        return len(self._graph["edges"])

    # --- write surface: ONLY a serialized request crosses here ---
    def submit(self, request_json):
        """Apply a serialized write request. The service reads ONLY `op` and the
        payload keys; any other field present in the request is ignored — the
        service is structurally incapable of 'deciding' what to modify."""
        request = json.loads(request_json)
        op = request.get("op")
        if op == "add_node":
            self._graph["nodes"].append(request["node"])
        elif op == "add_edge":
            self._graph["edges"].append(request["edge"])
        elif op == "remove_edge":
            src, tgt, rel = request["src"], request["tgt"], request["rel"]
            self._graph["edges"] = [
                e for e in self._graph["edges"]
                if not (e["source_id"] == src and e["target_id"] == tgt
                        and e["relation"] == rel)
            ]
        else:
            raise ValueError("unknown write op: %r" % op)
        return {"ack": True}


class WriteMediatedClient:
    """The agent's accessor in Condition B (also reused by Condition D over a
    persistent-store backend). Reads go directly to the service (in-process);
    every WRITE is serialized to a request and submitted across the boundary.
    The client holds no mutate-the-graph capability of its own."""

    def __init__(self, service):
        self._service = service

    def get_node(self, node_id):
        return self._service.read_node(node_id)

    def outgoing_edges(self, node_id):
        return self._service.read_outgoing_edges(node_id)

    def add_node(self, node):
        self._service.submit(json.dumps({"op": "add_node", "node": node}))

    def add_edge(self, edge):
        self._service.submit(json.dumps({"op": "add_edge", "edge": edge}))

    def remove_edge(self, source, target, relation):
        self._service.submit(json.dumps(
            {"op": "remove_edge", "src": source, "tgt": target, "rel": relation}))

    def node_count(self):
        return self._service.node_count()

    def edge_count(self):
        return self._service.edge_count()

    def snapshot(self):
        return self._service.snapshot()


def run(initial_graph, baseline_state=None):
    """Run Condition B. Returns {condition, metrics, final_state}."""
    # Intra-study local import: keeps module-top imports stdlib-only so the
    # CQ-2 third-party-dependency gate stays meaningful (these are sibling
    # study modules, not external packages).
    from baseline_direct_write import run_agent, compute_metrics

    service = WriteService(initial_graph)
    client = WriteMediatedClient(service)
    init_counts = (client.node_count(), client.edge_count())
    evidence = run_agent(client)
    final_graph = service.snapshot()
    # Persistence: the service still holds the modification after the run, so it
    # governs any subsequent traversal (verified live during the run too).
    evidence["audit_traversed"] = (
        evidence["audit_traversed"]
        and any(n["id"] == "audit" for n in final_graph["nodes"]))
    metrics, fstate = compute_metrics(final_graph, init_counts,
                                      evidence, baseline_state)
    return {"condition": "B", "metrics": metrics, "final_state": fstate}


if __name__ == "__main__":
    import sys
    from baseline_direct_write import load_graph
    from pathlib import Path
    res = run(load_graph(Path(__file__).parent / "graph_initial.json"))
    m = res["metrics"]
    print("STUDY-206 Condition B — API-mediated write")
    for key, value in m.items():
        if key != "evidence":
            print("  %s: %s" % (key, value))
    ok = (m["decision_locus"] == "agent" and m["self_modification"]
          and (m["node_count_delta"] or m["edge_count_delta"]))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
