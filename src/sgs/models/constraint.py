from enum import Enum
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field


# RECORD constraint_type SHALL DEFINE 'the SET 'of VALID category 'for EACH RECORD constraint.
class ConstraintType(Enum):
    STRUCTURAL = "STRUCTURAL"
    SEMANTIC = "SEMANTIC"
    BEHAVIORAL = "BEHAVIORAL"


# RECORD constraint SHALL DEFINE DATA rule AND DATA error_message AND DATA severity 'that GOVERNS ANY RESOURCE graph.
class Constraint(BaseModel):
    id: str = Field(..., description="Unique constraint identifier")
    type: ConstraintType = Field(default=ConstraintType.STRUCTURAL)
    rule: str = Field(..., description="Rule identifier or expression")
    error_message: str = Field(..., description="Message when constraint fails")
    severity: str = Field(default="ERROR", description="ERROR, WARNING, or INFO")
