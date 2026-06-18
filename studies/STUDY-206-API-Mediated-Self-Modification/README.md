# STUDY-206: API-Mediated Self-Modification — Modification Across a Service Boundary

## Classification: PUBLIC

## Abstract

This study demonstrates that interposing an API/service boundary between a computational agent and the graph substrate it modifies does not move the inventive act outside the agent/substrate boundary. One agent traverses a deterministic branching graph, executes node content, routes by the execution result, and performs a result-driven self-modification under four conditions that differ only in **where the write physically executes**: written **directly** to the persisted substrate (A), issued as a **serialized request to a separate write service** (B), issued across a **genuine operating-system process boundary** for both reads and writes (C), and issued across a boundary whose service writes to a **relational persistent store** (D). Across all four, the final graph state is structurally identical (B = C = D = A), the result-driven modification is decided **agent-side in every condition**, and the modification is **structurally live for the next traversal step** with no compile or restart boundary. The interposed boundary relocates the write *mechanism*, not the inventive *mechanism*.

## Study ID
**STUDY-206**

## Title
API-Mediated Self-Modification — Modification Across a Service Boundary

## Purpose
Establish prior art, by dated publication, for claims covering self-modification of an executable graph substrate **regardless of where the result-driven write physically executes relative to the agent**. The study forecloses the API-level-wrapper argument — that "the agent never writes to the substrate; it issues an API call and a separate service performs the write, so the modification happens outside the claimed boundary." It proves that the decision-locus (the result-dependent modification decision) remains at the agent, and the modification still persists and governs subsequent traversal, whether the write is direct or routed across a service, process, or persistent-store boundary.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
  - **Claims 1–3** (independent — the self-modification element): the agent computes a result-dependent modification of the graph during execution. This study shows that element is satisfied in every condition; only the write's execution location changes.
  - **Claim 8** (modifications persist and affect subsequent traversals): shown directly — the inserted node is traversed in the same run and survives in the post-run substrate, across each boundary.

This study supports a continuation-in-part (CIP) broadening that takes the **CIP filing date**, not the parent application date — the as-filed specification teaches the direct-write embodiment. It closes the **API-level-wrapper / decision-locus circumvention vector**.

## Hypothesis
A graph substrate comprising nodes with executable content and edges encoding directional relationships determines the sequence of computation and enables self-modification during execution, regardless of whether the result-driven modification is written by the agent **directly** to the substrate or **issued across an API/service boundary** that performs the write on the agent's behalf. The **locus of the result-dependent modification decision is the agent in both cases**; the boundary relocates the write mechanism, not the inventive mechanism. (Falsifiable: if any non-baseline condition produced a different final graph state, or if the decision of *what* to modify moved to the service, the hypothesis would fail.)

## Study Date
**June 2026**

## Method

1. **Shared baseline.** Author one deterministic branching graph (`graph_initial.json`) with a result-dependent (conditional) edge pair and one self-modification trigger. It is the only controlled input; the single variable across conditions is where the write executes.
2. **One shared agent.** A single agent implementation (`run_agent`) traverses by topology, executes node content, selects the outgoing edge by the execution result, and — when the result routes to the high branch — **decides agent-side** to insert an `audit` node, handing a fully-specified write to an accessor. The same agent code runs in every condition.
3. **Condition A — direct write.** The agent holds the substrate and writes the modification directly to the persisted serialized form.
4. **Condition B — API-mediated write.** The agent computes the modification and issues it as a **serialized request** to a separate write service (the sole holder and sole mutator of the substrate); the service performs the write. Reads are local; only writes cross the boundary.
5. **Condition C — API-mediated read and write.** Both reads and writes cross the boundary, and the boundary is a **separate operating-system process** (the agent and the service do not share an address space). The agent holds no storage handle — only request and response channels.
6. **Condition D — API over a persistent store.** The boundary is composed over a relational persistent store (an embedded, in-process relational store from the language standard library — not a serialized file); reads serve out of it, writes land in it.
7. **Measure.** For each condition, capture the seven metrics below into `results.json` (generated by running the harness, never hand-authored), and assert functional equivalence (B = C = D = A) plus the decision-locus, service-no-decide, and structural-liveness properties.

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, results, analysis |
| graph_initial.json | Shared starting graph substrate (cohort baseline) |
| baseline_direct_write.py | Condition A — direct-write baseline + shared agent/primitives |
| api_mediated_write.py | Condition B — write issued as a serialized request to a separate service |
| api_mediated_readwrite.py | Condition C — read + write across a genuine process boundary |
| combined_api_persistent.py | Condition D — API boundary composed over a relational persistent store |
| test_equivalence.py | Cross-condition equivalence + 7-metric + decision-locus + service-no-decide verification; generates results.json |
| results.json | Machine-readable results for all conditions (generated) |

## Key Mechanism

The study isolates **where the write executes** from **who decides what to write**. A single agent computes the modification from the execution result and hands a fully-specified write to an *accessor*; the accessor alone determines whether the write runs directly, crosses a serialized-request service boundary, crosses an operating-system process boundary, or lands in a relational persistent store. Because the agent code is identical across conditions, the **decision-locus is structurally the agent** in every case. The service is a **dumb transport**: it applies the operation named in the request and has no path to the execution result or the routing decision — so the inventive decision cannot migrate to it. And because each condition re-reads the live topology for the next step, a modification written mid-traversal is **immediately structurally live**: the agent follows an edge that did not exist until it issued the write, with no parsing, compilation, deployment, or restart step in between.

