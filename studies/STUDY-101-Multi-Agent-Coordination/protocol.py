"""
Minimal LLM-to-Graph Protocol

Two LLMs communicate through a shared graph:
1. Read the graph
2. Add nodes/edges to contribute
3. Pass turn to the other LLM

Rules:
- Append-only (no deletion)
- Weights can be adjusted
- Structure accumulates
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

# Try to load .env file if it exists
def load_env():
    """Load environment variables from .env file if it exists."""
    env_paths = [
        Path(__file__).parent.parent / ".env",  # repo root
        Path(__file__).parent / ".env",          # lab folder
        Path.home() / ".env"                     # home directory
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value and key not in os.environ:
                            os.environ[key] = value
            break

load_env()

# Import graph infrastructure from EGS
from egs import EGS
from egs.models import Node, Edge, NodeType


@dataclass
class Turn:
    """Record of one LLM's turn."""
    llm_name: str
    model: str
    nodes_added: List[str]
    edges_added: List[Tuple[str, str, str]]
    raw_response: str


SYSTEM_PROMPT = """You are {llm_name}, participating in a collaborative task with another LLM.

You communicate through a shared graph. The graph has:
- Nodes: entities with id, type, and data
- Edges: relationships between nodes with relation type and weight (0.0-1.0)

Node types: CONCEPT, PATTERN, BEHAVIOR, TASK, DECISION
Edge relations: REQUIRES, SUPPORTS, CONFLICTS_WITH, LEADS_TO, OWNED_BY

YOUR TASK: {task}

CURRENT GRAPH STATE:
{graph_context}

INSTRUCTIONS:
1. Read the graph to understand what exists
2. Add nodes and/or edges to contribute to the task
3. Reference existing nodes when creating edges
4. Use weights to indicate importance (0.9 = critical, 0.5 = moderate, 0.2 = minor)

Respond with JSON only:
{{
    "reasoning": "What you observe and why you're adding what you're adding",
    "nodes": [
        {{"id": "node-id", "type": "CONCEPT|PATTERN|BEHAVIOR|TASK|DECISION", "data": {{"description": "..."}}}},
        ...
    ],
    "edges": [
        {{"from_id": "...", "to_id": "...", "relation": "...", "weight": 0.8}},
        ...
    ]
}}

Add at least 1 node or edge. Build on what exists. Be concise.
"""


def graph_to_context(graph: EGS) -> str:
    """Convert graph to readable context for LLM."""
    lines = []
    
    # EGS.nodes is a Dict, EGS.edges is a List
    nodes = list(graph.nodes.values())
    edges = graph.edges  # Already a list
    
    if not nodes:
        return "Graph is empty. You are starting fresh."
    
    lines.append(f"NODES ({len(nodes)}):")
    for node in nodes:
        node_type = node.type.value if hasattr(node.type, 'value') else str(node.type)
        desc = node.data.get('description', 'No description')
        created_by = node.metadata.get('created_by', 'unknown')
        lines.append(f"  - {node.id} [{node_type}] by {created_by}: {desc}")
    
    lines.append(f"\nEDGES ({len(edges)}):")
    for edge in edges:
        lines.append(f"  - {edge.from_id} --[{edge.relation} w:{edge.weight}]--> {edge.to_id}")
    
    return "\n".join(lines)


def parse_response(response_text: str) -> Dict[str, Any]:
    """Parse LLM response to extract nodes and edges."""
    # Try to extract JSON from response
    try:
        # Handle markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        return {"error": str(e), "raw": response_text, "nodes": [], "edges": []}


