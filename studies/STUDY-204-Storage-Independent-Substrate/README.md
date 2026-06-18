# STUDY-204: Storage-Independent Graph Substrate — Database and Mediated Access

## Classification: PUBLIC

## Abstract

This study demonstrates that an executable graph substrate governs computation
regardless of where or how it is stored or accessed. One shared baseline graph is
executed under four conditions — **A** a serialized file, **B** a relational
persistent store (nodes and edges as table rows, read by query), **C** a mediation
layer through which the agent reaches the graph without any storage handle, and
**D** both at once (a relational store under the mediation layer). Across all four,
the final graph state is **structurally identical**, and the three substrate
properties — topology-as-program, result-driven edge selection, and in-traversal
self-modification with no compile/deploy boundary — are preserved unchanged. The
embodiment (storage format and access path) moved across maximum architectural
distance; the mechanism did not. Storage independence is **demonstrated by
functional equivalence**, not asserted.

## Study ID
**STUDY-204**

## Title
Storage-Independent Graph Substrate — Database and Mediated Access

## Purpose

Establish, by a dated and executable reduction to practice, that the graph
substrate's computational model is independent of its storage medium and access
path. The study proves that moving the graph off a serialized file — into a
relational store, behind a mediation interface, or both — leaves the substrate
mechanism unchanged, foreclosing the "it is no longer a file" design-around.

## Patent References

- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based
  Computation with Self-Modification by Autonomous Agents.
  - **Claims 1–3** (independent — system / method / medium): a computational agent
    traverses a graph substrate, obtains an execution result at a node, selects an
    outgoing edge by the result, and writes a topology modification that persists and
    affects subsequent traversal. This study exercises that full cycle under each
    storage/access embodiment.
  - **Claim 5**: result-driven selection of an outgoing edge — exercised at the
    `branch` node (the result selects the edge).
  - **Claim 8**: modifications add nodes and edges that persist and affect subsequent
    traversals — exercised by the live `injected` node and its edges.
  - **Claim 10**: continued traversal over the modified substrate.

> **Priority discipline (read with the claim mapping below).** This study feeds a
> **CIP-only, CIP-dated** storage-agnostic claim. It does **not** broaden the
> parent-date independents (Claims 1–3), which keep "the serialized file." See
> *Honesty and Claim Mapping*.

## Hypothesis

A graph substrate comprising nodes with executable content and directional edges
with condition properties determines the sequence of operations, routes by execution
result, and supports self-modification during execution, regardless of whether:

1. the substrate is held in a relational persistent store rather than a serialized
   file; and
2. the agent modifies the substrate through a mediation layer rather than by direct
   storage access.

**Falsifiable form:** every non-file condition (B, C, D) produces a final graph state
structurally equal to the serialized-file baseline (A), with the three mechanism
properties preserved in each.

## Study Date
**June 2026**

## Method

One shared baseline graph (`graph_initial.json`) is executed by a single traversal
agent that is **imported unchanged** by every condition (`baseline_file.traverse`).
Only the *store* differs between conditions, so any divergence would be a difference
of storage, never of mechanism.

The baseline's `grow` node has **no outgoing edge**: during execution it
self-modifies the substrate, creating the `injected` node and the edges that continue
the path. The agent then traverses the topology it just created — demonstrating
structural liveness (the modification is live on the very next step, with no compile
or redeploy).

### Condition A — Serialized File Baseline
The substrate is a JSON file on disk. The agent reads by parsing the file and writes
the self-modification in place. This is the EGS-979 base case and the comparison
baseline.

### Condition B — Relational Persistent Store
The substrate is held as rows: a node table and an edge table. The agent reads the
current node and its outgoing edges by issuing **SQL `SELECT`** queries and writes the
self-modification via **`INSERT` / `UPDATE` / `DELETE`**. The baseline is loaded into
the store once at setup; every traversal-time access is a query. The embedded
relational store is the standard library's `sqlite3` module — zero external services.

### Condition C — Mediated Graph Access
A mediation layer (`GraphMediator`) exposes the graph operations `read_node`,
`get_outgoing_edges`, `write_node`, `add_edge`, `remove_node`. The agent is handed
**only** the mediator; the backing store is private and unreachable. The agent holds
no storage handle of any kind.

