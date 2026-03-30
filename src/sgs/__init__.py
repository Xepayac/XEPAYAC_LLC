"""SGS - Superseding Graph Substrate."""

from sgs.graph import SGS
from sgs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata, Constraint, ConstraintType
from sgs.executor import GraphExecutor, ExecutionTrace, ExecutionStep, CycleError
from sgs.transform import TransformRegistry, TransformResult
from sgs.agent import Agent, AccessError, CoordinationSession
from sgs.provenance import ProvenanceEntry, ProvenanceGraph

__version__ = "0.3.0"
__all__ = [
    "SGS", "Node", "NodeMetadata", "NodeType", "Edge", "EdgeMetadata",
    "Constraint", "ConstraintType",
    "GraphExecutor", "ExecutionTrace", "ExecutionStep", "CycleError",
    "TransformRegistry", "TransformResult",
    "Agent", "AccessError", "CoordinationSession",
    "ProvenanceEntry", "ProvenanceGraph",
]
