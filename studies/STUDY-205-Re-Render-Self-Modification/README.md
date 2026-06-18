# STUDY-205: Re-Render Self-Modification — Wholesale Re-Rendering vs In-Place Mutation

## Classification: PUBLIC

## Abstract

This study demonstrates that an executable graph substrate self-modifies during
execution regardless of **how** the modification is materialized into the persisted
serialization. One shared baseline graph is executed under four conditions — **A** an
in-place edit of the serialized file (the base case), **B** a wholesale re-render that
re-serializes the entire graph and replaces the file content, **C** a re-render emitted
as a new file with the active substrate switched to it (the prior file left intact, no
provenance link written), and **D** a hybrid that mixes in-place edits and re-renders
within a single traversal. Across all four, the final graph **topology is structurally
identical** (compared by a topological structural diff, never a byte hash), while the
on-disk serialized **representation diverges** — the bytes differ from the baseline at
equal topology. *Representation differs; topology does not.* Wholesale re-rendering is
therefore a materialization strategy for the same result-driven self-modification, not
an escape from it. The study is deliberately scoped as
**materialization-strategy-equivalence** and does **not** claim re-render preserves
structural-liveness (see *Honesty and Claim Mapping*).

## Study ID
**STUDY-205**

## Title
Re-Render Self-Modification — Wholesale Re-Rendering vs In-Place Mutation

## Purpose

Establish, by a dated and executable reduction to practice, that a graph substrate
evolving through execution exhibits the same result-driven self-modification whether the
change is written as an in-place edit or materialized by wholesale re-rendering of the
serialized representation. The study forecloses the "I re-render instead of mutating, so
there is no self-modification by writing changes to the file" design-around: the agent's
execution result still drives the modification, and the modified, persisted topology
still governs subsequent traversal.

## Patent References

- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based
  Computation with Self-Modification by Autonomous Agents.
  - **Claims 1–3** (independent — system / method / medium): a computational agent
    traverses a graph substrate, obtains an execution result at a node, selects an
    outgoing edge by the result, and writes a topology modification that persists and
    affects subsequent traversal. This study exercises that full cycle under each
    materialization strategy.
  - **Claim 8**: modifications add nodes and edges that persist and affect subsequent
    traversals — exercised by the live `audit` node and its two continuation edges in
    every condition.

> **Priority discipline (read with the claim mapping below).** This study feeds a
> **CIP-only, CIP-dated** claim. It does **not** broaden the parent-date independents
> (Claims 1–3), which keep "writing changes to the serialized file." Re-render language
> must never migrate into those parent-date claims. See *Honesty and Claim Mapping*.

## Hypothesis

A graph substrate comprising nodes with executable content and directional edges with
condition properties determines the sequence of operations, routes by execution result,
and self-modifies during execution, regardless of whether a result-driven modification
is materialized as:

1. an **in-place edit** to the serialized representation (the base case), or
2. a **wholesale re-render** — re-serializing the entire graph and replacing the prior
   representation (same file, or as a new file the active substrate switches to), or
3. a **hybrid** of the two within one traversal.

**Falsifiable form:** every re-render condition (B, C, D) produces a final graph topology
structurally equal to the in-place baseline (A) **while** its serialized bytes differ
from A's — a real re-emit, not a no-op.

## Study Date
**June 2026**

## Method

One shared baseline graph (`graph_initial.json`) is executed by a single traversal agent
that is **imported unchanged** by every condition (`baseline_in_place_mutation.traverse`).
Only the *materialization strategy* of the substrate differs between conditions, so any
divergence in the final bytes is attributable to materialization, never to a difference
of mechanism. The initial "as-handed-over" serialization is written identically for all
four conditions, so the end-state byte divergence is caused solely by how the
self-modification was written back.

The baseline's `grow` node has **no outgoing edge**: during execution it self-modifies
the substrate, creating the `audit` node and the two edges that continue the path. The
agent then traverses the topology it just created. Equivalence is decided by a
**topological structural diff** (`structural_diff` / `topologically_equal`) over a
canonical, order-independent snapshot — explicitly **not** a byte or file-hash equality,
because re-render legitimately changes the bytes. The comparator carries an
**anti-tautology negative test**: two byte-divergent-but-topologically-equal graphs must
compare equal, and a graph differing by one node or edge must compare unequal.

### Condition A — In-Place Mutation Baseline
The substrate is a serialized file; the self-modification is written as a **localized,
layout-preserving edit** — untouched elements keep their on-disk order and format, and
only the delta is spliced in. This is the base case the other conditions are measured
against.

### Condition B — Wholesale Re-Render (same file)
The agent computes the same modification, then **re-serializes the entire graph** in a
canonical normal form and replaces the prior file content — no in-place delta is written.
The change persists in the same file and affects subsequent traversal.

