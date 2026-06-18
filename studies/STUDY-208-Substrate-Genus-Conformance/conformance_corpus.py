"""STUDY-208: Substrate-Genus Conformance — the conformance corpus.

AGPL-3.0 | Patent Pending (app 19/575,491)

This is THE mechanism, written ONCE, ABOVE the substrate contract, and run
UNCHANGED against every backend. It exercises the three never-broadened
substrate properties and captures the seven conformance metrics:

  1. topology-as-program        — traversal IS execution; the operation
                                   sequence is determined by the graph topology.
  2. result-driven edge select  — the execution RESULT of a node selects which
                                   outgoing edge the agent follows.
  3. structural-liveness        — an in-traversal persisted self-modification
                                   (incl. a supersede step) is immediately live:
                                   the just-written node/edge governs the very
                                   next traversal step, with no compile/deploy
                                   boundary.

Because this module is identical for all backends and touches the substrate
ONLY through `SubstrateContract`, any difference in final state between backends
would be a storage difference — which is exactly what the study shows does NOT
happen. The mechanism does the work; the storage does not.
"""

from __future__ import annotations

from typing import Any

from substrate_contract import SubstrateContract, Modification, make_edge, make_node

# The deterministic traversal the corpus produces over graph_initial.json:
EXPECTED_PATH = [
    "start", "gate", "odd_branch", "mutate", "audit",
    "supersede", "compute_v2", "end",
]


# ---------------------------------------------------------------------------
# Deterministic node execution — pure, no wall-clock, no randomness
# ---------------------------------------------------------------------------

def execute(node: dict[str, Any], state: dict[str, Any]) -> str:
    """Execute a node's operation against the agent state; return a result token.

    The result token is what result-driven edge selection keys on. Every op is
    deterministic, so the whole traversal is reproducible and cross-backend
    equivalence is decidable.
    """
    op = node["op"]
    if op.startswith("set:"):
        state["acc"] = int(op.split(":", 1)[1])
        return "go"
    if op == "parity":
        return "even" if state["acc"] % 2 == 0 else "odd"
    if op.startswith("add:"):
        state["acc"] += int(op.split(":", 1)[1])
        return "next"
    if op.startswith("self_modify"):
        return "audit"
    if op.startswith("supersede"):
        return "v2"
    if op.startswith("compute:"):
        return "next"
    if op == "finalize":
        return "stop"
    return "next"


# ---------------------------------------------------------------------------
# In-traversal self-modifications (additive, primitive vocabulary)
# ---------------------------------------------------------------------------

def self_mod_payload() -> Modification:
    """The self-modification trigger: add an 'audit' node and the edges that
    splice it into the live path. The newly-added `mutate -> audit` edge is
    selected on the very next step (structural-liveness)."""
    return {
        "add_nodes": [make_node("audit", "OPERATION", "record")],
        "add_edges": [
            make_edge("mutate", "audit", "COND", "audit"),
            make_edge("audit", "supersede", "THEN", None),
        ],
    }


def supersede_payload(target: str) -> Modification:
    """The supersede step: add a superseding node 'compute_v2', a structural
    SUPERSEDES edge to the old node, and the live traversal edges. The added
    `supersede -> compute_v2` edge governs the next step immediately."""
    return {
        "add_nodes": [make_node("compute_v2", "OPERATION", "compute:new")],
        "add_edges": [
            make_edge("supersede", "compute_v2", "COND", "v2"),
            make_edge("compute_v2", "end", "THEN", None),
            make_edge("compute_v2", target, "SUPERSEDES", None),
        ],
    }


# ---------------------------------------------------------------------------
# Result-driven edge selection (SUPERSEDES edges are structural, not control flow)
# ---------------------------------------------------------------------------

def select_edge(edges: list[dict[str, Any]], result: str):
    """Select the outgoing edge by the execution result.

    A conditioned edge whose condition equals the result wins (result-driven
    routing); otherwise an unconditioned edge is the deterministic fallback.
    Returns (edge_or_None, was_result_driven_branch).
    """
    conditioned = [e for e in edges if e["condition"] is not None]
    unconditioned = [e for e in edges if e["condition"] is None]
    for e in conditioned:
        if e["condition"] == result:
            return e, (len(edges) > 1)
    if unconditioned:
        return unconditioned[0], False
    return None, False


# ---------------------------------------------------------------------------
# The corpus run — the workload + the 7-metric capture
# ---------------------------------------------------------------------------

def run_corpus(contract: SubstrateContract, start_id: str = "start",
               max_steps: int = 64) -> dict[str, Any]:
    """Run the self-superseding workload against a backend (via the contract).

    Returns the seven conformance metrics plus the visited path and the final
    canonical substrate state. `functional_equivalence` is left None here and
    filled by the harness, which compares each backend's final state to the
    file baseline (A).
    """
    before = contract.export_canonical()
    n0, e0 = len(before["nodes"]), len(before["edges"])

    state: dict[str, Any] = {"acc": 0}
    visited: list[str] = []
    result_routed = 0
    mods = 0
    topology_ok = True

    cursor: str | None = start_id
    steps = 0
    while cursor is not None:
        steps += 1
        if steps > max_steps:
            raise RuntimeError("corpus exceeded max_steps — non-terminating traversal")

        node = contract.read_node(cursor)
        visited.append(cursor)
        result = execute(node, state)

        op = node["op"]
        if op.startswith("self_modify"):
            contract.write_modification(self_mod_payload())
            contract.persist()
            mods += 1
        elif op.startswith("supersede"):
            target = op.split(":", 1)[1] if ":" in op else "compute_v1"
            contract.write_modification(supersede_payload(target))
            contract.persist()
            mods += 1

        # Re-read AFTER any modification: liveness means the just-written edge
        # is already here and governs the next step. SUPERSEDES edges are
        # structural, not control flow, so they are excluded from selection.
        edges = [e for e in contract.get_outgoing_edges(cursor)
                 if e["relation"] != "SUPERSEDES"]
        if not edges:
            break

        nxt, routed = select_edge(edges, result)
        if nxt is None:
            break
        if routed:
            result_routed += 1
        if nxt["source"] != cursor:  # a transition that did not follow a real edge
            topology_ok = False
        cursor = nxt["target"]

    after = contract.export_canonical()
    n1, e1 = len(after["nodes"]), len(after["edges"])

    # Persistence + liveness: both added nodes were reached on subsequent steps.
    persistence = ("audit" in visited) and ("compute_v2" in visited)

    metrics = {
        "topology_determination": topology_ok,
        "result_dependent_routing": result_routed,
        "self_modification": mods,
        "modification_persistence": persistence,
        "functional_equivalence": None,  # filled by the harness vs baseline A
        "node_count_delta": n1 - n0,
        "edge_count_delta": e1 - e0,
    }
    return {
        "metrics": metrics,
        "visited": visited,
        "final_acc": state["acc"],
        "final_state": after,
    }
