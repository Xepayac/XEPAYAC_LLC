"""EGS - Executable Graph Substrate."""

from egs.graph import EGS
from egs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata, Constraint, ConstraintType
from egs.executor import GraphExecutor, ExecutionTrace, ExecutionStep, CycleError
from egs.transform import TransformRegistry, TransformResult
from egs.agent import Agent, AccessError, CoordinationSession
from egs.provenance import ProvenanceEntry, ProvenanceGraph

__version__ = "0.3.0"
__all__ = [
    "EGS", "Node", "NodeMetadata", "NodeType", "Edge", "EdgeMetadata",
    "Constraint", "ConstraintType",
    "GraphExecutor", "ExecutionTrace", "ExecutionStep", "CycleError",
    "TransformRegistry", "TransformResult",
    "Agent", "AccessError", "CoordinationSession",
    "ProvenanceEntry", "ProvenanceGraph",
]
