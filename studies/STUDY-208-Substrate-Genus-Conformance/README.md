# STUDY-208: Substrate-Genus Conformance — One Contract, N Persistent Stores, One Corpus

## Classification: PUBLIC

## Abstract

A self-superseding graph substrate — a graph whose topology determines computation and which an agent modifies in place during execution — was run **unchanged** across a representative spread of the persistent-store genus through a single uniform substrate contract. Five backends (serialized file, multi-file, relational store, key-value store, in-memory store) each implement one minimal interface (`read_node`, `get_outgoing_edges`, `write_modification`, `persist`) and nothing more; one conformance corpus (traversal-is-execution, result-driven edge selection, and an in-traversal persisted self-modification including a supersede step) runs identically against every backend. All five backends produced a final substrate state **structurally equivalent to the serialized-file baseline** (B==A, C==A, D==A, E==A), each passing all seven conformance metrics with nonzero node and edge deltas. The mechanism does the work; the storage does not — which is exactly what enables "a persistent store" across its genus.

## Study ID
**STUDY-208**

## Title
Substrate-Genus Conformance — One Substrate Contract, N Persistent Stores, One Conformance Corpus

## Purpose
This study demonstrates that the self-superseding graph-substrate mechanism is **storage-implementation-independent across the genus**: one substrate contract plus the identical mechanism and identical conformance corpus behave identically regardless of which persistent-store backend holds the graph. Where sibling point-studies prove single embodiments, this study proves the *genus* — the reduction-to-practice spine for a generic "a persistent store" claim.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents.
  - **Generic independent ("a persistent store")**: this study supplies dated reduction-to-practice that the self-superseding mechanism is enabled across the *whole* persistent-store genus, not at a single point — the full-scope (genus) enablement burden a generic independent carries under *Amgen v. Sanofi*, 598 U.S. 594 (with *Liebel-Flarsheim* and *Ariad*).
  - **Narrowing dependents (storage technologies)**: serialized file, multi-file, relational, key-value, and in-memory are the narrowing embodiments; this study exercises all five through one contract.

## Hypothesis

A graph substrate whose topology defines computation and which an agent self-modifies during execution behaves identically — same topology-determined operation sequence, same result-driven edge selection, same in-traversal persisted self-modification (including a supersede step) — regardless of which persistent-store backend holds it, when accessed through a uniform substrate contract. Falsifiable: any backend whose final state diverges from the serialized-file baseline, or which fails any of the seven conformance metrics, refutes it.

## Study Date
**June 2026**

## Method

1. **Substrate contract**: define one minimal interface — `read_node`, `get_outgoing_edges`, `write_modification`, `persist` — vendor-name-free and primitives only. The conformance corpus runs against this contract, never against a backend directly.
2. **Backends**: implement one adapter per backend behind the same contract — **(A)** a single serialized file, **(B)** multiple serialized files with cross-file edges, **(C)** a relational store (an embedded standard-library SQL engine; rows read via query, written via row mutation), **(D)** a key-value store (point access by key), **(E)** an in-memory store. Each implements the contract and nothing more.
3. **One conformance corpus**: run the same self-superseding workload against every backend — traversal-is-execution over a shared deterministic starting graph with a result-dependent (conditional) branch, an in-traversal self-modification, and a supersede step that splices a superseding node into the live path.
4. **Measure**: for each backend, capture the seven metrics below; assert each backend passes all seven AND that every backend's final substrate state is structurally equivalent to the serialized-file baseline (A).

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, the genus-enablement argument, results, honesty/claim-mapping |
| graph_initial.json | Shared deterministic starting substrate (branching topology, conditional edge, self-mod + supersede) |
| substrate_contract.py | The ONE uniform substrate interface (the keystone) |
| backend_file.py | Backend A — single serialized file (the baseline) |
| backend_multifile.py | Backend B — multiple serialized files + cross-file edges |
| backend_relational.py | Backend C — relational store (embedded standard-library SQL; rows via query) |
| backend_kv.py | Backend D — key-value store (point access by key) |
| backend_inmemory.py | Backend E — in-memory store (persist semantics within the run) |
| conformance_corpus.py | The single self-superseding workload + 7-metric capture, written once ABOVE the contract |
| test_genus_conformance.py | Runs the corpus against every backend; asserts cross-backend equivalence + the embodiment-only invariant; writes results.json |
| results.json | Machine-readable per-backend metrics (generated, not hand-authored) |

## Key Mechanism

The load-bearing design is that the **mechanism lives above a thin storage contract**. The conformance corpus holds all of the traversal, execution, result-driven routing, and self-modification logic, and it touches the substrate **only** through the four contract methods. Each backend is a pure storage adapter — it decides where nodes and edges live and how they are read and written, and contains no traversal, routing, or execution logic. Because the corpus is byte-for-byte identical for all five backends, any difference in final state could come only from storage — and none appears. That is the precise sense in which "the mechanism does the work, the storage does not," and it is what makes a generic "a persistent store" claim enabled across its genus rather than at one point.

Three never-broadened substrate properties are preserved per backend: **topology-as-program** (the operation sequence is determined by the graph topology — traversal is execution), **result-driven edge selection** (the execution result of a node selects the outgoing edge the agent follows), and **structural-liveness** (an in-traversal persisted self-modification, including a supersede step, is immediately live — the just-written node and edge govern the very next traversal step, with no compile/deploy boundary).

## Results

### Cross-backend conformance (7 metrics per backend)

