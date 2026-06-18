"""STUDY-209: Networked / Distributed Substrate — Condition B (networked store).

AGPL-3.0 | Patent Pending (app 19/575,491)

The substrate is held by a store service running in a SEPARATE OS process,
reached over a 127.0.0.1 loopback socket. The agent (this process) reads nodes
and outgoing edges, and writes its in-traversal self-modification, entirely
OVER THE BOUNDARY. A subsequent traversal step then operates on the
remotely-persisted, modified substrate — with no recompile, redeploy, or
restart between the remote write and its effect.

Two properties are load-bearing and asserted here, not assumed:

  * Embodiment-only — the store is a DUMB persistence locus. It exposes only
    read/write commands (read_node / has_node / get_outgoing_edges /
    write_modification / all_nodes / all_edges). It performs NO execution, NO
    routing, NO edge selection. The agent imported here is, byte-for-byte, the
    SAME ``Agent`` Condition A used; only the store's locus changed.
  * Structural liveness across the boundary — the modification written over the
    wire is immediately live: the agent re-reads the outgoing edges from the
    remote store and the next step walks the freshly-persisted edge.

Self-contained: a localhost loopback socket to this same module run as a
subprocess. No external server, no third-party package, stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import socket
import socketserver
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator, Optional

from baseline_local import (  # the SAME mechanism — unchanged across conditions
    GRAPH_INITIAL,
    Agent,
    LocalStore,
    Store,
    canonical_state,
    load_graph,
    metric_block,
)

HOST = "127.0.0.1"
_CONNECT_TIMEOUT_S = 10.0


# --------------------------------------------------------------------------- #
# Wire protocol — newline-delimited JSON request / response
# --------------------------------------------------------------------------- #
class _StoreHandler(socketserver.StreamRequestHandler):
    """Dispatches read/write commands to the server's dumb LocalStore.

    Note what is absent: there is no 'route', 'select', 'next', or 'execute'
    command. The store cannot make a control-flow decision — only persist and
    return data. That absence is the embodiment-only invariant, on the wire.
    """

    def handle(self) -> None:
        store: LocalStore = self.server.store  # type: ignore[attr-defined]
        for raw in self.rfile:
            try:
                req = json.loads(raw.decode("utf-8"))
                cmd = req["cmd"]
                if cmd == "read_node":
                    resp = {"ok": True, "result": store.read_node(req["id"])}
                elif cmd == "has_node":
                    resp = {"ok": True, "result": store.has_node(req["id"])}
                elif cmd == "get_outgoing_edges":
                    resp = {"ok": True, "result": store.get_outgoing_edges(req["id"])}
                elif cmd == "write_modification":
                    store.write_modification(req["modification"])
                    resp = {"ok": True, "result": None}
                elif cmd == "all_nodes":
                    resp = {"ok": True, "result": store.all_nodes()}
                elif cmd == "all_edges":
                    resp = {"ok": True, "result": store.all_edges()}
                elif cmd == "ping":
                    resp = {"ok": True, "result": "pong"}
                else:
                    resp = {"ok": False, "error": f"unknown cmd {cmd!r}"}
            except Exception as exc:  # noqa: BLE001 — report errors over the wire
                resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
            self.wfile.flush()


class _StoreServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _serve(graph_path: str, port_file: str) -> None:
    """Subprocess entry point: bind an ephemeral loopback port, publish it, and
    serve the substrate from a dumb in-memory LocalStore until killed."""
    graph = load_graph(Path(graph_path))
    server = _StoreServer((HOST, 0), _StoreHandler)
    server.store = LocalStore(graph)  # type: ignore[attr-defined]
    port = server.server_address[1]
    Path(port_file).write_text(str(port), encoding="utf-8")
    try:
        server.serve_forever()
    finally:  # pragma: no cover
        server.server_close()


# --------------------------------------------------------------------------- #
# Client — the agent's view of the remote store (satisfies the Store contract)
# --------------------------------------------------------------------------- #
class NetworkedStore(Store):
    """A client to a store service on a separate process, reached over a
    loopback socket. Holds ONLY a socket — never an in-process handle to the
    substrate data. Every method is one request/response round-trip over the
    boundary."""

    def __init__(self, host: str, port: int,
                 proc: Optional[subprocess.Popen] = None) -> None:
        self.host = host
        self.port = port
        self.proc = proc
        self._sock = socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT_S)
        self._rfile = self._sock.makefile("rb")

    @property
    def server_pid(self) -> Optional[int]:
        return self.proc.pid if self.proc is not None else None

    def _call(self, **req) -> object:
        self._sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
        line = self._rfile.readline()
        if not line:
            raise ConnectionError("store service closed the connection")
        resp = json.loads(line.decode("utf-8"))
        if not resp.get("ok"):
            raise RuntimeError(f"store error: {resp.get('error')}")
        return resp["result"]

    # --- the dumb persistence contract, each call crossing the boundary ---
    def read_node(self, node_id: str) -> dict:
        return self._call(cmd="read_node", id=node_id)  # type: ignore[return-value]

    def has_node(self, node_id: str) -> bool:
        return bool(self._call(cmd="has_node", id=node_id))

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        return self._call(cmd="get_outgoing_edges", id=node_id)  # type: ignore[return-value]

    def write_modification(self, modification: dict) -> None:
        self._call(cmd="write_modification", modification=modification)

    def all_nodes(self) -> list[dict]:
        return self._call(cmd="all_nodes")  # type: ignore[return-value]

    def all_edges(self) -> list[dict]:
        return self._call(cmd="all_edges")  # type: ignore[return-value]

    def ping(self) -> str:
        return self._call(cmd="ping")  # type: ignore[return-value]

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._rfile.close()
        with contextlib.suppress(Exception):
            self._sock.close()


@contextlib.contextmanager
def store_subprocess(graph_path: Path) -> Iterator[NetworkedStore]:
    """Spawn the store as a separate OS process and yield a connected client.
    Tears the process down on exit. This is a genuine network boundary on the
    loopback interface, reproducible with stdlib only."""
    tmp = tempfile.NamedTemporaryFile(prefix="study209_port_", suffix=".txt", delete=False)
    port_file = Path(tmp.name)
    tmp.close()
    port_file.write_text("", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()),
         "serve", "--graph", str(Path(graph_path).resolve()),
         "--port-file", str(port_file)],
        cwd=str(Path(__file__).resolve().parent),
    )
    client: Optional[NetworkedStore] = None
    try:
        deadline = time.monotonic() + _CONNECT_TIMEOUT_S
        port: Optional[int] = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"store service exited early (rc={proc.returncode})")
            text = port_file.read_text(encoding="utf-8").strip()
            if text:
                port = int(text)
                break
            time.sleep(0.02)
        if port is None:
            raise TimeoutError("store service did not publish a port in time")
        client = NetworkedStore(HOST, port, proc)
        client.ping()
        yield client
    finally:
        if client is not None:
            client.close()
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)
        if proc.poll() is None:  # pragma: no cover
            proc.kill()
        with contextlib.suppress(Exception):
            port_file.unlink()


def run_condition_B(baseline_state: Optional[dict]) -> tuple[dict, dict]:
    """Run Condition B over the network boundary; return (metric_block, final
    canonical state read back over the boundary)."""
    with store_subprocess(GRAPH_INITIAL) as store:
        n0, e0 = len(store.all_nodes()), len(store.all_edges())
        trace = Agent().traverse(store)              # SAME agent, over the wire
        state = canonical_state(store)               # final state, read over the wire
        block = metric_block(
            "B",
            "networked store (separate process, 127.0.0.1 loopback socket)",
            n0, e0, store, trace, baseline_state=baseline_state,
            across_boundary=True,
        )
    return block, state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STUDY-209 networked store")
    sub = parser.add_subparsers(dest="mode")
    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--graph", required=True)
    serve_p.add_argument("--port-file", required=True)
    args = parser.parse_args()

    if args.mode == "serve":
        _serve(args.graph, args.port_file)
    else:
        from baseline_local import run_condition_A
        a_block, a_state = run_condition_A()
        b_block, _ = run_condition_B(a_state)
        print("=" * 64)
        print("STUDY-209 — Condition B (networked store over a loopback socket)")
        print("=" * 64)
        for k, v in b_block.items():
            print(f"  {k}: {v}")
        ok = (
            b_block["functional_equivalence_to_A"] is True
            and b_block["structural_liveness_across_boundary"] is True
            and b_block["persistence_affects_subsequent_traversal"] is True
            and b_block["node_count_delta"] != 0
        )
        print("=" * 64)
        print("RESULT:", "B == A, liveness across the boundary HELD" if ok
              else "CHECK FAILED")
        sys.exit(0 if ok else 1)