### Condition C — Re-Render as New-File Emission
The agent **emits the modified graph as a new serialized file**; the active substrate
switches to it; the prior file is left intact and **no** `superseded_by` provenance edge
is written. This is *pure* re-render — deliberately the harder design-around: unlike a
supersede operation (which preserves topology **and** writes a persisted provenance
link), pure re-render need preserve neither.

### Condition D — Hybrid (mixed in-place and re-render)
Within a single traversal, the first modification is applied in place and the rest by
re-render — proving the two materialization strategies are interchangeable. The mix is
recorded so the audit can confirm both were exercised.

### Measured (7 metrics per condition)
topology determination · result-dependent routing · self-modification · modification
persistence · functional (topological) equivalence to the baseline · **representation
divergence** (bytes differ from A while topology matches) · node/edge-count delta.

## Files Included

| File | Purpose |
|------|---------|
| `graph_initial.json` | Shared baseline substrate (reused byte-identical from STUDY-203, the merged canonical; see Related Studies) |
| `baseline_in_place_mutation.py` | Condition A + the single shared agent, router, the two serializers, the topological comparator, the substrate, and the metrics |
| `rerender_full_emit.py` | Condition B — wholesale re-render to the same file |
| `rerender_new_file.py` | Condition C — re-render as a new-file emission (pure; no provenance edge) |
| `hybrid_mixed.py` | Condition D — mixed in-place + re-render in one traversal |
| `test_equivalence.py` | Equivalence + conformance suite (incl. the anti-tautology comparator test); generates `results.json` |
| `results.json` | Machine-readable results (generated by running the suite) |

## Key Mechanism

There is exactly **one** traversal agent. `traverse(store, ...)` reads the current node,
executes its content, then re-reads the node's outgoing edges and selects one by
evaluating each edge's condition against the execution result. The substrate is a
file-backed store parameterized by a **materialization strategy** — in-place edit (A),
wholesale re-render to the same file (B), re-render to a new file (C), or a hybrid (D).
Because the agent is materialization-agnostic and identical across conditions, equality
of the four final topologies isolates a single variable — how the modification is written
back — and shows the topology-as-program and result-driven-edge-selection mechanism
invariant under it.

The sharp end is the pair of metrics: **functional (topological) equivalence** proves the
final topology that governs subsequent traversal is the same in every condition, and
**representation divergence** proves the re-render genuinely re-emitted the whole
serialization (the bytes differ from the in-place baseline) rather than producing a
byte-identical no-op. Together they establish that wholesale re-rendering is a different
*materialization* of the same self-modification, not a different computational model.

## Results

All four conditions PASS; the suite reports 21/21 validation checks. Conditions B, C, and
D are each topologically equal to baseline A while their serialized bytes diverge from A.

| Metric | A (in-place) | B (re-render, same file) | C (re-render, new file) | D (hybrid) |
|--------|:---:|:---:|:---:|:---:|
| Topology determination | Y | Y | Y | Y |
| Result-dependent routing | Y | Y | Y | Y |
| Self-modification | Y | Y | Y | Y |
| Modification persistence | Y | Y | Y | Y |
| Functional (topological) equivalence to A | baseline | Y | Y | Y |
| Representation divergence (bytes ≠ A, topology = A) | reference | Y | Y | Y |
| Node-count delta | +1 | +1 | +1 | +1 |
| Edge-count delta | +2 | +2 | +2 | +2 |

**Materialization evidence.** A materialized only in place; B only by re-render; C emitted
new files and switched the active substrate while leaving the prior file intact and
writing no provenance edge; D used **both** in-place and re-render within one traversal.

**Traversal path (all conditions):** `start → compute → branch → grow → audit → finalize` (the
`audit` node is created during execution, then traversed).

**Result:** re-serializing the whole graph (B), emitting it as a new file (C), or mixing
strategies (D) does not change the computational outcome or the final topology — it only
changes the bytes on disk. The re-render design-around does not avoid the self-modification.

## Conclusions

### Core Finding
**An executable graph substrate self-modifies through execution regardless of how the
modification is materialized: an in-place edit, a wholesale re-render to the same file, a
re-render emitted as a new file, and a hybrid each produce a final topology structurally
identical to the in-place baseline, while the serialized representation diverges.
Wholesale re-rendering is a representational implementation of the same self-modification,
not an escape from it.**

### Properties Demonstrated
1. **Materialization independence (topology)**: in-place (A) ≡ re-render-same-file (B) ≡
   re-render-new-file (C) ≡ hybrid (D), by topological structural diff.
2. **Real re-emit (representation)**: B, C, and D each diverge from A in serialized bytes
   while matching in topology — the re-render is genuine, not a no-op.
3. **Mechanism under the shift**: topology-as-program and result-driven edge selection
   drive the same persisted self-modification in every condition, *during* execution.

## Honesty and Claim Mapping

This section is load-bearing: it states what the study supplies, what it consciously
surrenders, and what it does **not** discharge, so the artifact is not read as banking
more than it proves.

