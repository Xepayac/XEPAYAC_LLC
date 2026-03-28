"""
Test: LLM Creates Executable Calculation Graph

This test connects lab/ (LLM graph creation) to lab_executable/ (graph execution).

Flow:
1. LLM receives a calculation task
2. LLM creates a graph with OPERAND, OPERATION, RESULT nodes
3. Executor reads the graph and computes the result
4. We verify the answer is correct
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from egs import EGS
from egs.models import Node, Edge, NodeType

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from lab.protocol import load_env, parse_response
from lab_executable.executor import GraphExecutor

load_env()


CALCULATION_PROMPT = """You are creating an executable calculation graph.

The graph will be executed by a machine. It must have these exact node types:
- OPERAND: Contains a numeric value in data.value
- OPERATION: Contains operation type in data.operation (add, subtract, multiply, divide)
- RESULT: The final result node

Edges must use:
- REQUIRES relation to connect operation to its operands
- REQUIRES relation to connect result to operation

TASK: Create a graph that computes: {expression}

Example for "3 + 5":
{{
    "nodes": [
        {{"id": "a", "type": "OPERAND", "data": {{"value": 3}}}},
        {{"id": "b", "type": "OPERAND", "data": {{"value": 5}}}},
        {{"id": "add", "type": "OPERATION", "data": {{"operation": "add"}}}},
        {{"id": "result", "type": "RESULT", "data": {{}}}}
    ],
    "edges": [
        {{"from_id": "add", "to_id": "a", "relation": "REQUIRES", "weight": 1.0}},
        {{"from_id": "add", "to_id": "b", "relation": "REQUIRES", "weight": 1.0}},
        {{"from_id": "result", "to_id": "add", "relation": "REQUIRES", "weight": 1.0}}
    ]
}}

Now create the graph for: {expression}

Respond with JSON only. No explanation needed.
"""


def llm_create_calculation(expression: str, model: str = "claude-sonnet-4-20250514") -> dict:
    """Have LLM create an executable calculation graph."""
    if Anthropic is None:
        raise RuntimeError("Anthropic library not installed")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    
    client = Anthropic(api_key=api_key)
    
    prompt = CALCULATION_PROMPT.format(expression=expression)
    
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = response.content[0].text
    return parse_response(response_text), response_text


def execute_graph(graph_data: dict) -> tuple:
    """Execute a calculation graph and return result with trace."""
    executor = GraphExecutor(graph_data=graph_data)
    trace = executor.execute('result')
    return trace.final_result, trace


def run_test(expression: str, expected: float, verbose: bool = True) -> bool:
    """
    Run full test: LLM creates graph → executor runs it → verify result.
    
    Returns True if result matches expected.
    """
    if verbose:
        print("\n" + "=" * 60)
        print(f"  TEST: LLM Creates Executable Calculation")
        print("=" * 60)
        print(f"\nExpression: {expression}")
        print(f"Expected result: {expected}")
    
    # Step 1: LLM creates graph
    if verbose:
        print("\n--- Step 1: LLM Creates Graph ---")
    
    graph_data, raw_response = llm_create_calculation(expression)
    
    if "error" in graph_data:
        if verbose:
            print(f"ERROR: Failed to parse LLM response")
            print(f"Raw: {raw_response}")
        return False
    
    if verbose:
        print(f"Nodes created: {len(graph_data.get('nodes', []))}")
        for node in graph_data.get('nodes', []):
            print(f"  - {node['id']} [{node['type']}]: {node.get('data', {})}")
        print(f"Edges created: {len(graph_data.get('edges', []))}")
        for edge in graph_data.get('edges', []):
            print(f"  - {edge['from_id']} --{edge['relation']}--> {edge['to_id']}")
    
    # Step 2: Execute graph
    if verbose:
        print("\n--- Step 2: Execute Graph ---")
    
    try:
        result, trace = execute_graph(graph_data)
    except Exception as e:
        if verbose:
            print(f"ERROR: Execution failed: {e}")
        return False
    
    if verbose:
        trace.print_trace()
    
    # Step 3: Verify result
    if verbose:
        print("\n--- Step 3: Verify Result ---")
    
    # Handle floating point comparison
    if isinstance(result, float) and isinstance(expected, float):
        success = abs(result - expected) < 0.0001
    else:
        success = result == expected
    
    if verbose:
        print(f"Computed: {result}")
        print(f"Expected: {expected}")
        if success:
            print(f"\n✅ SUCCESS: LLM-created graph computed correctly!")
        else:
            print(f"\n❌ FAILURE: Result mismatch")
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Test LLM creating executable calculation graphs"
    )
    parser.add_argument('--expression', type=str, default="15 + 27",
                        help='Math expression (default: "15 + 27")')
    parser.add_argument('--expected', type=float, default=42,
                        help='Expected result (default: 42)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Minimal output')
    
    args = parser.parse_args()
    
    success = run_test(args.expression, args.expected, verbose=not args.quiet)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
