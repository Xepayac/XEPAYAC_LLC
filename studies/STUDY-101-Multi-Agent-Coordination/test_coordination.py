"""
Test: Can two LLMs coordinate through a shared graph?

This is the validation test for the graph communication hypothesis.
"""

import os
import sys
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lab.protocol import run_conversation, graph_to_context


def save_results(graph, turns, task: str, output_dir: Path):
    """Save test results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save final graph (nodes is dict, edges is list)
    graph_data = {
        "nodes": [
            {
                "id": n.id,
                "type": n.type.value if hasattr(n.type, 'value') else str(n.type),
                "data": n.data,
                "metadata": n.metadata
            }
            for n in graph.nodes.values()
        ],
        "edges": [
            {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "relation": e.relation,
                "weight": e.weight,
                "metadata": e.metadata
            }
            for e in graph.edges
        ]
    }
    
    with open(output_dir / "final_graph.json", "w") as f:
        json.dump(graph_data, f, indent=2)
    
    # Save turn history
    turn_data = []
    for turn in turns:
        turn_data.append({
            "llm_name": turn.llm_name,
            "model": turn.model,
            "nodes_added": turn.nodes_added,
            "edges_added": [list(e) for e in turn.edges_added],
            "raw_response": turn.raw_response
        })
    
    with open(output_dir / "turns.json", "w") as f:
        json.dump(turn_data, f, indent=2)
    
    # Save summary
    summary = f"""# Graph Communication Test Results

## Task
{task}

## Statistics
- Total nodes: {len(graph.nodes)}
- Total edges: {len(graph.edges)}
- Total turns: {len(turns)}

## Nodes by creator
"""
    creators = {}
    for node in graph.nodes.values():
        creator = node.metadata.get('created_by', 'unknown')
        creators[creator] = creators.get(creator, 0) + 1
    
    for creator, count in creators.items():
        summary += f"- {creator}: {count} nodes\n"
    
    summary += f"\n## Final Graph State\n\n```\n{graph_to_context(graph)}\n```\n"
    
    with open(output_dir / "summary.md", "w") as f:
        f.write(summary)
    
    print(f"\nResults saved to {output_dir}/")


def analyze_coordination(graph, turns) -> dict:
    """Analyze how well the LLMs coordinated."""
    analysis = {
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "cross_references": 0,  # Edges between nodes from different LLMs
        "self_references": 0,   # Edges between nodes from same LLM
        "coherence_score": 0.0
    }
    
    # Check cross-references (edges is a list)
    for edge in graph.edges:
        from_node = graph.get_node(edge.from_id)
        to_node = graph.get_node(edge.to_id)
        
        if from_node and to_node:
            from_creator = from_node.metadata.get('created_by', 'unknown')
            to_creator = to_node.metadata.get('created_by', 'unknown')
            
            if from_creator != to_creator:
                analysis["cross_references"] += 1
            else:
                analysis["self_references"] += 1
    
    # Coherence: ratio of cross-references to total edges
    total_edges = analysis["cross_references"] + analysis["self_references"]
    if total_edges > 0:
        analysis["coherence_score"] = analysis["cross_references"] / total_edges
    
    return analysis


def run_test(task: str = None, turns: int = 3, verbose: bool = True):
    """Run the coordination test."""
    
    if task is None:
        task = "Design a simple user authentication system. Define the components, their relationships, and key decisions."
    
    print("=" * 60)
    print("GRAPH COMMUNICATION PROTOCOL TEST")
    print("=" * 60)
    print(f"\nTask: {task}")
    print(f"Turns per LLM: {turns}")
    
    # Run conversation
    graph, turn_history = run_conversation(
        task=task,
        llm_a_name="Alpha",
        llm_a_model="claude-sonnet-4-20250514",
        llm_b_name="Beta", 
        llm_b_model="claude-sonnet-4-20250514",
        turns=turns,
        verbose=verbose
    )
    
    # Analyze results
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    
    analysis = analyze_coordination(graph, turn_history)
    
    print(f"\nTotal nodes created: {analysis['total_nodes']}")
    print(f"Total edges created: {analysis['total_edges']}")
    print(f"Cross-references (LLM A ↔ LLM B): {analysis['cross_references']}")
    print(f"Self-references: {analysis['self_references']}")
    print(f"Coherence score: {analysis['coherence_score']:.2%}")
    
    # Save results
    output_dir = Path(__file__).parent / "state" / "results"
    save_results(graph, turn_history, task, output_dir)
    
    print("\n" + "=" * 60)
    print("FINAL GRAPH")
    print("=" * 60)
    print(graph_to_context(graph))
    
    return graph, turn_history, analysis


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test graph-based LLM communication")
    parser.add_argument("--task", type=str, help="The collaborative task")
    parser.add_argument("--turns", type=int, default=3, help="Number of turns per LLM")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    parser.add_argument("--api-key", type=str, help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Set API key if provided
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    
    # Check if API key is available
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: No API key found.")
        print("\nProvide API key via one of:")
        print("  1. --api-key sk-ant-...")
        print("  2. export ANTHROPIC_API_KEY=sk-ant-...")
        print("  3. Create .env file with ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
    
    run_test(task=args.task, turns=args.turns, verbose=not args.quiet)
