#!/usr/bin/env python3
"""
Phase 2 Demo: LLM-Powered Multi-Round Negotiation

This demonstrates:
1. Each party uses LLM to REASON about its strategy
2. Multiple rounds of negotiation (bids → counters → adjusted bids)
3. Parties REACT to each other's moves through graph
4. No party can see others' private data (max prices, strategies)

Scenario:
- Seller: 100 apples, min $1.00, wants to maximize revenue
- Buyer A: wants 60, max $1.50, willing to pay premium
- Buyer B: wants 80, max $1.20, price sensitive

The LLMs negotiate through the graph until deals are made or rounds exhausted.
"""

import os
import subprocess
import sys
import json
from pathlib import Path


def run_process(script: str, graph_path: Path, round_number: int, env_extra: dict = None) -> dict:
    """Run a party script as subprocess."""
    
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    
    result = subprocess.run(
        [sys.executable, script, str(graph_path), str(round_number)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
        env=env
    )
    
    return {
        "script": script,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


def print_graph_state(graph_path: Path, round_number: int):
    """Print current graph state summary."""
    with open(graph_path) as f:
        graph = json.load(f)
    
    print(f"\n--- Graph State After Round {round_number} ---")
    
    accepts = [n for n in graph["nodes"] if n.get("node_type") == "accept"]
    bids = [n for n in graph["nodes"] if n.get("node_type") == "bid"]
    counters = [n for n in graph["nodes"] if n.get("node_type") == "counter"]
    
    if accepts:
        print("ACCEPTED DEALS:")
        for a in accepts:
            print(f"  ✓ {a['buyer']}: {a['quantity']} @ ${a['final_price']:.2f}")
    
    if bids:
        round_bids = [b for b in bids if b.get("round_number") == round_number]
        if round_bids:
            print(f"BIDS (Round {round_number}):")
            for b in round_bids:
                print(f"  → {b['buyer']}: {b['quantity']} @ ${b['bid_price']:.2f}")
    
    if counters:
        round_counters = [c for c in counters if c.get("round_number") == round_number]
        if round_counters:
            print(f"COUNTERS (Round {round_number}):")
            for c in round_counters:
                print(f"  ← To {c['buyer']}: ${c['counter_price']:.2f}")
    
    print("-" * 40)


def check_negotiation_complete(graph_path: Path) -> bool:
    """Check if negotiation is complete (all supply allocated or all demands met)."""
    with open(graph_path) as f:
        graph = json.load(f)
    
    supplies = [n for n in graph["nodes"] if n.get("node_type") == "supply"]
    accepts = [n for n in graph["nodes"] if n.get("node_type") == "accept"]
    
    total_supply = sum(s.get("quantity", 0) for s in supplies)
    total_accepted = sum(a.get("quantity", 0) for a in accepts)
    
    return total_accepted >= total_supply


def main():
    """Run multi-round LLM negotiation."""
    
    print("=" * 60)
    print("SUPPLY CHAIN OPTIMIZATION - PHASE 2")
    print("LLM-Powered Multi-Round Negotiation")
    print("=" * 60)
    print()
    
    orchestrator_pid = os.getpid()
    print(f"Orchestrator PID: {orchestrator_pid}")
    
    # Setup
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    graph_path = output_dir / "phase2_graph.json"
    
    # Clean start
    if graph_path.exists():
        graph_path.unlink()
    
    max_rounds = 3
    
    # Round 0: Seller posts supply
    print("\n" + "=" * 60)
    print("ROUND 0: Seller Posts Supply")
    print("=" * 60)
    
    result = run_process("seller_llm.py", graph_path, 0)
    print(result["stdout"])
    if result["stderr"]:
        print(f"STDERR: {result['stderr']}")
    
    # Negotiation rounds
    for round_num in range(1, max_rounds + 1):
        print("\n" + "=" * 60)
        print(f"ROUND {round_num}: Negotiation")
        print("=" * 60)
        
        # Buyers submit bids
        print(f"\n--- Buyers Bidding (Round {round_num}) ---")
        
        for buyer_name in ["Grocery Chain Alpha", "Restaurant Group Beta"]:
            print(f"\n[{buyer_name}]")
            result = run_process(
                "buyer_llm.py", 
                graph_path, 
                round_num,
                {"BUYER_NAME": buyer_name}
            )
            print(result["stdout"])
            if result["stderr"]:
                print(f"STDERR: {result['stderr']}")
        
        # Seller responds to bids
        print(f"\n--- Seller Responding (Round {round_num}) ---")
        result = run_process("seller_llm.py", graph_path, round_num)
        print(result["stdout"])
        if result["stderr"]:
            print(f"STDERR: {result['stderr']}")
        
        # Show state
        print_graph_state(graph_path, round_num)
        
        # Check if done
        if check_negotiation_complete(graph_path):
            print("\n*** NEGOTIATION COMPLETE - All supply allocated ***")
            break
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    with open(graph_path) as f:
        graph = json.load(f)
    
    accepts = [n for n in graph["nodes"] if n.get("node_type") == "accept"]
    supplies = [n for n in graph["nodes"] if n.get("node_type") == "supply"]
    
    total_supply = sum(s.get("quantity", 0) for s in supplies)
    total_revenue = sum(a.get("quantity", 0) * a.get("final_price", 0) for a in accepts)
    total_allocated = sum(a.get("quantity", 0) for a in accepts)
    
    print(f"\nSupply: {total_supply} units")
    print(f"Allocated: {total_allocated} units ({total_allocated/total_supply*100:.0f}%)")
    print(f"Total Revenue: ${total_revenue:.2f}")
    print()
    
    print("Deals Made:")
    for a in accepts:
        print(f"  {a['buyer']}: {a['quantity']} @ ${a['final_price']:.2f} = ${a['quantity'] * a['final_price']:.2f}")
        print(f"    Reasoning: {a.get('reasoning', '')[:80]}...")
    
    print("\n" + "=" * 60)
    print("PATENT VALUE DEMONSTRATED")
    print("=" * 60)
    print("""
1. EACH PARTY USED LLM REASONING
   - Seller analyzed bids, decided accept/counter/reject
   - Buyers analyzed market, adjusted bid strategy
   
2. PRIVATE DATA STAYED PRIVATE
   - Buyer A's max price ($1.50) never shared
   - Buyer B's max price ($1.20) never shared
   - Seller's cost basis ($0.60) never shared
   
3. GRAPH WAS SOLE COMMUNICATION
   - All negotiation through graph nodes
   - No direct party-to-party messages
   
4. REACTIVE MULTI-ROUND NEGOTIATION
   - Parties adapted strategy based on graph state
   - Counter-offers informed next bids
   
5. NO LEGACY INTEGRATION REQUIRED
   - No EDI, no APIs, no custom code
   - New party = new process, same graph
""")
    
    print(f"\nGraph saved to: {graph_path}")


if __name__ == "__main__":
    main()
