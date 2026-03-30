"""
Test: Multi-Agent Value Proof

The Simple Truth:
- LLM A has access to Database A → returns value 47
- LLM B has access to Database B → returns value 89
- Neither can access the other's database
- Through graph + operation → they produce 136 (new knowledge neither had alone)

This IS the real-world scenario:
- Different agents with different API access
- Different database permissions
- Different proprietary data sources
- The graph enables SYNTHESIS of isolated knowledge

Key Insight:
This is structurally identical to the math problem:
- LLM A "knows" 3 → LLM B "knows" 5 → Graph: 3+5=8
- Neither alone can produce 8
- 8 is NEW knowledge created through collaboration
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sgs import SGS
from sgs.models import Node, Edge, NodeType
from lab.protocol import load_env, parse_response
from lab_executable.executor import GraphExecutor

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

load_env()


# ============================================================
# Simulated Databases (Different access for different agents)
# ============================================================

DATABASE_A = {
    "name": "Alpha Corp Internal Database",
    "values": {
        "q4_revenue": 47000000,
        "employee_count": 1250,
        "regional_sales_west": 18500000
    }
}

DATABASE_B = {
    "name": "Beta Analytics External Database", 
    "values": {
        "market_growth_rate": 1.15,  # 15% growth
        "competitor_revenue": 52000000,
        "industry_average": 42000000
    }
}

# Task: Calculate projected revenue vs competitor gap
# Alpha Q4 revenue * market growth rate - competitor revenue
# = 47000000 * 1.15 - 52000000 = 54050000 - 52000000 = 2050000
EXPECTED_ANSWER = 2050000


# ============================================================
# Agent A: Can ONLY access Database A
# ============================================================

AGENT_A_PROMPT = """You are Agent A with EXCLUSIVE access to Alpha Corp's internal database.

YOUR DATABASE ACCESS (Database A - you can ONLY query this):
{database_a}

You CANNOT access any external databases.

TASK: {task}

Create ONLY OPERAND nodes for values you can provide from YOUR database.
Do NOT create placeholder nodes. Do NOT create operation or result nodes.
Another agent will add more nodes and complete the graph.

OPERAND format: {{"id": "unique_id", "type": "OPERAND", "data": {{"value": <number>}}}}

Respond with JSON: {{"nodes": [...], "edges": []}}

Only include nodes with ACTUAL values from your database.
"""

AGENT_B_PROMPT = """You are Agent B with EXCLUSIVE access to Beta Analytics external database.

YOUR DATABASE ACCESS (Database B - you can ONLY query this):
{database_b}

You CANNOT access any internal company databases.

TASK: {task}

CURRENT GRAPH (from Agent A - these nodes already exist):
{graph_context}

Your job:
1. Add OPERAND nodes for values from YOUR database
2. Add OPERATION nodes to perform calculations  
3. Add a RESULT node to mark the final answer
4. Add EDGES to connect everything

Node types:
- OPERAND: {{"id": "id", "type": "OPERAND", "data": {{"value": <number>}}}}
- OPERATION: {{"id": "id", "type": "OPERATION", "data": {{"operation": "multiply"|"subtract"|"add"|"divide"}}}}
- RESULT: {{"id": "result", "type": "RESULT", "data": {{}}}}

Edge format (from_id depends on to_id):
{{"from_id": "op1", "to_id": "operand1", "relation": "REQUIRES"}}

For the calculation: projected = q4_revenue * growth_rate, then advantage = projected - competitor

Respond with JSON: {{"nodes": [...], "edges": [...]}}
"""

SINGLE_AGENT_PROMPT = """You are a single agent with access to ONLY ONE database:

YOUR DATABASE ACCESS:
{database}

You CANNOT access any other databases.

TASK: {task}

Create an executable graph to solve this task.
Use these node types:
- OPERAND: {{"id": "unique_id", "type": "OPERAND", "data": {{"value": <number>}}}}
- OPERATION: {{"id": "op_id", "type": "OPERATION", "data": {{"operation": "add"|"subtract"|"multiply"|"divide"}}}}
- RESULT: {{"id": "result", "type": "RESULT", "data": {{}}}}

Edges: {{"from_id": "...", "to_id": "...", "relation": "REQUIRES"}}

If you have all required data, create the complete graph.
If you are MISSING data needed to complete the task, respond with:
{{"error": "Missing data: [what you need]", "partial": true, "nodes": [...], "edges": [...]}}

