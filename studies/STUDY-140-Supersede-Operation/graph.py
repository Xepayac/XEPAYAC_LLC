"""STUDY-140: Supersede Operation — graph substrate.

Self-contained minimal graph substrate with supersede support: typed nodes
with an active/stale lifecycle, directed edges, a type schema, a version
counter for optimistic concurrency, and an append-only provenance log.

Deliberately standalone (no external graph library) so the published study
is reproducible from this directory alone.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Edge relation used to link a superseded node to its replacement.
SUPERSEDED_BY = "SUPERSEDED_BY"

# Node lifecycle states.
ACTIVE = "active"
STALE = "stale"


@dataclass
class Node:
    """A typed graph node with an active/stale lifecycle."""

    id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    status: str = ACTIVE


@dataclass
class Edge:
    """A directed, labelled edge."""

    from_id: str
    to_id: str
    relation: str


@dataclass
class Schema:
    """Type rules the substrate enforces.

    allowed_types: every node type the graph accepts.
    required_properties: per-type property names a node must carry to be
        committed (checked at commit time, after structural application).
    """

    allowed_types: List[str] = field(default_factory=list)
    required_properties: Dict[str, List[str]] = field(default_factory=dict)

    def type_allowed(self, node_type: str) -> bool:
        return node_type in self.allowed_types

    def missing_properties(self, node: Node) -> List[str]:
        required = self.required_properties.get(node.type, [])
        return [p for p in required if p not in node.properties]


class Graph:
    """A mutable graph with versioning and provenance.

    `version` increments on every committed mutation; readers capture it
    and pass it back as `expected_version` to detect concurrent writes.
    `provenance` is append-only: one record per committed operation.
    """

    def __init__(self, schema: Optional[Schema] = None) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.schema: Schema = schema or Schema()
        self.version: int = 0
        self.provenance: List[Dict[str, Any]] = []

    # -- construction -----------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        if not self.schema.type_allowed(node.type):
            raise ValueError(f"type not allowed by schema: {node.type}")
        self.nodes[node.id] = node
        self.version += 1

    def add_edge(self, edge: Edge) -> None:
        if edge.from_id not in self.nodes or edge.to_id not in self.nodes:
            raise ValueError("edge endpoints must exist")
        self.edges.append(edge)
        self.version += 1

    # -- inspection -------------------------------------------------------

    def get_node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def incoming_edges(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges if e.to_id == node_id]

    def outgoing_edges(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges if e.from_id == node_id]

    def active_nodes(self) -> List[Node]:
        return [n for n in self.nodes.values() if n.status == ACTIVE]

    def supersede_chain(self, node_id: str) -> List[str]:
        """Walk SUPERSEDED_BY edges from `node_id`; returns the full chain
        starting at `node_id` and ending at the current (active) node."""
        chain = [node_id]
        seen = {node_id}
        cursor = node_id
        while True:
            nxt = [
                e.to_id
                for e in self.outgoing_edges(cursor)
                if e.relation == SUPERSEDED_BY
            ]
            if not nxt:
                return chain
            cursor = nxt[0]
            if cursor in seen:
                raise ValueError("cycle in supersede chain")
            seen.add(cursor)
            chain.append(cursor)

    def current(self, node_id: str) -> Node:
        """Resolve `node_id` through its supersede chain to the node that
        currently holds its role."""
        return self.nodes[self.supersede_chain(node_id)[-1]]

    # -- state capture ----------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """A deep, comparable copy of all graph state."""
        return {
            "nodes": copy.deepcopy(self.nodes),
            "edges": copy.deepcopy(self.edges),
            "version": self.version,
            "provenance": copy.deepcopy(self.provenance),
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        self.nodes = snap["nodes"]
        self.edges = snap["edges"]
        self.version = snap["version"]
        self.provenance = snap["provenance"]
