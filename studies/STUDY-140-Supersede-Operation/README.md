# STUDY-140: Supersede Operation — Graph Self-Replacement During Execution

## Classification: PUBLIC

## Abstract

This study demonstrates the **supersede primitive**: a graph node spawns a replacement node during execution, the original is marked stale, every incoming edge redirects to the replacement, and a `SUPERSEDED_BY` lineage edge records the transition — as one atomic operation. Eight automated tests prove atomicity, edge redirection, chain traversability (A→B→C with the original id resolving to the current node), schema type safety, rollback to the exact pre-operation state on failure, append-only provenance, concurrent-conflict detection between two writers, and application of an LLM-authored supersede proposal supplied as a recorded structured JSON document. All 8 tests pass (see `results.json`). The supersede operation is the atomic unit of graph self-modification; this study places a working, reproducible demonstration of that primitive in the public evidence layer.

## Study ID
**STUDY-140**

## Title
Supersede Operation — Graph Self-Replacement During Execution

## Purpose

Demonstrate that:
1. A graph node can be **atomically replaced** during execution — replacement active, original stale, no observable both-active state
2. **Topology is preserved through replacement** — every incoming edge of the original redirects to the replacement
3. **Replacement chains remain auditable** — A→B→C stays traversable and the original id resolves to the current node
4. The operation is **safe**: schema-violating replacements are rejected with the graph unchanged, failures restore the pre-operation state, and concurrent supersede attempts on the same node are detected
5. An **LLM can direct the operation** through a validated, structured JSON proposal

This study states what the substrate can do, not how any production system implements it.

## Patent References
- **Patent Application 19/575,491**: System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
- **Claim 1**: System — self-modification by writing changes during execution
- **Claim 2**: Method — self-modification by writing changes during execution
- **Claim 8**: Modifications include adding new nodes and edges that persist and affect subsequent traversals

Related public studies: STUDY-109 (graph mutation + rollback), STUDY-111 (LLM-directed mutation), STUDY-202 (multi-file spawn-and-supersede). STUDY-140 isolates the supersede primitive itself — the single-graph atomic replacement those studies compose around.

## Hypothesis

**H1**: A node can be replaced during execution in one atomic operation: the replacement activates, the original goes stale, and all incoming edges redirect — with no observable intermediate state.

**H2**: Chained supersession preserves auditability: after A→B→C, the chain is traversable from A and A resolves to C as the current node.

**H3**: The operation is conditionally safe: type-violating replacements are rejected and commit-time failures roll back, leaving the graph byte-identical to its pre-operation state in both cases.

**H4**: Two writers superseding the same node concurrently are detected: the first commit wins, the second is rejected having applied nothing.

**H5**: A structured supersede proposal authored by an LLM can be validated and applied through the same atomic path as any other writer.

## Study Date
**June 2026**

## Method

1. **Build substrate**: construct a typed graph (schema: allowed types + per-type required properties) with one PROCESS node and three callers holding incoming edges to it (`graph.py`).
2. **Apply supersede**: replace the PROCESS node via the supersede operation (`supersede.py`) and assert the post-state: original stale, replacement active, edges redirected, lineage edge present.
3. **Chain**: supersede the replacement again; walk the chain and resolve the original id to the current node.
4. **Break it**: attempt a type-violating replacement, a commit-failing replacement (missing required property), and a stale-version concurrent write; assert each rejection leaves the graph unchanged (snapshot equality).
5. **LLM-direct it**: apply a recorded LLM-authored JSON proposal; assert validation, application, and rejection of malformed proposals.
6. **Measure**: run the 8-test suite via `python demo_supersede.py`; counts are written to `results.json` (`test_count`, `pass_count`).

Reproduce with: `python -m pytest -q` (suite only) or `python demo_supersede.py` (narrated scenarios + suite + results capture). Requires Python 3 + pytest; no other dependencies.

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, results, analysis |
| graph.py | Self-contained graph substrate: typed nodes, edges, schema, versioning, provenance |
| supersede.py | The supersede operation + LLM-proposal application |
| test_supersede.py | Automated test suite (8 tests) |
| demo_supersede.py | Narrated demonstration of the 4 scenarios + results capture |
| results.json | Machine-readable results (`test_count`, `pass_count`, scenarios) |

## Key Mechanism

A supersede call names an original node and supplies a replacement node. The operation validates preconditions (original exists and is active; replacement type allowed by schema), then commits the full transition — activate replacement, mark original stale, redirect every incoming edge, append the `SUPERSEDED_BY` lineage edge — as a single all-or-nothing step guarded by a state snapshot: any failure, including commit-time validation of the replacement's required properties, restores the exact pre-operation state. A monotonic graph version supports optimistic concurrency (writers declare the version they read; a stale version is rejected before anything applies), and an append-only provenance log records each committed operation, so the full replacement history is reconstructable after the fact.

The essential insight: *stale-not-deleted plus edge redirection* is what makes self-replacement both atomic and auditable — the graph's past states remain addressable through lineage edges while its active topology moves forward.

## Results

### Test Suite: 8/8 PASS

| # | Test | Verifies | Result |
|---|------|----------|--------|
| 1 | `test_simple_supersede` | Atomic replace: original stale, replacement active, never both active | PASS |
| 2 | `test_chain_supersede` | A→B→C traversable; current(A) = C | PASS |
| 3 | `test_edge_redirection` | 3 incoming edges → all 3 redirect to replacement | PASS |
| 4 | `test_type_safety` | Schema-violating replacement rejected; graph unchanged | PASS |
| 5 | `test_rollback` | Commit-time failure restores exact pre-operation state | PASS |
| 6 | `test_provenance` | One reconstructable record per operation, version-ordered | PASS |
| 7 | `test_concurrent_conflict` | Stale-version writer rejected; nothing applied | PASS |
| 8 | `test_llm_directed` | Recorded LLM JSON proposal validated + applied; malformed rejected | PASS |

**Result**: All five hypotheses confirmed. The supersede primitive — atomic graph self-replacement with preserved topology, auditability, safety, and LLM-directability — is demonstrated and reproducible from this directory alone.

---

*License: AGPL-3.0 (see repository LICENSE). Patent Pending (app 19/575,491).*
