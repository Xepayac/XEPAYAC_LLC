#!/usr/bin/env python3
"""
Agent B: Isolated Process

This agent runs as a SEPARATE PROCESS.
It has EXCLUSIVE access to Database B.
It CANNOT access Database A.
It CANNOT communicate with Agent A directly.

The ONLY way to share information is through the graph file.

Usage: python agent_b.py <graph_file_path>
"""

import sys
import json
from pathlib import Path


# ============================================================
# DATABASE B - Hardcoded in this process
# ============================================================

DATABASE_B = {
    "name": "Beta Analytics External Database",
    "data": {
        "market_growth_rate": 1.15,    # 15% growth
        "competitor_revenue": 52_000_000,
        "industry_average": 42_000_000,
    }
}

# Agent A's database is NOT DEFINED HERE
# This process has NO ACCESS to Database A
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


def add_edge(graph: dict, edge: dict) -> None:
    """Add an edge to the graph."""
    graph["edges"].append(edge)


# ============================================================
# Agent B Contribution
# ============================================================

import os

def contribute(graph: dict) -> dict:
    """
    Agent B's contribution to the graph.
    
    This function:
    1. Reads existing nodes (from Agent A via graph file)
    2. Queries Database B (the only database this process can access)
    3. Adds nodes and edges to complete the computation
    4. Returns the updated graph
    
    It CANNOT query Database A because Database A does not exist
    in this process's memory space.
    """
    print(f"[Agent_B] Process ID: {os.getpid()}")
    print(f"[Agent_B] Database: {DATABASE_B['name']}")
    print(f"[Agent_B] Available keys: {list(DATABASE_B['data'].keys())}")
    
    # See what Agent A contributed (read from graph file)
    existing_nodes = [n["id"] for n in graph["nodes"]]
    print(f"[Agent_B] Existing nodes from graph: {existing_nodes}")
    
    # Query OUR database
    growth_rate = DATABASE_B["data"].get("market_growth_rate")
    competitor_revenue = DATABASE_B["data"].get("competitor_revenue")
    
    # Add our operand nodes
    if growth_rate is not None:
        node = {
            "id": "growth_rate",
            "type": "OPERAND",
            "data": {"value": growth_rate},
            "contributed_by": "Agent_B",
            "data_source": f"{DATABASE_B['name']}:market_growth_rate"
        }
        add_node(graph, node)
        print(f"[Agent_B] Added node: growth_rate = {growth_rate}")
    
    if competitor_revenue is not None:
        node = {
            "id": "competitor_revenue",
            "type": "OPERAND",
            "data": {"value": competitor_revenue},
            "contributed_by": "Agent_B",
            "data_source": f"{DATABASE_B['name']}:competitor_revenue"
        }
        add_node(graph, node)
        print(f"[Agent_B] Added node: competitor_revenue = {competitor_revenue}")
    
    # Add operation nodes to define computation structure
    
    # Step 1: Multiply q4_revenue * growth_rate
    multiply_node = {
        "id": "multiply_projection",
        "type": "OPERATION",
        "data": {"operation": "multiply"},
        "contributed_by": "Agent_B",
        "data_source": None
    }
    add_node(graph, multiply_node)
    add_edge(graph, {"from_id": "multiply_projection", "to_id": "q4_revenue", "relation": "REQUIRES"})
    add_edge(graph, {"from_id": "multiply_projection", "to_id": "growth_rate", "relation": "REQUIRES"})
    print(f"[Agent_B] Added operation: multiply_projection")
    
    # Step 2: Subtract competitor_revenue
    subtract_node = {
        "id": "subtract_advantage",
        "type": "OPERATION",
        "data": {"operation": "subtract"},
        "contributed_by": "Agent_B",
        "data_source": None
    }
    add_node(graph, subtract_node)
    add_edge(graph, {"from_id": "subtract_advantage", "to_id": "multiply_projection", "relation": "REQUIRES"})
    add_edge(graph, {"from_id": "subtract_advantage", "to_id": "competitor_revenue", "relation": "REQUIRES"})
    print(f"[Agent_B] Added operation: subtract_advantage")
    
    # Step 3: Mark result
    result_node = {
        "id": "result",
        "type": "RESULT",
        "data": {},
        "contributed_by": "Agent_B",
        "data_source": None
    }
    add_node(graph, result_node)
    add_edge(graph, {"from_id": "result", "to_id": "subtract_advantage", "relation": "REQUIRES"})
    print(f"[Agent_B] Added result node")
    
    print(f"[Agent_B] Contribution complete.")
    return graph


# ============================================================
# Main Entry Point
# ============================================================

def main():
    if len(sys.argv) != 2:
        print("Usage: python agent_b.py <graph_file_path>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    
    print(f"\n{'=' * 50}")
    print(f"  AGENT B (Separate Process)")
    print(f"{'=' * 50}")
    
    # Load current graph state
    graph = load_graph(graph_file)
    print(f"[Agent_B] Loaded graph with {len(graph['nodes'])} nodes")
    
    # Contribute to graph
    graph = contribute(graph)
    
    # Save updated graph
    save_graph(graph_file, graph)
    print(f"[Agent_B] Saved graph to {graph_file}")
    
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
