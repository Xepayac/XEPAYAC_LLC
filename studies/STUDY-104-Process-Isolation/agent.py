"""
Isolated Agents

Each agent has EXCLUSIVE access to its own database.
Agents CANNOT access each other's data.
Agents CANNOT communicate directly.
The ONLY way to share information is through the shared graph.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .graph import SharedGraph, Node, Edge, NodeType


class Database:
    """
    Simulates a data source with exclusive access.
    
    In a real system, this would be:
    - A database with authentication
    - An API with restricted credentials
    - A file system with permissions
    - Any data source with access control
    """
    
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self._data = data
    
    def query(self, key: str) -> Optional[Any]:
        """Query a value from the database."""
        return self._data.get(key)
    
    def list_keys(self) -> list:
        """List available keys."""
        return list(self._data.keys())


class IsolatedAgent(ABC):
    """
    An agent with isolated data access.
    
    KEY ARCHITECTURAL CONSTRAINTS:
    1. Each agent has exactly ONE database
    2. The agent CANNOT access any other database
    3. The agent CANNOT communicate directly with other agents
    4. The ONLY output mechanism is adding nodes/edges to the shared graph
    """
    
    def __init__(self, agent_id: str, database: Database):
        self.agent_id = agent_id
        self.database = database
    
    @abstractmethod
    def contribute(self, graph: SharedGraph, task: str) -> None:
        """
        Contribute to the shared graph.
        
        The agent:
        1. Reads the current graph state
        2. Queries its own database for relevant values
        3. Adds nodes and edges to the graph
        
        The agent CANNOT:
        1. Access other databases
        2. Send messages to other agents
        3. Modify nodes created by other agents
        """
        pass
    
    def _create_operand(self, node_id: str, value: Any, 
                        data_key: Optional[str] = None) -> Node:
        """Helper to create an operand node with provenance."""
        return Node(
            id=node_id,
            node_type=NodeType.OPERAND,
            data={"value": value},
            contributed_by=self.agent_id,
            data_source=f"{self.database.name}:{data_key}" if data_key else self.database.name
        )
    
    def _create_operation(self, node_id: str, operation: str) -> Node:
        """Helper to create an operation node."""
        return Node(
            id=node_id,
            node_type=NodeType.OPERATION,
            data={"operation": operation},
            contributed_by=self.agent_id
        )
    
    def _create_result(self, node_id: str = "result") -> Node:
        """Helper to create a result node."""
        return Node(
            id=node_id,
            node_type=NodeType.RESULT,
            data={},
            contributed_by=self.agent_id
        )


# ============================================================
# Concrete Agent Implementations
# ============================================================

class AgentA(IsolatedAgent):
    """
    Agent A: Has exclusive access to internal corporate database.
    
    CANNOT access external market data.
    """
    
    def contribute(self, graph: SharedGraph, task: str) -> None:
        """
        Contribute internal data to the graph.
        
        Agent A can ONLY query its own database.
        It adds nodes with values and their provenance.
        """
        print(f"\n[{self.agent_id}] Contributing to graph...")
        print(f"[{self.agent_id}] Database: {self.database.name}")
        print(f"[{self.agent_id}] Available data: {self.database.list_keys()}")
        
        # Query our database for relevant values
        q4_revenue = self.database.query("q4_revenue")
        
        if q4_revenue is not None:
            # Add our contribution to the graph
            node = self._create_operand(
                node_id="q4_revenue",
                value=q4_revenue,
                data_key="q4_revenue"
            )
            graph.add_node(node)
            print(f"[{self.agent_id}] Added node: q4_revenue = {q4_revenue}")
        
        print(f"[{self.agent_id}] Contribution complete.")


class AgentB(IsolatedAgent):
    """
    Agent B: Has exclusive access to external market analytics.
    
    CANNOT access internal corporate data.
    """
    
    def contribute(self, graph: SharedGraph, task: str) -> None:
        """
        Contribute external data and complete the computation structure.
        
        Agent B:
        1. Reads the existing graph (sees Agent A's contributions)
        2. Queries its own database for values
        3. Adds nodes for its values
        4. Adds operation nodes and edges to define computation
        5. Adds result node
        """
        print(f"\n[{self.agent_id}] Contributing to graph...")
        print(f"[{self.agent_id}] Database: {self.database.name}")
        print(f"[{self.agent_id}] Available data: {self.database.list_keys()}")
        
        # See what Agent A contributed (read-only access to graph)
        existing_nodes = list(graph.nodes.keys())
        print(f"[{self.agent_id}] Existing nodes in graph: {existing_nodes}")
        
        # Query our database
        growth_rate = self.database.query("market_growth_rate")
        competitor_revenue = self.database.query("competitor_revenue")
        
        # Add our operand nodes
        if growth_rate is not None:
            node = self._create_operand(
                node_id="growth_rate",
                value=growth_rate,
                data_key="market_growth_rate"
            )
            graph.add_node(node)
            print(f"[{self.agent_id}] Added node: growth_rate = {growth_rate}")
        
        if competitor_revenue is not None:
            node = self._create_operand(
                node_id="competitor_revenue",
                value=competitor_revenue,
                data_key="competitor_revenue"
            )
            graph.add_node(node)
            print(f"[{self.agent_id}] Added node: competitor_revenue = {competitor_revenue}")
        
        # Add operation nodes to define the computation
        # Step 1: Multiply q4_revenue * growth_rate = projected_revenue
        multiply_node = self._create_operation("multiply_projection", "multiply")
        graph.add_node(multiply_node)
        graph.add_edge(Edge("multiply_projection", "q4_revenue"))
        graph.add_edge(Edge("multiply_projection", "growth_rate"))
        print(f"[{self.agent_id}] Added operation: multiply_projection")
        
        # Step 2: Subtract competitor_revenue = advantage
        subtract_node = self._create_operation("subtract_advantage", "subtract")
        graph.add_node(subtract_node)
        graph.add_edge(Edge("subtract_advantage", "multiply_projection"))
        graph.add_edge(Edge("subtract_advantage", "competitor_revenue"))
        print(f"[{self.agent_id}] Added operation: subtract_advantage")
        
        # Step 3: Mark the result
        result_node = self._create_result("result")
        graph.add_node(result_node)
        graph.add_edge(Edge("result", "subtract_advantage"))
        print(f"[{self.agent_id}] Added result node")
        
        print(f"[{self.agent_id}] Contribution complete.")
