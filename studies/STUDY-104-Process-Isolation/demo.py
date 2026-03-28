#!/usr/bin/env python3
"""
Patent Demonstration: Isolated Agent Graph Communication

This script demonstrates the complete system:
1. Two agents with isolated database access
2. Each contributes to a shared graph
3. Neither can access the other's data
4. The graph executor produces a result
5. The result is NEW KNOWLEDGE neither agent could produce alone

Run: python -m patent.demo
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patent.graph import SharedGraph
from patent.agent import Database, AgentA, AgentB
from patent.executor import GraphExecutor


def main():
    """Run the patent demonstration."""
    
    print("\n" + "=" * 70)
    print("  PATENT DEMONSTRATION")
    print("  Isolated Agent Graph Communication")
    print("=" * 70)
    
    # ================================================================
    # STEP 1: Create isolated databases
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 1: Create Isolated Databases")
    print("-" * 70)
    
    # Database A: Internal corporate data
    # Agent A has EXCLUSIVE access to this
    database_a = Database(
        name="Alpha Corp Internal Database",
        data={
            "q4_revenue": 47_000_000,      # $47 million
            "employee_count": 1250,
            "operating_costs": 38_000_000,
        }
    )
    print(f"\n  Database A: {database_a.name}")
    print(f"    Contents: {database_a.list_keys()}")
    
    # Database B: External market analytics
    # Agent B has EXCLUSIVE access to this
    database_b = Database(
        name="Beta Analytics External Database",
        data={
            "market_growth_rate": 1.15,    # 15% growth
            "competitor_revenue": 52_000_000,
            "industry_average": 42_000_000,
        }
    )
    print(f"\n  Database B: {database_b.name}")
    print(f"    Contents: {database_b.list_keys()}")
    
    print("\n  KEY POINT: Neither database can be accessed by the other agent.")
    
    # ================================================================
    # STEP 2: Create isolated agents
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 2: Create Isolated Agents")
    print("-" * 70)
    
    agent_a = AgentA(agent_id="Agent_A", database=database_a)
    agent_b = AgentB(agent_id="Agent_B", database=database_b)
    
    print(f"\n  {agent_a.agent_id}: Has access ONLY to {database_a.name}")
    print(f"  {agent_b.agent_id}: Has access ONLY to {database_b.name}")
    print("\n  KEY POINT: Agents cannot communicate directly.")
    print("             The ONLY shared resource is the graph.")
    
    # ================================================================
    # STEP 3: Create shared graph
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 3: Create Shared Graph")
    print("-" * 70)
    
    graph = SharedGraph()
    print("\n  Empty graph created.")
    print("  This is the ONLY communication channel between agents.")
    
    # ================================================================
    # STEP 4: Define the task
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 4: Define Task")
    print("-" * 70)
    
    task = """
    Calculate the competitive revenue advantage:
    1. Get Q4 revenue (internal data)
    2. Apply market growth rate (external data)
    3. Compare to competitor revenue (external data)
    4. Result: projected_revenue - competitor_revenue
    """
    
    print(f"\n  TASK:{task}")
    print("  This task REQUIRES data from BOTH databases.")
    print("  Neither agent alone can complete it.")
    
    # ================================================================
    # STEP 5: Agent A contributes
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 5: Agent A Contributes")
    print("-" * 70)
    
    agent_a.contribute(graph, task)
    
    # ================================================================
    # STEP 6: Agent B contributes
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 6: Agent B Contributes")
    print("-" * 70)
    
    agent_b.contribute(graph, task)
    
    # ================================================================
    # STEP 7: Show graph structure
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 7: Graph Structure (The Communication Artifact)")
    print("-" * 70)
    
    graph.print_structure()
    
    # ================================================================
    # STEP 8: Execute graph
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 8: Execute Graph")
    print("-" * 70)
    
    executor = GraphExecutor(graph)
    trace = executor.execute("result")
    
    trace.print_trace()
    
    # ================================================================
    # STEP 9: Verify result
    # ================================================================
    
    print("\n" + "-" * 70)
    print("  STEP 9: Verification")
    print("-" * 70)
    
    # Manual calculation to verify
    q4_revenue = 47_000_000
    growth_rate = 1.15
    competitor = 52_000_000
    expected = (q4_revenue * growth_rate) - competitor
    
    print(f"\n  Manual verification:")
    print(f"    Q4 Revenue:        ${q4_revenue:,}")
    print(f"    × Growth Rate:     {growth_rate}")
    print(f"    = Projected:       ${q4_revenue * growth_rate:,.2f}")
    print(f"    - Competitor:      ${competitor:,}")
    print(f"    = Advantage:       ${expected:,.2f}")
    
    print(f"\n  Graph result:        ${trace.final_result:,.2f}")
    
    match = abs(trace.final_result - expected) < 0.01
    print(f"\n  Results match: {'✓ YES' if match else '✗ NO'}")
    
    # ================================================================
    # STEP 10: Patent claim summary
    # ================================================================
    
    print("\n" + "=" * 70)
    print("  PATENT CLAIM SUMMARY")
    print("=" * 70)
    
    print("""
  WHAT WE DEMONSTRATED:
  
  1. DATA ISOLATION
     - Agent A could ONLY access Database A
     - Agent B could ONLY access Database B
     - Neither could query the other's data source
  
  2. GRAPH AS SOLE COMMUNICATION
     - Agents did not communicate directly
     - Agents did not share memory
     - The ONLY shared artifact was the graph
  
  3. EMERGENT KNOWLEDGE
     - The result ($2,050,000) exists in NO database
     - Agent A alone could not compute it (missing growth rate, competitor)
     - Agent B alone could not compute it (missing Q4 revenue)
     - ONLY through graph-based collaboration was it possible
  
  4. AUDITABILITY
     - Every node records which agent contributed it
     - Every node records which data source it came from
     - The execution trace shows every computation step
     - The graph can be saved, replayed, and audited
  
  5. REPRODUCIBILITY
     - The graph is a deterministic computation structure
     - Re-executing the same graph produces the same result
     - The graph can be serialized and transmitted
    """)
    
    # ================================================================
    # STEP 11: Save graph artifact
    # ================================================================
    
    print("-" * 70)
    print("  GRAPH ARTIFACT (JSON)")
    print("-" * 70)
    
    print(graph.to_json())
    
    # Save to file
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "computation_graph.json")
    graph.save(output_file)
    print(f"\n  Graph saved to: {output_file}")
    
    print("\n" + "=" * 70)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 70)
    
    return trace.final_result


if __name__ == "__main__":
    result = main()
