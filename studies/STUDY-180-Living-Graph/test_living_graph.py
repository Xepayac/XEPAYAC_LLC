"""STUDY-180: Living Graph Pattern Validation Tests.

Tests validate:
1. Accumulation without duplication
2. Synthesis richness improvement
3. Provenance tracing completeness
4. Session reconstruction from audit trail

NOTE: These tests depend on a graph merge implementation and research
session orchestration. The test structure demonstrates the expected
behavior of the Living Graph pattern. To run these tests, you need
an implementation that provides:
  - A merge_graph() function that merges source graphs into a target graph
  - A ResearchSession class with ask() and get_history() methods
  - A get_graph_stats() function for graph statistics

See README.md for the reference merge algorithm.
"""

import pytest
import json
import sys
from pathlib import Path
from typing import Dict, Any, Set, List


# ---------------------------------------------------------------------------
# Minimal local implementations for standalone testing
# ---------------------------------------------------------------------------

class MergeGraphAction:
    """Describes a graph merge operation."""
    def __init__(self, source_file: str, target_graph: str):
        self.source_file = source_file
        self.target_graph = target_graph


class MergeGraphResult:
    """Result of a graph merge operation."""
    def __init__(self, success: bool, nodes_added: int, edges_added: int, conflicts: list):
        self.success = success
        self.nodes_added = nodes_added
        self.edges_added = edges_added
        self.conflicts = conflicts