## Results

### Test 1: Functional equivalence (B = C = D = A)
The final graph state (node identity + type + content, and edge topology) of Conditions B, C, and D is structurally identical to the direct-write baseline A.

**Result**: PASS — all three mediated conditions are functionally equivalent to the baseline.

### Test 2: Seven metrics per condition

| Metric | A (direct) | B (API write) | C (API read+write, process) | D (API over store) |
|--------|-----------|---------------|-----------------------------|--------------------|
| Topology determination | Yes | Yes | Yes | Yes |
| Result-dependent routing | Yes | Yes | Yes | Yes |
| Self-modification | Yes | Yes | Yes | Yes |
| **Decision locus** | **agent** | **agent** | **agent** | **agent** |
| Modification persistence | Yes | Yes | Yes | Yes |
| Functional equivalence to A | baseline | Yes | Yes | Yes |
| Node / edge count delta | +1 / +2 | +1 / +2 | +1 / +2 | +1 / +2 |

**Result**: PASS — the decision-locus is the agent in every condition; every condition self-modifies the live topology and the modification persists.

### Test 3: Service-no-decide (adversarial)
A request that attempts to smuggle an execution result or a routing decision into the write service has **no effect** on the outcome, and the services expose no result/decision attribute; the agent's clients never place a result/decision into a request.

**Result**: PASS — the services are dumb transports; the decision cannot migrate off the agent.

### Test 4: Structural-liveness across the boundary
In every condition the agent follows the `grow → audit` edge, which did not exist until it was written mid-traversal — proving the write is live for the very next step with no recompile or restart, including across the process boundary (C) and the persistent store (D).

**Result**: PASS.

### Test 5: Boundary actually crossed
Condition C runs the service in a process with a different PID than the agent; Condition D writes into a relational persistent store. 29/29 generated checks pass.

**Result**: PASS.

## Conclusions

### Core Finding
**An interposed API/service boundary is a transport detail, not a relocation of the inventive locus: the agent remains the decider of the result-driven self-modification, the modification stays structurally live, and the final substrate is identical — whether the write is direct, crosses a service or process boundary, or lands in a persistent store.**

### Properties Demonstrated
1. **Decision-locus invariance**: the result-dependent modification is decided agent-side in every condition.
2. **Service-no-decide**: the write service is a dumb transport with no access to the execution result or routing decision.
3. **Structural-liveness across the boundary**: a mid-traversal write governs the next step with no compile/deploy/restart boundary.
4. **Functional equivalence**: the API-wrapper conditions produce a final substrate structurally identical to the direct-write baseline.

## Honesty and Claim-Mapping Notes

- **The "an in-process API is just a function call" objection.** The distinguishing weight rests on two grounds, not on the mere existence of a boundary: (1) the **decision-locus** — the agent computes *what* to modify from the execution result and the service **never sees the result**; and (2) the **boundary is actually crossed** — the write is issued as a **serialized request** performed by a **separate service** component; **Condition C** crosses a genuine operating-system **process boundary** (the agent and service do not share an address space) and **Condition D** routes the write into a relational persistent store. The objection is therefore addressed structurally, not assumed away.
- **Mechanism-axis distinguisher.** Demonstrating that the write can be transported across a service boundary concedes that the embodiment is *distributable*. The study therefore rests its distinguishing weight on the **mechanism axis** — **result-driven edge selection** over a persisted topology, **structural-liveness** (no compile boundary), and **traversal-IS-execution** — and **never on "the write crossed an API" boundary**. A boundary crossing alone is not the invention; the self-hosting loop over a live, result-routed topology is.
- **Client-server / RPC / CRUD-over-API prior art is counsel's gate.** Because the API-wrapper breadth reads on a wide class of **client-server / RPC / CRUD-over-API** architectures, the corresponding prior-art search is **counsel's CIP gate** and is **not cleared** by this study; this study only manufactures the dated reduction-to-practice for the substrate mechanism.
- **Cross-machine network species is owed.** This study reduces to practice the **in-process / localhost** service boundary only (self-contained, standard-library). The **literal cross-machine network boundary** — the service on a **different host**, the write traveling **over a real network** — is **owed**, **not reduced to practice** here, and is left to a future study or counsel's CIP authoring.
- **Reduction-to-practice, not enablement.** A built, dated study establishes a reduction-to-practice **date** and an embodiment shape; it does **not** by itself establish §112 written-description / enablement in the patent — that is **not** this study's work and remains counsel's CIP-specification task.

## Related Studies
- **STUDY-204** (Storage-Independent Substrate): closes the *storage-independence* vector (where the graph is stored). STUDY-206 reuses its mediation flavor but keeps every assertion and the narrative on **decision-locus** (where the modification decision and boundary sit), not storage.
- **STUDY-203** (Decomposed Agent Systems): the deployment-detail framing this study extends to the API boundary.
- **STUDY-205** (Re-render): the sibling claim-scope dodge.
- **Baseline ownership (ADR-003)**: `graph_initial.json` is the **shared STUDY-203/204/206 cohort baseline**. **STUDY-203 is the authoritative author** (recorded in `results.json` as `baseline_authored_by: "STUDY-203"`); **STUDY-206 adopts it byte-identically**. The cross-study equivalence check (`test_cross_study_baseline_or_b1_skip`) actively verifies that STUDY-206's baseline is canonically identical to STUDY-204's (≡ STUDY-203's), so the cohort's combined-evidence claim is auditable and confirmed.
