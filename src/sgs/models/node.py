"""Node, NodeMetadata, and NodeType for SGS.

Based on PATENT/LAB/STUDIES/STUDY-106-Serialization/sgs.py
Converted to Pydantic v2.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(Enum):
    """Types of nodes in the SGS."""

    CONCEPT = "CONCEPT"      # Domain entity (abstract ideas)
    PATTERN = "PATTERN"      # Structural template (reusable structures)
    BEHAVIOR = "BEHAVIOR"    # Executable code (actual actions)
    SENSUS = "SENSUS"        # Perception node (LLM-powered query/reasoning)
    ACTUS = "ACTUS"          # Action node (LLM-powered execution)
    OPERAND = "OPERAND"      # Holds a value (leaf node in computation)
    OPERATION = "OPERATION"  # Computes a result from inputs
    RESULT = "RESULT"        # Terminal output node
    TRANSFORM = "TRANSFORM"  # Modifies the graph during execution
    BRANCH = "BRANCH"        # Conditional routing based on input
    MERGE = "MERGE"          # Combines multiple execution paths


class NodeMetadata(BaseModel):
    """Provenance and status information for a node."""

    created_by: str = Field(..., description="Agent ID, 'system', or 'user'")
    created_at: datetime = Field(..., description="When the node was created")
    modified_by: str | None = Field(default=None, description="Last modifier")
    modified_at: datetime | None = Field(default=None, description="Last modification time")
    status: str = Field(default="draft", description="One of: draft, review, approved, archived")


class Node(BaseModel):
    """A node in the superseding graph substrate."""

    id: str = Field(..., description="Unique identifier")
    type: NodeType = Field(..., description="Node type")
    data: dict[str, Any] = Field(default_factory=dict, description="Type-specific payload")
    metadata: NodeMetadata = Field(..., description="Provenance information")