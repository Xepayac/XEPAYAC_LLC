# STUDY-111: LLM Autonomous Decision Protocol

## Classification: PUBLIC

## Abstract

This study demonstrates autonomous LLM decision-making within graph substrate through the OBSERVE-REASON-DECIDE-APPLY pattern. In a supply chain negotiation scenario, two buyer LLMs (Grocery Chain Alpha, Restaurant Group Beta) and one seller LLM (Apple Farm Co) make independent decisions based on graph context while maintaining private strategies in isolated process memory. Each LLM observes public market state (supplies, bids), reasons against private constraints (max price, budget), decides via structured JSON output, and applies the decision as graph mutations. The graph substrate coordinates multiple autonomous LLM agents without integration code.

## Study ID
**STUDY-111**

## Title
LLM Autonomous Decision Protocol

## Purpose
Demonstrates autonomous LLM decision-making within the graph substrate - how LLMs can make independent decisions based on graph context and output structured responses that become graph mutations.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
  - **Claim 1**: System — graph substrate traversal constitutes execution, self-modification by writing changes to serialized file
  - **Claim 2**: Method — traversal, execution, and modification during execution
  - **Claim 4**: Edges determine traversal pathways including branching, conditional routing, cycles, and convergence
  - **Claim 5**: Execution state written into nodes — graph is simultaneously program and execution record
  - **Claim 8**: Modifications include adding nodes/edges, persist in serialized file, affect subsequent traversals

## Hypothesis

Multiple LLM agents can operate autonomously within a shared graph substrate, each observing public graph state, reasoning against private constraints, outputting structured JSON decisions, and applying those decisions as graph mutations—with the graph serving as the sole coordination mechanism requiring zero integration code between agents.

## Study Date
**December 2024** - Split from STUDY-91 for conceptual clarity

## Method

1. **Initialize Graph Substrate**: Create supply chain graph with public market state (supply nodes)
2. **Define Agent Processes**: Create separate processes for buyer_a (Grocery Chain Alpha), buyer_b (Restaurant Group Beta), seller (Apple Farm Co)
3. **Configure Private Constraints**: Each agent holds private data in process memory (max_price, demand for buyers; min_price, cost basis for seller)
4. **OBSERVE Phase**: Agent reads visible graph nodes (supplies, competitor bids, counters to self)
5. **REASON Phase**: Build LLM prompt combining private constraints with public market state
6. **DECIDE Phase**: LLM generates structured JSON response with quantity, bid_price/counter_price, reasoning
7. **APPLY Phase**: Parse JSON into BidNode/CounterNode, add to graph via mutation engine
8. **Execute Multi-Round Negotiation**: Run bid → counter → accept cycle with all agents
9. **Verify Autonomy**: Confirm each LLM made independent decisions based on graph context without direct communication
10. **Capture Output**: Store final negotiation state in phase1_graph.json with all agent decisions

## Files Included

| File | Purpose |
|------|---------|
| `buyer_llm.py` | LLM-powered buyer agent with autonomous decision-making |
| `seller_llm.py` | LLM-powered seller agent with autonomous pricing decisions |
| `party_buyer_a.py` | Buyer A party process (Grocery Chain Alpha) |
| `party_buyer_b.py` | Buyer B party process (Restaurant Group Beta) |
| `party_seller.py` | Seller party process (Apple Farm Co) |
| `demo_phase1.py` | Phase 1 negotiation demonstration orchestrator |
| `graph.py` | Supply chain graph substrate implementation |
| `output/phase1_graph.json` | Example output showing autonomous LLM decisions |
| `FIG-111-01.mmd` | Reactive execution architecture diagram |
| `FIG-111-02.mmd` | LLM decision cycle diagram |
| `FIG-111-03.mmd` | Multi-agent coordination diagram |
| `FIG-111-04.mmd` | Graph mutation flow diagram |

## Key Mechanism

The autonomous decision pattern operates in four phases:

