"""
Nested Graph Data Structures

Extends the basic SGS to support hierarchical composition:
- SubgraphNode: A node that references another graph
- NestedGraph: A graph that can contain subgraph references
- ScopedNodeId: A fully-qualified node reference across hierarchy

This enables:
1. Reusable graph components (like functions)
2. Scope isolation (node IDs don't conflict across levels)
3. Hierarchical execution (enter/exit subgraphs)
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


class NodeType(Enum):
    """Extended node types including SUBGRAPH."""
    CONCEPT = "CONCEPT"
    PATTERN = "PATTERN"
    BEHAVIOR = "BEHAVIOR"
    TASK = "TASK"
    DECISION = "DECISION"
    SUBGRAPH = "SUBGRAPH"  # References another graph
    OPERAND = "OPERAND"
    OPERATION = "OPERATION"
    RESULT = "RESULT"


@dataclass
class Node:
    """A node in the graph."""
    id: str
    type: NodeType
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For SUBGRAPH nodes only
    subgraph_ref: Optional[str] = None  # Path or ID of referenced graph
    
    def is_subgraph(self) -> bool:
        return self.type == NodeType.SUBGRAPH


@dataclass
class Edge:
    """An edge connecting two nodes."""
    from_id: str
    to_id: str
    relation: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScopedNodeId:
    """
    A fully-qualified node reference in a hierarchy.
    
    Examples:
        - ScopedNodeId(["task_1"]) - node in root graph
        - ScopedNodeId(["subprocess_1", "step_a"]) - node in first-level subgraph
        - ScopedNodeId(["sub_1", "sub_2", "node"]) - deeply nested
    """
    path: List[str]
    
    def __str__(self) -> str:
        return "/".join(self.path)
    
    @classmethod
    def from_string(cls, s: str) -> "ScopedNodeId":
        return cls(s.split("/"))
    
    @property
    def local_id(self) -> str:
        """The node ID within its immediate scope."""
        return self.path[-1]
    
    @property
    def parent_scope(self) -> Optional["ScopedNodeId"]:
        """The scope containing this node."""
        if len(self.path) <= 1:
            return None
        return ScopedNodeId(self.path[:-1])
    
    def child(self, node_id: str) -> "ScopedNodeId":
        """Create a child scope."""
        return ScopedNodeId(self.path + [node_id])


class NestedGraph:
    """
    A graph that supports hierarchical composition.
    
    Key features:
    - Nodes can be SUBGRAPH type, referencing other graphs
    - Subgraphs are loaded lazily when needed
    - Scope isolation: node IDs are local to their graph
    - Cross-scope edges use ScopedNodeId for resolution
    """
    
    def __init__(self, id: str = "root"):
        self.id = id
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.metadata: Dict[str, Any] = {}
        
        # Loaded subgraphs (lazy loading)
        self._subgraphs: Dict[str, "NestedGraph"] = {}
        
        # Base path for resolving subgraph references
        self.base_path: Optional[Path] = None
    
    def add_node(self, node: Node) -> None:
        """Add a node to this graph."""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: Edge) -> None:
        """Add an edge to this graph."""
        self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID (local scope only)."""
        return self.nodes.get(node_id)
    
    def get_subgraph_nodes(self) -> List[Node]:
        """Get all nodes that reference subgraphs."""
        return [n for n in self.nodes.values() if n.is_subgraph()]
    
    def load_subgraph(self, node_id: str) -> "NestedGraph":
        """
        Load the subgraph referenced by a SUBGRAPH node.
        
        Caches loaded subgraphs for efficiency.
        """
        if node_id in self._subgraphs:
            return self._subgraphs[node_id]
        
        node = self.get_node(node_id)
        if not node or not node.is_subgraph():
            raise ValueError(f"Node {node_id} is not a subgraph reference")
        
        # Load from file or inline data
        if node.subgraph_ref:
            subgraph = self._load_from_ref(node.subgraph_ref)
        elif "inline" in node.data:
            subgraph = NestedGraph.from_dict(node.data["inline"])
        else:
            raise ValueError(f"Subgraph node {node_id} has no reference or inline data")
        
        subgraph.id = node_id
        self._subgraphs[node_id] = subgraph
        return subgraph
    
    def _load_from_ref(self, ref: str) -> "NestedGraph":
        """Load a subgraph from a file reference."""
        if self.base_path:
            path = self.base_path / ref
        else:
            path = Path(ref)
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        graph = NestedGraph.from_dict(data)
        graph.base_path = path.parent
        return graph
    
    def resolve_scoped(self, scoped_id: ScopedNodeId) -> Tuple["NestedGraph", Node]:
        """
        Resolve a scoped node ID to the graph and node.
        
        Returns (graph_containing_node, node)
        """
        if len(scoped_id.path) == 1:
            # Local node
            node = self.get_node(scoped_id.local_id)
            if not node:
                raise ValueError(f"Node not found: {scoped_id}")
            return (self, node)
        
        # Traverse hierarchy
        current_graph = self
        for i, segment in enumerate(scoped_id.path[:-1]):
            subgraph = current_graph.load_subgraph(segment)
            current_graph = subgraph
        
        node = current_graph.get_node(scoped_id.local_id)
        if not node:
            raise ValueError(f"Node not found: {scoped_id}")
        return (current_graph, node)
    
    def flatten(self, prefix: str = "") -> Dict[str, Node]:
        """
        Return a flattened view of all nodes including subgraphs.
        
        Node IDs are prefixed with their scope path.
        """
        result = {}
        
        for node_id, node in self.nodes.items():
            full_id = f"{prefix}/{node_id}" if prefix else node_id
            
            if node.is_subgraph():
                # Add the subgraph reference node
                result[full_id] = node
                # Recursively flatten the subgraph
                try:
                    subgraph = self.load_subgraph(node_id)
                    result.update(subgraph.flatten(full_id))
                except Exception:
                    # Subgraph not loadable, just add reference
                    pass
            else:
                result[full_id] = node
        
        return result
    
    def node_count(self, recursive: bool = False) -> int:
        """Count nodes, optionally including subgraphs."""
        count = len(self.nodes)
        if recursive:
            for node in self.get_subgraph_nodes():
                try:
                    subgraph = self.load_subgraph(node.id)
                    count += subgraph.node_count(recursive=True)
                except Exception:
                    pass
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value,
                    "data": n.data,
                    "metadata": n.metadata,
                    "subgraph_ref": n.subgraph_ref
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from_id": e.from_id,
                    "to_id": e.to_id,
                    "relation": e.relation,
                    "weight": e.weight,
                    "metadata": e.metadata
                }
                for e in self.edges
            ],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NestedGraph":
        """Deserialize from dictionary."""
        graph = cls(id=data.get("id", "root"))
        graph.metadata = data.get("metadata", {})
        
        for node_data in data.get("nodes", []):
            node = Node(
                id=node_data["id"],
                type=NodeType(node_data["type"]),
                data=node_data.get("data", {}),
                metadata=node_data.get("metadata", {}),
                subgraph_ref=node_data.get("subgraph_ref")
            )
            graph.add_node(node)
        
        for edge_data in data.get("edges", []):
            edge = Edge(
                from_id=edge_data["from_id"],
                to_id=edge_data["to_id"],
                relation=edge_data["relation"],
                weight=edge_data.get("weight", 1.0),
                metadata=edge_data.get("metadata", {})
            )
            graph.add_edge(edge)
        
        return graph
    
    def save(self, path: Path) -> None:
        """Save graph to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "NestedGraph":
        """Load graph from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        graph = cls.from_dict(data)
        graph.base_path = path.parent
        return graph
    
    def __repr__(self) -> str:
        subgraph_count = len(self.get_subgraph_nodes())
        return f"NestedGraph(id={self.id}, nodes={len(self.nodes)}, subgraphs={subgraph_count}, edges={len(self.edges)})"
