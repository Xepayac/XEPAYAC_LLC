#!/usr/bin/env python3
"""
Buyer B Party - Runs as isolated process

PRIVATE DATA (hardcoded, not shared):
- Demand: 80 apples
- Maximum price willing to pay: $1.20/apple

This process can ONLY:
1. Read the graph file
2. Add its demand node to the graph
3. Write the graph file

It CANNOT access seller inventory or Buyer A's max price.
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from graph import SupplyChainGraph, DemandNode


# ============================================================
# PRIVATE DATA - This is Buyer B's secret information
# In reality, this would come from their private database
# ============================================================
BUYER_B_DATABASE = {
    "company": "Restaurant Group Beta",
    "product": "apples",
    "demand": 80,
    "max_price": 1.20,  # Won't pay more than this (tighter budget)
    "notes": "Bulk order for apple pie production"
}
# ============================================================


def main():
    """Buyer B contributes demand information to graph."""
    
    pid = os.getpid()
    print(f"[BUYER_B] Process started (PID: {pid})")
    print(f"[BUYER_B] Company: {BUYER_B_DATABASE['company']}")
    print(f"[BUYER_B] PRIVATE: Demand={BUYER_B_DATABASE['demand']}, MaxPrice=${BUYER_B_DATABASE['max_price']}")
    
    # Get graph path from command line
    if len(sys.argv) < 2:
        print("[BUYER_B] Error: Graph path required")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    print(f"[BUYER_B] Graph file: {graph_path}")
    
    # Load existing graph
    graph = SupplyChainGraph.load(graph_path)
    
    # Add our demand node
    demand = DemandNode(
        node_id="demand_buyer_b",
        node_type="demand",
        product=BUYER_B_DATABASE["product"],
        quantity=BUYER_B_DATABASE["demand"],
        max_price=BUYER_B_DATABASE["max_price"],
        contributed_by=BUYER_B_DATABASE["company"],
        data_source="buyer_b_private_orders"
    )
    
    graph.add_demand(demand)
    print(f"[BUYER_B] Added demand node: {demand.quantity} {demand.product} @ max ${demand.max_price}")
    
    # Save graph
    graph.save(graph_path)
    print(f"[BUYER_B] Graph saved")
    print(f"[BUYER_B] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