### L5 surrender — this is materialization-strategy-equivalence, not full-mechanism survival
Wholesale re-render is, by definition, a **generation / transformation step**: it
regenerates a separate serialized artifact rather than editing the live one in place. It
therefore **surrenders the structural-liveness ("no compile / parse / interpret step
between the modification and its effect") distinction** that the application as filed
relies on, and which the as-filed specification couples to the in-place write. This study
**does not** claim re-render preserves structural-liveness. Its distinguishing weight
rests **only** on **topology-as-program** (the final topology governs subsequent
traversal), **result-driven edge selection** (a result selects the modification and the
next edge), and **persistence affecting subsequent traversal** — never on the no-compile
property. Claiming otherwise would assert exactly the property re-render gives up and turn
this artifact into a liability rather than evidence.

### The graph-rewriting prior-art class is counsel's CIP gate
Re-rendering a graph by regenerating a transformed output artifact is, in primitives,
what **rule-based graph rewriting via a separate match/rewrite engine** does — apply
productions to a host graph and export a transformed model. A re-render claim walks
directly into the largely **unsearched** graph-transformation / graph-grammar prior-art
class (and into flow-redeploy systems that re-emit a whole workflow artifact on each
change). That element-by-element prior-art sweep is **counsel's CIP gate**, **not** cleared
by this study; this artifact establishes the embodiment shape and reduction-to-practice
date only.

### Reduction to practice, not §112 enablement; CIP-only, deferred from first filing
A built, run, and git-timestamped study establishes a **reduction-to-practice date** and
an embodiment shape. It does **not**, by itself, satisfy **§112(a)** written description /
enablement — authoring that enabling disclosure is counsel's CIP work. This study is
**deliberately held from the first filing** because the application as filed teaches the
opposite mechanism (it writes the modification *into* the existing serialized file and
continues on the modified graph, not on a regenerated successor). The re-render claim
therefore takes the **CIP filing date**, is filed as a **separate, CIP-dated** claim under
split-priority discipline, and its language must **never** be amended into the parent-date
independents (Claims 1–3) — re-render is the least defensible breadth to pull toward the
parent date, and contaminating the keystone claim with it would inject new matter and
forfeit the parent date.

### Equivalence is topological, never byte
Because re-render legitimately changes the serialized bytes, the equivalence gate compares
**structure** (node identities + content, the directed edge set + conditions) via
`structural_diff`, never a byte or file hash. The comparator carries an anti-tautology
negative test so it cannot false-pass by always reporting "equal"; the
`representation_divergence` metric simultaneously asserts the bytes **do** differ from the
baseline, so a byte-identical no-op masquerading as a re-render is caught.

## Related Studies
- **STUDY-203** (Decomposed Agent Systems): this study **reuses STUDY-203's
  `graph_initial.json` byte-identical** (`baseline_authored_by: "STUDY-203"` in
  `results.json`) and conforms to its substrate schema and execution model
  (op-based accumulator, result-driven edge selection over edge `condition` properties,
  data-driven self-modification). STUDY-203 landed first (merged) and is therefore the
  **canonical shared baseline** under the B1 contingency ("whichever study lands first
  authors it; the others conform byte-identically"). Because the baseline and the final
  topology (`start → compute → branch → grow → audit → finalize`) are identical,
  materialization-independence (205) and agent-decomposition (203) are proven against the
  **same** baseline — the combined-prior-art premise, and the cross-study equivalence
  check passes (not skipped).
- **STUDY-204** (Storage-Independent Graph Substrate): the closest structural sibling and
  the source of the topological `canonical_snapshot` comparator idiom this study adapts.
  STUDY-204 has since been reconciled to the canonical baseline and is now **byte-identical**
  to STUDY-203's `graph_initial.json` — the same fixture STUDY-205 uses — so STUDY-203,
  STUDY-204, and STUDY-205 are all proven against the **same** baseline; the
  combined-evidence claim is auditable via `baseline_authored_by`.
- **STUDY-140 / issue #1329** (Supersede Operation): re-render is the whole-graph
  limit-case of supersede. Supersede preserves topology **and** writes a persisted
  provenance link; Condition C's *pure* re-render preserves neither — which is why
  re-render is the harder design-around and is studied here distinctly.

## How to Run

```bash
cd studies/STUDY-205-Re-Render-Self-Modification
python baseline_in_place_mutation.py   # Condition A demo
python rerender_full_emit.py           # Condition B demo
python rerender_new_file.py            # Condition C demo
python hybrid_mixed.py                 # Condition D demo
python test_equivalence.py             # run all + regenerate results.json
pytest test_equivalence.py -v          # full conformance suite
```

**Requirements:** Python 3.10+ (standard library only — no external dependencies, no
network, no external services, no database).

## Date Evidence

**Study Date:** June 2026
**Git History:** available in repository commit log; the merged-commit timestamp is the
reduction-to-practice date and must precede the CIP filing date.
**Patent Application:** 19/575,491 (Non-Provisional).
