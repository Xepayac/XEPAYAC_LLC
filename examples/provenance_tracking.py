#!/usr/bin/env python3
"""EGS Provenance Tracking Example.

Demonstrates the ProvenanceGraph wrapper that logs every graph mutation
to a tamper-evident hash-chain ledger.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from datetime import datetime, timezone

from egs.graph import EGS
from egs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata
from egs.provenance import ProvenanceGraph


def main():
    # Create a ProvenanceGraph wrapping an EGS
    graph = EGS()
    pg = ProvenanceGraph(graph)

    now = datetime.now(timezone.utc)

    # Add OPERAND nodes from different agents
    nodes = [
        Node(
            id="sensor-temp",
            type=NodeType.OPERAND,
            data={"value": 72.5, "unit": "fahrenheit"},
            metadata=NodeMetadata(created_by="sensor-agent", created_at=now),
        ),
        Node(
            id="sensor-humidity",
            type=NodeType.OPERAND,
            data={"value": 45.0, "unit": "percent"},
            metadata=NodeMetadata(created_by="sensor-agent", created_at=now),
        ),
        Node(
            id="threshold",
            type=NodeType.OPERAND,
            data={"value": 80.0, "unit": "fahrenheit"},
            metadata=NodeMetadata(created_by="config-agent", created_at=now),
        ),
    ]

    for node in nodes:
        pg.add_node(node)
        print(f"Added node '{node.id}' by {node.metadata.created_by}")

    # Add FEEDS edges
    edge_meta = EdgeMetadata(created_by="pipeline-agent", created_at=now)
    pg.add_edge(Edge(
        source_id="sensor-temp",
        target_id="threshold",
        relation="FEEDS",
        metadata=edge_meta,
    ))
    pg.add_edge(Edge(
        source_id="sensor-humidity",
        target_id="threshold",
        relation="FEEDS",
        metadata=edge_meta,
    ))
    print("\nAdded 2 FEEDS edges")

    # Update a node
    pg.update_node("sensor-temp", {"value": 78.3}, agent_id="sensor-agent")
    print("Updated sensor-temp value to 78.3")

    # Remove a node
    pg.remove_node("sensor-humidity", agent_id="cleanup-agent")
    print("Removed sensor-humidity")

    # Print full provenance history
    print("\n--- Provenance History ---")
    for entry in pg.history():
        print(
            f"  [{entry.sequence}] {entry.operation:12s} "
            f"by {entry.agent_id:15s} "
            f"target={entry.target_id}"
        )

    # Verify chain integrity
    print(f"\nChain integrity: {'VALID' if pg.verify() else 'BROKEN'}")
    print(f"Ledger size: {pg.ledger_size()} entries")

    # Show who_created for each remaining node
    print("\n--- Node Creators ---")
    for node_id in pg.nodes:
        creator = pg.who_created(node_id)
        print(f"  {node_id}: created by {creator}")


if __name__ == "__main__":
    main()
