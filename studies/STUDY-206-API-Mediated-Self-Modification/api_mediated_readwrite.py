# AGPL-3.0 | Patent Pending (app 19/575,491)
"""STUDY-206: API-Mediated Self-Modification — Condition C (API-mediated read+write).

BOTH node-content reads AND topology writes cross the service boundary, and the
boundary is a GENUINE operating-system process boundary: the service runs in a
separate process (stdlib multiprocessing) holding the only copy of the
substrate. The agent has no storage handle at all — only a request channel and a
response channel. Every read and every write is a serialized request that
crosses the process boundary; the response crosses back.

This is the condition that structurally defeats the "an in-process API is just a
function call" objection: the agent and the service do not share an address
space, so the write cannot be a disguised local mutation. Structural-liveness is
shown across the real boundary — a modification written at one step is returned
by the very next read with no process restart or recompilation.

The worker is a dumb transport: it applies the op named in each request; it
never receives the execution result or the routing decision.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import multiprocessing
import os

# An explicit 'fork' context so a Queue can be passed to the worker as an
# argument (inheritance) regardless of the interpreter's default start method.
_CTX = multiprocessing.get_context("fork")


def _service_worker(request_q, response_q, initial_graph):
    """Runs in a SEPARATE process. Holds this process's own copy of the
    substrate and answers serialized read/write requests until told to stop.
    Reads only `op` + payload from each request — never a result or decision."""
    graph = initial_graph
    while True:
        request = json.loads(request_q.get())
        op = request.get("op")
        if op == "shutdown":
            response_q.put(json.dumps({"ack": True}))
            return
        if op == "pid":
            response_q.put(json.dumps({"pid": os.getpid()}))
        elif op == "get_node":
            node = next((n for n in graph["nodes"] if n["id"] == request["id"]), None)
            response_q.put(json.dumps({"node": node}))
        elif op == "outgoing_edges":
            edges = [e for e in graph["edges"] if e["source_id"] == request["id"]]
            response_q.put(json.dumps({"edges": edges}))
        elif op == "add_node":
            graph["nodes"].append(request["node"])
            response_q.put(json.dumps({"ack": True}))
        elif op == "add_edge":
            graph["edges"].append(request["edge"])
            response_q.put(json.dumps({"ack": True}))
        elif op == "remove_edge":
            src, tgt, rel = request["src"], request["tgt"], request["rel"]
            graph["edges"] = [
                e for e in graph["edges"]
                if not (e["source_id"] == src and e["target_id"] == tgt
                        and e["relation"] == rel)
            ]
            response_q.put(json.dumps({"ack": True}))
        elif op == "snapshot":
            response_q.put(json.dumps({"graph": graph}))
        elif op == "counts":
            response_q.put(json.dumps(
                {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}))
        else:
            response_q.put(json.dumps({"error": "unknown op: %r" % op}))


class ProcessMediatedClient:
    """The agent's accessor in Condition C. Holds NO substrate — only the two
    channels. Every read and every write is a serialized request across the
    process boundary."""

    def __init__(self, request_q, response_q):
        self._request_q = request_q
        self._response_q = response_q

    def _call(self, request):
        self._request_q.put(json.dumps(request))
        return json.loads(self._response_q.get(timeout=30))

    def get_node(self, node_id):
        return self._call({"op": "get_node", "id": node_id})["node"]

    def outgoing_edges(self, node_id):
        return self._call({"op": "outgoing_edges", "id": node_id})["edges"]

    def add_node(self, node):
        self._call({"op": "add_node", "node": node})

    def add_edge(self, edge):
        self._call({"op": "add_edge", "edge": edge})

    def remove_edge(self, source, target, relation):
        self._call({"op": "remove_edge", "src": source, "tgt": target, "rel": relation})

    def node_count(self):
        return self._call({"op": "counts"})["nodes"]

    def edge_count(self):
        return self._call({"op": "counts"})["edges"]

    def snapshot(self):
        return self._call({"op": "snapshot"})["graph"]

    def service_pid(self):
        return self._call({"op": "pid"})["pid"]


def run(initial_graph, baseline_state=None):
    """Run Condition C. Returns {condition, metrics, final_state}; metrics carry
    `process_boundary_crossed` evidence (service PID != agent PID)."""
    from baseline_direct_write import run_agent, compute_metrics

    request_q = _CTX.Queue()
    response_q = _CTX.Queue()
    worker = _CTX.Process(
        target=_service_worker,
        args=(request_q, response_q, json.loads(json.dumps(initial_graph))),
    )
    worker.start()
    try:
        client = ProcessMediatedClient(request_q, response_q)
        service_pid = client.service_pid()
        agent_pid = os.getpid()
        init_counts = (client.node_count(), client.edge_count())
        evidence = run_agent(client)
        final_graph = client.snapshot()
    finally:
        try:
            request_q.put(json.dumps({"op": "shutdown"}))
            response_q.get(timeout=5)
        except Exception:
            pass
        worker.join(timeout=10)
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    evidence["audit_traversed"] = (
        evidence["audit_traversed"]
        and any(n["id"] == "audit" for n in final_graph["nodes"]))
    metrics, fstate = compute_metrics(final_graph, init_counts,
                                      evidence, baseline_state)
    metrics["process_boundary_crossed"] = service_pid != agent_pid
    metrics["evidence"]["service_pid"] = service_pid
    metrics["evidence"]["agent_pid"] = agent_pid
    return {"condition": "C", "metrics": metrics, "final_state": fstate}


if __name__ == "__main__":
    import sys
    from baseline_direct_write import load_graph
    from pathlib import Path
    res = run(load_graph(Path(__file__).parent / "graph_initial.json"))
    m = res["metrics"]
    print("STUDY-206 Condition C — API-mediated read+write (real process boundary)")
    for key, value in m.items():
        if key != "evidence":
            print("  %s: %s" % (key, value))
    ok = (m["decision_locus"] == "agent" and m["self_modification"]
          and m.get("process_boundary_crossed")
          and (m["node_count_delta"] or m["edge_count_delta"]))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
