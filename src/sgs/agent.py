"""SGS Multi-Agent Coordination.

Provides Agent (type-scoped graph access) and CoordinationSession.

AGPL-3.0 | Patent Pending (app 19/575,491)
(multi-agent summary tracking).
"""

from typing import Optional

from sgs.graph import SGS
from sgs.models import Node, NodeType, Edge, EdgeMetadata


# EXCEPTION access_violation SHALL BE THROWN WHEN AGENT REQUESTS ANY NODE 'of INVALID type.
class AccessError(Exception):
    """Raised when an agent accesses a node type it's not authorized for."""


# SERVICE agent SHALL AUTHENTICATE EACH REQUEST BY RECORD allowed_types THEN GOVERN ALL RECORD node AND RECORD edge 'in RESOURCE graph.
class Agent:
    """Type-scoped proxy to a shared SGS graph.

    Each agent can only read/write nodes whose type is in its allowed_types.
    Metadata created_by is auto-stamped with the agent's ID.
    """

    def __init__(self, agent_id: str, graph: SGS, allowed_types: list[NodeType]):
        self.agent_id = agent_id
        self.graph = graph  # shared reference, NOT a copy
        self.allowed_types = set(allowed_types)

    # PROCESS add SHALL VALIDATE RECORD node SUBJECT_TO RECORD allowed_types THEN WRITE RESULT TO RESOURCE graph OR THROW EXCEPTION access_violation.
    def add_node(self, node: Node) -> None:
        """Add a node, raising AccessError if type not allowed."""
        if node.type not in self.allowed_types:
            raise AccessError(
                f"Agent '{self.agent_id}' cannot add node type {node.type.value}"
            )
        new_meta = node.metadata.model_copy(update={"created_by": self.agent_id})
        stamped = node.model_copy(update={"metadata": new_meta})
        self.graph.add_node(stamped)

    # PROCESS get SHALL READ RECORD node FROM RESOURCE graph THEN FILTER SUBJECT_TO RECORD allowed_types OR RETURN NULL.
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID. Returns None if not found or type not allowed."""
        node = self.graph.get_node(node_id)
        if node is None or node.type not in self.allowed_types:
            return None
        return node

    # PROCESS find SHALL READ ALL RECORD node FROM RESOURCE graph THEN FILTER SUBJECT_TO RECORD allowed_types.
    def find_nodes(self, **kwargs) -> list[Node]:
        """Find nodes matching criteria, filtered to allowed types."""
        results = self.graph.find_nodes(**kwargs)
        return [n for n in results if n.type in self.allowed_types]

    # PROCESS visible SHALL READ ALL RECORD node FROM RESOURCE graph THEN FILTER SUBJECT_TO RECORD allowed_types THEN RETURN RESULT AS MAP.
    def visible_nodes(self) -> dict[str, Node]:
        """All nodes in graph where type is in allowed_types."""
        return {
            nid: node
            for nid, node in self.graph.nodes.items()
            if node.type in self.allowed_types
        }

    # PROCESS add SHALL VALIDATE EACH endpoint SUBJECT_TO RECORD allowed_types THEN WRITE RECORD edge TO RESOURCE graph OR THROW EXCEPTION access_violation.
    def add_edge(self, edge: Edge) -> None:
        """Add an edge. Both endpoints must exist and be visible."""
        source = self.graph.get_node(edge.source_id)
        target = self.graph.get_node(edge.target_id)

        if source is None or source.type not in self.allowed_types:
            raise AccessError(
                f"Agent '{self.agent_id}' cannot access source node '{edge.source_id}'"
            )
        if target is None or target.type not in self.allowed_types:
            raise AccessError(
                f"Agent '{self.agent_id}' cannot access target node '{edge.target_id}'"
            )

        new_meta = edge.metadata.model_copy(update={"created_by": self.agent_id})
        stamped = edge.model_copy(update={"metadata": new_meta})
        self.graph.add_edge(stamped)

    # PROCESS get SHALL READ ALL RECORD edge FROM RESOURCE graph THEN FILTER BY ANY endpoint 'of TYPE allowed.
    def get_edges(self, **kwargs) -> list[Edge]:
        """Get edges where at least one endpoint is visible."""
        edges = self.graph.find_edges(**kwargs)
        visible_ids = {nid for nid, node in self.graph.nodes.items()
                       if node.type in self.allowed_types}
        return [
            e for e in edges
            if e.source_id in visible_ids or e.target_id in visible_ids
        ]


# SERVICE coordination SHALL CONTAIN ALL SERVICE agent THEN AGGREGATE RECORD activity FROM RESOURCE graph.
class CoordinationSession:
    """Tracks multiple agents operating on a shared graph."""

    def __init__(self, graph: SGS):
        self.graph = graph
        self.agents: list[Agent] = []

    # PROCESS register SHALL BIND SERVICE agent TO SESSION session.
    def add_agent(self, agent: Agent) -> None:
        """Register an agent with this session."""
        self.agents.append(agent)

    # PROCESS summary SHALL AGGREGATE RECORD node BY RECORD created_by THEN RETURN COUNT.
    def summary(self) -> dict:
        """Count nodes created by each agent: {agent_id: count}."""
        counts: dict[str, int] = {}
        for node in self.graph.nodes.values():
            creator = node.metadata.created_by
            counts[creator] = counts.get(creator, 0) + 1
        return counts
