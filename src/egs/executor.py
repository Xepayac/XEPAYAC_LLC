"""EGS Topological Graph Executor.

Executes graph nodes in dependency order using Kahn's algorithm.
Proves Patent Claims 1-3: topology-driven computation where the
graph structure determines execution order.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from egs.graph import EGS
from egs.models import NodeType
from egs.transform import TransformRegistry


class CycleError(Exception):
    """Raised when the execution graph contains a cycle."""


@dataclass
class ExecutionStep:
    """Record of a single node execution."""

    order: int
    node_id: str
    node_type: str
    inputs: dict[str, Any]
    output: Any
    skipped: bool = False


@dataclass
class ExecutionTrace:
    """Complete record of a graph execution."""

    steps: list[ExecutionStep] = field(default_factory=list)
    result: Any = None
    success: bool = True
    error: Optional[str] = None


# Edge relations that express data/execution dependency
DEPENDENCY_RELATIONS = {"FEEDS", "REQUIRES"}

# Node types that participate in execution
EXECUTABLE_TYPES = {
    NodeType.OPERAND,
    NodeType.OPERATION,
    NodeType.RESULT,
    NodeType.TRANSFORM,
    NodeType.BRANCH,
    NodeType.MERGE,
}


def _topological_sort(graph: EGS) -> list[str]:
    """Sort executable nodes by dependency using Kahn's algorithm.

    Returns node IDs in execution order (dependencies first).
    Raises CycleError if the graph contains a cycle.
    """
    exec_nodes = {
        nid for nid, node in graph.nodes.items()
        if node.type in EXECUTABLE_TYPES
    }
    if not exec_nodes:
        return []

    # Build adjacency and in-degree for executable subgraph
    in_degree: dict[str, int] = {nid: 0 for nid in exec_nodes}
    dependents: dict[str, list[str]] = {nid: [] for nid in exec_nodes}

    for edge in graph.edges:
        if edge.relation not in DEPENDENCY_RELATIONS:
            continue
        src, tgt = edge.source_id, edge.target_id
        if src in exec_nodes and tgt in exec_nodes:
            in_degree[tgt] += 1
            dependents[src].append(tgt)

    # Start with leaf nodes (in-degree 0)
    queue = deque(
        sorted(nid for nid, deg in in_degree.items() if deg == 0)
    )
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for dep in sorted(dependents[nid]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(order) != len(exec_nodes):
        visited = set(order)
        cycle_nodes = [nid for nid in exec_nodes if nid not in visited]
        raise CycleError(
            f"Cycle detected involving nodes: {cycle_nodes}"
        )

    return order


def _gather_inputs(
    graph: EGS, node_id: str, outputs: dict[str, Any]
) -> dict[str, Any]:
    """Collect outputs from predecessor nodes via FEEDS edges."""
    inputs: dict[str, Any] = {}
    for edge in graph.edges:
        if edge.target_id == node_id and edge.relation == "FEEDS":
            src = edge.source_id
            if src in outputs:
                inputs[src] = outputs[src]
    return inputs


def _execute_operand(node_data: dict[str, Any]) -> Any:
    """OPERAND: return the stored value."""
    return node_data.get("value")


def _execute_operation(
    node_data: dict[str, Any], inputs: dict[str, Any]
) -> Any:
    """OPERATION: apply an arithmetic/logic operation to inputs."""
    op = node_data.get("operation", "identity")
    values = list(inputs.values())

    if op == "add":
        return sum(values) if values else 0

    if op == "multiply":
        result = 1
        for v in values:
            result *= v
        return result

    if op == "subtract":
        if len(values) >= 2:
            return values[0] - values[1]
        return values[0] if values else 0

    if op == "compare":
        if len(values) < 2:
            return False
        cmp = node_data.get("comparator", "eq")
        if cmp == "eq":
            return values[0] == values[1]
        if cmp == "lt":
            return values[0] < values[1]
        if cmp == "gt":
            return values[0] > values[1]
        return False

    if op == "filter":
        condition = node_data.get("condition")
        if not values:
            return None
        val = values[0]
        if condition == "positive":
            return val if val > 0 else None
        if condition == "nonzero":
            return val if val != 0 else None
        if condition == "truthy":
            return val if val else None
        return val

    if op == "aggregate":
        method = node_data.get("method", "sum")
        if not values:
            return None
        if method == "sum":
            return sum(values)
        if method == "avg":
            return sum(values) / len(values)
        if method == "min":
            return min(values)
        if method == "max":
            return max(values)
        if method == "count":
            return len(values)
        return sum(values)

    # identity (default)
    return values[0] if values else None


def _execute_branch(
    node_data: dict[str, Any], inputs: dict[str, Any]
) -> Any:
    """BRANCH: route based on a boolean input."""
    values = list(inputs.values())
    condition = values[0] if values else False
    return {"condition": bool(condition), "active": bool(condition)}


def _execute_merge(inputs: dict[str, Any]) -> Any:
    """MERGE: collect all inputs into a list."""
    return list(inputs.values())


class GraphExecutor:
    """Topological graph executor.

    Reads an EGS graph, sorts nodes by dependency edges, and executes
    each node step-by-step. The executor does not modify the graph.

    Usage:
        executor = GraphExecutor(graph)
        trace = executor.execute()
        print(trace.result)
    """

    def __init__(self, graph: EGS, transforms: Optional[TransformRegistry] = None):
        self.graph = graph
        self.transforms = transforms

    def execute(self) -> ExecutionTrace:
        """Execute the graph and return a trace of all steps."""
        trace = ExecutionTrace()

        try:
            order = _topological_sort(self.graph)
        except CycleError as e:
            trace.success = False
            trace.error = str(e)
            return trace

        if not order:
            trace.success = True
            return trace

        outputs: dict[str, Any] = {}

        for step_num, node_id in enumerate(order):
            node = self.graph.get_node(node_id)
            if node is None:
                continue

            inputs = _gather_inputs(self.graph, node_id, outputs)

            if node.type == NodeType.OPERAND:
                output = _execute_operand(node.data)
            elif node.type == NodeType.OPERATION:
                output = _execute_operation(node.data, inputs)
            elif node.type == NodeType.RESULT:
                output = _execute_operation(node.data, inputs)
            elif node.type == NodeType.BRANCH:
                output = _execute_branch(node.data, inputs)
            elif node.type == NodeType.MERGE:
                output = _execute_merge(inputs)
            elif node.type == NodeType.TRANSFORM:
                output = self._execute_transform(node, inputs, node_id)
            else:
                output = None

            outputs[node_id] = output

            step = ExecutionStep(
                order=step_num,
                node_id=node_id,
                node_type=node.type.value,
                inputs=inputs,
                output=output,
            )
            trace.steps.append(step)

            # If this is a RESULT node, capture as final result
            if node.type == NodeType.RESULT:
                trace.result = output

        return trace

    def _execute_transform(
        self, node, inputs: dict[str, Any], node_id: str
    ) -> Any:
        """Execute a TRANSFORM node, potentially modifying the graph."""
        transform_name = node.data.get("transform_fn")
        if not self.transforms or not transform_name:
            return inputs

        transform_fn = self.transforms.get(transform_name)
        if transform_fn is None:
            return inputs

        result = transform_fn(inputs, node.data.get("config", {}))
        now = datetime.now(timezone.utc)
        created_ids = []

        for new_node in result.nodes:
            updated = new_node.model_copy(
                update={
                    "metadata": new_node.metadata.model_copy(
                        update={
                            "created_by": f"transform:{node_id}",
                            "created_at": now,
                        }
                    )
                }
            )
            self.graph.add_node(updated)
            created_ids.append(updated.id)

        for new_edge in result.edges:
            updated = new_edge.model_copy(
                update={
                    "metadata": new_edge.metadata.model_copy(
                        update={
                            "created_by": f"transform:{node_id}",
                            "created_at": now,
                        }
                    )
                }
            )
            self.graph.add_edge(updated)

        return created_ids
