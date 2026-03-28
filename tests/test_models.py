"""Tests for EGS models (Node, Edge, Constraint)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from egs.models import (
    Node, NodeMetadata, NodeType,
    Edge, EdgeMetadata,
    Constraint, ConstraintType
)


class TestNode:
    """Tests for Node model."""
    
    def test_create_node_valid(self):
        """Test creating a node with valid data."""
        metadata = NodeMetadata(
            created_by="user",
            created_at=datetime.now(timezone.utc)
        )
        node = Node(
            id="test-node-1",
            type=NodeType.CONCEPT,
            data={"key": "value"},
            metadata=metadata
        )
        assert node.id == "test-node-1"
        assert node.type == NodeType.CONCEPT
        assert node.data == {"key": "value"}
        assert node.metadata.created_by == "user"
    
    def test_create_node_missing_required_field(self):
        """Test that creating a node without required fields fails."""
        with pytest.raises(ValidationError):
            Node()  # Missing all required fields
    
    def test_node_type_enum_values(self):
        """Test that NodeType enum has expected values."""
        assert NodeType.CONCEPT.value == "CONCEPT"
        assert NodeType.PATTERN.value == "PATTERN"
        assert NodeType.BEHAVIOR.value == "BEHAVIOR"
        assert NodeType.SENSUS.value == "SENSUS"
        assert NodeType.ACTUS.value == "ACTUS"


class TestEdge:
    """Tests for Edge model."""
    
    def test_create_edge_valid(self):
        """Test creating an edge with valid data."""
        metadata = EdgeMetadata(
            created_by="user",
            created_at=datetime.now(timezone.utc)
        )
        edge = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            weight=0.8,
            metadata=metadata
        )
        assert edge.source_id == "node-1"
        assert edge.target_id == "node-2"
        assert edge.relation == "INSTRUCTS"
        assert edge.weight == 0.8
        assert edge.id == "node-1->INSTRUCTS->node-2"
    
    def test_edge_weight_clamping(self):
        """Test that edge weight is clamped to [0.0, 1.0]."""
        metadata = EdgeMetadata(
            created_by="user",
            created_at=datetime.now(timezone.utc)
        )
        
        # Test weight > 1.0 is clamped to 1.0
        edge = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            weight=1.5,
            metadata=metadata
        )
        assert edge.weight == 1.0
        
        # Test weight < 0.0 is clamped to 0.0
        edge2 = Edge(
            source_id="node-1",
            target_id="node-2",
            relation="INSTRUCTS",
            weight=-0.5,
            metadata=metadata
        )
        assert edge2.weight == 0.0


class TestConstraint:
    """Tests for Constraint model."""
    
    def test_create_constraint_valid(self):
        """Test creating a constraint with valid data."""
        constraint = Constraint(
            id="constraint-1",
            type=ConstraintType.STRUCTURAL,
            rule="all_sensus_have_model",
            error_message="All SENSUS nodes must have a model"
        )
        assert constraint.id == "constraint-1"
        assert constraint.type == ConstraintType.STRUCTURAL
        assert constraint.rule == "all_sensus_have_model"
        assert constraint.error_message == "All SENSUS nodes must have a model"
        assert constraint.severity == "ERROR"  # Default value
    
    def test_constraint_default_values(self):
        """Test constraint default values."""
        constraint = Constraint(
            id="constraint-2",
            rule="test_rule",
            error_message="Test error"
        )
        assert constraint.type == ConstraintType.STRUCTURAL
        assert constraint.severity == "ERROR"
    
    def test_constraint_type_enum_values(self):
        """Test that ConstraintType enum has expected values."""
        assert ConstraintType.STRUCTURAL.value == "STRUCTURAL"
        assert ConstraintType.SEMANTIC.value == "SEMANTIC"
        assert ConstraintType.BEHAVIORAL.value == "BEHAVIORAL"
