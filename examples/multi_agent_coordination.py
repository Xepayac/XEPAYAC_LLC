"""SGS Multi-Agent Coordination Example.

Agents coordinate through shared graph state.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""
import sys
sys.path.insert(0, '../src')

from sgs import Graph, Node, Edge, NodeType


def main():
    graph = Graph(name="multi_agent_research")
    
    # Coordinator agent
    coordinator = Node(
        id="coordinator",
        type=NodeType.AGENT,
        name="Research Coordinator",
        metadata={"role": "orchestrator"}
    )
    
    # Specialist agents
    searcher = Node(
        id="searcher",
        type=NodeType.AGENT,
        name="Search Agent",
        metadata={"role": "information_retrieval"}
    )
    
    analyzer = Node(
        id="analyzer",
        type=NodeType.AGENT,
        name="Analysis Agent", 
        metadata={"role": "critical_analysis"}
    )
    
    writer = Node(
        id="writer",
        type=NodeType.AGENT,
        name="Writer Agent",
        metadata={"role": "content_synthesis"}
    )
    
    # Shared context (pattern node)
    shared_context = Node(
        id="context",
        type=NodeType.PATTERN,
        name="Shared Context",
        metadata={"type": "knowledge_base"}
    )
    
    # Build graph
    for node in [coordinator, searcher, analyzer, writer, shared_context]:
        graph.add_node(node)
    
    # Coordinator delegates to specialists
    graph.add_edge(Edge(source_id="coordinator", target_id="searcher"))
    graph.add_edge(Edge(source_id="coordinator", target_id="analyzer"))
    
    # Specialists contribute to shared context
    graph.add_edge(Edge(source_id="searcher", target_id="context"))
    graph.add_edge(Edge(source_id="analyzer", target_id="context"))
    
    # Writer synthesizes from context
    graph.add_edge(Edge(source_id="context", target_id="writer"))
    
    print(f"Multi-Agent System: {graph.name}")
    print(f"Agents: {len([n for n in graph.nodes.values() if n.type == NodeType.AGENT])}")
    
    order = graph.topological_sort()
    print(f"Execution order: {[n.id for n in order]}")


if __name__ == "__main__":
    main()
