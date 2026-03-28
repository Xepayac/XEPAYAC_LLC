"""EGS Full Pipeline — All Four Patent Claims in One Execution.

1. Topological execution (Claims 1-3)
2. Self-modification (Claim 5)
3. Multi-agent coordination (Claim 4)
4. Provenance tracking (Claims 1-3)

AGPL-3.0 | Patent Pending (app 19/575,491)
"""
from datetime import datetime, timezone
from egs import (
    EGS, Node, NodeType, Edge, EdgeMetadata, NodeMetadata,
    GraphExecutor, TransformRegistry, TransformResult,
    Agent, ProvenanceGraph, ProvenanceEntry,
)
from egs.transform import default_registry


def meta(who: str = "setup") -> NodeMetadata:
    return NodeMetadata(created_by=who, created_at=datetime.now(timezone.utc))


def edge_meta(who: str = "setup") -> EdgeMetadata:
    return EdgeMetadata(created_by=who, created_at=datetime.now(timezone.utc))


def main():
    # --- Setup: ProvenanceGraph wrapping an EGS ---
    graph = EGS()
    pg = ProvenanceGraph(graph)

    # --- CLAIM 4: Multi-agent coordination ---
    # Two agents with different type permissions on the same provenance graph
    buyer = Agent("buyer", pg, [NodeType.OPERAND, NodeType.CONCEPT])
    seller = Agent("seller", pg, [NodeType.OPERAND, NodeType.RESULT])

    # Buyer creates offers (OPERAND nodes)
    buyer.add_node(Node(
        id="offer-1",
        type=NodeType.OPERAND,
        data={"label": "initial_offer", "value": 100},
        metadata=meta("buyer"),
    ))
    buyer.add_node(Node(
        id="offer-2",
        type=NodeType.OPERAND,
        data={"label": "revised_offer", "value": 90},
        metadata=meta("buyer"),
    ))

    # Seller creates counters (OPERAND nodes — shared channel)
    seller.add_node(Node(
        id="counter-1",
        type=NodeType.OPERAND,
        data={"label": "counter_offer", "value": 110},
        metadata=meta("seller"),
    ))

    print("=" * 60)
    print("MULTI-AGENT COORDINATION (Claim 4)")
    print("=" * 60)
    print(f"  Buyer sees:  {sorted(buyer.visible_nodes().keys())}")
    print(f"  Seller sees: {sorted(seller.visible_nodes().keys())}")
    print(f"  Both share OPERAND channel — buyer and seller")
    print(f"    can see each other's OPERAND nodes")

    # --- Build execution subgraph ---
    # OPERATION node: compute average of all offers
    node_count_before = len(pg.nodes)

    pg.add_node(Node(
        id="avg-calc",
        type=NodeType.OPERATION,
        data={"operation": "aggregate", "method": "avg"},
        metadata=meta("pipeline"),
    ))

    # TRANSFORM node: summarize all inputs
    pg.add_node(Node(
        id="summarizer",
        type=NodeType.TRANSFORM,
        data={"transform_fn": "summarize"},
        metadata=meta("pipeline"),
    ))

    # RESULT node: final output
    pg.add_node(Node(
        id="deal-result",
        type=NodeType.RESULT,
        data={"operation": "identity"},
        metadata=meta("pipeline"),
    ))

    # Wire FEEDS edges: offers/counters -> avg-calc and summarizer
    for offer_id in ["offer-1", "offer-2", "counter-1"]:
        pg.add_edge(Edge(
            source_id=offer_id,
            target_id="avg-calc",
            relation="FEEDS",
            metadata=edge_meta("pipeline"),
        ))
        pg.add_edge(Edge(
            source_id=offer_id,
            target_id="summarizer",
            relation="FEEDS",
            metadata=edge_meta("pipeline"),
        ))

    # avg-calc -> deal-result
    pg.add_edge(Edge(
        source_id="avg-calc",
        target_id="deal-result",
        relation="FEEDS",
        metadata=edge_meta("pipeline"),
    ))

    # --- CLAIMS 1-3: Topological execution ---
    executor = GraphExecutor(pg, transforms=default_registry)
    trace = executor.execute()

    print()
    print("=" * 60)
    print("TOPOLOGICAL EXECUTION (Claims 1-3)")
    print("=" * 60)
    for step in trace.steps:
        print(f"  Step {step.order}: {step.node_id} ({step.node_type})")
        if step.inputs:
            print(f"    inputs: {step.inputs}")
        print(f"    output: {step.output}")
    print(f"  Final result: {trace.result}")
    print(f"  Success: {trace.success}")

    # --- CLAIM 5: Self-modification ---
    node_count_after = len(pg.nodes)

    print()
    print("=" * 60)
    print("SELF-MODIFICATION (Claim 5)")
    print("=" * 60)
    print(f"  Nodes BEFORE execution: {node_count_before}")
    print(f"  Nodes AFTER execution:  {node_count_after}")
    summary = pg.get_node("summary")
    if summary:
        print(f"  New summary node created by transform:")
        print(f"    id:         {summary.id}")
        print(f"    type:       {summary.type.value}")
        print(f"    count:      {summary.data['count']}")
        print(f"    sum:        {summary.data['sum']}")
        print(f"    avg:        {summary.data['avg']}")
        print(f"    min:        {summary.data['min']}")
        print(f"    max:        {summary.data['max']}")
        print(f"    created_by: {summary.metadata.created_by}")

    # --- CLAIMS 1-3: Provenance tracking ---
    print()
    print("=" * 60)
    print("PROVENANCE (Claims 1-3)")
    print("=" * 60)
    print("  Full audit trail:")
    for entry in pg.history():
        print(
            f"    [{entry.sequence:2d}] {entry.operation:12s} "
            f"by {entry.agent_id:15s} "
            f"target={entry.target_id}"
        )
    print()
    chain_valid = pg.verify()
    print(f"  Chain integrity: {'VALID' if chain_valid else 'BROKEN'}")
    print(f"  Ledger size: {pg.ledger_size()} entries")
    print()
    print("  Node creators:")
    for node_id in sorted(pg.nodes.keys()):
        creator = pg.who_created(node_id)
        print(f"    {node_id}: {creator}")


if __name__ == "__main__":
    main()
