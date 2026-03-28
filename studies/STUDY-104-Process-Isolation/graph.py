"""
Shared Graph Structure

The graph is the ONLY communication channel between agents.
Agents cannot communicate directly - only through this structure.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum


class NodeType(Enum):
    """Types of nodes in the computation graph."""
    OPERAND = "OPERAND"      # Contains a value
    OPERATION = "OPERATION"  # Defines a computation
    RESULT = "RESULT"        # Marks the final output


@dataclass
class Node:
    """
    A node in the computation graph.
    
    Nodes are contributed by agents and contain either:
    - A value (OPERAND)
    - An operation (OPERATION)
    - A result marker (RESULT)
    """
    id: str
    node_type: NodeType
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Provenance: which agent contributed this node
    contributed_by: Optional[str] = None
    data_source: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.node_type.value,
            "data": self.data,
            "contributed_by": self.contributed_by,
            "data_source": self.data_source
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(
            id=d["id"],
            node_type=NodeType(d["type"]),
            data=d.get("data", {}),
            contributed_by=d.get("contributed_by"),
            data_source=d.get("data_source")
        )


@dataclass
class Edge:
    """
    An edge in the computation graph.
    
    Edges define dependencies: from_id REQUIRES to_id
    This means: to compute from_id, we first need to_id
    """
    from_id: str
    to_id: str
    relation: str = "REQUIRES"
    
    def to_dict(self) -> dict:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "relation": self.relation
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(
            from_id=d["from_id"],
            to_id=d["to_id"],
            relation=d.get("relation", "REQUIRES")
        )


class SharedGraph:
    """
    The shared graph structure.
    
    This is the ONLY mechanism through which agents can collaborate.
    
    Key properties:
    - Agents add nodes (they cannot modify other agents' nodes)
    - Agents add edges (connecting their nodes to existing nodes)
    - The graph is serializable for persistence and audit
    - The graph structure defines the computation
    """
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
    
    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")
        self.nodes[node.id] = node
    
    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        # Validate that referenced nodes exist
        if edge.from_id not in self.nodes:
            raise ValueError(f"Node {edge.from_id} not found")
        if edge.to_id not in self.nodes:
            raise ValueError(f"Node {edge.to_id} not found")
        self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes that a given node depends on."""
        return [e.to_id for e in self.edges if e.from_id == node_id]
    
    def to_dict(self) -> dict:
        """Serialize graph to dictionary."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize graph to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, d: dict) -> "SharedGraph":
        """Deserialize graph from dictionary."""
        graph = cls()
        for node_dict in d.get("nodes", []):
            graph.nodes[node_dict["id"]] = Node.from_dict(node_dict)
        for edge_dict in d.get("edges", []):
            graph.edges.append(Edge.from_dict(edge_dict))
        return graph
    
    @classmethod
    def from_json(cls, json_str: str) -> "SharedGraph":
        """Deserialize graph from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def save(self, filepath: str) -> None:
        """Save graph to file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, filepath: str) -> "SharedGraph":
        """Load graph from file."""
        with open(filepath, 'r') as f:
            return cls.from_json(f.read())
    
    def print_structure(self) -> None:
        """Print a visual representation of the graph."""
        print("\n" + "=" * 50)
        print("GRAPH STRUCTURE")
        print("=" * 50)
        
        print("\nNODES:")
        for node in self.nodes.values():
            if node.node_type == NodeType.OPERAND:
                print(f"  [{node.id}] OPERAND: {node.data.get('value')}")
            elif node.node_type == NodeType.OPERATION:
                print(f"  [{node.id}] OPERATION: {node.data.get('operation')}")
            else:
                print(f"  [{node.id}] RESULT")
            if node.contributed_by:
                print(f"       └─ contributed by: {node.contributed_by}")
            if node.data_source:
                print(f"       └─ data source: {node.data_source}")
        
        print("\nEDGES:")
        for edge in self.edges:
            print(f"  {edge.from_id} ──{edge.relation}──> {edge.to_id}")
        
        print("=" * 50)
