"""STUDY-209: Networked / Distributed Substrate — Condition C (distributed store).

AGPL-3.0 | Patent Pending (app 19/575,491)

The maximum-locus-distance datapoint: the substrate is sharded across TWO store
services, each in its own OS process, each reached over its own 127.0.0.1
loopback socket. Nodes (and the edges that originate at them) are partitioned by
a deterministic hash. The agent — unchanged from Conditions A and B — traverses
the substrate, self-modifies it, and a subsequent step observes the persisted
change, even though the modification is written to whichever shard owns the new
topology. Self-modification and structural liveness survive a substrate that is
not merely remote but split across multiple services.

This condition is OPTIONAL by plan (ADR-005 / B9): it is built here because the
study is titled "Networked / Distributed" and claim 9 reaches the distributed
species — it adds a genuine datapoint (substrate split across two services) at
modest, compositional cost over Condition B, not noise. The build decision is
recorded in results.json (`condition_c`) and the README.

Reuses Condition B's dumb store service and the same Agent — only the client's
routing layer is new, and that routing is the *client's* concern, never the
store's (the store remains a dumb persistence locus). Self-contained, stdlib
only.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Iterator, Optional

from baseline_local import GRAPH_INITIAL, Agent, Store, canonical_state, load_graph, metric_block
from networked_store import NetworkedStore, store_subprocess

NUM_SHARDS = 2


def _shard_of(node_id: str, num_shards: int) -> int:
    """Deterministic, salt-free shard assignment (Python's builtin hash is
    salted per-process, which would make sharding non-reproducible)."""
    digest = hashlib.sha1(node_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % num_shards


def _split_into_shards(graph: dict, num_shards: int) -> list[dict]:
    """Partition the substrate: a node lives on its hash shard; an edge lives on
    the shard of its source node (so get_outgoing_edges(n) is answerable by the
    single shard that owns n)."""
    shards = [{"id": f"{graph.get('id', 'graph')}_shard_{k}",
               "description": f"STUDY-209 distributed shard {k}/{num_shards}",
               "nodes": [], "edges": []} for k in range(num_shards)]
    for node in graph["nodes"]:
        shards[_shard_of(node["id"], num_shards)]["nodes"].append(node)
    for edge in graph["edges"]:
        shards[_shard_of(edge["source"], num_shards)]["edges"].append(edge)
    return shards


class DistributedStore(Store):
    """A client over N shard services. Routing lives in the CLIENT; each shard
    service is the same dumb persistence locus as Condition B."""

    def __init__(self, shards: list[NetworkedStore]) -> None:
        self._shards = shards
        self._n = len(shards)

    def _shard(self, node_id: str) -> NetworkedStore:
        return self._shards[_shard_of(node_id, self._n)]

    @property
    def server_pids(self) -> list[Optional[int]]:
        return [s.server_pid for s in self._shards]

    def read_node(self, node_id: str) -> dict:
        return self._shard(node_id).read_node(node_id)

    def has_node(self, node_id: str) -> bool:
        return self._shard(node_id).has_node(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        # edges originate at their source node, which lives on this shard
        return self._shard(node_id).get_outgoing_edges(node_id)

    def write_modification(self, modification: dict) -> None:
        per: list[dict] = [{"add_nodes": [], "add_edges": []} for _ in range(self._n)]
        for node in modification.get("add_nodes", []):
            per[_shard_of(node["id"], self._n)]["add_nodes"].append(node)
        for edge in modification.get("add_edges", []):
            per[_shard_of(edge["source"], self._n)]["add_edges"].append(edge)
        for k, sub in enumerate(per):
            if sub["add_nodes"] or sub["add_edges"]:
                self._shards[k].write_modification(sub)

    def all_nodes(self) -> list[dict]:
        out: list[dict] = []
        for s in self._shards:
            out.extend(s.all_nodes())
        return out

    def all_edges(self) -> list[dict]:
        out: list[dict] = []
        for s in self._shards:
            out.extend(s.all_edges())
        return out


@contextlib.contextmanager
def distributed_subprocess(graph_path: Path = GRAPH_INITIAL,
                           num_shards: int = NUM_SHARDS) -> Iterator[DistributedStore]:
    """Spawn one store service per shard and yield a routing client. Each shard
    is a genuine separate process + loopback socket (reuses Condition B)."""
    graph = load_graph(Path(graph_path))
    slices = _split_into_shards(graph, num_shards)
    with contextlib.ExitStack() as stack:
        clients: list[NetworkedStore] = []
        for sl in slices:
            tmp = tempfile.NamedTemporaryFile(
                prefix="study209_shard_", suffix=".json", delete=False)
            slice_path = Path(tmp.name)
            tmp.write(json.dumps(sl).encode("utf-8"))
            tmp.close()
            stack.callback(lambda p=slice_path: p.unlink(missing_ok=True))
            clients.append(stack.enter_context(store_subprocess(slice_path)))
        yield DistributedStore(clients)


def run_condition_C(baseline_state: Optional[dict]) -> tuple[dict, dict]:
    """Run Condition C across the distributed locus; return (metric_block, final
    canonical state assembled from both shards over the boundary)."""
    with distributed_subprocess() as store:
        n0, e0 = len(store.all_nodes()), len(store.all_edges())
        trace = Agent().traverse(store)          # SAME agent, across two services
        state = canonical_state(store)
        block = metric_block(
            "C",
            f"distributed across {NUM_SHARDS} store services (separate processes, 127.0.0.1 loopback)",
            n0, e0, store, trace, baseline_state=baseline_state,
            across_boundary=True,
        )
    return block, state


if __name__ == "__main__":
    import sys

    from baseline_local import run_condition_A

    _, a_state = run_condition_A()
    c_block, _ = run_condition_C(a_state)
    print("=" * 64)
    print("STUDY-209 — Condition C (distributed across 2 store services)")
    print("=" * 64)
    for k, v in c_block.items():
        print(f"  {k}: {v}")
    ok = (
        c_block["functional_equivalence_to_A"] is True
        and c_block["structural_liveness_across_boundary"] is True
        and c_block["persistence_affects_subsequent_traversal"] is True
    )
    print("=" * 64)
    print("RESULT:", "C == A across the distributed locus, liveness HELD" if ok
          else "CHECK FAILED")
    sys.exit(0 if ok else 1)
