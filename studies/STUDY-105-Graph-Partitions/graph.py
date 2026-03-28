"""
Shared Graph for Supply Chain Optimization

This is the ONLY shared resource between parties.
Each party reads/writes to this file.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class SupplyNode:
    """A node contributed by the seller."""
    node_id: str
    node_type: str  # "supply"
    product: str
    quantity: int
    min_price: float
    contributed_by: str
    data_source: str


@dataclass
class DemandNode:
    """A node contributed by a buyer."""
    node_id: str
    node_type: str  # "demand"
    product: str
    quantity: int
    max_price: float
    contributed_by: str
    data_source: str


@dataclass
class AllocationNode:
    """A node contributed by the optimizer."""
    node_id: str
    node_type: str  # "allocation"
    seller: str
    buyer: str
    quantity: int
    price: float
    contributed_by: str
    reasoning: str


@dataclass
class BidNode:
    """A bid from a buyer - Phase 2 LLM negotiation."""
    node_id: str
    node_type: str  # "bid"
    buyer: str
    product: str
    quantity: int
    bid_price: float
    round_number: int
    contributed_by: str
    reasoning: str  # LLM's reasoning for this bid


@dataclass
class CounterNode:
    """A counter-offer from seller - Phase 2 LLM negotiation."""
    node_id: str
    node_type: str  # "counter"
    seller: str
    buyer: str
    product: str
    quantity: int
    counter_price: float
    round_number: int
    contributed_by: str
    reasoning: str  # LLM's reasoning for this counter


@dataclass
class AcceptNode:
    """Acceptance of a deal - Phase 2 LLM negotiation."""
    node_id: str
    node_type: str  # "accept"
    buyer: str
    seller: str
    quantity: int
    final_price: float
    round_number: int
    contributed_by: str
    reasoning: str


@dataclass
class Edge:
    """Connection between nodes."""
    source: str
    target: str
    edge_type: str
    label: Optional[str] = None


@dataclass 
class SupplyChainGraph:
    """The shared graph structure."""
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    execution_log: list = field(default_factory=list)
    
    def add_supply(self, node: SupplyNode) -> None:
        """Add a supply node from seller."""
        self.nodes.append(asdict(node))
        self.execution_log.append({
            "action": "add_supply",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by
        })
    
    def add_demand(self, node: DemandNode) -> None:
        """Add a demand node from buyer."""
        self.nodes.append(asdict(node))
        self.execution_log.append({
            "action": "add_demand",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by
        })
    
    def add_allocation(self, node: AllocationNode, supply_id: str, demand_id: str) -> None:
        """Add an allocation node and connect to supply/demand."""
        self.nodes.append(asdict(node))
        self.edges.append(asdict(Edge(
            source=supply_id,
            target=node.node_id,
            edge_type="supplies",
            label=f"{node.quantity} units"
        )))
        self.edges.append(asdict(Edge(
            source=node.node_id,
            target=demand_id,
            edge_type="fulfills",
            label=f"{node.quantity} units @ ${node.price}"
        )))
        self.execution_log.append({
            "action": "add_allocation",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by
        })
    
    def get_supplies(self) -> list:
        """Get all supply nodes."""
        return [n for n in self.nodes if n.get("node_type") == "supply"]
    
    def get_demands(self) -> list:
        """Get all demand nodes."""
        return [n for n in self.nodes if n.get("node_type") == "demand"]
    
    def get_allocations(self) -> list:
        """Get all allocation nodes."""
        return [n for n in self.nodes if n.get("node_type") == "allocation"]
    
    def get_bids(self, buyer: str = None, round_number: int = None) -> list:
        """Get bid nodes, optionally filtered."""
        bids = [n for n in self.nodes if n.get("node_type") == "bid"]
        if buyer:
            bids = [b for b in bids if b.get("buyer") == buyer]
        if round_number is not None:
            bids = [b for b in bids if b.get("round_number") == round_number]
        return bids
    
    def get_counters(self, buyer: str = None, round_number: int = None) -> list:
        """Get counter-offer nodes, optionally filtered."""
        counters = [n for n in self.nodes if n.get("node_type") == "counter"]
        if buyer:
            counters = [c for c in counters if c.get("buyer") == buyer]
        if round_number is not None:
            counters = [c for c in counters if c.get("round_number") == round_number]
        return counters
    
    def get_accepts(self) -> list:
        """Get all acceptance nodes."""
        return [n for n in self.nodes if n.get("node_type") == "accept"]
    
    def add_bid(self, node) -> None:
        """Add a bid node from buyer."""
        self.nodes.append(asdict(node))
        self.execution_log.append({
            "action": "add_bid",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by,
            "round": node.round_number
        })
    
    def add_counter(self, node) -> None:
        """Add a counter-offer node from seller."""
        self.nodes.append(asdict(node))
        self.execution_log.append({
            "action": "add_counter",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by,
            "round": node.round_number
        })
    
    def add_accept(self, node) -> None:
        """Add an acceptance node."""
        self.nodes.append(asdict(node))
        self.execution_log.append({
            "action": "add_accept",
            "node_id": node.node_id,
            "contributed_by": node.contributed_by,
            "round": node.round_number
        })
    
    def get_current_round(self) -> int:
        """Get the current negotiation round based on graph state."""
        max_round = 0
        for node in self.nodes:
            if "round_number" in node:
                max_round = max(max_round, node["round_number"])
        return max_round
    
    def save(self, path: Path) -> None:
        """Save graph to file."""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "SupplyChainGraph":
        """Load graph from file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        graph = cls()
        graph.nodes = data.get("nodes", [])
        graph.edges = data.get("edges", [])
        graph.execution_log = data.get("execution_log", [])
        return graph
