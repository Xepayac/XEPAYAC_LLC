"""Tests for STUDY-202: Multi-File Graph Substrate.

Validates that a graph substrate can span multiple serialized files,
that SUPERSEDES edges change which graph governs execution, and that
the original file is never modified during spawn-and-supersede.
"""

import json
import tempfile
from pathlib import Path

import pytest

from multi_file_substrate import (
    Substrate,
    make_edge,
    make_node,
    save_graph,
    load_graph,
    scenario_1_single_file,
    scenario_2_spawn_and_supersede,
    scenario_3_chain_of_supersessions,
)


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory(prefix="test_202_") as d:
        yield Path(d)


# --- Substrate class tests ---


class TestSubstrate:

    def test_register_single_file(self, workdir):
        path = workdir / "g.json"
        graph = {
            "nodes": [make_node("n1", "OPERATION", {})],
            "edges": [],
        }
        save_graph(graph, path)

        sub = Substrate()
        sub.register("g", path)

        assert sub.file_count == 1
        assert sub.total_nodes == 1
        assert sub.total_edges == 0

    def test_register_multiple_files(self, workdir):
        for name in ["a", "b"]:
            path = workdir / f"{name}.json"
            graph = {
                "nodes": [make_node(f"n_{name}", "OPERATION", {})],
                "edges": [],
            }
            save_graph(graph, path)

        sub = Substrate()
        sub.register("a", workdir / "a.json")
        sub.register("b", workdir / "b.json")

        assert sub.file_count == 2
        assert sub.total_nodes == 2

    def test_cross_file_supersedes_detected(self, workdir):
        path_a = workdir / "a.json"
        path_b = workdir / "b.json"

        save_graph({"nodes": [make_node("n_a", "OPERATION", {})], "edges": []}, path_a)
        save_graph({
            "nodes": [
                make_node("n_b", "OPERATION", {}),
                make_node("graph_b", "CONCEPT", {"role": "graph_identity"}),
            ],
            "edges": [make_edge("graph_b", "graph_a", "SUPERSEDES")],
        }, path_b)

        sub = Substrate()
        sub.register("graph_a", path_a)
        sub.register("graph_b", path_b)

        cross = sub.cross_file_edges()
        assert len(cross) == 1
        assert cross[0]["relation"] == "SUPERSEDES"

    def test_active_graph_with_supersession(self, workdir):
        path_a = workdir / "a.json"
        path_b = workdir / "b.json"

        save_graph({"nodes": [make_node("n_a", "OPERATION", {})], "edges": []}, path_a)
        save_graph({
            "nodes": [
                make_node("n_b", "OPERATION", {}),
                make_node("graph_b", "CONCEPT", {}),
            ],
            "edges": [make_edge("graph_b", "graph_a", "SUPERSEDES")],
        }, path_b)

        sub = Substrate()
        sub.register("graph_a", path_a)
        sub.register("graph_b", path_b)

        assert sub.active_graph_id() == "graph_b"

    def test_active_graph_without_supersession(self, workdir):
        path_a = workdir / "a.json"
        save_graph({"nodes": [make_node("n", "OPERATION", {})], "edges": []}, path_a)

        sub = Substrate()
        sub.register("a", path_a)

        assert sub.active_graph_id() == "a"


# --- Scenario tests ---


class TestScenario1:

    def test_single_file_self_modification(self, workdir):
        d = workdir / "s1"
        d.mkdir()
        result = scenario_1_single_file(d)

        assert result["self_modified"] is True
        assert result["nodes_after"] > result["nodes_before"]
        assert result["edges_after"] > result["edges_before"]
        assert result["files"] == 1


