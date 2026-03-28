"""
Graph Executor: Reads graph structure and executes operations.

The executor is generic—it doesn't know what computation to do.
The graph tells it:
  - What operands exist (nodes with values)
  - What operations to perform (edges with relations)
  - What order to execute (dependency traversal)
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class ExecutionStep:
    """Record of one step in graph execution."""
    node_id: str
    action: str
    value: Any
    source: str  # "graph" or "computed"


@dataclass
class ExecutionTrace:
    """Complete trace of graph execution."""
    steps: List[ExecutionStep]
    final_result: Any
    
    def print_trace(self):
        """Print human-readable execution trace."""
        print("\nExecution Trace:")
        print("-" * 50)
        for step in self.steps:
            print(f"  {step.action}: {step.value} (from {step.source})")
        print("-" * 50)
        print(f"  Result: {self.final_result}")
        print()


class GraphExecutor:
    """
    Executes computation defined by graph structure.
    
    The executor reads:
    - Node data for operand values
    - Edge relations for operations (REQUIRES = input, PRODUCES = output)
    - Node types for operation types (OPERAND, OPERATION, RESULT)
    """
    
    def __init__(self, graph_path: Optional[str] = None, graph_data: Optional[dict] = None):
        """Load graph from file or dict."""
        if graph_data:
            data = graph_data
        elif graph_path:
            with open(graph_path, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError("Must provide graph_path or graph_data")
        
        # Index nodes by ID
        self.nodes: Dict[str, dict] = {}
        for node in data.get('nodes', []):
            self.nodes[node['id']] = node
        
        # Index edges
        self.edges: List[dict] = data.get('edges', [])
        
        # Build adjacency for traversal
        self.edges_from: Dict[str, List[dict]] = {}
        self.edges_to: Dict[str, List[dict]] = {}
        for edge in self.edges:
            from_id = edge['from_id']
            to_id = edge['to_id']
            
            if from_id not in self.edges_from:
                self.edges_from[from_id] = []
            self.edges_from[from_id].append(edge)
            
            if to_id not in self.edges_to:
                self.edges_to[to_id] = []
            self.edges_to[to_id].append(edge)
    
    def get_node(self, node_id: str) -> Optional[dict]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_inputs(self, node_id: str) -> List[str]:
        """Get all nodes that feed INTO this node (via REQUIRES edges)."""
        inputs = []
        for edge in self.edges_to.get(node_id, []):
            if edge['relation'] == 'REQUIRES':
                inputs.append(edge['from_id'])
        return inputs
    
    def get_operands(self, operation_id: str) -> List[str]:
        """Get operand node IDs for an operation."""
        operands = []
        for edge in self.edges_from.get(operation_id, []):
            if edge['relation'] == 'REQUIRES':
                operands.append(edge['to_id'])
        return operands
    
    def execute(self, result_node_id: str) -> ExecutionTrace:
        """
        Execute the graph to compute a result.
        
        Traverses from result node backwards through REQUIRES edges,
        collects operands, performs operations.
        """
        steps: List[ExecutionStep] = []
        computed: Dict[str, Any] = {}
        
        def compute(node_id: str) -> Any:
            """Recursively compute a node's value."""
            if node_id in computed:
                return computed[node_id]
            
            node = self.get_node(node_id)
            if not node:
                raise ValueError(f"Node not found: {node_id}")
            
            node_type = node.get('type', '')
            node_data = node.get('data', {})
            
            # OPERAND: value comes directly from graph
            if node_type == 'OPERAND':
                value = node_data.get('value')
                steps.append(ExecutionStep(
                    node_id=node_id,
                    action=f"Read {node_id}",
                    value=value,
                    source="graph"
                ))
                computed[node_id] = value
                return value
            
            # OPERATION: compute based on operands
            if node_type == 'OPERATION':
                operation = node_data.get('operation', 'unknown')
                operand_ids = self.get_operands(node_id)
                
                # Compute operands first
                operand_values = [compute(op_id) for op_id in operand_ids]
                
                # Perform the operation
                if operation == 'add':
                    result = sum(operand_values)
                elif operation == 'subtract':
                    result = operand_values[0] - operand_values[1] if len(operand_values) >= 2 else 0
                elif operation == 'multiply':
                    result = 1
                    for v in operand_values:
                        result *= v
                elif operation == 'divide':
                    result = operand_values[0] / operand_values[1] if len(operand_values) >= 2 and operand_values[1] != 0 else 0
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                steps.append(ExecutionStep(
                    node_id=node_id,
                    action=f"{operation}({', '.join(str(v) for v in operand_values)})",
                    value=result,
                    source="computed"
                ))
                computed[node_id] = result
                return result
            
            # RESULT: just pass through from its input
            if node_type == 'RESULT':
                input_ids = self.get_operands(node_id)
                if input_ids:
                    result = compute(input_ids[0])
                    steps.append(ExecutionStep(
                        node_id=node_id,
                        action=f"Result",
                        value=result,
                        source="computed"
                    ))
                    computed[node_id] = result
                    return result
            
            raise ValueError(f"Cannot compute node type: {node_type}")
        
        final_result = compute(result_node_id)
        
        return ExecutionTrace(
            steps=steps,
            final_result=final_result
        )


def create_addition_graph(a: int, b: int) -> dict:
    """
    Create a graph that represents: a + b = result
    
    This is what LLMs would create. For testing, we create it directly.
    """
    return {
        "nodes": [
            {
                "id": "operand-a",
                "type": "OPERAND",
                "data": {"value": a, "description": f"First operand: {a}"}
            },
            {
                "id": "operand-b", 
                "type": "OPERAND",
                "data": {"value": b, "description": f"Second operand: {b}"}
            },
            {
                "id": "addition",
                "type": "OPERATION",
                "data": {"operation": "add", "description": "Add the operands"}
            },
            {
                "id": "result",
                "type": "RESULT",
                "data": {"description": "The final result"}
            }
        ],
        "edges": [
            {"from_id": "addition", "to_id": "operand-a", "relation": "REQUIRES", "weight": 1.0},
            {"from_id": "addition", "to_id": "operand-b", "relation": "REQUIRES", "weight": 1.0},
            {"from_id": "result", "to_id": "addition", "relation": "REQUIRES", "weight": 1.0}
        ]
    }
