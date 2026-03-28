#!/usr/bin/env python3
"""
Seller Party - Runs as isolated process

PRIVATE DATA (hardcoded, not shared):
- Inventory: 100 apples
- Minimum acceptable price: $1.00/apple

This process can ONLY:
1. Read the graph file
2. Add its supply node to the graph
3. Write the graph file

It CANNOT access buyer data.
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from graph import SupplyChainGraph, SupplyNode


# ============================================================
# PRIVATE DATA - This is the seller's secret information
# In reality, this would come from their private database
# ============================================================
SELLER_DATABASE = {
    "company": "Apple Farm Co",
    "product": "apples",
    "inventory": 100,
    "min_price": 1.00,  # Won't sell below this
    "notes": "Fresh harvest, grade A"
}
# ============================================================


def main():
    """Seller contributes supply information to graph."""
    
    pid = os.getpid()
    print(f"[SELLER] Process started (PID: {pid})")
    print(f"[SELLER] Company: {SELLER_DATABASE['company']}")
    print(f"[SELLER] PRIVATE: Inventory={SELLER_DATABASE['inventory']}, MinPrice=${SELLER_DATABASE['min_price']}")
    
    # Get graph path from command line
    if len(sys.argv) < 2:
        print("[SELLER] Error: Graph path required")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    print(f"[SELLER] Graph file: {graph_path}")
    
    # Load existing graph (or create new)
    graph = SupplyChainGraph.load(graph_path)
    
    # Add our supply node
    supply = SupplyNode(
        node_id="supply_apples",
        node_type="supply",
        product=SELLER_DATABASE["product"],
        quantity=SELLER_DATABASE["inventory"],
        min_price=SELLER_DATABASE["min_price"],
        contributed_by=SELLER_DATABASE["company"],
        data_source="seller_private_inventory"
    )
    
    graph.add_supply(supply)
    print(f"[SELLER] Added supply node: {supply.quantity} {supply.product} @ min ${supply.min_price}")
    
    # Save graph
    graph.save(graph_path)
    print(f"[SELLER] Graph saved")
    print(f"[SELLER] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
