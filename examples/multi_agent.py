"""SGS Multi-Agent Coordination Example: buyer/seller negotiation.

Two agents share a graph but have different type permissions.
OPERAND is the shared channel; CONCEPT and RESULT are private.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from datetime import datetime, timezone

from sgs import SGS, Agent, CoordinationSession
from sgs.models import Node, NodeMetadata, NodeType, Edge, EdgeMetadata


def make_meta() -> NodeMetadata:
    return NodeMetadata(created_by="setup", created_at=datetime.now(timezone.utc))


def main():
    # Shared graph
    graph = SGS()

    # Buyer sees OPERAND + CONCEPT
    buyer = Agent("buyer", graph, [NodeType.OPERAND, NodeType.CONCEPT])
    # Seller sees OPERAND + RESULT
    seller = Agent("seller", graph, [NodeType.OPERAND, NodeType.RESULT])

    session = CoordinationSession(graph)
    session.add_agent(buyer)
    session.add_agent(seller)

    # Step 1: Buyer creates an OPERAND offer
    buyer.add_node(Node(
        id="offer-1",
        type=NodeType.OPERAND,
        data={"label": "initial_offer", "price": 100},
        metadata=make_meta(),
    ))
    print("=== Step 1: Buyer posts offer (OPERAND, price=100) ===")
    print(f"  Buyer sees: {list(buyer.visible_nodes().keys())}")
    print(f"  Seller sees: {list(seller.visible_nodes().keys())}")

    # Step 2: Seller sees the offer (OPERAND is shared) and creates a RESULT counter
    seller_offer = seller.get_node("offer-1")
    print(f"\n=== Step 2: Seller reads offer ===")
    print(f"  Seller reads offer-1 price: {seller_offer.data['price']}")

    seller.add_node(Node(
        id="counter-1",
        type=NodeType.RESULT,
        data={"label": "counter_offer", "price": 120},
        metadata=make_meta(),
    ))
    print(f"  Seller posts counter (RESULT, price=120)")
    print(f"  Buyer sees counter-1: {buyer.get_node('counter-1')}")
    print(f"  Seller sees: {list(seller.visible_nodes().keys())}")

    # Step 3: Seller posts a revised offer via the shared channel (OPERAND)
    seller.add_node(Node(
        id="offer-2",
        type=NodeType.OPERAND,
        data={"label": "revised_offer", "price": 110},
        metadata=make_meta(),
    ))
    print(f"\n=== Step 3: Seller posts revised offer (OPERAND, price=110) ===")
    print(f"  Buyer sees: {list(buyer.visible_nodes().keys())}")
    print(f"  Seller sees: {list(seller.visible_nodes().keys())}")

    # Both can see all OPERAND nodes
    buyer_operands = buyer.find_nodes(node_type=NodeType.OPERAND)
    seller_operands = seller.find_nodes(node_type=NodeType.OPERAND)
    print(f"\n=== Final: OPERAND nodes visible to both ===")
    print(f"  Buyer OPERAND count: {len(buyer_operands)}")
    print(f"  Seller OPERAND count: {len(seller_operands)}")

    # Session summary
    print(f"\n=== Coordination Summary ===")
    print(f"  Nodes by creator: {session.summary()}")


if __name__ == "__main__":
    main()
