"""
Graph Executor

Traverses the graph structure and computes the result.
The executor does NOT have access to any database.
It ONLY operates on values already in the graph.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from .graph import SharedGraph, Node, NodeType


@dataclass
class ExecutionStep:
    """A single step in the execution trace."""
    node_id: str
    operation: str
    inputs: List[Any]
    output: Any
    

@dataclass
class ExecutionTrace:
    """Complete trace of graph execution for auditability."""
    steps: List[ExecutionStep] = field(default_factory=list)
    final_result: Optional[Any] = None
    
    def add_step(self, node_id: str, operation: str, 
                 inputs: List[Any], output: Any) -> None:
        self.steps.append(ExecutionStep(node_id, operation, inputs, output))
    
    def print_trace(self) -> None:
        """Print the execution trace."""
        print("\n" + "=" * 50)
        print("EXECUTION TRACE")
        print("=" * 50)
        
        for step in self.steps:
            if step.operation == "read":
                print(f"  READ  {step.node_id}: {step.output}")
            else:
                inputs_str = ", ".join(str(i) for i in step.inputs)
                print(f"  {step.operation.upper()}({inputs_str}) = {step.output}")
        
        print("-" * 50)
        print(f"  FINAL RESULT: {self.final_result}")
        print("=" * 50)


class GraphExecutor:
    """
    Executes the computation defined by the graph structure.
    
    KEY PROPERTIES:
    1. Executor has NO database access
    2. Executor ONLY uses values in the graph
    3. Execution follows edge dependencies
    4. Execution is deterministic and reproducible
    5. Execution produces an audit trace
    """
    
    OPERATIONS = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else None,
    }
    
    def __init__(self, graph: SharedGraph):
        self.graph = graph
        self.computed: Dict[str, Any] = {}
        self.trace = ExecutionTrace()
    
    def execute(self, target_node_id: str = "result") -> ExecutionTrace:
        """
        Execute the graph starting from target node.
        
        Returns an execution trace for auditability.
        """
        print(f"\n[Executor] Starting execution from '{target_node_id}'")
        
        result = self._compute_node(target_node_id)
        self.trace.final_result = result
        
        print(f"[Executor] Execution complete. Result: {result}")
        
        return self.trace
    
    def _compute_node(self, node_id: str) -> Any:
        """Recursively compute a node's value."""
        
        # Check cache
        if node_id in self.computed:
            return self.computed[node_id]
        
        node = self.graph.get_node(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")
        
        # Handle by node type
        if node.node_type == NodeType.OPERAND:
            # Operand: just read the value
            value = node.data.get("value")
            self.computed[node_id] = value
            self.trace.add_step(node_id, "read", [], value)
            return value
        
        elif node.node_type == NodeType.OPERATION:
            # Operation: compute based on dependencies
            deps = self.graph.get_dependencies(node_id)
            inputs = [self._compute_node(dep) for dep in deps]
            
            operation = node.data.get("operation")
            if operation not in self.OPERATIONS:
                raise ValueError(f"Unknown operation: {operation}")
            
            # Execute the operation
            if len(inputs) == 2:
                result = self.OPERATIONS[operation](inputs[0], inputs[1])
            else:
                raise ValueError(f"Operation {operation} requires 2 inputs, got {len(inputs)}")
            
            self.computed[node_id] = result
            self.trace.add_step(node_id, operation, inputs, result)
            return result
        
        elif node.node_type == NodeType.RESULT:
            # Result: compute the dependency
            deps = self.graph.get_dependencies(node_id)
            if len(deps) != 1:
                raise ValueError(f"Result node must have exactly 1 dependency")
            
            result = self._compute_node(deps[0])
            self.computed[node_id] = result
            return result
        
        else:
            raise ValueError(f"Unknown node type: {node.node_type}")