### Condition D — Combined (Store + Mediation)
The relational store of Condition B, placed **under** the mediation layer of
Condition C — maximum architectural distance from the file baseline. D is
compositional: it imports and stacks the B store and the C mediator.

### Measured (7 metrics per condition)
topology determination · result-dependent routing · self-modification · modification
persistence · functional equivalence to baseline · node-count delta · edge-count
delta.

## Files Included

| File | Purpose |
|------|---------|
| `graph_initial.json` | Shared baseline substrate (authored by STUDY-204; see Related Studies) |
| `baseline_file.py` | Condition A + the single shared agent, router, metrics, and stores |
| `persistent_store.py` | Condition B — relational store (rows; SQL read/write) |
| `mediated_access.py` | Condition C — `GraphMediator`; agent holds no storage handle |
| `combined_store_mediated.py` | Condition D — relational store under mediation (composes B∘C) |
| `test_equivalence.py` | Equivalence + conformance suite; generates `results.json` |
| `results.json` | Machine-readable results (generated by running the suite) |

## Key Mechanism

There is exactly **one** traversal agent. `traverse(store, ...)` reads the current
node, executes its content, then re-reads the node's outgoing edges and selects one by
evaluating each edge's condition against the execution result. The store is an
interface: a serialized file (A), relational rows (B), a mediation layer over an
in-memory medium (C), or a mediation layer over relational rows (D). Because the agent
is storage-agnostic and identical across conditions, equivalence of the four final
states isolates a single variable — the embodiment — and shows the mechanism invariant
under it.

The self-modification is the sharp end: a node that did not exist at start is created
mid-traversal and is then traversed. The new topology takes effect immediately, with
no parse/compile/deploy step between the write and its effect — under every storage
medium and access path alike.

## Results

All four conditions PASS; the suite reports 17/17 validation checks. Conditions B, C,
and D are each structurally equal to baseline A.

| Metric | A (file) | B (relational) | C (mediated) | D (both) |
|--------|:---:|:---:|:---:|:---:|
| Topology determination | Y | Y | Y | Y |
| Result-dependent routing | Y | Y | Y | Y |
| Self-modification | Y | Y | Y | Y |
| Modification persistence | Y | Y | Y | Y |
| Functional equivalence to A | baseline | Y | Y | Y |
| Node-count delta | +1 | +1 | +1 | +1 |
| Edge-count delta | +2 | +2 | +2 | +2 |

**Access-pattern evidence.** Condition B issued SQL queries and performed **zero**
graph-file parses during traversal. Conditions C and D report the agent held **no
storage handle**. Condition D's backing store served the traversal entirely via SQL.

**Traversal path (all conditions):** `start → branch → grow → injected → finalize`
(the `injected` node is created during execution, then traversed).

**Result:** changing the storage medium (B), interposing a mediation layer (C), or
both (D) does not change the computational outcome. The substrate is
storage-independent.

## Conclusions

### Core Finding
**An executable graph substrate governs computation independently of its storage
medium and access path: a relational store, a mediation layer, and their combination
each produce a final state structurally identical to the serialized-file baseline,
with topology-as-program, result-driven edge selection, and in-traversal
self-modification preserved unchanged.**

### Properties Demonstrated
1. **Storage independence**: file (A) ≡ relational rows (B) ≡ mediated (C) ≡ both (D).
2. **Access independence**: direct file I/O, SQL queries, and an opaque mediation
   interface all yield the same execution.
3. **Mechanism invariance**: the three substrate properties hold *during* each run,
   not merely at its end.

## Honesty and Claim Mapping

This section is load-bearing: it states what the study supplies, what it concedes, and
what it does **not** discharge, so the artifact is not read as banking more than it
proves.

### The "still a file" objection (access pattern, then mediation)
An embedded relational store backed by a single database file invites the objection
that it is *still a file*. The rebuttal stands on two grounds. **(1) Access pattern:**
in Condition B the agent reads **rows via SQL `SELECT`** and writes via
`INSERT`/`UPDATE`/`DELETE`; it **never parses the serialized JSON** graph at traversal
time — a fundamentally different access pattern from file I/O. **(2) Condition C**: the
**mediation** layer **removes** even that residual file-similarity entirely — the
agent is handed only an interface and holds **no storage handle**, file or otherwise.
Together, B and C close the objection on both the access-pattern and the
no-storage-handle grounds.

