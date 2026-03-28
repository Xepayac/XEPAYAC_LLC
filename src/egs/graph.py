"""EGS - Executable Graph Substrate main class.

Core graph data structure with CRUD operations, serialization,
query interface, and constraint validation.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from egs.models import Node, Edge, Constraint, NodeType


class EGS:
    """
    Executable Graph Substrate - the core data structure.

    This graph stores nodes, edges, and constraints, providing
    CRUD operations and serialization capabilities.
    """
    
    def __init__(
        self,
        nodes: Optional[List[Node]] = None,
        edges: Optional[List[Edge]] = None,
        constraints: Optional[List[Constraint]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize an EGS.
        
        Args:
            nodes: Optional list of nodes to initialize with
            edges: Optional list of edges to initialize with
            constraints: Optional list of constraints to initialize with
            metadata: Optional metadata dictionary
        """
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._constraints: List[Constraint] = []
        self._metadata: Dict[str, Any] = metadata or {}
        
        # Initialize with provided data
        if nodes:
            for node in nodes:
                self.add_node(node)
        if edges:
            for edge in edges:
                self.add_edge(edge)
        if constraints:
            for constraint in constraints:
                self.add_constraint(constraint)
    
    @property
    def nodes(self) -> Dict[str, Node]:
        """Get all nodes in the graph."""
        return self._nodes.copy()
    
    @property
    def edges(self) -> List[Edge]:
        """Get all edges in the graph."""
        return self._edges.copy()
    
    @property
    def constraints(self) -> List[Constraint]:
        """Get all constraints in the graph."""
        return self._constraints.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get graph metadata."""
        return self._metadata.copy()
    
    def add_node(self, node: Node) -> None:
        """
        Add a node to the graph.
        
        Args:
            node: The node to add
            
        Raises:
            ValueError: If a node with the same ID already exists
        """
        if node.id in self._nodes:
            raise ValueError(f"Node with id '{node.id}' already exists")
        
        self._nodes[node.id] = node
    
    def remove_node(self, node_id: str) -> Optional[Node]:
        """
        Remove a node from the graph.
        
        Args:
            node_id: ID of the node to remove
            
        Returns:
            The removed node, or None if not found
        """
        node = self._nodes.pop(node_id, None)
        if node:
            # Remove edges connected to this node
            self._edges = [
                e for e in self._edges 
                if e.source_id != node_id and e.target_id != node_id
            ]
        return node
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            node_id: ID of the node to get
            
        Returns:
            The node, or None if not found
        """
        return self._nodes.get(node_id)
    
    def add_edge(self, edge: Edge) -> None:
        """
        Add an edge to the graph.
        
        Args:
            edge: The edge to add
            
        Raises:
            ValueError: If source or target node doesn't exist or edge already exists
        """
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node '{edge.source_id}' does not exist")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node '{edge.target_id}' does not exist")
        
        # Check for duplicate edges
        for existing in self._edges:
            if (existing.source_id == edge.source_id and 
                existing.target_id == edge.target_id and 
                existing.relation == edge.relation):
                raise ValueError(f"Edge already exists: {edge.id}")
        
        self._edges.append(edge)
    
    def remove_edge(self, from_id: str, to_id: str, relation: str) -> Optional[Edge]:
        """
        Remove an edge from the graph.
        
        Args:
            from_id: Source node ID
            to_id: Target node ID
            relation: Edge relation type
            
        Returns:
            The removed edge, or None if not found
        """
        for i, edge in enumerate(self._edges):
            if (edge.source_id == from_id and 
                edge.target_id == to_id and 
                edge.relation == relation):
                return self._edges.pop(i)
        return None
    
    def get_edges(
        self, 
        from_id: Optional[str] = None, 
        to_id: Optional[str] = None
    ) -> List[Edge]:
        """
        Get edges, optionally filtered by source and/or target node.
        
        Args:
            from_id: Optional source node ID to filter by
            to_id: Optional target node ID to filter by
            
        Returns:
            List of matching edges
        """
        result = []
        for edge in self._edges:
            match = True
            if from_id is not None and edge.source_id != from_id:
                match = False
            if to_id is not None and edge.target_id != to_id:
                match = False
            if match:
                result.append(edge)
        return result
    
    def add_constraint(self, constraint: Constraint) -> None:
        """
        Add a constraint to the graph.
        
        Args:
            constraint: The constraint to add
        """
        self._constraints.append(constraint)
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate all constraints in the graph.
        
        Note: This is a basic implementation that returns True since
        constraint validation logic would require callable validators
        which are not serializable. For v0.1.0, this is a placeholder.
        
        Returns:
            Tuple of (all_valid, list_of_error_messages)
        """
        # For v0.1.0, we don't have runtime constraint validation
        # This would be implemented in a future version with proper
        # constraint rule management
        return True, []
    
    def find_nodes(
        self,
        node_type: Optional[NodeType] = None,
        data_key: Optional[str] = None,
        data_value: Optional[Any] = None
    ) -> List[Node]:
        """
        Find nodes matching criteria.
        
        Args:
            node_type: Optional NodeType to filter by
            data_key: Optional key that must exist in node data
            data_value: Optional value for data_key (requires data_key)
            
        Returns:
            List of matching nodes
        """
        result = []
        for node in self._nodes.values():
            match = True
            
            # Filter by type
            if node_type is not None and node.type != node_type:
                match = False
            
            # Filter by data_key existence
            if data_key is not None and data_key not in node.data:
                match = False
            
            # Filter by data_value (only if data_key is specified)
            if data_key is not None and data_value is not None:
                if node.data.get(data_key) != data_value:
                    match = False
            
            if match:
                result.append(node)
        
        return result
    
    def find_edges(
        self,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation: Optional[str] = None
    ) -> List[Edge]:
        """
        Find edges matching criteria.
        
        Args:
            from_id: Optional source node ID to filter by
            to_id: Optional target node ID to filter by
            relation: Optional relation type to filter by
            
        Returns:
            List of matching edges
        """
        result = []
        for edge in self._edges:
            match = True
            
            if from_id is not None and edge.source_id != from_id:
                match = False
            
            if to_id is not None and edge.target_id != to_id:
                match = False
            
            if relation is not None and edge.relation != relation:
                match = False
            
            if match:
                result.append(edge)
        
        return result
    
    def get_neighbors(
        self,
        node_id: str,
        direction: str = "outgoing",
        relation: Optional[str] = None
    ) -> List[Tuple[Node, Edge]]:
        """
        Get neighboring nodes connected to a given node.
        
        Args:
            node_id: ID of the source node
            direction: 'outgoing', 'incoming', or 'both'
            relation: Optional relation type to filter by
            
        Returns:
            List of (neighbor_node, connecting_edge) tuples
        """
        result = []
        
        # Get outgoing neighbors
        if direction in ("outgoing", "both"):
            for edge in self._edges:
                if edge.source_id == node_id:
                    if relation is None or edge.relation == relation:
                        neighbor = self._nodes.get(edge.target_id)
                        if neighbor:
                            result.append((neighbor, edge))
        
        # Get incoming neighbors
        if direction in ("incoming", "both"):
            for edge in self._edges:
                if edge.target_id == node_id:
                    if relation is None or edge.relation == relation:
                        neighbor = self._nodes.get(edge.source_id)
                        if neighbor:
                            result.append((neighbor, edge))
        
        return result
    
    def update_node(self, node_id: str, data: Dict[str, Any]) -> Optional[Node]:
        """
        Update a node's data (creates new node with merged data).
        
        Args:
            node_id: ID of the node to update
            data: Data to merge into existing node data
            
        Returns:
            The updated node, or None if not found
        """
        existing = self._nodes.get(node_id)
        if not existing:
            return None
        
        # Merge data (new data overwrites existing)
        merged_data = {**existing.data, **data}
        
        # Create new node with merged data
        updated_node = Node(
            id=existing.id,
            type=existing.type,
            data=merged_data,
            metadata=existing.metadata
        )
        
        # Replace the node
        self._nodes[node_id] = updated_node
        
        return updated_node
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the graph structure.
        
        Returns:
            Dictionary with:
            - total_nodes: int
            - total_edges: int
            - total_constraints: int
            - nodes_by_type: Dict[str, int]
            - relations: List[str] (unique edge relations)
        """
        # Count nodes by type
        nodes_by_type = {}
        for node in self._nodes.values():
            type_str = node.type.value
            nodes_by_type[type_str] = nodes_by_type.get(type_str, 0) + 1
        
        # Get unique relations
        relations = sorted(list(set(edge.relation for edge in self._edges)))
        
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "total_constraints": len(self._constraints),
            "nodes_by_type": nodes_by_type,
            "relations": relations
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the entire graph to a dictionary.
        
        Returns:
            Dictionary representation of the graph
        """
        return {
            "nodes": [node.model_dump(mode="json") for node in self._nodes.values()],
            "edges": [edge.model_dump(mode="json") for edge in self._edges],
            "constraints": [constraint.model_dump(mode="json") for constraint in self._constraints],
            "metadata": self._metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EGS":
        """
        Deserialize a graph from a dictionary.

        Args:
            data: Dictionary representation of the graph

        Returns:
            New EGS instance
        """
        nodes = [Node.model_validate(n) for n in data.get("nodes", [])]
        edges = [Edge.model_validate(e) for e in data.get("edges", [])]
        constraints = [Constraint.model_validate(c) for c in data.get("constraints", [])]
        metadata = data.get("metadata", {})
        
        return cls(nodes=nodes, edges=edges, constraints=constraints, metadata=metadata)
    
    def save(self, filepath: str | Path) -> None:
        """
        Save the graph to a JSON file.
        
        Args:
            filepath: Path to save the file to
        """
        filepath = Path(filepath)
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str | Path) -> "EGS":
        """
        Load a graph from a JSON file.

        Args:
            filepath: Path to load the file from

        Returns:
            New EGS instance
        """
        filepath = Path(filepath)
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def __repr__(self) -> str:
        """String representation of the graph."""
        return (f"EGS(nodes={len(self._nodes)}, "
                f"edges={len(self._edges)}, "
                f"constraints={len(self._constraints)})")