def apply_modifications(graph: EGS, parsed: Dict, llm_name: str) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    """Apply parsed modifications to graph. Returns lists of added nodes and edges."""
    nodes_added = []
    edges_added = []
    
    # Add nodes
    for node_data in parsed.get("nodes", []):
        node_id = node_data.get("id")
        if not node_id:
            continue
        
        # Skip if node already exists
        if graph.get_node(node_id):
            continue
        
        node_type_str = node_data.get("type", "CONCEPT")
        try:
            node_type = NodeType(node_type_str)
        except ValueError:
            node_type = NodeType.CONCEPT
        
        data = node_data.get("data", {})
        metadata = {"created_by": llm_name}
        
        node = Node(id=node_id, type=node_type, data=data, metadata=metadata)
        graph.add_node(node)
        nodes_added.append(node_id)
    
    # Add edges
    for edge_data in parsed.get("edges", []):
        from_id = edge_data.get("from_id")
        to_id = edge_data.get("to_id")
        relation = edge_data.get("relation", "RELATES_TO")
        weight = edge_data.get("weight", 0.7)
        
        if not from_id or not to_id:
            continue
        
        # Skip if nodes don't exist
        if not graph.get_node(from_id) or not graph.get_node(to_id):
            continue
        
        # Check if edge already exists (edges is a list)
        edge_exists = any(
            e.from_id == from_id and e.to_id == to_id and e.relation == relation
            for e in graph.edges
        )
        if edge_exists:
            continue
        
        metadata = {"created_by": llm_name}
        edge = Edge(from_id=from_id, to_id=to_id, relation=relation, weight=weight, metadata=metadata)
        graph.add_edge(edge)
        edges_added.append((from_id, to_id, relation))
    
    return nodes_added, edges_added


def llm_turn(
    llm_name: str,
    model: str,
    graph: EGS,
    task: str,
    client: Optional[Any] = None
) -> Turn:
    """
    Execute one LLM's turn: read graph, add contributions, return modified graph.
    """
    if client is None:
        if Anthropic is None:
            raise RuntimeError("Anthropic library not installed")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        client = Anthropic(api_key=api_key)
    
    # Build prompt
    graph_context = graph_to_context(graph)
    prompt = SYSTEM_PROMPT.format(
        llm_name=llm_name,
        task=task,
        graph_context=graph_context
    )
    
    # Call LLM
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = response.content[0].text
    
    # Parse and apply
    parsed = parse_response(response_text)
    nodes_added, edges_added = apply_modifications(graph, parsed, llm_name)
    
    return Turn(
        llm_name=llm_name,
        model=model,
        nodes_added=nodes_added,
        edges_added=edges_added,
        raw_response=response_text
    )


def run_conversation(
    task: str,
    llm_a_name: str = "Alpha",
    llm_a_model: str = "claude-haiku-4-5-20251001",
    llm_b_name: str = "Beta",
    llm_b_model: str = "claude-haiku-4-5-20251001",
    turns: int = 3,
    verbose: bool = True
) -> Tuple[EGS, List[Turn]]:
    """
    Run a full conversation between two LLMs.
    
    Args:
        task: The collaborative task
        llm_a_name: Name for first LLM
        llm_a_model: Model for first LLM
        llm_b_name: Name for second LLM
        llm_b_model: Model for second LLM
        turns: Number of turns per LLM
        verbose: Print progress
    
    Returns:
        (final_graph, list_of_turns)
    """
    graph = EGS()
    turn_history = []
    
    # Initialize client once
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)
    
    for i in range(turns):
        # LLM-A's turn
        if verbose:
            print(f"\n--- Turn {i+1}: {llm_a_name} ---")
        
        turn_a = llm_turn(llm_a_name, llm_a_model, graph, task, client)
        turn_history.append(turn_a)
        
        if verbose:
            print(f"Added {len(turn_a.nodes_added)} nodes, {len(turn_a.edges_added)} edges")
        
        # LLM-B's turn
        if verbose:
            print(f"\n--- Turn {i+1}: {llm_b_name} ---")
        
        turn_b = llm_turn(llm_b_name, llm_b_model, graph, task, client)
        turn_history.append(turn_b)
        
        if verbose:
            print(f"Added {len(turn_b.nodes_added)} nodes, {len(turn_b.edges_added)} edges")
    
    return graph, turn_history
