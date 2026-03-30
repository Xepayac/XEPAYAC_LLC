"""Basic SGS usage example.

Demonstrates creating a graph, adding nodes and edges,
querying, and serialization.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""
from datetime import datetime, timezone

from sgs import SGS, Node, NodeType, Edge, EdgeMetadata, NodeMetadata


def main():
    # Create a graph
    graph = SGS()
    now = datetime.now(timezone.utc)
    meta = NodeMetadata(created_by="example", created_at=now)
    edge_meta = EdgeMetadata(created_by="example", created_at=now)

    # Add nodes representing concepts
    graph.add_node(Node(
        id="query",
        type=NodeType.CONCEPT,
        data={"content": "What is SGS?"},
        metadata=meta,
    ))
    graph.add_node(Node(
        id="search",
        type=NodeType.OPERATION,
        data={"operation": "identity", "action": "semantic_search"},
        metadata=meta,
    ))
    graph.add_node(Node(
        id="synthesize",
        type=NodeType.OPERATION,
        data={"operation": "identity", "action": "llm_generate"},
        metadata=meta,
    ))

    # Connect with edges (data flow)
    graph.add_edge(Edge(
        source_id="query", target_id="search",
        relation="FEEDS", metadata=edge_meta,
    ))
    graph.add_edge(Edge(
        source_id="search", target_id="synthesize",
        relation="FEEDS", metadata=edge_meta,
    ))

    # Query the graph
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")

    # Find nodes by type
    ops = graph.find_nodes(node_type=NodeType.OPERATION)
    print(f"OPERATION nodes: {[n.id for n in ops]}")

    # Serialize to dict
    data = graph.to_dict()
    print(f"\nSerialized keys: {list(data.keys())}")
    print(f"Node count in dict: {len(data['nodes'])}")
    print(f"Edge count in dict: {len(data['edges'])}")

    # Summary
    summary = graph.get_summary()
    print(f"\nSummary: {summary}")


if __name__ == "__main__":
    main()
