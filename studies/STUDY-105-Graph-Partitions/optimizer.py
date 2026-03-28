#!/usr/bin/env python3
"""
Optimizer - Runs as isolated process

NO PRIVATE DATA - This process has NO database access.
It can ONLY read what's in the graph file.

The optimizer:
1. Reads supply and demand nodes from graph
2. Computes optimal allocation
3. Writes allocation nodes to graph

KEY PATENT POINT:
The optimizer sees ONLY what each party chose to share.
It cannot access the seller's cost structure or buyers' budgets
beyond what's in the graph.
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from graph import SupplyChainGraph, AllocationNode


def optimize_allocation(supplies: list, demands: list) -> list:
    """
    Compute optimal allocation given supply and demand constraints.
    
    Strategy:
    1. Sort demands by max_price (highest first = most willing to pay)
    2. Allocate supply to highest bidders first
    3. Price at the clearing price (seller's min or buyer's max, whichever works)
    
    This is a simple greedy algorithm. Real world would use linear programming.
    """
    
    allocations = []
    
    # Get total supply
    total_supply = sum(s["quantity"] for s in supplies)
    remaining_supply = total_supply
    
    # Get seller's minimum price
    seller_min = supplies[0]["min_price"] if supplies else 0
    seller_id = supplies[0]["node_id"] if supplies else None
    seller_company = supplies[0]["contributed_by"] if supplies else "Unknown"
    
    # Sort demands by max_price descending (prioritize highest bidders)
    sorted_demands = sorted(demands, key=lambda d: d["max_price"], reverse=True)
    
    print(f"[OPTIMIZER] Total supply: {total_supply}")
    print(f"[OPTIMIZER] Seller minimum price: ${seller_min}")
    print(f"[OPTIMIZER] Demands (sorted by max_price):")
    for d in sorted_demands:
        print(f"  - {d['contributed_by']}: {d['quantity']} @ max ${d['max_price']}")
    
    for demand in sorted_demands:
        if remaining_supply <= 0:
            print(f"[OPTIMIZER] No supply remaining for {demand['contributed_by']}")
            continue
            
        # Check if buyer's max price >= seller's min price
        if demand["max_price"] < seller_min:
            print(f"[OPTIMIZER] {demand['contributed_by']} max ${demand['max_price']} < seller min ${seller_min} - NO DEAL")
            continue
        
        # Allocate as much as possible
        allocated_qty = min(demand["quantity"], remaining_supply)
        remaining_supply -= allocated_qty
        
        # Price: meet in the middle (or use seller's min for simplicity)
        # In reality, this would be more sophisticated
        price = seller_min  # Seller gets their minimum
        
        allocation = {
            "seller_id": seller_id,
            "demand_id": demand["node_id"],
            "buyer": demand["contributed_by"],
            "quantity": allocated_qty,
            "price": price,
            "unfulfilled": demand["quantity"] - allocated_qty
        }
        allocations.append(allocation)
        
        print(f"[OPTIMIZER] Allocated {allocated_qty} to {demand['contributed_by']} @ ${price}")
        if allocation["unfulfilled"] > 0:
            print(f"[OPTIMIZER]   (unfulfilled: {allocation['unfulfilled']})")
    
    return allocations


def main():
    """Optimizer reads graph and adds allocation nodes."""
    
    pid = os.getpid()
    print(f"[OPTIMIZER] Process started (PID: {pid})")
    print(f"[OPTIMIZER] NOTE: This process has NO database access")
    
    # Get graph path from command line
    if len(sys.argv) < 2:
        print("[OPTIMIZER] Error: Graph path required")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    print(f"[OPTIMIZER] Graph file: {graph_path}")
    
    # Load graph
    graph = SupplyChainGraph.load(graph_path)
    
    # Get supply and demand nodes
    supplies = graph.get_supplies()
    demands = graph.get_demands()
    
    print(f"[OPTIMIZER] Found {len(supplies)} supply node(s)")
    print(f"[OPTIMIZER] Found {len(demands)} demand node(s)")
    
    if not supplies:
        print("[OPTIMIZER] Error: No supply nodes in graph")
        sys.exit(1)
    
    if not demands:
        print("[OPTIMIZER] Error: No demand nodes in graph")
        sys.exit(1)
    
    # Compute optimal allocation
    print(f"\n[OPTIMIZER] Computing optimal allocation...")
    allocations = optimize_allocation(supplies, demands)
    
    # Add allocation nodes to graph
    print(f"\n[OPTIMIZER] Adding allocation nodes to graph...")
    for i, alloc in enumerate(allocations):
        node = AllocationNode(
            node_id=f"allocation_{i+1}",
            node_type="allocation",
            seller=supplies[0]["contributed_by"],
            buyer=alloc["buyer"],
            quantity=alloc["quantity"],
            price=alloc["price"],
            contributed_by="Optimizer",
            reasoning=f"Allocated {alloc['quantity']} units @ ${alloc['price']}/unit"
        )
        graph.add_allocation(node, alloc["seller_id"], alloc["demand_id"])
    
    # Calculate summary
    total_allocated = sum(a["quantity"] for a in allocations)
    total_revenue = sum(a["quantity"] * a["price"] for a in allocations)
    
    print(f"\n[OPTIMIZER] ========== RESULT ==========")
    print(f"[OPTIMIZER] Total allocated: {total_allocated} units")
    print(f"[OPTIMIZER] Total revenue: ${total_revenue:.2f}")
    print(f"[OPTIMIZER] Allocations:")
    for alloc in allocations:
        print(f"  - {alloc['buyer']}: {alloc['quantity']} @ ${alloc['price']} = ${alloc['quantity'] * alloc['price']:.2f}")
        if alloc["unfulfilled"] > 0:
            print(f"    (unfulfilled: {alloc['unfulfilled']})")
    print(f"[OPTIMIZER] ===============================")
    
    # Save graph
    graph.save(graph_path)
    print(f"[OPTIMIZER] Graph saved")
    print(f"[OPTIMIZER] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
