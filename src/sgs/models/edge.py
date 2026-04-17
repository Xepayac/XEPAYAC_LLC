"""Edge and EdgeMetadata for SGS.

Based on PATENT/LAB/STUDIES/STUDY-106-Serialization/sgs.py
Converted to Pydantic v2.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# RECORD edge_metadata SHALL CAPTURE DATA created_by AND DATA created_at 'for EACH RECORD edge.
class EdgeMetadata(BaseModel):
    """Provenance information for an edge."""

    created_by: str = Field(..., description="Agent ID, 'system', or 'user'")
    created_at: datetime = Field(..., description="When the edge was created")


# RECORD edge SHALL BIND RECORD source TO RECORD target BY DATA relation AND DATA weight.
class Edge(BaseModel):
    """A directed relationship between two nodes."""

    source_id: str = Field(..., description="Source node ID (from)")
    target_id: str = Field(..., description="Target node ID (to)")
    relation: str = Field(..., description="Relationship type")
    weight: float = Field(default=1.0, description="Strength 0.0-1.0")
    metadata: EdgeMetadata = Field(..., description="Provenance information")

    @field_validator("weight")
    @classmethod
    def weight_must_be_valid(cls, v: float) -> float:
        """Clamp weight to valid range [0.0, 1.0]."""
        return max(0.0, min(1.0, float(v)))

    @property
    def id(self) -> str:
        """Generate unique ID for this edge."""
        return f"{self.source_id}->{self.relation}->{self.target_id}"