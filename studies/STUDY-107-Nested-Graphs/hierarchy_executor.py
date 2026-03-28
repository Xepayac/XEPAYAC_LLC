"""
Hierarchical Graph Executor

Executes nested graph structures while respecting scope boundaries.

Key features:
- Enters/exits subgraphs during execution
- Maintains execution context stack
- Supports cross-scope data flow via edges
- Provides detailed execution trace
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from nested_graph import NestedGraph, Node, NodeType, ScopedNodeId


@dataclass
class ExecutionContext:
    """Context for a single scope level during execution."""
    graph: NestedGraph
    scope_path: List[str]
    local_results: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def scope_id(self) -> str:
        return "/".join(self.scope_path) if self.scope_path else "root"


@dataclass 
class ExecutionStep:
    """A single step in the execution trace."""
    scope_path: List[str]
    node_id: str
    node_type: str
    action: str
    result: Any = None
    
    @property
    def full_id(self) -> str:
        if self.scope_path:
            return "/".join(self.scope_path) + "/" + self.node_id
        return self.node_id
    
    def __str__(self) -> str:
        indent = "    " * len(self.scope_path)
        return f"{indent}[{self.node_type}] {self.node_id}: {self.action}"


class HierarchyExecutor:
    """
    Executes nested graphs hierarchically.
    
    The executor:
    1. Follows edge dependencies (topological order)
    2. Enters subgraphs when encountering SUBGRAPH nodes
    3. Maintains separate result contexts per scope
    4. Supports custom node handlers
    """
    
    def __init__(self, root_graph: NestedGraph):
        self.root_graph = root_graph
        self.context_stack: List[ExecutionContext] = []
        self.trace: List[ExecutionStep] = []
        self.results: Dict[str, Any] = {}  # Scoped results
        
        # Custom handlers for different node types
        self.handlers: Dict[NodeType, Callable[[Node, ExecutionContext], Any]] = {
            NodeType.TASK: self._handle_task,
            NodeType.OPERAND: self._handle_operand,
            NodeType.OPERATION: self._handle_operation,
            NodeType.RESULT: self._handle_result,
            NodeType.CONCEPT: self._handle_concept,
            NodeType.DECISION: self._handle_decision,
        }
    
    def execute(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Execute the entire graph hierarchy.
        
        Returns dict of all results keyed by scoped node ID.
        """
        # Start with root context
        root_context = ExecutionContext(
            graph=self.root_graph,
            scope_path=[]
        )
        
        self._execute_graph(root_context, verbose)
        
        return self.results
    
    def _execute_graph(self, context: ExecutionContext, verbose: bool) -> None:
        """Execute a single graph in the hierarchy."""
        self.context_stack.append(context)
        
        # Get execution order (topological sort based on edges)
        order = self._get_execution_order(context.graph)
        
        for node_id in order:
            node = context.graph.get_node(node_id)
            if not node:
                continue
            
            if node.is_subgraph():
                # Enter subgraph
                self._enter_subgraph(node, context, verbose)
            else:
                # Execute regular node
                self._execute_node(node, context, verbose)
        
        self.context_stack.pop()
    
    def _enter_subgraph(self, node: Node, parent_context: ExecutionContext, verbose: bool) -> None:
        """Enter and execute a subgraph."""
        step = ExecutionStep(
            scope_path=parent_context.scope_path.copy(),
            node_id=node.id,
            node_type="SUBGRAPH",
            action=f"Entering {node.subgraph_ref or 'inline'}..."
        )
        self.trace.append(step)
        
        if verbose:
            indent = "  " * len(parent_context.scope_path)
            print(f"{indent}[SUBGRAPH] Entering {node.id}...")
        
        try:
            subgraph = parent_context.graph.load_subgraph(node.id)
            
            # Create child context
            child_context = ExecutionContext(
                graph=subgraph,
                scope_path=parent_context.scope_path + [node.id]
            )
            
            # Execute subgraph
            self._execute_graph(child_context, verbose)
            
            # Record subgraph completion
            scoped_id = "/".join(parent_context.scope_path + [node.id])
            self.results[scoped_id] = {"status": "completed", "nodes_executed": len(subgraph.nodes)}
            
            if verbose:
                print(f"{indent}[SUBGRAPH] Exiting {node.id}")
                
        except Exception as e:
            if verbose:
                indent = "  " * len(parent_context.scope_path)
                print(f"{indent}[SUBGRAPH] Error in {node.id}: {e}")
    
    def _execute_node(self, node: Node, context: ExecutionContext, verbose: bool) -> Any:
        """Execute a single node."""
        handler = self.handlers.get(node.type, self._handle_default)
        result = handler(node, context)
        
        # Store result with scoped ID
        scoped_id = "/".join(context.scope_path + [node.id]) if context.scope_path else node.id
        self.results[scoped_id] = result
        context.local_results[node.id] = result
        
        # Record step
        step = ExecutionStep(
            scope_path=context.scope_path.copy(),
            node_id=node.id,
            node_type=node.type.value,
            action=str(result)[:50],
            result=result
        )
        self.trace.append(step)
        
        if verbose:
            indent = "  " * len(context.scope_path)
            print(f"{indent}[{node.type.value}] {node.id}: {str(result)[:50]}")
        
        return result
    
    def _get_execution_order(self, graph: NestedGraph) -> List[str]:
        """Get topological execution order based on edges."""
        # Build dependency graph
        deps: Dict[str, set] = {n: set() for n in graph.nodes}
        
        for edge in graph.edges:
            if edge.relation in ("REQUIRES", "DEPENDS_ON"):
                # to_id requires from_id, so from_id comes first
                if edge.to_id in deps:
                    deps[edge.to_id].add(edge.from_id)
            elif edge.relation == "LEADS_TO":
                # from_id leads to to_id, so from_id comes first
                if edge.to_id in deps:
                    deps[edge.to_id].add(edge.from_id)
        
        # Topological sort
        order = []
        visited = set()
        temp_visited = set()
        
        def visit(node_id: str):
            if node_id in temp_visited:
                return  # Cycle, skip
            if node_id in visited:
                return
            
            temp_visited.add(node_id)
            for dep in deps.get(node_id, []):
                if dep in graph.nodes:
                    visit(dep)
            temp_visited.remove(node_id)
            visited.add(node_id)
            order.append(node_id)
        
        for node_id in graph.nodes:
            if node_id not in visited:
                visit(node_id)
        
        return order
    
    # Node type handlers
    
    def _handle_task(self, node: Node, context: ExecutionContext) -> Any:
        """Handle TASK nodes."""
        desc = node.data.get("description", node.id)
        return {"status": "completed", "task": desc}
    
    def _handle_operand(self, node: Node, context: ExecutionContext) -> Any:
        """Handle OPERAND nodes - return the value."""
        return node.data.get("value", 0)
    
    def _handle_operation(self, node: Node, context: ExecutionContext) -> Any:
        """Handle OPERATION nodes - perform calculation."""
        op = node.data.get("operation", "identity")
        inputs = []
        
        # Get inputs from edges
        for edge in context.graph.edges:
            if edge.to_id == node.id and edge.relation == "REQUIRES":
                if edge.from_id in context.local_results:
                    inputs.append(context.local_results[edge.from_id])
        
        # Perform operation
        if op == "add" and len(inputs) >= 2:
            return sum(inputs)
        elif op == "multiply" and len(inputs) >= 2:
            result = 1
            for v in inputs:
                result *= v
            return result
        elif op == "validate":
            return all(inputs)
        else:
            return inputs[0] if inputs else None
    
    def _handle_result(self, node: Node, context: ExecutionContext) -> Any:
        """Handle RESULT nodes."""
        # Get input from edges
        for edge in context.graph.edges:
            if edge.to_id == node.id:
                if edge.from_id in context.local_results:
                    return context.local_results[edge.from_id]
        return None
    
    def _handle_concept(self, node: Node, context: ExecutionContext) -> Any:
        """Handle CONCEPT nodes."""
        return node.data.get("description", node.id)
    
    def _handle_decision(self, node: Node, context: ExecutionContext) -> Any:
        """Handle DECISION nodes."""
        return node.data.get("choice", "default")
    
    def _handle_default(self, node: Node, context: ExecutionContext) -> Any:
        """Default handler for unknown node types."""
        return {"node": node.id, "type": node.type.value}
    
    def print_trace(self) -> None:
        """Print the execution trace."""
        print("\n=== EXECUTION TRACE ===")
        for step in self.trace:
            print(step)
        print("======================\n")