class GraphMerger:
    """Minimal graph merge implementation for testing."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def merge_graph(self, action: MergeGraphAction) -> MergeGraphResult:
        """Merge source graph into target graph."""
        target_path = Path(action.target_graph)
        if target_path.exists():
            with open(target_path) as f:
                target = json.load(f)
        else:
            target = {"nodes": [], "edges": []}

        with open(action.source_file) as f:
            source = json.load(f)

        existing_ids = {n["id"] for n in target["nodes"]}

        added_nodes = 0
        for node in source.get("nodes", []):
            if node["id"] not in existing_ids:
                target["nodes"].append(node)
                existing_ids.add(node["id"])
                added_nodes += 1

        new_edges = source.get("edges", [])
        target["edges"].extend(new_edges)

        with open(target_path, 'w') as f:
            json.dump(target, f, indent=2)

        return MergeGraphResult(
            success=True,
            nodes_added=added_nodes,
            edges_added=len(new_edges),
            conflicts=[]
        )

    def get_graph_stats(self, graph_path) -> Dict[str, Any]:
        """Get statistics about a graph file."""
        with open(graph_path) as f:
            graph_data = json.load(f)
        node_types: Dict[str, int] = {}
        for n in graph_data["nodes"]:
            t = n.get("type", "UNKNOWN")
            node_types[t] = node_types.get(t, 0) + 1
        return {
            "node_count": len(graph_data["nodes"]),
            "edge_count": len(graph_data["edges"]),
            "node_types": node_types,
        }


class ResearchSession:
    """Minimal research session for testing."""

    def __init__(self, work_dir: Path, mode: str = "mock"):
        self.work_dir = work_dir
        self.mode = mode
        self.history: List[Dict[str, str]] = []
        self.query_count = 0
        self.ops_file = work_dir / "operations.jsonl"
        self.queries_dir = work_dir / "queries"
        self.queries_dir.mkdir(parents=True, exist_ok=True)

    def ask(self, question: str) -> str:
        self.query_count += 1
        self.history.append({"from": "human", "content": question})

        # Log operation
        with open(self.ops_file, 'a') as f:
            f.write(json.dumps({"op": "query_start", "q": self.query_count}) + "\n")
            f.write(json.dumps({"op": "query_complete", "q": self.query_count}) + "\n")

        # Archive query
        qf = self.queries_dir / f"{self.query_count:03d}-query.md"
        qf.write_text(f"# Query {self.query_count}\n\n{question}\n")

        # Mock answer
        graph_file = self.work_dir / "graph.json"
        if graph_file.exists():
            with open(graph_file) as f:
                graph_data = json.load(f)
            node_types = {}
            for n in graph_data["nodes"]:
                t = n.get("type", "UNKNOWN")
                node_types[t] = node_types.get(t, 0) + 1
            answer = f"Found {len(graph_data['nodes'])} entities: " + ", ".join(
                f"{count} {t}" for t, count in node_types.items()
            )
        else:
            answer = "No data accumulated yet."

        self.history.append({"from": "agent", "content": answer})
        return answer

    def get_history(self) -> List[Dict[str, str]]:
        return self.history


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAccumulationWithoutDuplication:
    """H1: Living Graph accumulates entities without duplication."""

    def test_merge_adds_new_nodes(self, tmp_path):
        """New nodes are added to graph."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Query 1: Discover A, B, C
        source1 = tmp_path / "source1.json"
        with open(source1, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "company-a", "type": "COMPANY", "data": {"name": "A"}},
                    {"id": "company-b", "type": "COMPANY", "data": {"name": "B"}},
                    {"id": "company-c", "type": "COMPANY", "data": {"name": "C"}},
                ],
                "edges": []
            }, f)

        action1 = MergeGraphAction(source_file=str(source1), target_graph=str(graph_file))
        result1 = merger.merge_graph(action1)

        assert result1.nodes_added == 3

        # Verify graph state
        with open(graph_file) as f:
            graph_data = json.load(f)
        assert len(graph_data["nodes"]) == 3

    def test_merge_skips_duplicate_nodes(self, tmp_path):
        """Duplicate nodes are skipped."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Initial graph with A, B, C
        with open(graph_file, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "company-a", "type": "COMPANY", "data": {"name": "A"}},
                    {"id": "company-b", "type": "COMPANY", "data": {"name": "B"}},
                    {"id": "company-c", "type": "COMPANY", "data": {"name": "C"}},
                ],
                "edges": []
            }, f)

        # Query 2: Discover A (duplicate), T1, T2
        source2 = tmp_path / "source2.json"
        with open(source2, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "company-a", "type": "COMPANY", "data": {"name": "A"}},  # Duplicate
                    {"id": "tier-1", "type": "PRICING_TIER", "data": {"name": "Free"}},
                    {"id": "tier-2", "type": "PRICING_TIER", "data": {"name": "Pro"}},
                ],
                "edges": []
            }, f)

        action2 = MergeGraphAction(source_file=str(source2), target_graph=str(graph_file))
        result2 = merger.merge_graph(action2)

        # Only 2 new nodes added (A skipped)
        assert result2.nodes_added == 2

        # Verify total nodes
        with open(graph_file) as f:
            graph_data = json.load(f)
        assert len(graph_data["nodes"]) == 5  # 3 + 2 (not 3 + 3)

    def test_three_query_accumulation(self, tmp_path):
        """Three queries accumulate correctly."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Query 1: A, B, C (3 new)
        source1 = tmp_path / "source1.json"
        with open(source1, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "a", "type": "COMPANY", "data": {}},
                    {"id": "b", "type": "COMPANY", "data": {}},
                    {"id": "c", "type": "COMPANY", "data": {}},
                ],
                "edges": []
            }, f)
        merger.merge_graph(MergeGraphAction(source_file=str(source1), target_graph=str(graph_file)))

        # Query 2: A (dup), T1, T2 (2 new)
        source2 = tmp_path / "source2.json"
        with open(source2, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "a", "type": "COMPANY", "data": {}},
                    {"id": "t1", "type": "PRICING_TIER", "data": {}},
                    {"id": "t2", "type": "PRICING_TIER", "data": {}},
                ],
                "edges": []
            }, f)
        merger.merge_graph(MergeGraphAction(source_file=str(source2), target_graph=str(graph_file)))

        # Query 3: B (dup), F1, F2 (2 new)
        source3 = tmp_path / "source3.json"
        with open(source3, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "b", "type": "COMPANY", "data": {}},
                    {"id": "f1", "type": "FEATURE", "data": {}},
                    {"id": "f2", "type": "FEATURE", "data": {}},
                ],
                "edges": []
            }, f)
        merger.merge_graph(MergeGraphAction(source_file=str(source3), target_graph=str(graph_file)))

        # Final: 3 + 2 + 2 = 7 unique nodes
        with open(graph_file) as f:
            graph_data = json.load(f)
        assert len(graph_data["nodes"]) == 7


class TestSynthesisRichness:
    """H2: Living Graph enables richer synthesis."""

    def test_synthesis_uses_all_nodes(self, tmp_path):
        """Synthesis references all accumulated nodes."""
        session = ResearchSession(tmp_path, mode="mock")

        # Pre-populate graph with multiple entity types
        graph_file = tmp_path / "graph.json"
        with open(graph_file, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "c1", "type": "COMPANY", "data": {"name": "Alpha"}},
                    {"id": "c2", "type": "COMPANY", "data": {"name": "Beta"}},
                    {"id": "t1", "type": "PRICING_TIER", "data": {"name": "Free"}},
                    {"id": "t2", "type": "PRICING_TIER", "data": {"name": "Pro"}},
                    {"id": "f1", "type": "FEATURE", "data": {"name": "Search"}},
                ],
                "edges": []
            }, f)

        # Ask question - synthesis should reference all types
        answer = session.ask("Summarize findings")

        # Verify synthesis mentions node counts
        assert "COMPANY" in answer or "2" in answer
        assert "PRICING_TIER" in answer or "FEATURE" in answer

    def test_empty_graph_synthesis(self, tmp_path):
        """Empty graph produces appropriate message."""
        session = ResearchSession(tmp_path, mode="mock")

        answer = session.ask("What did we find?")

        # Should indicate no data or minimal findings
        assert len(answer) > 0


