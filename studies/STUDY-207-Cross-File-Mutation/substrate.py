"""STUDY-207: Multi-File Substrate Mutation — substrate scaffolding.

A substrate is the connected set of serialized graph files. Unlike a single
file, the substrate boundary is discovered by *following cross-file edges*
(no manifest, no registry): the connected file set IS the program.

Cross-file references use the form ``<filename>:<node_id>`` (a ``file_reference``).
The supported cross-file edge types are FEEDS, SUPERSEDED_BY, CONTAINS, and
DEPENDS_ON. A mutation written into another file is immediately live for
subsequent traversal across the file boundary — there is no parse / compile /
deploy step (structural liveness).

This file demonstrates WHAT the substrate can do (the capability), not how any
production system implements it. The cross-file primitives are the single-file
primitives of STUDY-109 (mutation) / STUDY-140 (supersede) / STUDY-202
(multi-file substrate) lifted across a file boundary inside the cross-file
transaction (transaction.py); the embodiment shifts (one file -> many), the
mechanism does not.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Supported cross-file edge types (substrate invariant).
FEEDS = "FEEDS"
SUPERSEDED_BY = "SUPERSEDED_BY"
CONTAINS = "CONTAINS"
DEPENDS_ON = "DEPENDS_ON"
CROSS_FILE_RELATIONS = (FEEDS, SUPERSEDED_BY, CONTAINS, DEPENDS_ON)

ACTIVE = "active"
STALE = "stale"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_FILES = ("file_a.json", "file_b.json", "file_c.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_node(
    node_id: str,
    node_type: str,
    data: Optional[dict] = None,
    created_by: str = "system",
    status: str = ACTIVE,
) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "data": data or {},
        "metadata": {
            "created_by": created_by,
            "created_at": now_iso(),
            "status": status,
        },
    }


def make_edge(source_id: str, target_id: str, relation: str) -> dict:
    return {
        "source_id": source_id,
        "target_id": target_id,
        "relation": relation,
        "metadata": {"created_at": now_iso()},
    }


def ref(filename: str, node_id: str) -> str:
    """Build a cross-file reference of the form ``filename:node_id``."""
    return f"{filename}:{node_id}"


def split_ref(identifier: str) -> tuple[Optional[str], str]:
    """Split a possible ``file_reference``.

    Returns ``(filename, node_id)`` when ``identifier`` is a cross-file
    reference (``something.json:node``), else ``(None, identifier)``. A bare
    node id (no ``.json:`` boundary) resolves within the current file.
    """
    if ":" in identifier:
        head, tail = identifier.split(":", 1)
        if head.endswith(".json"):
            return head, tail
    return None, identifier


def save_graph(graph: dict, path: Path) -> None:
    with Path(path).open("w") as f:
        json.dump(graph, f, indent=2)


def load_graph(path: Path) -> dict:
    with Path(path).open("r") as f:
        return json.load(f)


def copy_fixtures(dest_dir: Path) -> dict[str, Path]:
    """Copy the three committed baseline fixtures into ``dest_dir``.

    Tests and the demo always run on copies — the committed ``fixtures/`` files
    are never mutated.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name in FIXTURE_FILES:
        dst = dest_dir / name
        shutil.copyfile(FIXTURES_DIR / name, dst)
        out[name] = dst
    return out


class Substrate:
    """The connected set of graph files, keyed by filename.

    The substrate is not a single file: it is the union of all files reachable
    by following cross-file edges. Cross-file references are resolved by
    ``filename:node_id``; the boundary is discovered, never declared.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir: Optional[Path] = Path(base_dir) if base_dir else None
        self.files: dict[str, Path] = {}   # filename -> path
        self.graphs: dict[str, dict] = {}  # filename -> graph dict

    # -- registration / reload -------------------------------------------------

    def register(self, path: Path) -> str:
        path = Path(path)
        fname = path.name
        self.files[fname] = path
        self.graphs[fname] = load_graph(path)
        if self.base_dir is None:
            self.base_dir = path.parent
        return fname

    def reload(self) -> None:
        for fname, path in self.files.items():
            self.graphs[fname] = load_graph(path)

    @classmethod
    def from_dir(cls, base_dir: Path, filenames=FIXTURE_FILES) -> "Substrate":
        base_dir = Path(base_dir)
        sub = cls(base_dir)
        for name in filenames:
            p = base_dir / name
            if p.exists():
                sub.register(p)
        return sub

    # -- counts ----------------------------------------------------------------

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_nodes(self) -> int:
        return sum(len(g.get("nodes", [])) for g in self.graphs.values())

    @property
    def total_edges(self) -> int:
        return sum(len(g.get("edges", [])) for g in self.graphs.values())

    # -- node / edge access ----------------------------------------------------

    def nodes_in(self, filename: str) -> list[dict]:
        return self.graphs[filename].get("nodes", [])

    def edges_in(self, filename: str) -> list[dict]:
        return self.graphs[filename].get("edges", [])

    def get_node(self, filename: str, node_id: str) -> Optional[dict]:
        for node in self.nodes_in(filename):
            if node["id"] == node_id:
                return node
        return None

    def resolve(self, identifier: str, current_file: str) -> Optional[dict]:
        """Resolve a (possibly cross-file) reference to its node dict."""
        fname, node_id = split_ref(identifier)
        fname = fname or current_file
        if fname not in self.graphs:
            return None
        return self.get_node(fname, node_id)

    def version_of(self, filename: str) -> int:
        return int(self.graphs[filename].get("version", 1))

    # -- cross-file edges ------------------------------------------------------

    def is_cross_file_edge(self, edge: dict, current_file: str) -> bool:
        fname, _ = split_ref(edge.get("target_id", ""))
        return fname is not None and fname != current_file

    def cross_file_edges(self) -> list[dict]:
        """All edges whose target references a node in a different file."""
        cross: list[dict] = []
        for fname, graph in self.graphs.items():
            for edge in graph.get("edges", []):
                if self.is_cross_file_edge(edge, fname):
                    cross.append(dict(edge, _file=fname))
        return cross

    def cross_file_edges_of_type(self, relation: str) -> list[dict]:
        return [e for e in self.cross_file_edges() if e["relation"] == relation]

    def neighbour_files(self, filename: str) -> set[str]:
        """Filenames directly referenced by ``filename``'s cross-file edges."""
        out: set[str] = set()
        for edge in self.edges_in(filename):
            for endpoint in (edge.get("source_id", ""), edge.get("target_id", "")):
                fname, _ = split_ref(endpoint)
                if fname is not None and fname != filename:
                    out.add(fname)
        return out

    # -- referential integrity -------------------------------------------------

    def dangling_cross_file_edges(self) -> list[dict]:
        """Cross-file edges whose target node does not exist (should be empty)."""
        dangling: list[dict] = []
        for edge in self.cross_file_edges():
            fname, node_id = split_ref(edge["target_id"])
            if fname not in self.graphs or self.get_node(fname, node_id) is None:
                dangling.append(edge)
        return dangling