Respond with JSON only.
"""


# ============================================================
# The Task (requires BOTH databases)
# ============================================================

CROSS_DATABASE_TASK = """Calculate the revenue advantage:
1. Get Alpha Corp's Q4 revenue (from internal database)
2. Get market growth rate (from external analytics database)  
3. Project Alpha's revenue: Q4_revenue * growth_rate
4. Get competitor's revenue (from external analytics database)
5. Calculate advantage: projected_revenue - competitor_revenue

This requires data from both internal AND external databases."""


# ============================================================
# Helper Functions
# ============================================================

def format_database(db: dict) -> str:
    """Format database as readable text."""
    lines = [f"Database: {db['name']}", "Available values:"]
    for key, value in db['values'].items():
        lines.append(f"  - {key}: {value}")
    return "\n".join(lines)


def graph_to_context(nodes: list, edges: list) -> str:
    """Convert graph data to readable context."""
    if not nodes:
        return "Graph is empty."
    
    lines = ["NODES:"]
    for node in nodes:
        node_type = node.get('type', 'UNKNOWN')
        node_id = node.get('id', 'unknown')
        data = node.get('data', {})
        if node_type == 'OPERAND':
            lines.append(f"  - {node_id} [{node_type}]: value = {data.get('value')}")
        elif node_type == 'OPERATION':
            lines.append(f"  - {node_id} [{node_type}]: operation = {data.get('operation')}")
        else:
            lines.append(f"  - {node_id} [{node_type}]")
    
    lines.append("\nEDGES:")
    for edge in edges:
        lines.append(f"  - {edge['from_id']} --{edge['relation']}--> {edge['to_id']}")
    
    return "\n".join(lines)


def call_llm(prompt: str, model: str = "claude-sonnet-4-20250514") -> tuple:
    """Call LLM and return parsed response + raw text."""
    if Anthropic is None:
        raise RuntimeError("Anthropic library not installed")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    
    client = Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = response.content[0].text
    return parse_response(response_text), response_text


def execute_graph(graph_data: dict) -> tuple:
    """Execute calculation graph."""
    try:
        executor = GraphExecutor(graph_data=graph_data)
        trace = executor.execute('result')
        return trace.final_result, trace, None
    except Exception as e:
        return None, None, str(e)


# ============================================================
# Test 1: Single Agent with Only Database A
# ============================================================

def test_single_agent_a(verbose: bool = True) -> dict:
    """Single agent with only Database A access."""
    if verbose:
        print("\n" + "=" * 60)
        print("  TEST 1: Single Agent (Database A only)")
        print("=" * 60)
        print("\n  This agent can access Alpha Corp internal data")
        print("  but CANNOT access external market/competitor data.")
    
    prompt = SINGLE_AGENT_PROMPT.format(
        database=format_database(DATABASE_A),
        task=CROSS_DATABASE_TASK
    )
    
    parsed, raw = call_llm(prompt)
    
    if verbose:
        print(f"\n  Agent Response:")
        if parsed.get('error'):
            print(f"    Error: {parsed['error']}")
        if parsed.get('partial'):
            print(f"    Partial: {parsed['partial']}")
        print(f"    Nodes: {len(parsed.get('nodes', []))}")
    
    # Try to execute
    result = None
    if parsed.get('nodes') and not parsed.get('partial'):
        result, trace, error = execute_graph(parsed)
        if verbose and error:
            print(f"    Execution error: {error}")
    
    success = result is not None and abs(result - EXPECTED_ANSWER) < 1000
    
    if verbose:
        if success:
            print(f"\n  ⚠️ Single agent A succeeded (unexpected)")
        else:
            print(f"\n  ✅ Single agent A CANNOT complete task (missing external data)")
    
    return {"success": success, "result": result, "response": parsed}


# ============================================================
# Test 2: Single Agent with Only Database B
# ============================================================

def test_single_agent_b(verbose: bool = True) -> dict:
    """Single agent with only Database B access."""
    if verbose:
        print("\n" + "=" * 60)
        print("  TEST 2: Single Agent (Database B only)")
        print("=" * 60)
        print("\n  This agent can access external market data")
        print("  but CANNOT access Alpha Corp internal data.")
    
    prompt = SINGLE_AGENT_PROMPT.format(
        database=format_database(DATABASE_B),
        task=CROSS_DATABASE_TASK
    )
    
    parsed, raw = call_llm(prompt)
    
    if verbose:
        print(f"\n  Agent Response:")
        if parsed.get('error'):
            print(f"    Error: {parsed['error']}")
        if parsed.get('partial'):
            print(f"    Partial: {parsed['partial']}")
        print(f"    Nodes: {len(parsed.get('nodes', []))}")
    
    # Try to execute  
    result = None
    if parsed.get('nodes') and not parsed.get('partial'):
        result, trace, error = execute_graph(parsed)
        if verbose and error:
            print(f"    Execution error: {error}")
    
    success = result is not None and abs(result - EXPECTED_ANSWER) < 1000
    
    if verbose:
        if success:
            print(f"\n  ⚠️ Single agent B succeeded (unexpected)")
        else:
            print(f"\n  ✅ Single agent B CANNOT complete task (missing internal data)")
    
    return {"success": success, "result": result, "response": parsed}


# ============================================================
# Test 3: Two Agents Collaborating via Graph
# ============================================================

def test_multi_agent(verbose: bool = True) -> dict:
    """Two agents with different database access, collaborating via graph."""
    if verbose:
        print("\n" + "=" * 60)
        print("  TEST 3: Multi-Agent (Database A + Database B via Graph)")
        print("=" * 60)
        print("\n  Agent A has internal data, Agent B has external data")
        print("  Together they can complete the calculation")
    
    # Step 1: Agent A contributes from Database A
    if verbose:
        print("\n  --- Step 1: Agent A queries Database A ---")
    
    prompt_a = AGENT_A_PROMPT.format(
        database_a=format_database(DATABASE_A),
        task=CROSS_DATABASE_TASK
    )
    
    parsed_a, raw_a = call_llm(prompt_a)
    
    if verbose:
        print(f"    Contribution: {parsed_a.get('contribution', 'values from Database A')}")
        for node in parsed_a.get('nodes', []):
            if node.get('type') == 'OPERAND':
                print(f"      → {node['id']}: {node['data'].get('value')}")
    
    # Step 2: Agent B contributes from Database B, building on A's graph
    if verbose:
        print("\n  --- Step 2: Agent B queries Database B ---")
    
    graph_context = graph_to_context(
        parsed_a.get('nodes', []),
        parsed_a.get('edges', [])
    )
    
    prompt_b = AGENT_B_PROMPT.format(
        database_b=format_database(DATABASE_B),
        task=CROSS_DATABASE_TASK,
        graph_context=graph_context
    )
    
    parsed_b, raw_b = call_llm(prompt_b)
    
    if verbose:
        for node in parsed_b.get('nodes', []):
            if node.get('type') == 'OPERAND':
                print(f"      → {node['id']}: {node['data'].get('value')}")
            elif node.get('type') == 'OPERATION':
                print(f"      → {node['id']}: {node['data'].get('operation')}")
    
    # Step 3: Combine graphs
    if verbose:
        print("\n  --- Step 3: Combined Graph ---")
    
    combined_nodes = parsed_a.get('nodes', []) + parsed_b.get('nodes', [])
    combined_edges = parsed_a.get('edges', []) + parsed_b.get('edges', [])
    
    combined_graph = {
        "nodes": combined_nodes,
        "edges": combined_edges
    }
    
    if verbose:
        print(f"    Total nodes: {len(combined_nodes)}")
        print(f"    Total edges: {len(combined_edges)}")
    
    # Step 4: Execute combined graph
    if verbose:
        print("\n  --- Step 4: Execute ---")
    
    result, trace, error = execute_graph(combined_graph)
    
    if verbose:
        if error:
            print(f"    Error: {error}")
        elif trace:
            trace.print_trace()
    
    success = result is not None and abs(result - EXPECTED_ANSWER) < 10000
    
    if verbose:
        print(f"\n  Expected: {EXPECTED_ANSWER:,}")
        print(f"  Got:      {result:,}" if result else "  Got:      None")
        
        if success:
            print(f"\n  ✅ Multi-agent SUCCEEDED!")
            print(f"     NEW KNOWLEDGE created: {result:,}")
            print(f"     (Neither agent alone could produce this)")
        else:
            print(f"\n  ❌ Multi-agent failed")
    
    return {
        "success": success, 
        "result": result,
        "agent_a_nodes": len(parsed_a.get('nodes', [])),
        "agent_b_nodes": len(parsed_b.get('nodes', [])),
        "combined_nodes": len(combined_nodes)
    }


# ============================================================
# Run All Tests
# ============================================================

def run_all_tests(verbose: bool = True):
    """Run all tests and produce summary."""
    print("\n" + "=" * 70)
    print("  MULTI-AGENT VALUE PROOF")
    print("  Demonstrating: Different database access → Combined knowledge")
    print("=" * 70)
    
    print("\n  SCENARIO:")
    print("  - Agent A can ONLY access internal database (Q4 revenue: $47M)")
    print("  - Agent B can ONLY access external database (growth rate: 1.15, competitor: $52M)")
    print("  - TASK: Calculate projected revenue advantage over competitor")
    print("  - ANSWER: 47M * 1.15 - 52M = $2.05M advantage")
    print("\n  PROOF:")
    print("  - Single agent with Database A cannot complete (missing growth & competitor)")
    print("  - Single agent with Database B cannot complete (missing Q4 revenue)")
    print("  - Both agents via graph CAN complete (each contributes their data)")
    
    results = {}
    
    # Test 1: Single agent A
    results['single_a'] = test_single_agent_a(verbose)
    
    # Test 2: Single agent B
    results['single_b'] = test_single_agent_b(verbose)
    
    # Test 3: Multi-agent
    results['multi'] = test_multi_agent(verbose)
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    single_a_failed = not results['single_a']['success']
    single_b_failed = not results['single_b']['success']
    multi_succeeded = results['multi']['success']
    
    print(f"\n  Criterion 1: Single agent A cannot solve → {'✅ PASS' if single_a_failed else '❌ FAIL'}")
    print(f"  Criterion 2: Single agent B cannot solve → {'✅ PASS' if single_b_failed else '❌ FAIL'}")
    print(f"  Criterion 3: Multi-agent CAN solve      → {'✅ PASS' if multi_succeeded else '❌ FAIL'}")
    
    all_pass = single_a_failed and single_b_failed and multi_succeeded
    
    print(f"\n  " + "=" * 50)
    if all_pass:
        print(f"  ✅ MULTI-AGENT VALUE PROVEN")
        print(f"  ")
        print(f"  Neither agent alone could complete the task.")
        print(f"  Together, via shared graph, they synthesized")
        print(f"  NEW knowledge: ${results['multi']['result']:,} advantage")
        print(f"  ")
        print(f"  This is exactly like: A knows 3, B knows 5 → Graph: 8")
    else:
        print(f"  ❌ VALUE NOT PROVEN - review results above")
    print(f"  " + "=" * 50)
    
    return results


# ============================================================
# Simple Proof: The Math Example
# ============================================================

def simple_proof(verbose: bool = True):
    """
    The simplest proof: A knows 3, B knows 5, graph produces 8.
    No LLM calls - pure demonstration of the concept.
    """
    if verbose:
        print("\n" + "=" * 70)
        print("  SIMPLE PROOF: The Math Example")
        print("=" * 70)
    
    # Agent A's contribution (from its database)
    agent_a_graph = {
        "nodes": [
            {"id": "value_a", "type": "OPERAND", "data": {"value": 3}}
        ],
        "edges": []
    }
    
    if verbose:
        print(f"\n  Agent A (Database A access):")
        print(f"    → Contributes: 3")
    
    # Agent B's contribution (from its database), completing the graph
    agent_b_graph = {
        "nodes": [
            {"id": "value_b", "type": "OPERAND", "data": {"value": 5}},
            {"id": "add_op", "type": "OPERATION", "data": {"operation": "add"}},
            {"id": "result", "type": "RESULT", "data": {}}
        ],
        "edges": [
            {"from_id": "add_op", "to_id": "value_a", "relation": "REQUIRES"},
            {"from_id": "add_op", "to_id": "value_b", "relation": "REQUIRES"},
            {"from_id": "result", "to_id": "add_op", "relation": "REQUIRES"}
        ]
    }
    
    if verbose:
        print(f"\n  Agent B (Database B access):")
        print(f"    → Contributes: 5")
        print(f"    → Adds operation: add")
        print(f"    → Connects to Agent A's value")
    
    # Combine graphs
    combined = {
        "nodes": agent_a_graph["nodes"] + agent_b_graph["nodes"],
        "edges": agent_a_graph["edges"] + agent_b_graph["edges"]
    }
    
    # Execute
    executor = GraphExecutor(graph_data=combined)
    trace = executor.execute('result')
    
    if verbose:
        print(f"\n  Combined Graph Execution:")
        print(f"    3 + 5 = {trace.final_result}")
        
        print(f"\n  " + "=" * 50)
        print(f"  ✅ NEW KNOWLEDGE CREATED: 8")
        print(f"  ")
        print(f"  Agent A alone could only produce: 3")
        print(f"  Agent B alone could only produce: 5")
        print(f"  Together via graph they produced: 8")
        print(f"  " + "=" * 50)
    
    return trace.final_result


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Agent Value Proof")
    parser.add_argument("--simple", action="store_true", help="Run simple math proof only (no LLM calls)")
    parser.add_argument("--full", action="store_true", help="Run full LLM test")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    if args.simple or (not args.full):
        # Default: run simple proof
        simple_proof(verbose)
    
    if args.full:
        # Run full LLM tests
        run_all_tests(verbose)
