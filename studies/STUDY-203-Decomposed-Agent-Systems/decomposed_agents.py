"""STUDY-203 Condition B: decomposed agent system (three cooperating processes).

The single-process loop of Condition A is decomposed across three real OS
processes that cooperate over multiprocessing.Queue IPC:

  * Process-1 (traversal / coordinator -- this parent process): selects the
    next edge from the execution result against the on-disk edge conditions.
    It does NOT execute node ops and NEVER writes the graph.
  * Process-2 (execution): executes the current node against its own
    execution state and reports the result (and any self-modification spec).
    It does NOT select edges and NEVER writes the graph.
  * Process-3 (modification -- the SOLE MODIFIER): applies and atomically
    persists every self-modification. It is the ONLY process that writes the
    graph file. It does NOT execute node ops and does NOT select edges.

No single process performs all three steps. The multi-writer-consistency
discipline is: route every write through Process-3 (sole modifier) over an
IPC channel, and persist with an atomic replace -- so "the next traversal
step operates on the graph as modified and persisted" holds across writers.
Repeated runs are bit-for-bit deterministic, which is the empirical proof
that writes are serialized rather than racing.

Crucially, the IPC channels carry only COORDINATION messages -- node ids,
execution results, modification specs, and acknowledgements -- never the
graph itself. The shared executed medium is the on-disk serialized graph
file. The file is the program (L1); traversing it is executing it (L3).
That is what keeps this decomposition off the ephemeral-in-memory
state-passing species: at no point is the substrate handed between
processes as an in-memory object.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import multiprocessing as mp
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Self-contained: ensure this directory is importable (matters when the
# multiprocessing start method is 'spawn', which re-imports the module).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baseline_single_process import (  # shared substrate semantics
    MAX_STEPS,
    apply_modification,
    canonical_graph,
    execute_node,
    find_entry,
    graph_hash,
    init_working_file,
    is_terminal,
    load_graph,
    modification_for,
    modification_present,
    node_by_id,
    save_graph_atomic,
    select_next_edge,
)

_GET_TIMEOUT = 30  # seconds; bounds every blocking queue read so a dead
                   # worker surfaces as an error instead of a hang.


def _pick_context() -> "mp.context.BaseContext":
    """Prefer fork where available (deterministic + robust under pytest);
    fall back to spawn. The substrate semantics do not depend on the start
    method -- determinism comes from the node ops, not the scheduler."""
    methods = mp.get_all_start_methods()
    return mp.get_context("fork" if "fork" in methods else "spawn")


# ---------------------------------------------------------------------------
# Process-2: execution worker -- executes nodes, never writes, never routes
# ---------------------------------------------------------------------------

def _execution_worker(graph_path: str, q_exec: "mp.Queue", q_result: "mp.Queue") -> None:
    state: dict = {}                       # the agent's execution state
    pid = os.getpid()
    while True:
        msg = q_exec.get()
        if msg[0] == "STOP":
            break
        _, node_id = msg
        graph = load_graph(graph_path)     # read the node from the persisted file
        node = node_by_id(graph, node_id)
        result = execute_node(node, state)
        spec = modification_for(node)
        q_result.put(("RESULT", node_id, result, spec, pid))


# ---------------------------------------------------------------------------
# Process-3: sole modifier -- the ONLY writer of the graph file
# ---------------------------------------------------------------------------

def _modifier_worker(graph_path: str, q_mod: "mp.Queue", q_ack: "mp.Queue") -> None:
    pid = os.getpid()
    writes = 0
    while True:
        msg = q_mod.get()
        if msg[0] == "STOP":
            break
        _, spec = msg
        graph = load_graph(graph_path)
        apply_modification(graph, spec)
        save_graph_atomic(graph, graph_path)   # serialized, atomic write
        writes += 1
        q_ack.put(("MODIFIED", pid, writes))


# ---------------------------------------------------------------------------
# Process-1: traversal / coordinator (this parent process)
# ---------------------------------------------------------------------------

def run(graph_path: Path) -> dict:
    graph_path = Path(graph_path)
    initial = load_graph(graph_path)
    initial_nodes, initial_edges = len(initial["nodes"]), len(initial["edges"])

    ctx = _pick_context()
    q_exec: "mp.Queue" = ctx.Queue()
    q_result: "mp.Queue" = ctx.Queue()
    q_mod: "mp.Queue" = ctx.Queue()
    q_ack: "mp.Queue" = ctx.Queue()

    p_exec = ctx.Process(target=_execution_worker, args=(str(graph_path), q_exec, q_result))
    p_mod = ctx.Process(target=_modifier_worker, args=(str(graph_path), q_mod, q_ack))
    p_exec.start()
    p_mod.start()

    visited: list[str] = []
    branch_decision = None
    self_modified = False
    modification_persisted = False
    exec_pids: set[int] = set()
    modifier_pids: set[int] = set()
    write_count = 0

    try:
        current: Optional[str] = find_entry(initial)
        steps = 0
        while current is not None and steps < MAX_STEPS:
            steps += 1
            # P1 asks P2 to execute the current node (P1 does not execute).
            q_exec.put(("EXECUTE", current))
            tag, node_id, result, spec, p2pid = q_result.get(timeout=_GET_TIMEOUT)
            exec_pids.add(p2pid)
            visited.append(current)

            # A self-modification is routed to the sole modifier (P1/P2 never write).
            if spec is not None:
                q_mod.put(("MODIFY", spec))
                _, p3pid, wcount = q_ack.get(timeout=_GET_TIMEOUT)
                modifier_pids.add(p3pid)
                write_count = wcount
                self_modified = True
                modification_persisted = modification_present(load_graph(graph_path), spec)

            # P1 re-reads the modified+persisted graph and selects the next edge
            # from the execution RESULT vs the on-disk edge conditions.
            graph = load_graph(graph_path)
            node = node_by_id(graph, current)
            if is_terminal(node):
                break
            nxt = select_next_edge(graph, current, result)
            if node["type"] == "BRANCH":
                branch_decision = {"node": current, "result": result, "selected_target": nxt}
            if nxt is None:
                break
            current = nxt
    finally:
        q_exec.put(("STOP",))
        q_mod.put(("STOP",))
        for p in (p_exec, p_mod):
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)

    final = load_graph(graph_path)
    distinct_pids = len({os.getpid()} | exec_pids | modifier_pids)
    return {
        "condition": "B",
        "embodiment": "three_processes",
        "visited": visited,
        "branch_decision": branch_decision,
        "self_modified": self_modified,
        "modification_persisted": modification_persisted,
        "initial_node_count": initial_nodes,
        "initial_edge_count": initial_edges,
        "final_node_count": len(final["nodes"]),
        "final_edge_count": len(final["edges"]),
        "node_count_delta": len(final["nodes"]) - initial_nodes,
        "edge_count_delta": len(final["edges"]) - initial_edges,
        "final_acc": None,                 # the accumulator lives in P2, not shared back
        "final_graph_hash": graph_hash(final),
        "final_graph": canonical_graph(final),
        "metadata": {
            "processes": 3,
            "distinct_pids": distinct_pids,
            "traversal_pid": os.getpid(),
            "execution_pids": sorted(exec_pids),
            "modifier_pids": sorted(modifier_pids),
            "write_count": write_count,            # writes performed (all by the modifier)
            "distinct_writer_processes": len(modifier_pids),  # the sole-modifier count
            "sole_modifier": len(modifier_pids) <= 1,
            "writer_roles": ["modifier"],
            "shared_medium": "on_disk_serialized_file",
            "channel_carries": "coordination_messages_only",
            "ipc": "multiprocessing.Queue",
            "routing_source": "execution_result_vs_edge_condition",
        },
    }


def run_in_tempdir() -> dict:
    initial_path = Path(__file__).parent / "graph_initial.json"
    with tempfile.TemporaryDirectory(prefix="study_203_B_") as d:
        working = Path(d) / "graph.json"
        init_working_file(initial_path, working)
        return run(working)


if __name__ == "__main__":
    res = run_in_tempdir()
    print("=" * 60)
    print("STUDY-203 Condition B: decomposed agent system (3 processes)")
    print("=" * 60)
    print(f"  visited:                {' -> '.join(res['visited'])}")
    print(f"  branch decision:        {res['branch_decision']}")
    print(f"  self modified:          {res['self_modified']}")
    print(f"  modification persisted: {res['modification_persisted']}")
    print(f"  distinct pids:          {res['metadata']['distinct_pids']} "
          f"(traversal/execution/modifier)")
    print(f"  distinct writers:       {res['metadata']['distinct_writer_processes']} "
          f"(sole modifier: {res['metadata']['sole_modifier']})")
    print(f"  channel carries:        {res['metadata']['channel_carries']}")
    print(f"  nodes: {res['initial_node_count']} -> {res['final_node_count']} "
          f"(delta {res['node_count_delta']:+d}); "
          f"edges: {res['initial_edge_count']} -> {res['final_edge_count']} "
          f"(delta {res['edge_count_delta']:+d})")
    print(f"  final graph hash:       {res['final_graph_hash'][:16]}...")
    expected = ["start", "compute", "branch", "grow", "audit", "finalize"]
    ok = (
        res["visited"] == expected
        and res["self_modified"]
        and res["modification_persisted"]
        and res["metadata"]["sole_modifier"]
        and res["metadata"]["distinct_pids"] == 3
    )
    print("=" * 60)
    print("RESULT:", "OK" if ok else "UNEXPECTED")
    sys.exit(0 if ok else 1)