| Backend | Store | Topology determines sequence | Result-driven routing | Self-modification (+ supersede) | Modification persists & live | Functional equivalence to A | Δnodes | Δedges |
|---------|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A | serialized file | yes | 3 | 2 | yes | baseline | +2 | +5 |
| B | multi-file | yes | 3 | 2 | yes | yes | +2 | +5 |
| C | relational store | yes | 3 | 2 | yes | yes | +2 | +5 |
| D | key-value store | yes | 3 | 2 | yes | yes | +2 | +5 |
| E | in-memory store | yes | 3 | 2 | yes | yes | +2 | +5 |

**Result**: All five backends pass all seven metrics; B, C, D, and E each produce a final substrate state structurally equivalent to the serialized-file baseline A. The agent's traversal on every backend is `start → gate → odd_branch → mutate → audit → supersede → compute_v2 → end`, where `audit` and `compute_v2` are nodes added *during* traversal and immediately governing it.

### Embodiment-only invariant

**Result**: The corpus calls only the four contract methods (plus a non-mechanism `export_canonical` measurement affordance) on every backend; it imports no backend module; the relational backend's read path issues SQL queries; the in-memory backend's modification is invisible until `persist()` and immediately live after. The embodiment varies; the mechanism does not.

## Conclusions

### Core Finding

**One substrate contract plus the identical self-superseding mechanism runs unchanged across a representative spread of the persistent-store genus — serialized file, multi-file, relational, key-value, and in-memory — all producing a structurally-equivalent final substrate; the mechanism does the work, the storage does not.**

### Properties Demonstrated

1. **Genus conformance**: a single uniform contract suffices for five distinct storage embodiments; functional equivalence to the file baseline holds for every one.
2. **Mechanism invariance under the storage shift**: topology-as-program, result-driven edge selection, and structural-liveness are preserved per backend.
3. **Embodiment-only**: storage logic never enters the mechanism; routing is decided by the execution result, never by adapter/storage logic, and modifications are immediately live after `persist()` with no compile/deploy seam.

## Honesty / Claim-Mapping

- **"A relational store is technically still a file; an in-memory store is technically still ephemeral."** The rebuttal is the **access pattern**, not the storage medium. Backend C reads **rows via SQL** queries and writes via row mutation — not by parsing a serialized graph file. Backend E holds nothing on disk yet still satisfies **persist semantics within the run**: a modification is invisible to subsequent traversal until `persist()` commits it, and immediately governs the modified topology thereafter. The distinction this study rests on is the **mechanism, not the storage** — never "serialized vs not."

- **EGS-979 claim mapping (CIP, not the parent).** This study feeds the CIP's **generic "a persistent store" independent claims** — the continuation-in-part patent (which takes the CIP filing date), not the parent's serialized-file independents (which keep the earlier date). A generic independent carries a **full-scope (genus) enablement** burden under *Amgen v. Sanofi*; this study supplies dated reduction-to-practice that the mechanism is enabled across a representative spread of the genus.

- **Reduction-to-practice, not enabling disclosure.** Publishing this study (a dated public commit) establishes a **reduction-to-practice** date and the genus embodiment shape. It is **not** the patent's §112(a) enabling disclosure — drafting that disclosure, and the definiteness lexicography for "persistent store," is counsel's work, not this study's.

- **L1-concession / L3+L5 distinguisher.** Demonstrating storage-independence **concedes** the **L1** "graph-in-a-store" axis: a graph held in any store is, at L1, just data in a store. The substrate's distinguishing weight therefore rests on **L3** (traversal-is-execution — the topology *is* the program) and **L5** (in-traversal persisted self-modification, immediately live, with no compile/deploy boundary) — **never** on "serialized vs not." An artifact that banked the L1 distinction it here surrenders would be an overclaim.

- **Graph-database prior art is counsel's CIP gate.** A **graph database** is, definitionally, "a persistent store holding a graph of nodes and edges," so a broad "any persistent store" claim walks into the largely-**unsearched graph-database and graph-transformation prior-art** class. That **prior-art sweep is counsel's CIP gate**, not discharged by this study; this study only manufactures the dated genus reduction-to-practice.

- **Coverage delta — the networked/distributed species is owed.** STUDY-208 proves the genus via the A–E spread, all of which keep the substrate locally always-live. It does **not** reduce to practice the **networked/distributed species** — the one genus member carrying the structural-liveness-across-a-network-boundary hole. That species is **owed** to **STUDY-209** (and to counsel's CIP authoring); it is **not reduced to practice here**, and is named, not silently dropped.

## Related Studies
- **STUDY-204** (Storage-Independent Substrate): the storage-independent *point* study (file / relational / mediated). STUDY-208 generalizes it to the genus-conformance spine; the key-value and in-memory backends fold in here.
- **STUDY-202** (Multi-File Substrate) / **STUDY-203** (Decomposed Agent Systems): the file and multi-process point embodiments.
- **STUDY-209** (Networked/Distributed Species): the one genus member STUDY-208 does **not** cover end-to-end — owed, not reduced to practice here.
- **Baseline authoring (cross-study record)**: `graph_initial.json` was **authored by STUDY-208** (`baseline_authored_by: "STUDY-208"` in results.json). Sibling studies STUDY-203/204 were unbuilt at authoring time; whichever lands first authors the canonical baseline and the others conform — the byte-identity cross-check is deferred until both exist, while the authoring record is recorded now so the cross-study comparability claim is auditable.
