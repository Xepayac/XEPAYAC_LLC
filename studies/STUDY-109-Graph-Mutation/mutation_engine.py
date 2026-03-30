"""
LLM-Directed Graph Mutation Engine

Demonstrates how LLM outputs are parsed and applied as graph mutations.
This is evidence for SGS-71: LLM-Directed Graph Mutation Protocol.
"""

import json
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class MutationType(Enum):
    """Types of mutations that can be applied to a graph."""
    ADD_NODE = "ADD_NODE"
    ADD_EDGE = "ADD_EDGE"
    UPDATE_NODE = "UPDATE_NODE"
    DELETE_NODE = "DELETE_NODE"
    DELETE_EDGE = "DELETE_EDGE"


@dataclass
class MutationInstruction:
    """A single mutation instruction from LLM output."""
    mutation_type: MutationType
    target_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MutationInstruction":
        """Parse mutation from dictionary."""
        return cls(
            mutation_type=MutationType(data["type"]),
            target_id=data["target"],
            payload=data.get("payload", {})
        )


@dataclass
class ValidationResult:
    """Result of mutation validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass 
class MutationResult:
    """Result of applying a mutation."""
    success: bool
    mutation: MutationInstruction
    error: Optional[str] = None


class GraphState:
    """Simple graph state for mutation demonstration."""
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []
    
    def copy(self) -> "GraphState":
        """Create a deep copy for rollback."""
        new_state = GraphState()
        new_state.nodes = copy.deepcopy(self.nodes)
        new_state.edges = copy.deepcopy(self.edges)
        return new_state
    
    def restore_from(self, other: "GraphState") -> None:
        """Restore state from another graph (rollback)."""
        self.nodes = copy.deepcopy(other.nodes)
        self.edges = copy.deepcopy(other.edges)


class MutationEngine:
    """
    Engine for applying LLM-directed mutations to a graph.
    
    Key capabilities:
    - Parse structured LLM output into mutations
    - Validate mutations before applying
    - Atomic rollback on failure
    - Support for add, update, delete operations
    """
    
    # Schema for validation
    REQUIRED_NODE_FIELDS = {"id", "type"}
    VALID_NODE_TYPES = {"TASK", "DECISION", "CONTEXT", "AGENT_OUTPUT", "DATA"}
    
    def __init__(self, graph: Optional[GraphState] = None):
        self.graph = graph or GraphState()
        self.mutation_log: List[MutationResult] = []
    
    def parse_llm_output(self, llm_output: str) -> List[MutationInstruction]:
        """
        Parse LLM output into mutation instructions.
        
        Expected format:
        {
            "mutations": [
                {"type": "ADD_NODE", "target": "node_id", "payload": {...}},
                {"type": "ADD_EDGE", "target": "edge_id", "payload": {"source": "a", "target": "b"}}
            ]
        }
        """
        try:
            data = json.loads(llm_output)
            mutations = []
            for m in data.get("mutations", []):
                mutations.append(MutationInstruction.from_dict(m))
            return mutations
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Failed to parse LLM output: {e}")
    
    def validate_mutation(self, mutation: MutationInstruction) -> ValidationResult:
        """
        Validate a mutation before applying.
        
        Checks:
        - Required fields present
        - Valid node types
        - Target exists (for updates/deletes)
        - No duplicates (for adds)
        """
        errors = []
        
        if mutation.mutation_type == MutationType.ADD_NODE:
            # Check required fields
            if "type" not in mutation.payload:
                errors.append("Missing required field: type")
            elif mutation.payload.get("type") not in self.VALID_NODE_TYPES:
                errors.append(f"Invalid node type: {mutation.payload.get('type')}")
            
            # Check for duplicate
            if mutation.target_id in self.graph.nodes:
                errors.append(f"Node already exists: {mutation.target_id}")
        
        elif mutation.mutation_type == MutationType.UPDATE_NODE:
            if mutation.target_id not in self.graph.nodes:
                errors.append(f"Node not found: {mutation.target_id}")
        
        elif mutation.mutation_type == MutationType.DELETE_NODE:
            if mutation.target_id not in self.graph.nodes:
                errors.append(f"Node not found: {mutation.target_id}")
        
        elif mutation.mutation_type == MutationType.ADD_EDGE:
            source = mutation.payload.get("source")
            target = mutation.payload.get("target")
            if not source or not target:
                errors.append("Edge requires source and target")
            # Note: We allow edges to non-existent nodes for flexibility
        
        elif mutation.mutation_type == MutationType.DELETE_EDGE:
            source = mutation.payload.get("source")
            target = mutation.payload.get("target")
            edge_exists = any(
                e["source"] == source and e["target"] == target 
                for e in self.graph.edges
            )
            if not edge_exists:
                errors.append(f"Edge not found: {source} -> {target}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
    
    def apply_mutation(self, mutation: MutationInstruction) -> MutationResult:
        """Apply a single mutation to the graph."""
        
        # Validate first
        validation = self.validate_mutation(mutation)
        if not validation.valid:
            return MutationResult(
                success=False,
                mutation=mutation,
                error="; ".join(validation.errors)
            )
        
        try:
            if mutation.mutation_type == MutationType.ADD_NODE:
                self.graph.nodes[mutation.target_id] = {
                    "id": mutation.target_id,
                    **mutation.payload
                }
            
            elif mutation.mutation_type == MutationType.UPDATE_NODE:
                self.graph.nodes[mutation.target_id].update(mutation.payload)
            
            elif mutation.mutation_type == MutationType.DELETE_NODE:
                del self.graph.nodes[mutation.target_id]
                # Also remove connected edges
                self.graph.edges = [
                    e for e in self.graph.edges 
                    if e["source"] != mutation.target_id and e["target"] != mutation.target_id
                ]
            
            elif mutation.mutation_type == MutationType.ADD_EDGE:
                self.graph.edges.append({
                    "source": mutation.payload["source"],
                    "target": mutation.payload["target"],
                    "type": mutation.payload.get("type", "connects")
                })
            
            elif mutation.mutation_type == MutationType.DELETE_EDGE:
                source = mutation.payload["source"]
                target = mutation.payload["target"]
                self.graph.edges = [
                    e for e in self.graph.edges
                    if not (e["source"] == source and e["target"] == target)
                ]
            
            return MutationResult(success=True, mutation=mutation)
        
        except Exception as e:
            return MutationResult(
                success=False,
                mutation=mutation,
                error=str(e)
            )
    
    def apply_mutations_atomic(
        self, 
        mutations: List[MutationInstruction],
        rollback_on_failure: bool = True
    ) -> Tuple[List[MutationResult], bool]:
        """
        Apply multiple mutations atomically.
        
        If rollback_on_failure is True and any mutation fails,
        the entire batch is rolled back.
        """
        # Save state for potential rollback
        checkpoint = self.graph.copy()
        results = []
        all_success = True
        
        for mutation in mutations:
            result = self.apply_mutation(mutation)
            results.append(result)
            self.mutation_log.append(result)
            
            if not result.success:
                all_success = False
                if rollback_on_failure:
                    # Rollback to checkpoint
                    self.graph.restore_from(checkpoint)
                    break
        
        return results, all_success
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get summary of current graph state."""
        return {
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
            "node_ids": list(self.graph.nodes.keys()),
            "mutations_applied": len(self.mutation_log),
            "successful_mutations": sum(1 for r in self.mutation_log if r.success)
        }


def create_initial_graph() -> GraphState:
    """Create an initial graph for testing."""
    graph = GraphState()
    graph.nodes = {
        "task_1": {"id": "task_1", "type": "TASK", "content": "Implement feature A"},
        "task_2": {"id": "task_2", "type": "TASK", "content": "Test feature A"},
        "decision_1": {"id": "decision_1", "type": "DECISION", "content": "Use approach X"}
    }
    graph.edges = [
        {"source": "task_1", "target": "task_2", "type": "precedes"},
        {"source": "decision_1", "target": "task_1", "type": "informs"}
    ]
    return graph
