#!/usr/bin/env python3
"""
LLM-Powered Buyer - Phase 2

This buyer uses an LLM to:
1. Analyze available supply and competing bids
2. Decide on optimal bid strategy
3. React to counter-offers from seller

PRIVATE DATA varies by buyer (passed as environment variable)
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
    SupplyChainGraph, BidNode, AcceptNode
)

# Try to import Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


# ============================================================
# BUYER PROFILES - Each buyer has different private data
# ============================================================
BUYER_PROFILES = {
    "Grocery Chain Alpha": {
        "company": "Grocery Chain Alpha",
        "product": "apples",
        "demand": 60,
        "max_price": 1.50,
        "budget": 90.00,  # Total budget
        "strategy": "Willing to pay premium for reliability. Start with mid-range bid.",
        "opening_bid_factor": 0.85,  # Start at 85% of max
    },
    "Restaurant Group Beta": {
        "company": "Restaurant Group Beta",
        "product": "apples",
        "demand": 80,
        "max_price": 1.20,
        "budget": 96.00,
        "strategy": "Price sensitive. Start low, increase if needed. Accept partial orders.",
        "opening_bid_factor": 0.75,  # Start at 75% of max
    }
}
# ============================================================


def get_buyer_config() -> dict:
    """Get buyer configuration from environment."""
    buyer_name = os.environ.get("BUYER_NAME")
    if not buyer_name or buyer_name not in BUYER_PROFILES:
        raise RuntimeError(f"BUYER_NAME must be one of: {list(BUYER_PROFILES.keys())}")
    return BUYER_PROFILES[buyer_name]


def call_llm(prompt: str) -> str:
    """Call Claude Haiku for buyer decisions."""
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


def decide_bid(graph: SupplyChainGraph, buyer: dict, round_number: int) -> BidNode:
    """
    LLM decides on a bid based on graph state.
    """
    
    # Get current state
    supplies = graph.get_supplies()
    my_bids = graph.get_bids(buyer=buyer["company"])
    my_accepts = [a for a in graph.get_accepts() if a.get("buyer") == buyer["company"]]
    counters_to_me = graph.get_counters(buyer=buyer["company"])
    all_bids = graph.get_bids(round_number=round_number - 1) if round_number > 1 else []
    
    # Calculate what I've already secured
    secured_qty = sum(a.get("quantity", 0) for a in my_accepts)
    remaining_need = buyer["demand"] - secured_qty
    
    if remaining_need <= 0:
        return None  # Already have what I need
    
    # Get available supply
    total_supply = sum(s.get("quantity", 0) for s in supplies)
    total_accepted = sum(a.get("quantity", 0) for a in graph.get_accepts())
    remaining_supply = total_supply - total_accepted
    
    # Build prompt for LLM
    prompt = f"""You are the procurement AI for {buyer['company']}.

PRIVATE DATA (your secrets):
- Remaining need: {remaining_need} {buyer['product']}
- Maximum price willing to pay: ${buyer['max_price']:.2f}
- Remaining budget: ${buyer['budget'] - sum(a.get('quantity', 0) * a.get('final_price', 0) for a in my_accepts):.2f}
- Strategy: {buyer['strategy']}

MARKET STATE:
- Available supply: {remaining_supply} units
- Total supply: {total_supply} units
- Round: {round_number}
"""

    if counters_to_me:
        latest_counter = counters_to_me[-1]
        prompt += f"""
LATEST COUNTER-OFFER TO YOU:
- Price: ${latest_counter['counter_price']:.2f}
- Quantity: {latest_counter['quantity']}
- Seller reasoning: {latest_counter.get('reasoning', 'Not stated')}
"""

    if my_bids:
        prompt += f"""
YOUR PREVIOUS BIDS:
"""
        for bid in my_bids[-3:]:
            prompt += f"- Round {bid['round_number']}: {bid['quantity']} @ ${bid['bid_price']:.2f}\n"

    # Show competitor bids (but not their private max prices!)
    other_bids = [b for b in all_bids if b.get("buyer") != buyer["company"]]
    if other_bids:
        prompt += f"""
COMPETITOR BIDS (last round):
"""
        for bid in other_bids:
            prompt += f"- {bid['buyer']}: {bid['quantity']} @ ${bid['bid_price']:.2f}\n"

    prompt += f"""
DECISION REQUIRED:
Submit a bid to acquire up to {remaining_need} units.

Rules:
1. Never bid above ${buyer['max_price']:.2f}
2. Consider competition and available supply
3. If counter-offer is acceptable, bid at that price to accept
4. If supply is low, you may need to bid higher

Respond in JSON format:
{{
    "quantity": number (how many to bid for),
    "bid_price": number (price per unit),
    "reasoning": "your reasoning"
}}

Only output the JSON, nothing else."""

    print(f"[{buyer['company']}] Deciding bid for round {round_number}...")
    
    # Call LLM
    response_text = call_llm(prompt)
    
    # Parse response
    try:
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        decision = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"[{buyer['company']}] Failed to parse LLM response: {e}")
        print(f"[{buyer['company']}] Raw response: {response_text}")
        # Fallback: simple bid
        decision = {
            "quantity": min(remaining_need, remaining_supply),
            "bid_price": buyer["max_price"] * buyer["opening_bid_factor"],
            "reasoning": "Fallback bid due to parse error"
        }
    
    # Validate and clamp
    qty = min(decision["quantity"], remaining_need, remaining_supply)
    price = min(decision["bid_price"], buyer["max_price"])
    
    if qty <= 0:
        return None
    
    bid = BidNode(
        node_id=f"bid_{buyer['company'].replace(' ', '_').lower()}_r{round_number}",
        node_type="bid",
        buyer=buyer["company"],
        product=buyer["product"],
        quantity=qty,
        bid_price=round(price, 2),
        round_number=round_number,
        contributed_by=buyer["company"],
        reasoning=decision.get("reasoning", "")
    )
    
    print(f"[{buyer['company']}] BID: {qty} @ ${price:.2f}")
    print(f"[{buyer['company']}] Reasoning: {decision.get('reasoning', '')[:100]}...")
    
    return bid


def main():
    """Buyer LLM agent process."""
    
    pid = os.getpid()
    buyer = get_buyer_config()
    
    print(f"[{buyer['company']}] Process started (PID: {pid})")
    
    # Get arguments
    if len(sys.argv) < 3:
        print(f"[{buyer['company']}] Usage: buyer_llm.py <graph_path> <round_number>")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    round_number = int(sys.argv[2])
    
    print(f"[{buyer['company']}] Graph: {graph_path}")
    print(f"[{buyer['company']}] Round: {round_number}")
    print(f"[{buyer['company']}] PRIVATE: Demand={buyer['demand']}, MaxPrice=${buyer['max_price']:.2f}")
    
    # Load graph
    graph = SupplyChainGraph.load(graph_path)
    
    # Decide and submit bid
    bid = decide_bid(graph, buyer, round_number)
    
    if bid:
        graph.add_bid(bid)
        print(f"[{buyer['company']}] Bid added to graph")
    else:
        print(f"[{buyer['company']}] No bid needed (demand satisfied or no supply)")
    
    # Save graph
    graph.save(graph_path)
    print(f"[{buyer['company']}] Graph saved")
    print(f"[{buyer['company']}] Process complete (PID: {pid})")


if __name__ == "__main__":
    main()
