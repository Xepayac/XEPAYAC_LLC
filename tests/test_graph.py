"""Tests for SGS graph operations."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sgs.graph import SGS
from sgs.models import (
    Node, NodeMetadata, NodeType,
    Edge, EdgeMetadata,
    Constraint, ConstraintType
)


@pytest.fixture
def sample_metadata():
    """Create sample metadata for testing."""
    return NodeMetadata(
        created_by="test",
        created_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_edge_metadata():
    """Create sample edge metadata for testing."""
    return EdgeMetadata(
        created_by="test",
        created_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_node(sample_metadata):
    """Create a sample node for testing."""
    return Node(
        id="node-1",
        type=NodeType.CONCEPT,
        data={"description": "Test node"},
        metadata=sample_metadata
    )


@pytest.fixture
def sample_graph(sample_metadata, sample_edge_metadata):
    """Create a sample graph for testing."""
    graph = SGS()
    
    # Add nodes
    node1 = Node(
        id="node-1",
        type=NodeType.CONCEPT,
        data={"description": "First node"},
        metadata=sample_metadata
    )
    node2 = Node(
        id="node-2",
        type=NodeType.BEHAVIOR,
        data={"description": "Second node"},
        metadata=sample_metadata
    )
    graph.add_node(node1)
    graph.add_node(node2)
    
    # Add edge
    edge = Edge(
        source_id="node-1",
        target_id="node-2",
        relation="INSTRUCTS",
        weight=0.8,
        metadata=sample_edge_metadata
    )
    graph.add_edge(edge)
    
    return graph


class TestSGSBasics:
    """Tests for basic SGS operations."""
    
    def test_create_empty_graph(self):
        """Test creating an empty graph."""
        graph = SGS()
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert len(graph.constraints) == 0
        assert repr(graph) == "SGS(nodes=0, edges=0, constraints=0)"
    
    def test_create_graph_with_metadata(self):
        """Test creating a graph with metadata."""
        metadata = {"version": "0.1.0", "author": "test"}
        graph = SGS(metadata=metadata)
        assert graph.metadata == metadata


class TestNodeOperations:
    """Tests for node CRUD operations."""
    
    def test_add_node(self, sample_node):
        """Test adding a node to the graph."""
        graph = SGS()
        graph.add_node(sample_node)
        assert len(graph.nodes) == 1
        assert "node-1" in graph.nodes
    
    def test_add_duplicate_node(self, sample_node):
        """Test that adding a duplicate node raises an error."""
        graph = SGS()
        graph.add_node(sample_node)
        
        # Try to add the same node again
        with pytest.raises(ValueError, match="Node with id 'node-1' already exists"):
            graph.add_node(sample_node)
    
    def test_get_node(self, sample_node):
        """Test retrieving a node by ID."""
        graph = SGS()
        graph.add_node(sample_node)
        
        retrieved = graph.get_node("node-1")
        assert retrieved is not None
        assert retrieved.id == "node-1"
    
    def test_get_nonexistent_node(self):
        """Test retrieving a non-existent node returns None."""
        graph = SGS()
        assert graph.get_node("nonexistent") is None
    
    def test_remove_node(self, sample_node):
        """Test removing a node from the graph."""
        graph = SGS()
        graph.add_node(sample_node)
        
        removed = graph.remove_node("node-1")
        assert removed is not None
        assert removed.id == "node-1"
        assert len(graph.nodes) == 0
    
    def test_remove_node_also_removes_connected_edges(self, sample_graph):
        """Test that removing a node also removes its connected edges."""
        # sample_graph has 2 nodes and 1 edge
        assert len(sample_graph.nodes) == 2
        assert len(sample_graph.edges) == 1
        
        # Remove node-1
        sample_graph.remove_node("node-1")
        
        # Edge should be removed as well
        assert len(sample_graph.nodes) == 1
        assert len(sample_graph.edges) == 0


class TestEdgeOperations:
    """Tests for edge CRUD operations."""
    
    def test_add_edge(self, sample_metadata, sample_edge_metadata):
        """Test adding an edge to the graph."""
        graph = SGS()
        
        # Add nodes first
        node1 = Node(id="node-1", type=NodeType.CONCEPT, metadata=sample_metadata)
        node2 = Node(id="node-2", type=NodeType.BEHAVIOR, metadata=sample_metadata)
        graph.add_node(node1)
        graph.add_node(node2)
        
        # Add edge
        edge = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            metadata=sample_edge_metadata
        )
        graph.add_edge(edge)
        
        assert len(graph.edges) == 1
    
    def test_add_edge_invalid_source(self, sample_metadata, sample_edge_metadata):
        """Test that adding an edge with invalid source node fails."""
        graph = SGS()
        
        # Add only target node
        node2 = Node(id="node-2", type=NodeType.BEHAVIOR, metadata=sample_metadata)
        graph.add_node(node2)
        
        # Try to add edge with non-existent source
        edge = Edge(
            source_id="nonexistent",
            target_id="node-2",
            relation="INSTRUCTS",
            metadata=sample_edge_metadata
        )
        
        with pytest.raises(ValueError, match="Source node 'nonexistent' does not exist"):
            graph.add_edge(edge)
    
    def test_add_edge_invalid_target(self, sample_metadata, sample_edge_metadata):
        """Test that adding an edge with invalid target node fails."""
        graph = SGS()
        
        # Add only source node
        node1 = Node(id="node-1", type=NodeType.CONCEPT, metadata=sample_metadata)
        graph.add_node(node1)
        
        # Try to add edge with non-existent target
        edge = Edge(
            source_id="node-1",
            target_id="nonexistent",
            relation="INSTRUCTS",
            metadata=sample_edge_metadata
        )
        
        with pytest.raises(ValueError, match="Target node 'nonexistent' does not exist"):
            graph.add_edge(edge)
    
    def test_add_duplicate_edge(self, sample_graph):
        """Test that adding a duplicate edge fails."""
        # sample_graph already has an edge from node-1 to node-2 with INSTRUCTS
        edge_metadata = EdgeMetadata(
            created_by="test",
            created_at=datetime.now(timezone.utc)
        )
        duplicate_edge = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            metadata=edge_metadata
        )
        
        with pytest.raises(ValueError, match="Edge already exists"):
            sample_graph.add_edge(duplicate_edge)
    
    def test_remove_edge(self, sample_graph):
        """Test removing an edge from the graph."""
        assert len(sample_graph.edges) == 1
        
        removed = sample_graph.remove_edge("node-1", "node-2", "INSTRUCTS")
        assert removed is not None
        assert removed.source_id == "node-1"
        assert removed.target_id == "node-2"
        assert len(sample_graph.edges) == 0
    
    def test_remove_nonexistent_edge(self, sample_graph):
        """Test removing a non-existent edge returns None."""
        removed = sample_graph.remove_edge("node-1", "node-2", "NONEXISTENT")
        assert removed is None
    
    def test_get_edges_no_filter(self, sample_graph):
        """Test getting all edges without filters."""
        edges = sample_graph.get_edges()
        assert len(edges) == 1
    
    def test_get_edges_filter_by_source(self, sample_graph):
        """Test getting edges filtered by source node."""
        edges = sample_graph.get_edges(from_id="node-1")
        assert len(edges) == 1
        assert edges[0].source_id == "node-1"
        
        edges = sample_graph.get_edges(from_id="node-2")
        assert len(edges) == 0
    
    def test_get_edges_filter_by_target(self, sample_graph):
        """Test getting edges filtered by target node."""
        edges = sample_graph.get_edges(to_id="node-2")
        assert len(edges) == 1
        assert edges[0].target_id == "node-2"
        
        edges = sample_graph.get_edges(to_id="node-1")
        assert len(edges) == 0
    
    def test_get_edges_filter_by_both(self, sample_graph):
        """Test getting edges filtered by both source and target."""
        edges = sample_graph.get_edges(from_id="node-1", to_id="node-2")
        assert len(edges) == 1


class TestConstraintOperations:
    """Tests for constraint operations."""
    
    def test_add_constraint(self):
        """Test adding a constraint to the graph."""
        graph = SGS()
        constraint = Constraint(
            id="c1",
            type=ConstraintType.STRUCTURAL,
            rule="test_rule",
            error_message="Test constraint"
        )
        graph.add_constraint(constraint)
        
        assert len(graph.constraints) == 1
    
    def test_validate_constraints(self, sample_graph):
        """Test constraint validation."""
        # Add a constraint
        constraint = Constraint(
            id="c1",
            type=ConstraintType.STRUCTURAL,
            rule="test_rule",
            error_message="Test constraint"
        )
        sample_graph.add_constraint(constraint)
        
        # For v0.1.0, validation always returns True
        valid, errors = sample_graph.validate()
        assert valid is True
        assert errors == []


class TestSerialization:
    """Tests for graph serialization and deserialization."""
    
    def test_to_dict(self, sample_graph):
        """Test converting graph to dictionary."""
        data = sample_graph.to_dict()
        
        assert "nodes" in data
        assert "edges" in data
        assert "constraints" in data
        assert "metadata" in data
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
    
    def test_from_dict(self, sample_graph):
        """Test creating graph from dictionary."""
        data = sample_graph.to_dict()
        new_graph = SGS.from_dict(data)
        
        assert len(new_graph.nodes) == 2
        assert len(new_graph.edges) == 1
        assert "node-1" in new_graph.nodes
        assert "node-2" in new_graph.nodes
    
    def test_serialization_roundtrip(self, sample_graph):
        """Test that serialization round-trip preserves data."""
        # Convert to dict and back
        data = sample_graph.to_dict()
        new_graph = SGS.from_dict(data)
        
        # Check nodes
        assert len(new_graph.nodes) == len(sample_graph.nodes)
        for node_id in sample_graph.nodes:
            assert node_id in new_graph.nodes
            original = sample_graph.get_node(node_id)
            restored = new_graph.get_node(node_id)
            assert original.id == restored.id
            assert original.type == restored.type
            assert original.data == restored.data
        
        # Check edges
        assert len(new_graph.edges) == len(sample_graph.edges)


class TestFileSerialization:
    """Tests for file save/load operations."""
    
    def test_save_and_load(self, sample_graph):
        """Test saving and loading graph from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_graph.json"
            
            # Save graph
            sample_graph.save(filepath)
            assert filepath.exists()
            
            # Load graph
            loaded_graph = SGS.load(filepath)
            
            assert len(loaded_graph.nodes) == 2
            assert len(loaded_graph.edges) == 1
            assert "node-1" in loaded_graph.nodes
            assert "node-2" in loaded_graph.nodes
    
    def test_file_roundtrip(self, sample_graph):
        """Test that file save/load round-trip preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_graph.json"
            
            # Save and load
            sample_graph.save(filepath)
            loaded_graph = SGS.load(filepath)
            
            # Verify data matches
            original_data = sample_graph.to_dict()
            loaded_data = loaded_graph.to_dict()
            
            # Compare JSON strings to ensure exact match
            original_json = json.dumps(original_data, sort_keys=True)
            loaded_json = json.dumps(loaded_data, sort_keys=True)
            assert original_json == loaded_json


class TestQueryOperations:
    """Tests for query and traversal operations."""
    
    def test_find_nodes_all(self, sample_graph):
        """Test finding all nodes without filters."""
        nodes = sample_graph.find_nodes()
        assert len(nodes) == 2
    
    def test_find_nodes_by_type(self, sample_graph):
        """Test finding nodes by type."""
        # Find CONCEPT nodes
        concept_nodes = sample_graph.find_nodes(node_type=NodeType.CONCEPT)
        assert len(concept_nodes) == 1
        assert concept_nodes[0].id == "node-1"
        
        # Find BEHAVIOR nodes
        behavior_nodes = sample_graph.find_nodes(node_type=NodeType.BEHAVIOR)
        assert len(behavior_nodes) == 1
        assert behavior_nodes[0].id == "node-2"
        
        # Find non-existent type
        pattern_nodes = sample_graph.find_nodes(node_type=NodeType.PATTERN)
        assert len(pattern_nodes) == 0
    
    def test_find_nodes_by_data_key(self, sample_graph):
        """Test finding nodes by data key."""
        # Find nodes with 'description' key
        nodes = sample_graph.find_nodes(data_key="description")
        assert len(nodes) == 2
        
        # Find nodes with non-existent key
        nodes = sample_graph.find_nodes(data_key="nonexistent")
        assert len(nodes) == 0
    
    def test_find_nodes_by_data_value(self, sample_graph):
        """Test finding nodes by data key/value."""
        # Find node with specific description
        nodes = sample_graph.find_nodes(data_key="description", data_value="First node")
        assert len(nodes) == 1
        assert nodes[0].id == "node-1"
        
        # Find with non-matching value
        nodes = sample_graph.find_nodes(data_key="description", data_value="Nonexistent")
        assert len(nodes) == 0
    
    def test_find_nodes_combined_filters(self, sample_graph):
        """Test finding nodes with combined filters."""
        # Find CONCEPT nodes with specific description
        nodes = sample_graph.find_nodes(
            node_type=NodeType.CONCEPT,
            data_key="description",
            data_value="First node"
        )
        assert len(nodes) == 1
        assert nodes[0].id == "node-1"
        
        # Find BEHAVIOR nodes with CONCEPT's description (should find nothing)
        nodes = sample_graph.find_nodes(
            node_type=NodeType.BEHAVIOR,
            data_key="description",
            data_value="First node"
        )
        assert len(nodes) == 0
    
    def test_find_edges_all(self, sample_graph):
        """Test finding all edges without filters."""
        edges = sample_graph.find_edges()
        assert len(edges) == 1
    
    def test_find_edges_by_from_id(self, sample_graph):
        """Test finding edges by source node."""
        edges = sample_graph.find_edges(from_id="node-1")
        assert len(edges) == 1
        assert edges[0].source_id == "node-1"
        
        edges = sample_graph.find_edges(from_id="node-2")
        assert len(edges) == 0
    
    def test_find_edges_by_to_id(self, sample_graph):
        """Test finding edges by target node."""
        edges = sample_graph.find_edges(to_id="node-2")
        assert len(edges) == 1
        assert edges[0].target_id == "node-2"
        
        edges = sample_graph.find_edges(to_id="node-1")
        assert len(edges) == 0
    
    def test_find_edges_by_relation(self, sample_graph):
        """Test finding edges by relation."""
        edges = sample_graph.find_edges(relation="INSTRUCTS")
        assert len(edges) == 1
        assert edges[0].relation == "INSTRUCTS"
        
        edges = sample_graph.find_edges(relation="NONEXISTENT")
        assert len(edges) == 0
    
    def test_find_edges_combined_filters(self, sample_graph):
        """Test finding edges with combined filters."""
        edges = sample_graph.find_edges(
            from_id="node-1",
            to_id="node-2",
            relation="INSTRUCTS"
        )
        assert len(edges) == 1
        
        # Wrong relation
        edges = sample_graph.find_edges(
            from_id="node-1",
            to_id="node-2",
            relation="WRONG"
        )
        assert len(edges) == 0
    
    def test_get_neighbors_outgoing(self, sample_graph):
        """Test getting outgoing neighbors."""
        neighbors = sample_graph.get_neighbors("node-1", direction="outgoing")
        assert len(neighbors) == 1
        
        neighbor_node, edge = neighbors[0]
        assert neighbor_node.id == "node-2"
        assert edge.source_id == "node-1"
        assert edge.target_id == "node-2"
        
        # Node with no outgoing edges
        neighbors = sample_graph.get_neighbors("node-2", direction="outgoing")
        assert len(neighbors) == 0
    
    def test_get_neighbors_incoming(self, sample_graph):
        """Test getting incoming neighbors."""
        neighbors = sample_graph.get_neighbors("node-2", direction="incoming")
        assert len(neighbors) == 1
        
        neighbor_node, edge = neighbors[0]
        assert neighbor_node.id == "node-1"
        assert edge.source_id == "node-1"
        assert edge.target_id == "node-2"
        
        # Node with no incoming edges
        neighbors = sample_graph.get_neighbors("node-1", direction="incoming")
        assert len(neighbors) == 0
    
    def test_get_neighbors_both(self, sample_metadata, sample_edge_metadata):
        """Test getting neighbors in both directions."""
        graph = SGS()
        
        # Create a triangle: 1 -> 2 -> 3 -> 1
        for i in range(1, 4):
            node = Node(
                id=f"node-{i}",
                type=NodeType.CONCEPT,
                data={},
                metadata=sample_metadata
            )
            graph.add_node(node)
        
        # Add edges in a cycle
        edge1 = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="NEXT",
            metadata=sample_edge_metadata
        )
        edge2 = Edge(
            source_id="node-2",
            target_id="node-3",
            relation="NEXT",
            metadata=sample_edge_metadata
        )
        edge3 = Edge(
            source_id="node-3",
            target_id="node-1",
            relation="NEXT",
            metadata=sample_edge_metadata
        )
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)
        
        # Node-2 has both incoming (from node-1) and outgoing (to node-3)
        neighbors = graph.get_neighbors("node-2", direction="both")
        assert len(neighbors) == 2
        
        neighbor_ids = {n.id for n, e in neighbors}
        assert neighbor_ids == {"node-1", "node-3"}
    
    def test_get_neighbors_with_relation_filter(self, sample_metadata, sample_edge_metadata):
        """Test getting neighbors with relation filter."""
        graph = SGS()
        
        # Create nodes
        node1 = Node(id="node-1", type=NodeType.CONCEPT, data={}, metadata=sample_metadata)
        node2 = Node(id="node-2", type=NodeType.CONCEPT, data={}, metadata=sample_metadata)
        node3 = Node(id="node-3", type=NodeType.CONCEPT, data={}, metadata=sample_metadata)
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        
        # Add edges with different relations
        edge1 = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            metadata=sample_edge_metadata
        )
        edge2 = Edge(
            source_id="node-1",
            target_id="node-3",
            relation="CONTAINS",
            metadata=sample_edge_metadata
        )
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        
        # Get only INSTRUCTS neighbors
        neighbors = graph.get_neighbors("node-1", direction="outgoing", relation="INSTRUCTS")
        assert len(neighbors) == 1
        assert neighbors[0][0].id == "node-2"
        
        # Get only CONTAINS neighbors
        neighbors = graph.get_neighbors("node-1", direction="outgoing", relation="CONTAINS")
        assert len(neighbors) == 1
        assert neighbors[0][0].id == "node-3"
    
    def test_update_node(self, sample_graph):
        """Test updating node data."""
        # Update existing node
        updated = sample_graph.update_node("node-1", {"new_field": "new_value"})
        assert updated is not None
        assert updated.id == "node-1"
        assert updated.data["description"] == "First node"  # Original data preserved
        assert updated.data["new_field"] == "new_value"  # New data added
        
        # Verify the node in the graph is updated
        node = sample_graph.get_node("node-1")
        assert node.data["new_field"] == "new_value"
    
    def test_update_node_overwrite(self, sample_graph):
        """Test that update overwrites existing fields."""
        # Update with overlapping field
        updated = sample_graph.update_node("node-1", {"description": "Updated description"})
        assert updated is not None
        assert updated.data["description"] == "Updated description"
    
    def test_update_node_nonexistent(self, sample_graph):
        """Test updating non-existent node returns None."""
        updated = sample_graph.update_node("nonexistent", {"field": "value"})
        assert updated is None
    
    def test_get_summary_empty_graph(self):
        """Test getting summary of empty graph."""
        graph = SGS()
        summary = graph.get_summary()
        
        assert summary["total_nodes"] == 0
        assert summary["total_edges"] == 0
        assert summary["total_constraints"] == 0
        assert summary["nodes_by_type"] == {}
        assert summary["relations"] == []
    
    def test_get_summary(self, sample_graph):
        """Test getting graph summary."""
        summary = sample_graph.get_summary()
        
        assert summary["total_nodes"] == 2
        assert summary["total_edges"] == 1
        assert summary["total_constraints"] == 0
        assert summary["nodes_by_type"] == {
            "CONCEPT": 1,
            "BEHAVIOR": 1
        }
        assert summary["relations"] == ["INSTRUCTS"]
    
    def test_get_summary_multiple_relations(self, sample_metadata, sample_edge_metadata):
        """Test summary with multiple edge relations."""
        graph = SGS()
        
        # Create nodes
        node1 = Node(id="n1", type=NodeType.CONCEPT, data={}, metadata=sample_metadata)
        node2 = Node(id="n2", type=NodeType.CONCEPT, data={}, metadata=sample_metadata)
        node3 = Node(id="n3", type=NodeType.BEHAVIOR, data={}, metadata=sample_metadata)
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        
        # Add edges with different relations
        edge1 = Edge(source_id="n1", target_id="n2", relation="CONTAINS", metadata=sample_edge_metadata)
        edge2 = Edge(source_id="n2", target_id="n3", relation="INSTRUCTS", metadata=sample_edge_metadata)
        edge3 = Edge(source_id="n1", target_id="n3", relation="ACTIVATES", metadata=sample_edge_metadata)
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)
        
        summary = graph.get_summary()
        
        assert summary["total_nodes"] == 3
        assert summary["total_edges"] == 3
        assert summary["nodes_by_type"] == {
            "CONCEPT": 2,
            "BEHAVIOR": 1
        }
        # Relations should be sorted
        assert summary["relations"] == ["ACTIVATES", "CONTAINS", "INSTRUCTS"]
