"""SGS Workflow Orchestration Example.

Parallel and sequential tasks via graph-based execution.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""
import sys
sys.path.insert(0, '../src')

from sgs import Graph, Node, Edge, NodeType


def main():
    graph = Graph(name="document_pipeline")
    
    # Input node
    input_doc = Node(
        id="input",
        type=NodeType.CONCEPT,
        name="Input Document",
    )
    
    # Parallel processing nodes
    extract_text = Node(
        id="extract_text",
        type=NodeType.BEHAVIOR,
        name="Extract Text",
    )
    
    extract_metadata = Node(
        id="extract_metadata", 
        type=NodeType.BEHAVIOR,
        name="Extract Metadata",
    )
    
    # Merge node
    merge = Node(
        id="merge",
        type=NodeType.PATTERN,
        name="Merge Results",
    )
    
    # Output
    output = Node(
        id="output",
        type=NodeType.CONCEPT,
        name="Processed Document",
    )
    
    # Build graph
    for node in [input_doc, extract_text, extract_metadata, merge, output]:
        graph.add_node(node)
    
    # Fan-out from input
    graph.add_edge(Edge(source_id="input", target_id="extract_text"))
    graph.add_edge(Edge(source_id="input", target_id="extract_metadata"))
    
    # Fan-in to merge
    graph.add_edge(Edge(source_id="extract_text", target_id="merge"))
    graph.add_edge(Edge(source_id="extract_metadata", target_id="merge"))
    
    # Final output
    graph.add_edge(Edge(source_id="merge", target_id="output"))
    
    # Analyze
    print(f"Workflow: {graph.name}")
    print(f"Parallel branches: extract_text, extract_metadata")
    
    order = graph.topological_sort()
    print(f"Execution order: {[n.id for n in order]}")


if __name__ == "__main__":
    main()
