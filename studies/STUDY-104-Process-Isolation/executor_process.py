#!/usr/bin/env python3
"""
Executor: Isolated Process

The executor runs as a SEPARATE PROCESS.
It has NO database access.
It ONLY reads the graph file and computes the result.

Usage: python executor_process.py <graph_file_path>
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


# ============================================================
# The executor has NO DATABASE ACCESS
# It can only operate on values already in the graph
# ============================================================


def load_graph(filepath: str) -> dict:
    """Load graph from JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


class GraphExecutor:
    """Execute computation defined by graph structure."""
    
    OPERATIONS = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else None,
    }
    
    def __init__(self, graph: dict):
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.edges = graph["edges"]
        self.computed: Dict[str, Any] = {}
        self.trace: List[str] = []
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes that a given node depends on."""
        return [e["to_id"] for e in self.edges if e["from_id"] == node_id]
    
    def execute(self, target: str = "result") -> Optional[float]:
        """Execute graph from target node."""
        return self._compute(target)
    
    def _compute(self, node_id: str) -> Any:
        """Recursively compute a node's value."""
        
        if node_id in self.computed:
            return self.computed[node_id]
        
        node = self.nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")
        
        node_type = node["type"]
        
        if node_type == "OPERAND":
            value = node["data"]["value"]
            self.computed[node_id] = value
            self.trace.append(f"READ {node_id}: {value}")
            return value
        
        elif node_type == "OPERATION":
            deps = self.get_dependencies(node_id)
            inputs = [self._compute(dep) for dep in deps]
            
            operation = node["data"]["operation"]
            if operation not in self.OPERATIONS:
                raise ValueError(f"Unknown operation: {operation}")
            
            result = self.OPERATIONS[operation](inputs[0], inputs[1])
            self.computed[node_id] = result
            self.trace.append(f"{operation.upper()}({inputs[0]}, {inputs[1]}) = {result}")
            return result
        
        elif node_type == "RESULT":
            deps = self.get_dependencies(node_id)
            result = self._compute(deps[0])
            self.computed[node_id] = result
            return result
        
        else:
            raise ValueError(f"Unknown node type: {node_type}")
    
    def print_trace(self) -> None:
        """Print execution trace."""
        print("\n" + "=" * 50)
        print("EXECUTION TRACE")
        print("=" * 50)
        for step in self.trace:
            print(f"  {step}")
        print("-" * 50)
        print(f"  FINAL RESULT: {self.computed.get('result')}")
        print("=" * 50)


def main():
    if len(sys.argv) != 2:
        print("Usage: python executor_process.py <graph_file_path>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    
    print(f"\n{'=' * 50}")
    print(f"  EXECUTOR (Separate Process)")
    print(f"{'=' * 50}")
    
    import os
    print(f"[Executor] Process ID: {os.getpid()}")
    print(f"[Executor] Database access: NONE")
    
    # Load graph
    graph = load_graph(graph_file)
    print(f"[Executor] Loaded graph with {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    
    # Execute
    executor = GraphExecutor(graph)
    result = executor.execute("result")
    
    executor.print_trace()
    
    # Verify
    print("\n" + "-" * 50)
    print("VERIFICATION")
    print("-" * 50)
    expected = (47_000_000 * 1.15) - 52_000_000
    print(f"  Expected: ${expected:,.2f}")
    print(f"  Got:      ${result:,.2f}")
    print(f"  Match:    {'✓ YES' if abs(result - expected) < 0.01 else '✗ NO'}")
    
    print(f"{'=' * 50}\n")
    
    return result


if __name__ == "__main__":
    main()