**1. OBSERVE**: LLM agent reads relevant graph nodes
- Current market offers and bids
- Private constraints (stored in agent's partition)
- Negotiation history and competitor actions

**2. REASON**: LLM processes full context autonomously
- Evaluates alternatives against strategy
- Considers market conditions and competition
- Applies decision logic based on constraints

**3. DECIDE**: LLM outputs structured JSON response
```json
{
  "quantity": 60,
  "bid_price": 1.27,
  "reasoning": "Market competitive, bidding below max"
}
```

**4. APPLY**: Mutation engine updates graph state
- Structured output becomes graph nodes
- New state triggers dependent LLM agents
- Creates audit trail of all decisions

```python
# Core pattern from buyer_llm.py:
def decide_bid(graph: SupplyChainGraph, buyer: dict, round_number: int):
    # 1. OBSERVE: Get visible context
    supplies = graph.get_supplies()
    my_bids = graph.get_bids(buyer=buyer["company"])
    counters = graph.get_counters(buyer=buyer["company"])
    
    # 2. REASON: Build prompt with private + public data
    prompt = f"""You are {buyer['company']}.
    Private: max_price=${buyer['max_price']}, demand={buyer['demand']}
    Market: supply={supplies}, competitors={other_bids}
    Decide: quantity and bid_price as JSON"""
    
    # 3. DECIDE: LLM generates structured output
    decision = json.loads(call_llm(prompt))
    
    # 4. APPLY: Create graph mutation
    bid = BidNode(
        buyer=buyer["company"],
        quantity=decision["quantity"],
        bid_price=decision["bid_price"],
        reasoning=decision["reasoning"]
    )
    graph.add_bid(bid)
```

## Key Results

**Autonomous Agent Behavior Demonstrated:**
- Two buyer LLMs (Grocery Chain Alpha, Restaurant Group Beta) made independent decisions
- Each LLM maintained private strategy while observing public market state
- LLM agents adjusted bids based on competition and supply scarcity
- Decisions were structured (JSON) and became graph nodes automatically
- No human orchestration between observe-reason-decide-apply cycle

**From `output/phase1_graph.json`:**
- Graph shows 5 nodes: 1 supply, 2 demands, 2 allocations
- Buyer A: Secured 60 units (full demand, higher budget)
- Buyer B: Secured 40 units (partial, 40 unfulfilled due to competition)
- All decisions attributed via `contributed_by` field
- Complete provenance: "Apple Farm Co", "Grocery Chain Alpha", "Restaurant Group Beta", "Optimizer"

## Key Insight

**The LLM is an autonomous agent, not a tool** - it reads context, reasons, and decides independently. The graph substrate provides both the information and the communication channel. Unlike traditional LLM integration where humans orchestrate and responses go to users, here LLMs act as self-directed agents whose structured outputs directly modify shared state, enabling multi-agent coordination without central control.

## Patent Implications

**Claims Validated:**
1. **Autonomous Operation** (EGS-979, Claim 1): LLMs operate independently within graph context without human intervention per decision
2. **State-Based Reasoning** (EGS-979, Claim 2): Decisions derived from reading graph state (supplies, bids, history)
3. **Structured Mutations** (EGS-979, Claim 3): JSON output becomes graph nodes via mutation engine
4. **Multi-Agent Coordination** (EGS-979, Claim 4): Multiple LLMs coordinate through shared graph substrate

**Differentiation from Prior Art:**

| Traditional LLM Integration | Graph-Based Autonomy (Patentable) |
|----------------------------|-----------------------------------|
| LLM is a function call | LLM is an autonomous agent |
| Human orchestrates workflow | LLM decides independently |
| Responses go to user | Responses modify graph state |
| Stateless (no memory) | Context persists in graph |
| Centralized control | Distributed decision-making |

**Key Innovation**: LLMs transition from passive tools to active agents whose structured outputs become system state changes, enabling provable multi-party coordination without trusted intermediaries.

## How to Run

**Prerequisites:**
```bash
pip install anthropic python-dotenv
export ANTHROPIC_API_KEY="your-api-key"
```

**Execute Phase 1 Demonstration:**
```bash
cd /PATENT/LAB/STUDIES/STUDY-111-Autonomous-Decision/
python demo_phase1.py
```

**Run Individual Agents (for testing):**
```bash
# Buyer A agent
BUYER_NAME="Grocery Chain Alpha" python buyer_llm.py output/phase1_graph.json 1

# Buyer B agent
BUYER_NAME="Restaurant Group Beta" python buyer_llm.py output/phase1_graph.json 1

# Seller agent
python seller_llm.py output/phase1_graph.json 1
```

## Expected Output

**Console Output:**
```
============================================================
SUPPLY CHAIN OPTIMIZATION - PHASE 1
1 Seller, 2 Buyers, No Shipping
============================================================

STEP 1: Seller contributes supply
----------------------------------------
[Apple Farm Co] Process started (PID: 12345)
[Apple Farm Co] Added 100 apples @ min $1.00

STEP 2: Buyer A contributes demand
----------------------------------------
[Grocery Chain Alpha] Process started (PID: 12346)
[Grocery Chain Alpha] BID: 60 @ $1.27
[Grocery Chain Alpha] Reasoning: Market competitive...

STEP 3: Buyer B contributes demand
----------------------------------------
[Restaurant Group Beta] Process started (PID: 12347)
[Restaurant Group Beta] BID: 80 @ $0.90
[Restaurant Group Beta] Reasoning: Price sensitive strategy...

STEP 4: Optimizer computes allocation
----------------------------------------
[Optimizer] Allocated 60 to Grocery Chain Alpha
[Optimizer] Allocated 40 to Restaurant Group Beta
```

**Graph File (`output/phase1_graph.json`):**
- 5 nodes: 1 supply, 2 demands, 2 allocations
- Each node has `contributed_by` showing autonomous agent attribution
- Complete provenance trail for patent evidence
- Structured decision reasoning in each node

## Related Studies

- **STUDY-105**: Multi-Party Privacy via Graph Partitions (demonstrates how LLMs maintain private data while reading shared state)
- **STUDY-112**: Graph-Based Optimization Engine (shows non-LLM computation in same substrate)
- **STUDY-106**: Real-Time Graph Updates (demonstrates edge-triggered execution for LLM agents)

## Date Evidence / GitHub Issue

**Creation Date:** December 2024  
**Source:** Split from STUDY-91 (now STUDY-105) for conceptual clarity  
**GitHub Issues:** Track development in EGS-979 (Application 19/575,491)  
**Git History:** All changes tracked in `/PATENT/LAB/STUDIES/STUDY-111-Autonomous-Decision/`  
**Related Work:** Part of EGS-979 Patent Family (Application 19/575,491)
