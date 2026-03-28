#!/usr/bin/env python3
"""
Buyer A Party - Runs as isolated process

PRIVATE DATA (hardcoded, not shared):
- Demand: 60 apples
- Maximum price willing to pay: $1.50/apple

This process can ONLY:
1. Read the graph file
2. Add its demand node to the graph
3. Write the graph file

It CANNOT access seller inventory or Buyer B's max price.
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from graph import SupplyChainGraph, DemandNode


# ============================================================
# PRIVATE DATA - This is Buyer A's secret information
# In reality, this would come from their private database
# ============================================================
BUYER_A_DATABASE = {
    "company": "Grocery Chain Alpha",
    "product": "apples",
    "demand": 60,
    "max_price": 1.50,  # Won't pay more than this
    "notes": "Weekly restock for 12 stores"
}
# ============================================================


def main():
    """Buyer A contributes demand information to graph."""
    
    pid = os.getpid()
    print(f"[BUYER_A] Process started (PID: {pid})")
    print(f"[BUYER_A] Company: {BUYER_A_DATABASE['company']}")
    print(f"[BUYER_A] PRIVATE: Demand={BUYER_A_DATABASE['demand']}, MaxPrice=${BUYER_A_DATABASE['max_price']}")
    
    # Get graph path from command line
    if len(sys.argv) < 2:
        print("[BUYER_A] Error: Graph path required")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    print(f"[BUYER_A] Graph file: {graph_path}")
    
    # Load existing graph
    graph = SupplyChainGraph.load(graph_path)
    
    # Add our demand node
    demand = DemandNode(
        node_id="demand_buyer_a",
        node_type="demand",
        product=BUYER_A_DATABASE["product"],
        quantity=BUYER_A_DATABASE["demand"],
        max_price=BUYER_A_DATABASE["max_price"],
        contributed_by=BUYER_A_DATABASE["company"],
        data_source="buyer_a_private_orders"
    )
    
    graph.add_demand(demand)
    print(f"[BUYER_A] Added demand node: {demand.quantity} {demand.product} @ max ${demand.max_price}")
    
    # Save graph
    graph.save(graph_path)
    print(f"[BUYER_A] Graph saved")
    print(f"[BUYER_A] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
