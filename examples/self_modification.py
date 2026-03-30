"""SGS Self-Modification Example.

Demonstrates how a TRANSFORM node modifies the graph during execution
by creating a summary node from numeric operands.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from datetime import datetime, timezone

from sgs.graph import SGS
from sgs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata
from sgs.executor import GraphExecutor
from sgs.transform import default_registry


def main():
    graph = SGS()
    meta = NodeMetadata(created_by="user", created_at=datetime.now(timezone.utc))
    edge_meta = EdgeMetadata(created_by="user", created_at=datetime.now(timezone.utc))

    # Three numeric operands
    for name, value in [("op_a", 10), ("op_b", 20), ("op_c", 30)]:
        graph.add_node(Node(
            id=name,
            type=NodeType.OPERAND,
            data={"value": value},
            metadata=meta,
        ))

    # TRANSFORM node that will summarize inputs
    graph.add_node(Node(
        id="summarizer",
        type=NodeType.TRANSFORM,
        data={"transform_fn": "summarize"},
        metadata=meta,
    ))

    # Wire FEEDS edges from operands to transform
    for op_id in ["op_a", "op_b", "op_c"]:
        graph.add_edge(Edge(
            source_id=op_id,
            target_id="summarizer",
            relation="FEEDS",
            metadata=edge_meta,
        ))

    print(f"Node count BEFORE execution: {len(graph.nodes)}")

    # Execute with the built-in registry
    executor = GraphExecutor(graph, transforms=default_registry)
    trace = executor.execute()

    print(f"Node count AFTER execution:  {len(graph.nodes)}")
    print(f"Execution success: {trace.success}")

    # Print the summary node's data
    summary = graph.get_node("summary")
    if summary:
        print(f"\nSummary node data:")
        print(f"  count: {summary.data['count']}")
        print(f"  sum:   {summary.data['sum']}")
        print(f"  avg:   {summary.data['avg']}")
        print(f"  min:   {summary.data['min']}")
        print(f"  max:   {summary.data['max']}")
        print(f"  created_by: {summary.metadata.created_by}")


if __name__ == "__main__":
    main()
