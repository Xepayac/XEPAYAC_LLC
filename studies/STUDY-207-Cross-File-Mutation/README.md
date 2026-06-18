# STUDY-207: Multi-File Substrate Mutation — Cross-File Graph Self-Modification

<!-- AGPL-3.0 | Patent Pending (app 19/575,491) -->

## Classification: PUBLIC

## Abstract

A graph substrate spanning multiple serialized files can self-modify *across*
its own file boundaries: an agent executing in one file reaches into another
file and modifies that file's contents in place — creating a result node,
superseding a node, redirecting an edge — with both files committed atomically
or both rolled back. This study demonstrates that capability over a connected
set of **3 files** with **9 passing tests** (9/9/0): cross-file node creation,
cross-file supersede with a traversable v1→v2 audit trail, all-or-nothing
rollback under an injected mid-transaction failure, substrate discovery by
edge-following with no manifest, immediate structural liveness of a cross-file
mutation, multi-agent provenance, referential-integrity (dangling-edge)
rejection, and optimistic-versioning conflict detection. The conclusion: the
self-modification mechanism survives the single-file → multi-file embodiment
shift — the substrate is a *substrate*, not a file format.

## Study ID
**STUDY-207**

## Title
Multi-File Substrate Mutation — Cross-File Graph Self-Modification

## Purpose
Demonstrate that a graph substrate distributed across multiple serialized files
can modify *another* file's contents in place during execution, with atomic
all-or-nothing cross-file transaction semantics, while preserving the
substrate's defining properties (structural liveness; the boundary is
discovered by following edges, not declared by a manifest). This is the
capability that distinguishes a *substrate* from a *file format*.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable
  Graph-Based Computation with Self-Modification by Autonomous Agents
  - **Claim 1**: cross-file in-place mutation is self-modification of the
    substrate where the substrate is a connected multi-file structure.
  - **Claim 2**: cross-file references (`file_path:node_id`) are resolved during
    traversal; a mutation written across a boundary is immediately live.
  - **Claim 8**: the connected file set, discovered by following cross-file
    edges, constitutes a single self-modifying executable graph.

This study supplies reduction-to-practice *direction* for CIP Broadening #1
(Multi-File Substrate) — the cross-file in-place-mutation flavor. It is
reduction-to-practice, not §112 enablement, and it does not clear intervening
art; those remain the patent specification's and counsel's work.

## Hypothesis

An agent can modify a *second* serialized file during execution of a *first*,
with both files committing atomically or neither, while the substrate boundary
remains discoverable by edge-following alone — falsifiable by any test in which
a file is left partially written, a dangling cross-file edge survives, or
discovery requires a manifest.

## Study Date
**June 2026**

## Method

1. **Baseline substrate**: three connected fixture files — `file_a.json` (a
   PIPELINE of chained STAGE nodes), `file_b.json` (a results graph holding a
   REPORT v1), and `file_c.json` (an archive reached only by following a
   cross-file edge).
2. **Atomic transaction**: a write-ahead-log primitive (`transaction.py`) logs
   the intended writes, temp-writes every file, atomically renames each into
   place, and marks the log complete — rolling back on any failure.
3. **Cross-file mutation**: `cross_file_mutation.py` creates a RESULT node in
   the target file and a FEEDS edge in the source file, supersedes a node in
   the target file in place (with a SUPERSEDED_BY lineage edge), and guards
   referential integrity.
4. **Discovery**: `discovery.py` follows cross-file edges transitively from an
   entry file to find the connected set, with no manifest.
5. **Measure**: 9 tests (one per scenario/matrix row) plus a runnable demo that
   captures `results.json`.

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, results, analysis |
| substrate.py | Multi-file substrate manager + node/edge helpers + cross-file references |
| transaction.py | Atomic cross-file transaction (write-ahead log + deterministic failure injection) |
| cross_file_mutation.py | `mutate_cross_file` / `add_cross_file_edge` / `supersede_cross_file` |
| discovery.py | `discover_substrate` (boundary by edge-following) + cross-file traversal |
| fixtures/file_a.json, file_b.json, file_c.json | The shared baseline substrate (3 connected files) |
| test_cross_file_mutation.py | 9-test pytest suite (one per matrix row) |
| demo_cross_file.py | Runnable demonstration; writes results.json |
| results.json | Machine-readable results (9/9/0 + per-scenario metrics) |

## Key Mechanism

A cross-file reference has the form `file_path:node_id`. A mutation is applied
to in-memory copies of the affected files, then committed through an atomic
cross-file transaction: a write-ahead log records every intended write, all
targets are temp-written, each temp is atomically renamed into place, and the
log is marked complete. If any step fails before the renames begin, the temps
are discarded and every original is byte-identical; a two-phase commit
(prepare-all, then commit-all) is the equivalent alternative for the local case.
Because a committed mutation is just the new file content on disk, it is
immediately live for the next traversal across the file boundary — there is no
parse, compile, or deploy step. The substrate boundary is never declared: it is
discovered by following cross-file edges, so the connected file set *is* the
program.

