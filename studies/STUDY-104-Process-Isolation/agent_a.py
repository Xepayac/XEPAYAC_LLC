#!/usr/bin/env python3
"""
Agent A: Isolated Process

This agent runs as a SEPARATE PROCESS.
It has EXCLUSIVE access to Database A.
It CANNOT access Database B.
It CANNOT communicate with Agent B directly.

The ONLY way to share information is through the graph file.

Usage: python agent_a.py <graph_file_path>
"""

import sys
import json
from pathlib import Path


# ============================================================
# DATABASE A - Hardcoded in this process
# ============================================================

DATABASE_A = {
    "name": "Alpha Corp Internal Database",
    "data": {
        "q4_revenue": 47_000_000,      # $47 million
        "employee_count": 1250,
        "operating_costs": 38_000_000,
    }
}

# Agent B's database is NOT DEFINED HERE
# This process has NO ACCESS to Database B
# This is enforced by process isolation


# ============================================================
# Graph Operations (minimal, self-contained)
# ============================================================

def load_graph(filepath: str) -> dict:
    """Load graph from JSON file."""
    path = Path(filepath)
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"nodes": [], "edges": []}


def save_graph(filepath: str, graph: dict) -> None:
    """Save graph to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(graph, f, indent=2)


def add_node(graph: dict, node: dict) -> None:
    """Add a node to the graph."""
    graph["nodes"].append(node)


# ============================================================
# Agent A Contribution
# ============================================================

def contribute(graph: dict) -> dict:
    """
    Agent A's contribution to the graph.
    
    This function:
    1. Queries Database A (the only database this process can access)
    2. Adds nodes to the graph
    3. Returns the updated graph
    
    It CANNOT query Database B because Database B does not exist
    in this process's memory space.
    """
    print(f"[Agent_A] Process ID: {os.getpid()}")
    print(f"[Agent_A] Database: {DATABASE_A['name']}")
    print(f"[Agent_A] Available keys: {list(DATABASE_A['data'].keys())}")
    
    # Query OUR database
    q4_revenue = DATABASE_A["data"].get("q4_revenue")
    
    if q4_revenue is not None:
        node = {
            "id": "q4_revenue",
            "type": "OPERAND",
            "data": {"value": q4_revenue},
            "contributed_by": "Agent_A",
            "data_source": f"{DATABASE_A['name']}:q4_revenue"
        }
        add_node(graph, node)
        print(f"[Agent_A] Added node: q4_revenue = {q4_revenue}")
    
    print(f"[Agent_A] Contribution complete.")
    return graph


# ============================================================
# Main Entry Point
# ============================================================

import os

def main():
    if len(sys.argv) != 2:
        print("Usage: python agent_a.py <graph_file_path>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    
    print(f"\n{'=' * 50}")
    print(f"  AGENT A (Separate Process)")
    print(f"{'=' * 50}")
    
    # Load current graph state
    graph = load_graph(graph_file)
    print(f"[Agent_A] Loaded graph with {len(graph['nodes'])} nodes")
    
    # Contribute to graph
    graph = contribute(graph)
    
    # Save updated graph
    save_graph(graph_file, graph)
    print(f"[Agent_A] Saved graph to {graph_file}")
    
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
