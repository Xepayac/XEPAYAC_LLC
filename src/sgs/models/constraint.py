from enum import Enum
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field


class ConstraintType(Enum):
    STRUCTURAL = "STRUCTURAL"
    SEMANTIC = "SEMANTIC"
    BEHAVIORAL = "BEHAVIORAL"


class Constraint(BaseModel):
    id: str = Field(..., description="Unique constraint identifier")
    type: ConstraintType = Field(default=ConstraintType.STRUCTURAL)
    rule: str = Field(..., description="Rule identifier or expression")
    error_message: str = Field(..., description="Message when constraint fails")
    severity: str = Field(default="ERROR", description="ERROR, WARNING, or INFO")
