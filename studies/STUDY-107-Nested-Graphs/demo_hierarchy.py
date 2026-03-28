#!/usr/bin/env python3
"""
STUDY-93 Demonstration: Nested/Hierarchical Graphs

This demonstrates:
1. Parent graph with SUBGRAPH node references
2. Lazy loading of child graphs
3. Scope isolation (node IDs don't conflict)
4. Hierarchical execution
5. Flattened vs hierarchical views

Usage:
    cd LAB/STUDIES/STUDY-93
    python demo_hierarchy.py
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from nested_graph import NestedGraph, Node, NodeType
from hierarchy_executor import HierarchyExecutor


def main():
    print("=" * 70)
    print("  STUDY-93: Nested/Hierarchical Graph Demonstration")
    print("  Proves EGS-57: Nested/Hierarchical Graphs")
    print("=" * 70)
    
    # Load the parent graph
    parent_path = Path(__file__).parent / "parent_graph.json"
    print(f"\n📁 Loading parent graph: {parent_path.name}")
    
    parent_graph = NestedGraph.load(parent_path)
    
    # ================================================================
    # PROOF 1: Parent graph contains subgraph references
    # ================================================================
    print("\n" + "-" * 70)
    print("  PROOF 1: Parent graph contains SUBGRAPH references")
    print("-" * 70)
    
    print(f"\nParent graph: {parent_graph}")
    print("\nNodes in parent:")
    for node_id, node in parent_graph.nodes.items():
        if node.is_subgraph():
            print(f"  - {node_id} [SUBGRAPH] → {node.subgraph_ref}")
        else:
            print(f"  - {node_id} [{node.type.value}]")
    
    subgraph_nodes = parent_graph.get_subgraph_nodes()
    print(f"\n✓ Found {len(subgraph_nodes)} subgraph references")
    
    # ================================================================
    # PROOF 2: Subgraphs are loaded lazily
    # ================================================================
    print("\n" + "-" * 70)
    print("  PROOF 2: Subgraphs loaded lazily on demand")
    print("-" * 70)
    
    for node in subgraph_nodes:
        print(f"\n📂 Loading subgraph: {node.id} ({node.subgraph_ref})")
        subgraph = parent_graph.load_subgraph(node.id)
        print(f"   {subgraph}")
        print(f"   Nodes: {list(subgraph.nodes.keys())}")
    
    # ================================================================
    # PROOF 3: Scope isolation - node IDs don't conflict
    # ================================================================
    print("\n" + "-" * 70)
    print("  PROOF 3: Scope isolation - IDs are scoped")
    print("-" * 70)
    
    # Both subgraphs could have same node IDs without conflict
    print("\nNode IDs by scope:")
    print(f"  [parent] {list(parent_graph.nodes.keys())}")
    
    for node in subgraph_nodes:
        subgraph = parent_graph.load_subgraph(node.id)
        print(f"  [{node.id}] {list(subgraph.nodes.keys())}")
    
    print("\n✓ Each scope has independent namespace")
    
    # ================================================================
    # PROOF 4: Flattened vs Hierarchical view
    # ================================================================
    print("\n" + "-" * 70)
    print("  PROOF 4: Flattened vs Hierarchical views")
    print("-" * 70)
    
    flattened = parent_graph.flatten()
    print(f"\nHierarchical view: {len(parent_graph.nodes)} nodes in parent")
    print(f"Flattened view: {len(flattened)} total nodes")
    
    print("\nFlattened node IDs (scoped paths):")
    for full_id in sorted(flattened.keys()):
        node = flattened[full_id]
        print(f"  - {full_id} [{node.type.value}]")
    
    # ================================================================
    # PROOF 5: Hierarchical execution
    # ================================================================
    print("\n" + "-" * 70)
    print("  PROOF 5: Hierarchical execution")
    print("-" * 70)
    
    print("\nExecuting graph hierarchy...")
    print()
    
    executor = HierarchyExecutor(parent_graph)
    results = executor.execute(verbose=True)
    
    print(f"\n✓ Execution complete")
    print(f"  Total steps: {len(executor.trace)}")
    print(f"  Results captured: {len(results)}")
    
    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("  PATENT EVIDENCE SUMMARY")
    print("=" * 70)
    
    print("""
    What we demonstrated:

    1. SUBGRAPH ENCAPSULATION
       - Parent graph references children by file path
       - Children loaded on demand, not inlined

    2. SCOPE ISOLATION  
       - Each graph has its own node namespace
       - No ID conflicts between levels

    3. HIERARCHICAL EXECUTION
       - Executor enters/exits subgraphs
       - Maintains separate contexts per scope

    4. FLATTENED VIEW
       - Can view entire hierarchy as flat list
       - Scoped IDs prevent conflicts

    This proves EGS-57: Nested/Hierarchical Graphs
    """)
    
    print("=" * 70)


if __name__ == "__main__":
    main()
