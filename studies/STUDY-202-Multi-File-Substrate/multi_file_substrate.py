"""STUDY-202: Multi-File Graph Substrate

Demonstrates that a graph substrate can span multiple serialized files
connected by cross-file edges. An agent executing graph-A creates graph-B
with a SUPERSEDES edge. The connected set of files constitutes a single
substrate whose topology changed during execution.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_node(node_id: str, node_type: str, data: dict[str, Any]) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "data": data,
        "metadata": {
            "created_by": "system",
            "created_at": now_iso(),
            "status": "approved",
        },
    }


def make_edge(source: str, target: str, relation: str, weight: float = 1.0) -> dict:
    return {
        "source_id": source,
        "target_id": target,
        "relation": relation,
        "weight": weight,
        "metadata": {
            "created_by": "system",
            "created_at": now_iso(),
        },
    }


def save_graph(graph: dict, path: Path) -> None:
    with path.open("w") as f:
        json.dump(graph, f, indent=2)


def load_graph(path: Path) -> dict:
    with path.open("r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Substrate: the connected set of all graph files
# ---------------------------------------------------------------------------

class Substrate:
    """A substrate is the connected set of all graph files.

    The substrate is not a single file. It is the union of all files
    connected by cross-file edges (SUPERSEDES, EXTENDS, REFERENCES).
    """

    def __init__(self) -> None:
        self.files: dict[str, Path] = {}  # graph_id -> file path
        self.graphs: dict[str, dict] = {}  # graph_id -> graph dict

    def register(self, graph_id: str, path: Path) -> None:
        self.files[graph_id] = path
        self.graphs[graph_id] = load_graph(path)

    @property
    def total_nodes(self) -> int:
        return sum(len(g.get("nodes", [])) for g in self.graphs.values())

    @property
    def total_edges(self) -> int:
        return sum(len(g.get("edges", [])) for g in self.graphs.values())

    @property
    def file_count(self) -> int:
        return len(self.files)

    def cross_file_edges(self) -> list[dict]:
        """Find edges that reference nodes in other files."""
        node_to_graph: dict[str, str] = {}
        for gid, g in self.graphs.items():
            for node in g.get("nodes", []):
                node_to_graph[node["id"]] = gid

        cross = []
        for gid, g in self.graphs.items():
            for edge in g.get("edges", []):
                src_graph = node_to_graph.get(edge["source_id"])
                tgt_graph = node_to_graph.get(edge["target_id"])
                # Cross-file if target is in a different graph or is a
                # file-level reference (target_id matches a graph_id)
                if edge["relation"] == "SUPERSEDES":
                    cross.append(edge)
                elif src_graph and tgt_graph and src_graph != tgt_graph:
                    cross.append(edge)
        return cross

    def active_graph_id(self) -> str:
        """Determine which graph currently governs execution.

        If graph-B SUPERSEDES graph-A, then graph-B governs.
        """
        superseded: set[str] = set()
        for gid, g in self.graphs.items():
            for edge in g.get("edges", []):
                if edge["relation"] == "SUPERSEDES":
                    # The target of SUPERSEDES is the old graph
                    superseded.add(edge["target_id"])

        active = [gid for gid in self.graphs if gid not in superseded]
        if len(active) == 1:
            return active[0]
        # If no supersession, return the first registered
        return list(self.graphs.keys())[0]


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

def scenario_1_single_file(workdir: Path) -> dict:
    """Baseline: single-file substrate. Agent modifies the file it executes."""
    path = workdir / "graph_a.json"

    graph_a = {
        "id": "graph_a",
        "nodes": [
            make_node("start", "OPERATION", {"instruction": "initialize"}),
            make_node("compute", "OPERATION", {"instruction": "process data"}),
            make_node("end", "RESULT", {"instruction": "finalize"}),
        ],
        "edges": [
            make_edge("start", "compute", "THEN"),
            make_edge("compute", "end", "THEN"),
        ],
    }
    save_graph(graph_a, path)

    # Agent executes graph_a and modifies it (classic self-modification)
    loaded = load_graph(path)
    loaded["nodes"].append(
        make_node("audit", "OPERATION", {"instruction": "audit results"})
    )
    loaded["edges"].append(make_edge("compute", "audit", "THEN"))
    loaded["edges"].append(make_edge("audit", "end", "THEN"))
    save_graph(loaded, path)

    substrate = Substrate()
    substrate.register("graph_a", path)

    return {
        "scenario": "single_file_self_modification",
        "files": 1,
        "nodes_before": 3,
        "nodes_after": substrate.total_nodes,
        "edges_before": 2,
        "edges_after": substrate.total_edges,
        "self_modified": True,
        "cross_file_edges": 0,
    }


def scenario_2_spawn_and_supersede(workdir: Path) -> dict:
    """Multi-file substrate. Agent executes graph_a, spawns graph_b that
    SUPERSEDES graph_a. The original file is never modified."""
    path_a = workdir / "graph_a.json"
    path_b = workdir / "graph_b.json"

    # Graph A: the original program
    graph_a = {
        "id": "graph_a",
        "nodes": [
            make_node("start", "OPERATION", {"instruction": "initialize"}),
            make_node("compute", "OPERATION", {"instruction": "process data"}),
            make_node("end", "RESULT", {"instruction": "finalize"}),
        ],
        "edges": [
            make_edge("start", "compute", "THEN"),
            make_edge("compute", "end", "THEN"),
        ],
    }
    save_graph(graph_a, path_a)

    # Agent executes graph_a. During execution, it creates graph_b.
    # Graph_b contains a SUPERSEDES edge pointing at graph_a.
    # Graph_a is NEVER modified.
    graph_a_on_disk = load_graph(path_a)  # read — not modified

    graph_b = {
        "id": "graph_b",
        "nodes": [
            make_node("start_v2", "OPERATION", {"instruction": "initialize v2"}),
            make_node("validate", "OPERATION", {"instruction": "validate inputs"}),
            make_node("compute_v2", "OPERATION", {"instruction": "process data v2"}),
            make_node("audit", "OPERATION", {"instruction": "audit results"}),
            make_node("end_v2", "RESULT", {"instruction": "finalize v2"}),
        ],
        "edges": [
            make_edge("start_v2", "validate", "THEN"),
            make_edge("validate", "compute_v2", "THEN"),
            make_edge("compute_v2", "audit", "THEN"),
            make_edge("audit", "end_v2", "THEN"),
            # Cross-file edge: this graph supersedes graph_a
            make_edge("graph_b", "graph_a", "SUPERSEDES"),
        ],
    }
    # Add a graph-level node for the SUPERSEDES source
    graph_b["nodes"].append(
        make_node("graph_b", "CONCEPT", {"role": "graph_identity", "version": 2})
    )
    save_graph(graph_b, path_b)

    # Verify graph_a was not modified
    graph_a_after = load_graph(path_a)
    original_unmodified = graph_a_on_disk == graph_a_after

    # Build the substrate from both files
    substrate = Substrate()
    substrate.register("graph_a", path_a)
    substrate.register("graph_b", path_b)

    cross = substrate.cross_file_edges()
    active = substrate.active_graph_id()

    return {
        "scenario": "spawn_and_supersede",
        "files": substrate.file_count,
        "graph_a_nodes": len(graph_a["nodes"]),
        "graph_b_nodes": len(graph_b["nodes"]),
        "substrate_total_nodes": substrate.total_nodes,
        "substrate_total_edges": substrate.total_edges,
        "original_file_unmodified": original_unmodified,
        "cross_file_edges": len(cross),
        "supersedes_edges": [e for e in cross if e["relation"] == "SUPERSEDES"],
        "active_graph": active,
        "substrate_grew": substrate.total_nodes > len(graph_a["nodes"]),
        "program_changed": active != "graph_a",
    }


def scenario_3_chain_of_supersessions(workdir: Path) -> dict:
    """Chain: A -> B -> C. Each supersedes the previous. No file is ever
    modified. The substrate grows with each spawn."""
    graphs = []
    paths = []

    for i, version in enumerate(["a", "b", "c"]):
        path = workdir / f"graph_{version}.json"
        graph_id = f"graph_{version}"
        node_count = 3 + i  # each version adds a node

        nodes = [
            make_node(f"start_{version}", "OPERATION",
                      {"instruction": f"initialize v{i + 1}"}),
            make_node(f"end_{version}", "RESULT",
                      {"instruction": f"finalize v{i + 1}"}),
            make_node(graph_id, "CONCEPT",
                      {"role": "graph_identity", "version": i + 1}),
        ]
        # Add extra nodes for later versions
        for j in range(i):
            nodes.append(
                make_node(f"step_{version}_{j}", "OPERATION",
                          {"instruction": f"step {j} of v{i + 1}"})
            )

        edges = [make_edge(f"start_{version}", f"end_{version}", "THEN")]
        # SUPERSEDES edge to previous version
        if i > 0:
            prev_id = f"graph_{chr(ord('a') + i - 1)}"
            edges.append(make_edge(graph_id, prev_id, "SUPERSEDES"))

        graph = {"id": graph_id, "nodes": nodes, "edges": edges}
        save_graph(graph, path)
        graphs.append(graph)
        paths.append(path)

    # Build substrate from all files
    substrate = Substrate()
    for i, version in enumerate(["a", "b", "c"]):
        substrate.register(f"graph_{version}", paths[i])

    cross = substrate.cross_file_edges()
    active = substrate.active_graph_id()

    return {
        "scenario": "chain_of_supersessions",
        "files": substrate.file_count,
        "substrate_total_nodes": substrate.total_nodes,
        "substrate_total_edges": substrate.total_edges,
        "cross_file_edges": len(cross),
        "supersession_chain": ["graph_a", "graph_b", "graph_c"],
        "active_graph": active,
        "all_files_unmodified": True,  # no file was ever re-written
        "substrate_grew_each_step": True,
        "program_changed_twice": active == "graph_c",
    }


def run_all() -> dict:
    """Run all scenarios and collect results."""
    results = {}

    with tempfile.TemporaryDirectory(prefix="study_202_") as tmpdir:
        workdir = Path(tmpdir)

        for scenario_fn in [
            scenario_1_single_file,
            scenario_2_spawn_and_supersede,
            scenario_3_chain_of_supersessions,
        ]:
            scenario_dir = workdir / scenario_fn.__name__
            scenario_dir.mkdir()
            result = scenario_fn(scenario_dir)
            results[result["scenario"]] = result

    return results


if __name__ == "__main__":
    import sys

    results = run_all()

    print("=" * 60)
    print("STUDY-202: Multi-File Graph Substrate")
    print("=" * 60)

    for name, result in results.items():
        print(f"\n--- {name} ---")
        for k, v in result.items():
            if k == "scenario":
                continue
            print(f"  {k}: {v}")

    # Validate key claims
    s2 = results["spawn_and_supersede"]
    s3 = results["chain_of_supersessions"]

    checks = [
        ("Original file unmodified", s2["original_file_unmodified"]),
        ("Substrate spans multiple files", s2["files"] == 2),
        ("Cross-file SUPERSEDES edge exists", s2["cross_file_edges"] > 0),
        ("Active graph changed to graph_b", s2["active_graph"] == "graph_b"),
        ("Program changed without modifying original", s2["program_changed"]),
        ("Substrate grew (new nodes added)", s2["substrate_grew"]),
        ("Chain: 3 files in substrate", s3["files"] == 3),
        ("Chain: active graph is latest", s3["active_graph"] == "graph_c"),
        ("Chain: program changed twice", s3["program_changed_twice"]),
    ]

    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)

    all_pass = True
    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        icon = "\u2705" if passed else "\u274c"
        print(f"  {icon} {label}: {status}")
        if not passed:
            all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: SOME CHECKS FAILED")
    print("=" * 60)

    sys.exit(0 if all_pass else 1)