### Claim mapping (CIP date — not the parent date)
This study supplies a dated reduction to practice and the embodiment shape for a
**storage-agnostic** claim that takes the **CIP filing date**, because the application
as filed teaches the substrate only as "the serialized file." Under **split-priority
discipline**, the storage-agnostic breadth is filed as a separate, CIP-dated claim and
is **never** amended into the parent-date independents (Claims 1–3) or their
dependents (5, 8, 10), which keep "the serialized file." The base mechanism those
claims recite (traverse → result-driven edge → persisted self-mod → continued
traversal) is what this CIP claim extends to any persistent store.

### Reduction to practice, not §112 enablement
A built, run, and git-timestamped study establishes a **reduction-to-practice date**
and an embodiment shape. It does **not**, by itself, satisfy **§112(a)** written
description / enablement for the patent — authoring that enabling disclosure across the
full claimed genus is counsel's CIP work. This artifact is RTP evidence, **not** the
enabling disclosure.

### L1 concession; the distinction rests on L3 + L5
Demonstrating storage independence **concedes** the **L1 "graph-in-a-store" axis**: a
broad "graph in any persistent store" reading admits that merely holding graph data in
a store is not itself distinguishing, and collapses against general-purpose
workflow-orchestration systems that keep a serialized task-graph in a metadata
database, and against the graph-database class. The substrate's distinguishing weight
therefore rests on **L3 (traversal-is-execution — the topology *is* the program)** and
**L5 (in-traversal persisted self-modification, with no compile/deploy boundary)** —
**never** on "serialized-vs-not." This study is deliberately silent on storage-format
as a distinguisher precisely because it surrenders that axis.

### The graph-database prior-art class is counsel's CIP gate
A **graph database** is, definitionally, "a persistent store holding a graph of nodes
and edges," so a storage-agnostic claim walks straight into the largely **unsearched**
graph-database and graph-transformation prior-art class. That **prior-art sweep is
counsel's CIP gate**, **not** cleared by this study; this artifact establishes the
embodiment and RTP only.

### Coverage delta — the network-boundary (Gap-4) species is owed, not reduced here
The broadening's enabling disclosure has five items; this study supplies reduction to
practice for items **1–3** only: the storage-abstraction interface (Condition C), one
worked relational species (Condition B), and the mediation species (C, and B∘C in D).
It deliberately does **not** supply item 4 — the **network-boundary / Gap-4
distributed** species (store on one device, agent on another, traversal over a network
connection), the hardest part, where structural liveness must be shown to survive the
network/mediation boundary. That species is scoped out for self-containment and remains
**owed** — to a future **STUDY-204b** or to counsel's CIP authoring; it is **not
reduced to practice here**. Item 5 (definiteness lexicography for "persistent store")
is likewise counsel's work.

## Related Studies
- **STUDY-203** (Decomposed Agent Systems): co-owns the shared `graph_initial.json`
  baseline (ADR-003). Per the **B1 contingency**, STUDY-203 was unbuilt when this study
  landed, so **STUDY-204 authored the canonical baseline** (`baseline_authored_by:
  "STUDY-204"` in `results.json`); STUDY-203 will conform to it **byte-identically**
  when built. Until both exist, the cross-study equivalence check skips with this
  rationale; the authoring record is recorded so the combined-evidence claim is
  auditable.
- **STUDY-202** (Multi-File Substrate): the adjacent embodiment broadening (file →
  multi-file connected set); this study continues the chain to *any persistent store*.

## How to Run

```bash
cd studies/STUDY-204-Storage-Independent-Substrate
python baseline_file.py            # Condition A demo
python persistent_store.py         # Condition B demo
python mediated_access.py          # Condition C demo
python combined_store_mediated.py  # Condition D demo
python test_equivalence.py         # run all + regenerate results.json
pytest test_equivalence.py -v      # full conformance suite
```

**Requirements:** Python 3.10+ (standard library only — no external dependencies, no
network, no external services).

## Date Evidence

**Study Date:** June 2026
**Git History:** available in repository commit log; the merged-commit timestamp is the
reduction-to-practice date and must precede the CIP filing date.
**Patent Application:** 19/575,491 (Non-Provisional).
