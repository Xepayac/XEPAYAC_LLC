#!/usr/bin/env python3
"""
Phase 1 Demo: 1 Seller, 2 Buyers, No Shipping

This demonstrates:
1. Each party runs as SEPARATE PROCESS (different PIDs)
2. Graph file is the ONLY shared resource
3. Private data stays private (hardcoded in each process)
4. Optimizer only sees what parties shared

Scenario:
- Seller: 100 apples, min $1.00
- Buyer A: wants 60, max $1.50 (higher budget)
- Buyer B: wants 80, max $1.20 (lower budget)
- Total demand: 140 > 100 supply

Expected outcome:
- Buyer A gets 60 (full demand, high priority due to price)
- Buyer B gets 40 (partial, 40 unfulfilled)
- Seller revenue: $100 (100 * $1.00)
"""

import os
import subprocess
import sys
from pathlib import Path


def run_party(script: str, graph_path: Path) -> dict:
    """Run a party script as subprocess and capture output."""
    
    result = subprocess.run(
        [sys.executable, script, str(graph_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )
    
    return {
        "script": script,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


def main():
    """Run the Phase 1 demonstration."""
    
    print("=" * 60)
    print("SUPPLY CHAIN OPTIMIZATION - PHASE 1")
    print("1 Seller, 2 Buyers, No Shipping")
    print("=" * 60)
    print()
    
    orchestrator_pid = os.getpid()
    print(f"Orchestrator PID: {orchestrator_pid}")
    print()
    
    # Setup
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    graph_path = output_dir / "phase1_graph.json"
    
    # Clean start
    if graph_path.exists():
        graph_path.unlink()
    
    print("STEP 1: Seller contributes supply")
    print("-" * 40)
    result = run_party("party_seller.py", graph_path)
    print(result["stdout"])
    if result["stderr"]:
        print(f"STDERR: {result['stderr']}")
    
    print("\nSTEP 2: Buyer A contributes demand")
    print("-" * 40)
    result = run_party("party_buyer_a.py", graph_path)
    print(result["stdout"])
    if result["stderr"]:
        print(f"STDERR: {result['stderr']}")
    
    print("\nSTEP 3: Buyer B contributes demand")
    print("-" * 40)
    result = run_party("party_buyer_b.py", graph_path)
    print(result["stdout"])
    if result["stderr"]:
        print(f"STDERR: {result['stderr']}")
    
    print("\nSTEP 4: Optimizer computes allocation")
    print("-" * 40)
    result = run_party("optimizer.py", graph_path)
    print(result["stdout"])
    if result["stderr"]:
        print(f"STDERR: {result['stderr']}")
    
    # Summary
    print("\n" + "=" * 60)
    print("PATENT DEMONSTRATION COMPLETE")
    print("=" * 60)
    print()
    print("Key Points:")
    print("1. Each party ran as SEPARATE PROCESS (see different PIDs above)")
    print("2. Graph file was the ONLY communication channel")
    print("3. Private data (inventory, budgets) stayed in each process")
    print("4. Optimizer had NO database access - only read graph")
    print()
    print(f"Graph saved to: {graph_path}")
    print()
    
    # Verify graph
    import json
    with open(graph_path) as f:
        graph = json.load(f)
    
    print("Graph Summary:")
    print(f"  - Nodes: {len(graph['nodes'])}")
    print(f"  - Edges: {len(graph['edges'])}")
    print(f"  - Log entries: {len(graph['execution_log'])}")
    print()
    
    print("Provenance (who contributed what):")
    for node in graph['nodes']:
        print(f"  - {node['node_id']}: {node['contributed_by']} ({node.get('data_source', 'computed')})")


if __name__ == "__main__":
    main()
