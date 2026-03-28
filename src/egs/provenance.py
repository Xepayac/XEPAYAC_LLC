"""EGS Provenance — hash-chain ledger for graph mutations.

Every mutation (add/remove/update node or edge) is recorded as a
ProvenanceEntry in a tamper-evident chain. Read operations pass
through without logging.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from egs.graph import EGS
from egs.models import Node, Edge


@dataclass
class ProvenanceEntry:
    """Single entry in the provenance hash chain."""

    sequence: int
    timestamp: str           # ISO 8601
    operation: str           # "add_node", "remove_node", "add_edge", "remove_edge", "update_node"
    agent_id: str            # who performed it
    target_id: str           # node_id or edge id affected
    detail: dict             # operation-specific data
    previous_hash: str       # hash of previous entry ("" for first)
    hash: str                # SHA-256 of this entry


def _compute_hash(
    sequence: int,
    timestamp: str,
    operation: str,
    agent_id: str,
    target_id: str,
    detail: dict,
    previous_hash: str,
) -> str:
    """Compute SHA-256 hash for a provenance entry."""
    payload = json.dumps(
        {
            "sequence": sequence,
            "timestamp": timestamp,
            "operation": operation,
            "agent_id": agent_id,
            "target_id": target_id,
            "detail": detail,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class ProvenanceGraph:
    """Wrapper around EGS that logs every mutation to a hash-chain ledger."""

    def __init__(self, graph: EGS):
        self.graph = graph
        self._ledger: list[ProvenanceEntry] = []
        self._sequence = 0

    def _log(
        self, operation: str, agent_id: str, target_id: str, detail: dict
    ) -> ProvenanceEntry:
        """Append a new entry to the ledger and return it."""
        ts = datetime.now(timezone.utc).isoformat()
        prev = self._ledger[-1].hash if self._ledger else ""
        h = _compute_hash(self._sequence, ts, operation, agent_id, target_id, detail, prev)
        entry = ProvenanceEntry(
            sequence=self._sequence,
            timestamp=ts,
            operation=operation,
            agent_id=agent_id,
            target_id=target_id,
            detail=detail,
            previous_hash=prev,
            hash=h,
        )
        self._ledger.append(entry)
        self._sequence += 1
        return entry

    # --- Mutation methods (logged) ---

    def add_node(self, node: Node) -> None:
        """Add a node and log the operation."""
        self.graph.add_node(node)
        self._log(
            "add_node",
            node.metadata.created_by,
            node.id,
            {"node_type": node.type.value, "node_id": node.id},
        )

    def remove_node(self, node_id: str, agent_id: str = "system") -> Optional[Node]:
        """Remove a node and log the operation if successful."""
        result = self.graph.remove_node(node_id)
        if result:
            self._log(
                "remove_node",
                agent_id,
                node_id,
                {"node_type": result.type.value, "node_id": node_id},
            )
        return result

    def add_edge(self, edge: Edge) -> None:
        """Add an edge and log the operation."""
        self.graph.add_edge(edge)
        self._log(
            "add_edge",
            edge.metadata.created_by,
            edge.id,
            {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation,
            },
        )

    def remove_edge(
        self, from_id: str, to_id: str, relation: str, agent_id: str = "system"
    ) -> Optional[Edge]:
        """Remove an edge and log the operation if successful."""
        result = self.graph.remove_edge(from_id, to_id, relation)
        if result:
            self._log(
                "remove_edge",
                agent_id,
                result.id,
                {"source_id": from_id, "target_id": to_id, "relation": relation},
            )
        return result

    def update_node(
        self, node_id: str, data: dict, agent_id: str = "system"
    ) -> Optional[Node]:
        """Update a node's data and log the operation if successful."""
        result = self.graph.update_node(node_id, data)
        if result:
            self._log(
                "update_node",
                agent_id,
                node_id,
                {"node_id": node_id, "updated_keys": list(data.keys())},
            )
        return result

    # --- Read methods (pass through, no logging) ---

    def get_node(self, node_id: str):
        """Get a node by ID (not logged)."""
        return self.graph.get_node(node_id)

    def find_nodes(self, **kwargs):
        """Find nodes matching criteria (not logged)."""
        return self.graph.find_nodes(**kwargs)

    def find_edges(self, **kwargs):
        """Find edges matching criteria (not logged)."""
        return self.graph.find_edges(**kwargs)

    def get_neighbors(self, *args, **kwargs):
        """Get neighboring nodes (not logged)."""
        return self.graph.get_neighbors(*args, **kwargs)

    @property
    def nodes(self):
        """Get all nodes in the graph."""
        return self.graph.nodes

    @property
    def edges(self):
        """Get all edges in the graph."""
        return self.graph.edges

    def to_dict(self):
        """Serialize the graph to a dictionary."""
        return self.graph.to_dict()

    def get_summary(self):
        """Get a summary of the graph structure."""
        return self.graph.get_summary()

    # --- Provenance query interface ---

    def history(self) -> list[ProvenanceEntry]:
        """Return a copy of the full ledger."""
        return list(self._ledger)

    def history_for(self, target_id: str) -> list[ProvenanceEntry]:
        """Return ledger entries for a specific target."""
        return [e for e in self._ledger if e.target_id == target_id]

    def verify(self) -> bool:
        """Verify the hash chain integrity. Returns True if valid."""
        for i, entry in enumerate(self._ledger):
            prev = self._ledger[i - 1].hash if i > 0 else ""
            expected = _compute_hash(
                entry.sequence,
                entry.timestamp,
                entry.operation,
                entry.agent_id,
                entry.target_id,
                entry.detail,
                prev,
            )
            if entry.hash != expected:
                return False
        return True

    def who_created(self, node_id: str) -> Optional[str]:
        """Return the agent_id that first added a node, or None."""
        for entry in self._ledger:
            if entry.operation == "add_node" and entry.target_id == node_id:
                return entry.agent_id
        return None

    def ledger_size(self) -> int:
        """Return the number of entries in the ledger."""
        return len(self._ledger)