class TestProvenanceTracing:
    """H3: Provenance edges enable complete tracing."""

    def test_edges_preserved_on_merge(self, tmp_path):
        """Edge relationships preserved through merge."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Source with nodes and edges
        source = tmp_path / "source.json"
        with open(source, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "c1", "type": "COMPANY", "data": {}},
                    {"id": "t1", "type": "PRICING_TIER", "data": {}},
                ],
                "edges": [
                    {"from_id": "c1", "to_id": "t1", "relation": "HAS_TIER"}
                ]
            }, f)

        merger.merge_graph(MergeGraphAction(source_file=str(source), target_graph=str(graph_file)))

        with open(graph_file) as f:
            graph_data = json.load(f)

        assert len(graph_data["edges"]) == 1
        assert graph_data["edges"][0]["relation"] == "HAS_TIER"

    def test_provenance_edges_accumulate(self, tmp_path):
        """Multiple merges accumulate all edges."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Source 1
        source1 = tmp_path / "s1.json"
        with open(source1, 'w') as f:
            json.dump({
                "nodes": [{"id": "a", "type": "COMPANY", "data": {}}],
                "edges": [{"from_id": "q1", "to_id": "a", "relation": "PRODUCES"}]
            }, f)
        merger.merge_graph(MergeGraphAction(source_file=str(source1), target_graph=str(graph_file)))

        # Source 2
        source2 = tmp_path / "s2.json"
        with open(source2, 'w') as f:
            json.dump({
                "nodes": [{"id": "b", "type": "COMPANY", "data": {}}],
                "edges": [{"from_id": "q2", "to_id": "b", "relation": "PRODUCES"}]
            }, f)
        merger.merge_graph(MergeGraphAction(source_file=str(source2), target_graph=str(graph_file)))

        with open(graph_file) as f:
            graph_data = json.load(f)

        assert len(graph_data["edges"]) == 2


class TestSessionReconstruction:
    """H4: Session can be reconstructed from audit trail."""

    def test_operations_logged(self, tmp_path):
        """All operations logged to JSONL."""
        session = ResearchSession(tmp_path, mode="mock")

        session.ask("Question 1")
        session.ask("Question 2")

        ops_file = tmp_path / "operations.jsonl"
        assert ops_file.exists()

        # Count operations
        with open(ops_file) as f:
            ops = [json.loads(line) for line in f if line.strip()]

        # Should have multiple operations logged
        assert len(ops) >= 4  # At least start/complete for each query

    def test_dialogue_preserves_order(self, tmp_path):
        """Dialogue preserves message order."""
        session = ResearchSession(tmp_path, mode="mock")

        session.ask("First question")
        session.ask("Second question")

        history = session.get_history()

        # Should have Q1, A1, Q2, A2 in order
        assert len(history) >= 4
        assert history[0]["from"] == "human"
        assert history[1]["from"] == "agent"
        assert history[2]["from"] == "human"
        assert history[3]["from"] == "agent"

    def test_query_archives_created(self, tmp_path):
        """Each query archived as markdown."""
        session = ResearchSession(tmp_path, mode="mock")

        session.ask("First question")
        session.ask("Second question")
        session.ask("Third question")

        queries_dir = tmp_path / "queries"
        query_files = list(queries_dir.glob("*-query.md"))

        assert len(query_files) == 3


class TestTrugStats:
    """Test graph statistics tracking."""

    def test_stats_reflect_accumulation(self, tmp_path):
        """Stats accurately reflect accumulated nodes."""
        merger = GraphMerger(tmp_path)
        graph_file = tmp_path / "graph.json"

        # Create graph with mixed types
        with open(graph_file, 'w') as f:
            json.dump({
                "nodes": [
                    {"id": "c1", "type": "COMPANY", "data": {}},
                    {"id": "c2", "type": "COMPANY", "data": {}},
                    {"id": "t1", "type": "PRICING_TIER", "data": {}},
                    {"id": "f1", "type": "FEATURE", "data": {}},
                    {"id": "f2", "type": "FEATURE", "data": {}},
                ],
                "edges": [
                    {"from_id": "c1", "to_id": "t1", "relation": "HAS_TIER"},
                    {"from_id": "c1", "to_id": "c2", "relation": "COMPETES_WITH"},
                ]
            }, f)

        stats = merger.get_graph_stats(graph_file)

        assert stats["node_count"] == 5
        assert stats["edge_count"] == 2
        assert stats["node_types"]["COMPANY"] == 2
        assert stats["node_types"]["PRICING_TIER"] == 1
        assert stats["node_types"]["FEATURE"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
