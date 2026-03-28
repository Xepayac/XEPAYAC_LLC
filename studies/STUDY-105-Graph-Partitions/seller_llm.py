#!/usr/bin/env python3
"""
LLM-Powered Seller - Phase 2

This seller uses an LLM to:
1. Analyze incoming bids from buyers
2. Decide whether to accept, counter, or reject
3. Reason about optimal pricing strategy

PRIVATE DATA (not shared):
- Inventory: 100 apples
- Minimum price: $1.00
- Cost basis: $0.60 (profit margin target)
- Strategy: Maximize revenue, prefer bulk buyers
"""

import os
import sys
import json
from pathlib import Path
from dataclasses import asdict

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supply_chain.graph import (
    SupplyChainGraph, SupplyNode, CounterNode, AcceptNode, BidNode
)

# Try to import Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


# ============================================================
# PRIVATE DATA - Seller's secret information
# ============================================================
SELLER_DATABASE = {
    "company": "Apple Farm Co",
    "product": "apples",
    "inventory": 100,
    "min_price": 1.00,
    "cost_basis": 0.60,  # What it costs us per apple
    "strategy": "Maximize revenue. Prefer larger orders. Counter low bids.",
}
# ============================================================


def call_llm(prompt: str) -> str:
    """Call Claude Haiku for seller decisions."""
    if Anthropic is None:
        raise RuntimeError("Anthropic library not installed")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def analyze_bids_and_respond(graph: SupplyChainGraph, round_number: int) -> list:
    """
    LLM analyzes bids and decides how to respond.
    
    Returns list of response nodes (counters or accepts).
    """
    
    # Get current state
    supplies = graph.get_supplies()
    bids = graph.get_bids(round_number=round_number)
    previous_counters = graph.get_counters()
    accepts = graph.get_accepts()
    
    if not bids:
        print(f"[SELLER-LLM] No bids in round {round_number}")
        return []
    
    # Calculate remaining inventory (subtract accepted deals)
    accepted_qty = sum(a.get("quantity", 0) for a in accepts)
    remaining_inventory = SELLER_DATABASE["inventory"] - accepted_qty
    
    # Build prompt for LLM
    prompt = f"""You are the sales AI for {SELLER_DATABASE['company']}.

PRIVATE DATA (your secrets):
- Remaining inventory: {remaining_inventory} {SELLER_DATABASE['product']}
- Minimum acceptable price: ${SELLER_DATABASE['min_price']:.2f}
- Cost basis: ${SELLER_DATABASE['cost_basis']:.2f} per unit
- Strategy: {SELLER_DATABASE['strategy']}

CURRENT BIDS (Round {round_number}):
"""
    
    for bid in bids:
        prompt += f"""
- Buyer: {bid['buyer']}
  Quantity: {bid['quantity']}
  Bid Price: ${bid['bid_price']:.2f}
  Their reasoning: {bid.get('reasoning', 'Not stated')}
"""
    
    if previous_counters:
        prompt += "\nPREVIOUS NEGOTIATIONS:\n"
        for counter in previous_counters[-5:]:  # Last 5 counters
            prompt += f"- Round {counter['round_number']}: Counter to {counter['buyer']} @ ${counter['counter_price']:.2f}\n"
    
    prompt += f"""
DECISION REQUIRED:
For each bid, decide: ACCEPT, COUNTER, or REJECT.

Rules:
1. Never accept below ${SELLER_DATABASE['min_price']:.2f}
2. Total accepted quantity cannot exceed {remaining_inventory}
3. Higher bids should get priority
4. Counter offers should be reasonable (between their bid and your minimum)

Respond in JSON format:
{{
    "decisions": [
        {{
            "buyer": "buyer name",
            "action": "ACCEPT" | "COUNTER" | "REJECT",
            "quantity": number,
            "price": number,
            "reasoning": "your reasoning"
        }}
    ]
}}

Only output the JSON, nothing else."""

    print(f"[SELLER-LLM] Analyzing {len(bids)} bids...")
    
    # Call LLM
    response_text = call_llm(prompt)
    
    # Parse response
    try:
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        decisions = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"[SELLER-LLM] Failed to parse LLM response: {e}")
        print(f"[SELLER-LLM] Raw response: {response_text}")
        return []
    
    # Convert decisions to graph nodes
    response_nodes = []
    for i, decision in enumerate(decisions.get("decisions", [])):
        action = decision.get("action", "").upper()
        
        if action == "ACCEPT":
            node = AcceptNode(
                node_id=f"accept_r{round_number}_{i}",
                node_type="accept",
                buyer=decision["buyer"],
                seller=SELLER_DATABASE["company"],
                quantity=decision["quantity"],
                final_price=decision["price"],
                round_number=round_number,
                contributed_by=SELLER_DATABASE["company"],
                reasoning=decision.get("reasoning", "")
            )
            print(f"[SELLER-LLM] ACCEPT: {decision['buyer']} gets {decision['quantity']} @ ${decision['price']:.2f}")
            response_nodes.append(("accept", node))
            
        elif action == "COUNTER":
            node = CounterNode(
                node_id=f"counter_r{round_number}_{i}",
                node_type="counter",
                seller=SELLER_DATABASE["company"],
                buyer=decision["buyer"],
                product=SELLER_DATABASE["product"],
                quantity=decision["quantity"],
                counter_price=decision["price"],
                round_number=round_number,
                contributed_by=SELLER_DATABASE["company"],
                reasoning=decision.get("reasoning", "")
            )
            print(f"[SELLER-LLM] COUNTER: {decision['buyer']} offered ${decision['price']:.2f}")
            response_nodes.append(("counter", node))
            
        else:  # REJECT
            print(f"[SELLER-LLM] REJECT: {decision['buyer']} - {decision.get('reasoning', '')}")
    
    return response_nodes


def main():
    """Seller LLM agent process."""
    
    pid = os.getpid()
    print(f"[SELLER-LLM] Process started (PID: {pid})")
    print(f"[SELLER-LLM] Company: {SELLER_DATABASE['company']}")
    
    # Get arguments
    if len(sys.argv) < 3:
        print("[SELLER-LLM] Usage: seller_llm.py <graph_path> <round_number>")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    round_number = int(sys.argv[2])
    
    print(f"[SELLER-LLM] Graph: {graph_path}")
    print(f"[SELLER-LLM] Round: {round_number}")
    
    # Load graph
    graph = SupplyChainGraph.load(graph_path)
    
    # If round 0, just add supply node
    if round_number == 0:
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
        print(f"[SELLER-LLM] Added supply: {supply.quantity} {supply.product} @ min ${supply.min_price:.2f}")
    else:
        # Analyze bids and respond
        responses = analyze_bids_and_respond(graph, round_number)
        
        for node_type, node in responses:
            if node_type == "accept":
                graph.add_accept(node)
            elif node_type == "counter":
                graph.add_counter(node)
    
    # Save graph
    graph.save(graph_path)
    print(f"[SELLER-LLM] Graph saved")
    print(f"[SELLER-LLM] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
