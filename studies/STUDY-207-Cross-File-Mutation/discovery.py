"""STUDY-207: substrate discovery + cross-file traversal.

The substrate boundary is *discovered*, never declared: starting from any entry
file, follow its cross-file edges transitively (A -> B -> C). There is no
manifest, no registry — the connected file set IS the program (topology-as-
program). A mutation written across a file boundary is immediately live for the
next traversal, with no parse / compile / deploy step (structural liveness).

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

from pathlib import Path
from typing import Optional

from substrate import Substrate, split_ref


def discover_substrate(
    entry_file: Path,
    base_dir: Optional[Path] = None,
) -> dict:
    """Discover the connected file set by following cross-file edges from
    ``entry_file``, transitively. No manifest is read.

    Returns a dict with the discovered filenames, count, ``manifest_used:
    False``, and the loaded ``Substrate``.
    """
    entry = Path(entry_file)
    base = Path(base_dir) if base_dir else entry.parent

    discovered: dict[str, Path] = {}
    frontier: list[str] = [entry.name]
    sub = Substrate(base)

    while frontier:
        fname = frontier.pop(0)
        if fname in discovered:
            continue
        path = base / fname
        if not path.exists():
            continue
        discovered[fname] = path
        sub.register(path)
        for neighbour in sub.neighbour_files(fname):
            if neighbour not in discovered and neighbour not in frontier:
                frontier.append(neighbour)

    return {
        "entry_file": entry.name,
        "files_discovered": sorted(discovered),
        "count": len(discovered),
        "manifest_used": False,
        "substrate": sub,
    }


def reachable(
    substrate: Substrate,
    start_file: str,
    start_node_id: str,
) -> set[str]:
    """All node references (``file:node``) reachable from a start node by
    following edges, including across file boundaries. Used to prove that a
    cross-file mutation is immediately live for traversal.
    """
    start_ref = f"{start_file}:{start_node_id}"
    seen: set[str] = set()
    frontier: list[str] = [start_ref]

    while frontier:
        current = frontier.pop(0)
        if current in seen:
            continue
        seen.add(current)
        cur_file, cur_node = split_ref(current)
        cur_file = cur_file or start_file
        if cur_file not in substrate.graphs:
            continue
        for edge in substrate.edges_in(cur_file):
            # match edges whose source is the current node (within this file)
            if edge.get("source_id") != cur_node:
                continue
            tgt = edge["target_id"]
            tfile, tnode = split_ref(tgt)
            tfile = tfile or cur_file
            ref_str = f"{tfile}:{tnode}"
            if ref_str not in seen:
                frontier.append(ref_str)
    return seen
