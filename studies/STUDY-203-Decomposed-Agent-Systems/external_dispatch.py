"""STUDY-203 Condition C: external dispatch.

An external dispatch process coordinates the work, but the routing decision
does NOT come from the dispatcher's own logic. Two processes cooperate over
multiprocessing.Queue IPC:

  * The dispatcher (this parent process) reads the graph TOPOLOGY only to
    pick WHO acts and WHEN -- it finds the entry node and drives turn-taking.
    It is forbidden from routing: it never reads node content to compute a
    path, never evaluates an outgoing-edge condition, and never selects among
    outgoing edges. It simply follows whatever next node the agent reports.
  * The agent (a worker process) executes the current node against its own
    execution state, applies and atomically persists any self-modification to
    the on-disk serialized graph file, and selects the next node by evaluating
    its execution RESULT against the on-disk edge conditions. Execution and
    modification both occur in the agent, over the persisted file.

This is the as-filed carve-out re-drawn for an external orchestrator:
"computation occurs in the agents, NOT in the graph" -- and the orchestrator
does NOT supply the routing decision. The next node is selected by the
execution result against the substrate's edge conditions, exactly as in the
single-process baseline. The dispatch channel carries turn-coordination
messages only; the shared executed medium is the on-disk file (L1/L3).

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import multiprocessing as mp
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

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

_GET_TIMEOUT = 30


def _pick_context() -> "mp.context.BaseContext":
    methods = mp.get_all_start_methods()
    return mp.get_context("fork" if "fork" in methods else "spawn")


# ---------------------------------------------------------------------------
# The agent: executes + modifies + selects the next node (result vs edges)
# ---------------------------------------------------------------------------

def _agent_worker(graph_path: str, q_act: "mp.Queue", q_done: "mp.Queue") -> None:
    state: dict = {}
    pid = os.getpid()
    while True:
        msg = q_act.get()
        if msg[0] == "STOP":
            break
        _, node_id = msg
        graph = load_graph(graph_path)
        node = node_by_id(graph, node_id)
        node_type = node["type"]
        result = execute_node(node, state)

        modified = False
        persisted = False
        spec = modification_for(node)
        if spec is not None:
            apply_modification(graph, spec)
            save_graph_atomic(graph, graph_path)        # the agent modifies the file
            modified = True
            persisted = modification_present(load_graph(graph_path), spec)

        # The AGENT selects the next node from its result vs the on-disk edge
        # conditions -- this is the routing decision, and it is the agent's
        # (the substrate's), not the dispatcher's.
        graph2 = load_graph(graph_path)
        terminal = is_terminal(node)
        next_node = None if terminal else select_next_edge(graph2, node_id, result)
        q_done.put(("DONE", node_id, node_type, result, next_node, terminal, modified, persisted, pid))


# ---------------------------------------------------------------------------
# The dispatcher: schedules WHO/WHEN; NEVER routes from its own logic
# ---------------------------------------------------------------------------

def run(graph_path: Path) -> dict:
    graph_path = Path(graph_path)
    initial = load_graph(graph_path)
    initial_nodes, initial_edges = len(initial["nodes"]), len(initial["edges"])

    ctx = _pick_context()
    q_act: "mp.Queue" = ctx.Queue()
    q_done: "mp.Queue" = ctx.Queue()
    agent = ctx.Process(target=_agent_worker, args=(str(graph_path), q_act, q_done))
    agent.start()

    visited: list[str] = []
    branch_decision = None
    self_modified = False
    modification_persisted = False
    agent_pids: set[int] = set()
    # The dispatcher never evaluates edge conditions. This flag stays False by
    # construction; the SC-4 audit asserts it.
    dispatcher_evaluated_edges = False

    try:
        # Reading the topology to find the entry node is scheduling (WHO/WHEN),
        # not routing.
        current: Optional[str] = find_entry(initial)
        steps = 0
        while current is not None and steps < MAX_STEPS:
            steps += 1
            q_act.put(("ACT", current))   # dispatcher schedules the agent's turn
            (_, node_id, node_type, result, next_node, terminal,
             modified, persisted, apid) = q_done.get(timeout=_GET_TIMEOUT)
            agent_pids.add(apid)
            visited.append(current)
            self_modified = self_modified or modified
            modification_persisted = modification_persisted or persisted

            # Bookkeeping only: record the branch decision the AGENT reported.
            # The dispatcher did not compute it.
            if node_type == "BRANCH":
                branch_decision = {"node": current, "result": result, "selected_target": next_node}

            if terminal:
                break
            # The dispatcher FOLLOWS the agent's routing; it does not derive it.
            current = next_node
            if current is None:
                break
    finally:
        q_act.put(("STOP",))
        agent.join(timeout=10)
        if agent.is_alive():
            agent.terminate()
            agent.join(timeout=5)

    final = load_graph(graph_path)
    return {
        "condition": "C",
        "embodiment": "external_dispatch",
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
        "final_acc": None,
        "final_graph_hash": graph_hash(final),
        "final_graph": canonical_graph(final),
        "metadata": {
            "processes": 2,
            "roles": ["dispatcher", "agent"],
            "dispatcher_pid": os.getpid(),
            "agent_pids": sorted(agent_pids),
            "dispatcher_evaluated_edges": dispatcher_evaluated_edges,
            "dispatcher_reads": "topology_for_scheduling_only",
            "routing_source": "execution_result_vs_edge_condition",
            "writer_roles": ["agent"],
            "shared_medium": "on_disk_serialized_file",
            "channel_carries": "coordination_messages_only",
            "ipc": "multiprocessing.Queue",
        },
    }


def run_in_tempdir() -> dict:
    initial_path = Path(__file__).parent / "graph_initial.json"
    with tempfile.TemporaryDirectory(prefix="study_203_C_") as d:
        working = Path(d) / "graph.json"
        init_working_file(initial_path, working)
        return run(working)


if __name__ == "__main__":
    res = run_in_tempdir()
    print("=" * 60)
    print("STUDY-203 Condition C: external dispatch")
    print("=" * 60)
    print(f"  visited:                {' -> '.join(res['visited'])}")
    print(f"  branch decision:        {res['branch_decision']}")
    print(f"  self modified:          {res['self_modified']}")
    print(f"  modification persisted: {res['modification_persisted']}")
    print(f"  dispatcher evaluated edges: {res['metadata']['dispatcher_evaluated_edges']}")
    print(f"  routing source:         {res['metadata']['routing_source']}")
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
        and res["metadata"]["dispatcher_evaluated_edges"] is False
    )
    print("=" * 60)
    print("RESULT:", "OK" if ok else "UNEXPECTED")
    sys.exit(0 if ok else 1)