## Results

### Test 1: Cross-file node creation (Scenario 1)
Execution of STAGE-3 in `file_a.json` spawns a RESULT node into `file_b.json`
and writes a FEEDS edge in `file_a.json` pointing at it.
**Result**: `file_b.json` grows to 3 nodes; exactly 1 FEEDS cross-file edge; the
edge type is FEEDS, not a generic edge.

### Test 2: Cross-file edge
A cross-file edge connects a node in File A to a node in File B; both files
reflect it and the reference resolves.
**Result**: edge present in File A; target resolves in File B; no dangling edge.

### Test 3: Cross-file supersede (Scenario 2 — the STUDY-202 delta)
REPORT v1 in `file_b.json` is marked stale, REPORT v2 is created active, a
SUPERSEDED_BY lineage edge is added, and File A's reference is redirected to v2.
**Result**: File B's on-disk content changes; the v1→v2 audit trail is
traversable; File A now resolves to v2.

### Test 4: Atomic rollback (Scenario 3)
A failure injected between the File-B temp write and commit aborts the
transaction.
**Result**: both files byte-identical; no partial node; no dangling edge.

### Test 5: Substrate discovery (Scenario 4)
Discovery from `file_a.json` follows cross-file edges transitively (A→B→C).
**Result**: 3 files discovered; `manifest_used: false`.

### Test 6: Traversal after mutation
After the Scenario-1 mutation, traversal from STAGE-3 crosses the file boundary.
**Result**: the new RESULT node in File B is reachable — the mutation is
immediately live.

### Test 7: Multi-agent cross-file provenance (Scenario 5)
Agent 1 writes a node into Agent 2's file.
**Result**: the created node's provenance names `agent_one`.

### Test 8: Dangling-edge prevention
A cross-file edge to a non-existent target is attempted.
**Result**: rejected; no dangling edge introduced.

### Test 9: Concurrent cross-file writers
Two writers read File B at the same version and both attempt to supersede the
same node.
**Result**: exactly one succeeds, one conflicts (optimistic versioning).

All **9 tests** pass (9/9/0); the demo exits 0 and writes `results.json` across
**3 files**.

## Conclusions

### Core Finding

**A multi-file graph substrate can modify one of its files in place during
execution of another, with atomic all-or-nothing cross-file commit — the
fourth flavor of self-modification (cross-file in-place mutation), demonstrated
end to end.**

### Properties Demonstrated

1. **Cross-file in-place mutation**: File B's contents change (node created,
   node superseded, edge redirected) driven by execution in File A.
2. **Cross-file atomicity**: both files commit or neither does; an injected
   mid-transaction failure leaves both byte-identical.
3. **Structural liveness**: a cross-file mutation is immediately live for
   traversal — no parse/compile/deploy step.
4. **Topology-as-program**: the substrate boundary is discovered by following
   cross-file edges (no manifest, no registry).
5. **Referential integrity & concurrency safety**: dangling cross-file edges are
   refused; concurrent writers resolve one-succeed-one-conflict.

### The four flavors of self-modification

1. **Additive** — append to the same file (STUDY-109).
2. **CRUD** — add/remove/modify in the same file (STUDY-109).
3. **Spawn-and-supersede** — write a *new* file whose cross-file SUPERSEDES edge
   changes which graph governs, leaving every pre-existing file byte-for-byte
   unmodified (STUDY-202).
4. **Cross-file in-place mutation** — reach into another file and modify it,
   with cross-file atomic transaction (**this study, STUDY-207**).

The load-bearing delta over **STUDY-202**: STUDY-202 keeps File A read-only and
adds a new file; **STUDY-207 modifies File B in place** — Test 3 fails unless the
target file's content actually changes. The two are different claims (topology
vs in-place mutation); STUDY-207 does not supersede or modify STUDY-202.

### Scope (honest)

This study is **demonstrated for 2-3 files**. The write-ahead-log primitive is
N-file-shaped (the log lists every intended write), but unbounded-N atomicity is
**not** proven here — that full-scope-enablement burden belongs to the patent
specification, not to this reduction-to-practice.

## Related Studies
- **STUDY-202** (Multi-File Substrate): spawn-and-supersede topology; File A read-only. The sibling this study contrasts with (in-place vs additive).
- **STUDY-140** (Supersede Operation): the single-file supersede primitive (atomic replace + edge-redirect + rollback + optimistic versioning) that cross-file supersede lifts across a file boundary.
- **STUDY-109** (Graph Mutation): the single-file copy-then-restore rollback pattern the cross-file transaction generalizes.