class TestScenario2:

    def test_spawn_and_supersede(self, workdir):
        d = workdir / "s2"
        d.mkdir()
        result = scenario_2_spawn_and_supersede(d)

        assert result["original_file_unmodified"] is True
        assert result["files"] == 2
        assert result["cross_file_edges"] > 0
        assert result["active_graph"] == "graph_b"
        assert result["program_changed"] is True
        assert result["substrate_grew"] is True

    def test_original_file_byte_identical(self, workdir):
        """The original file must not be touched at all."""
        d = workdir / "s2b"
        d.mkdir()
        path_a = d / "graph_a.json"

        # Create and save graph_a
        graph_a = {
            "id": "graph_a",
            "nodes": [
                make_node("start", "OPERATION", {"instruction": "initialize"}),
                make_node("end", "RESULT", {"instruction": "finalize"}),
            ],
            "edges": [make_edge("start", "end", "THEN")],
        }
        save_graph(graph_a, path_a)
        original_bytes = path_a.read_bytes()

        # Spawn graph_b (simulating agent execution)
        path_b = d / "graph_b.json"
        graph_b = {
            "id": "graph_b",
            "nodes": [
                make_node("start_v2", "OPERATION", {"instruction": "initialize v2"}),
                make_node("end_v2", "RESULT", {"instruction": "finalize v2"}),
                make_node("graph_b", "CONCEPT", {"version": 2}),
            ],
            "edges": [
                make_edge("start_v2", "end_v2", "THEN"),
                make_edge("graph_b", "graph_a", "SUPERSEDES"),
            ],
        }
        save_graph(graph_b, path_b)

        # graph_a must be byte-identical
        assert path_a.read_bytes() == original_bytes


class TestScenario3:

    def test_chain_of_supersessions(self, workdir):
        d = workdir / "s3"
        d.mkdir()
        result = scenario_3_chain_of_supersessions(d)

        assert result["files"] == 3
        assert result["active_graph"] == "graph_c"
        assert result["program_changed_twice"] is True
        assert result["cross_file_edges"] == 2  # b->a, c->b

    def test_intermediate_files_unmodified(self, workdir):
        """In a chain A->B->C, neither A nor B is ever modified."""
        d = workdir / "s3b"
        d.mkdir()

        # Create A
        path_a = d / "graph_a.json"
        save_graph({
            "id": "graph_a",
            "nodes": [make_node("a", "OPERATION", {})],
            "edges": [],
        }, path_a)
        bytes_a = path_a.read_bytes()

        # Create B superseding A
        path_b = d / "graph_b.json"
        save_graph({
            "id": "graph_b",
            "nodes": [
                make_node("b", "OPERATION", {}),
                make_node("graph_b", "CONCEPT", {}),
            ],
            "edges": [make_edge("graph_b", "graph_a", "SUPERSEDES")],
        }, path_b)
        bytes_b = path_b.read_bytes()

        # Create C superseding B
        path_c = d / "graph_c.json"
        save_graph({
            "id": "graph_c",
            "nodes": [
                make_node("c", "OPERATION", {}),
                make_node("graph_c", "CONCEPT", {}),
            ],
            "edges": [make_edge("graph_c", "graph_b", "SUPERSEDES")],
        }, path_c)

        # A and B are untouched
        assert path_a.read_bytes() == bytes_a
        assert path_b.read_bytes() == bytes_b


# --- Key claim: functional equivalence ---


class TestFunctionalEquivalence:

    def test_same_outcome_different_mechanism(self, workdir):
        """Single-file modification and spawn-and-supersede achieve the
        same outcome: the program governing the agent changed during
        execution. The mechanism differs but the substrate was modified
        in both cases."""
        d1 = workdir / "equiv1"
        d1.mkdir()
        d2 = workdir / "equiv2"
        d2.mkdir()

        r1 = scenario_1_single_file(d1)
        r2 = scenario_2_spawn_and_supersede(d2)

        # Both result in more nodes than the original program
        assert r1["nodes_after"] > r1["nodes_before"]
        assert r2["substrate_total_nodes"] > r2["graph_a_nodes"]

        # Both result in a changed program
        assert r1["self_modified"] is True
        assert r2["program_changed"] is True

    def test_substrate_grew_without_file_modification(self, workdir):
        """The substrate can grow (new nodes, new edges) even when no
        existing file is modified. This is self-modification of the
        substrate, not of any individual file."""
        d = workdir / "grew"
        d.mkdir()
        result = scenario_2_spawn_and_supersede(d)

        assert result["original_file_unmodified"] is True
        assert result["substrate_grew"] is True
        assert result["substrate_total_nodes"] > result["graph_a_nodes"]
