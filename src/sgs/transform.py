"""SGS Transform Registry and built-in transforms.

Provides the TransformRegistry for registering named transform functions,
and two built-in transforms: duplicate and summarize.

Transform functions modify the graph during execution by producing new
nodes and edges, proving self-modification (Patent Claim 3).

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sgs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata


# RECORD transform_result SHALL AGGREGATE ALL RECORD node AND ALL RECORD edge 'produced 'by ANY PROCESS transform.
@dataclass
class TransformResult:
    """Result of a transform function execution."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


# Type alias for transform functions
TransformFn = Callable[[dict[str, Any], dict], TransformResult]


# SERVICE transform_registry SHALL BIND DATA name TO PROCESS transform THEN RESOLVE DATA name TO PROCESS transform 'on request.
class TransformRegistry:
    """Registry of named transform functions.

    Transform functions take (inputs, config) and return a TransformResult
    containing new nodes and edges to add to the graph.
    """

    def __init__(self):
        self._transforms: dict[str, TransformFn] = {}

    # PROCESS register SHALL BIND PROCESS transform TO DATA name 'as 'an 'idempotent registration.
    def register(self, name: str):
        """Decorator that registers a function by name.

        Usage:
            registry = TransformRegistry()

            @registry.register("my_transform")
            def my_transform(inputs, config):
                return TransformResult(nodes=[...], edges=[...])
        """
        def decorator(fn: TransformFn) -> TransformFn:
            self._transforms[name] = fn
            return fn
        return decorator

    # PROCESS get SHALL RESOLVE DATA name TO PROCESS transform OR RETURN NULL.
    def get(self, name: str) -> TransformFn | None:
        """Return the registered function or None."""
        return self._transforms.get(name)


# Module-level default registry with built-in transforms
default_registry = TransformRegistry()


@default_registry.register("duplicate")
def _builtin_duplicate(inputs: dict[str, Any], config: dict) -> TransformResult:
    """Duplicate input nodes as OPERAND copies with new IDs."""
    nodes = []
    for src_id, value in inputs.items():
        new_node = Node(
            id=f"{src_id}_copy",
            type=NodeType.OPERAND,
            data={"value": value},
            metadata=NodeMetadata(
                created_by="builtin:duplicate",
                created_at=datetime.now(timezone.utc),
            ),
        )
        nodes.append(new_node)
    return TransformResult(nodes=nodes)


@default_registry.register("summarize")
def _builtin_summarize(inputs: dict[str, Any], config: dict) -> TransformResult:
    """Summarize numeric inputs into a single CONCEPT node with statistics."""
    values = [v for v in inputs.values() if isinstance(v, (int, float))]
    output_id = config.get("output_id", "summary")

    stats = {}
    if values:
        stats = {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
    else:
        stats = {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}

    summary_node = Node(
        id=output_id,
        type=NodeType.CONCEPT,
        data=stats,
        metadata=NodeMetadata(
            created_by="builtin:summarize",
            created_at=datetime.now(timezone.utc),
        ),
    )
    return TransformResult(nodes=[summary_node])
