"""SGS Basic Execution Example.

Demonstrates topology-driven computation: the graph structure
determines execution order. Nodes execute in dependency order
via Kahn's algorithm.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from datetime import datetime, timezone

from sgs import SGS, Node, NodeType, Edge, EdgeMetadata, NodeMetadata
from sgs.executor import GraphExecutor


def meta() -> NodeMetadata:
    return NodeMetadata(created_by="example", created_at=datetime.now(timezone.utc))


def edge_meta() -> EdgeMetadata:
    return EdgeMetadata(created_by="example", created_at=datetime.now(timezone.utc))


def main():
    """Build and execute: (3 + 5) * 2 = 16"""

    graph = SGS()

    # Leaf nodes — operands hold values
    graph.add_node(Node(id="three", type=NodeType.OPERAND, data={"value": 3}, metadata=meta()))
    graph.add_node(Node(id="five", type=NodeType.OPERAND, data={"value": 5}, metadata=meta()))
    graph.add_node(Node(id="two", type=NodeType.OPERAND, data={"value": 2}, metadata=meta()))

    # Intermediate operation — add
    graph.add_node(Node(id="sum", type=NodeType.OPERATION, data={"operation": "add"}, metadata=meta()))

    # Final result — multiply
    graph.add_node(Node(id="product", type=NodeType.RESULT, data={"operation": "multiply"}, metadata=meta()))

    # Wire dependencies with FEEDS edges
    graph.add_edge(Edge(source_id="three", target_id="sum", relation="FEEDS", metadata=edge_meta()))
    graph.add_edge(Edge(source_id="five", target_id="sum", relation="FEEDS", metadata=edge_meta()))
    graph.add_edge(Edge(source_id="sum", target_id="product", relation="FEEDS", metadata=edge_meta()))
    graph.add_edge(Edge(source_id="two", target_id="product", relation="FEEDS", metadata=edge_meta()))

    # Execute
    executor = GraphExecutor(graph)
    trace = executor.execute()

    # Print trace
    print("SGS Topological Execution: (3 + 5) * 2")
    print("=" * 50)
    for step in trace.steps:
        print(f"  Step {step.order}: {step.node_id} ({step.node_type})")
        if step.inputs:
            print(f"    inputs: {step.inputs}")
        print(f"    output: {step.output}")
    print("=" * 50)
    print(f"Result: {trace.result}")
    print(f"Success: {trace.success}")


if __name__ == "__main__":
    main()
