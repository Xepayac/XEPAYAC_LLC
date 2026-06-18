# STUDY-209: Networked / Distributed Substrate — Self-Modification and Structural Liveness Across a Network Boundary

## Classification: PUBLIC

## Abstract

This study demonstrates that the self-superseding graph-substrate mechanism —
topology-is-execution, result-driven edge selection, and in-traversal
self-modification that persists and governs the next traversal step — is
**locus-independent across a network boundary**. One shared starting substrate
is traversed by one agent under three conditions: **(A)** a local baseline with
the agent and the substrate in a single process; **(B)** a networked store held
by a separate process and reached over a loopback socket, where the agent reads
nodes/edges and writes its self-modification *over the boundary*; and **(C)** a
distributed store sharded across two separate store services. Conditions B and C
each produce a final graph state **structurally identical** to the local
baseline A (+1 node, +2 edges from the in-traversal self-modification), and the
load-bearing property — **structural liveness** — is shown to **survive the
boundary**: the modification written over the wire is immediately live, with no
recompile, redeploy, or restart between the remote write and its effect on the
next traversal step. The result establishes the networked species of the
persistent-store genus by reduction to practice.

## Study ID
**STUDY-209**

## Title
Networked / Distributed Substrate — Self-Modification and Structural Liveness Across a Network Boundary

## Purpose
Demonstrate that a graph substrate governs computation — determining the
sequence, routing by execution result, and supporting self-modification that
persists and affects subsequent traversal with no authoring→execution boundary —
when the substrate is stored on a service **separate from the agent** and reached
over a network boundary. The study isolates and proves the one property the
as-filed disclosure defines only for a local graph: that **structural liveness
holds across the boundary**.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable
  Graph-Based Computation with Self-Modification by Autonomous Agents.
  - **Claim 9** (networked storage / store-and-agent on separate devices): the
    persistent store is a networked storage service residing on a first device,
    the computational agent executes on a second device, and the reading, the
    writing of the modification, and the continued traversal occur via a network
    connection between the two. This study is the reduction to practice that
    converts that species from *anchor-only* to *enabled* — it closes the
    "Gap-4" unenabled tail of the storage-independent genus, the species
    sibling STUDY-204 explicitly left owed.

## Hypothesis
The mechanism is locus-independent across a network boundary: an agent
traversing and self-modifying a substrate held by a separate store service
produces the **same** topology-determined sequence and the **same** persisted
self-modification — the next step operating on the modified substrate, with no
restart or redeploy — as the local baseline.

## Study Date
**June 2026**

## Method

1. **Shared baseline.** Author one deterministic starting substrate
   (`graph_initial.json`): a branching topology with a result-dependent
   (conditional) edge at `gate` and a self-modification trigger at `mutate`.
   `mutate` has no outgoing edge initially — executing it makes the agent add an
   `audit` node and the edges that carry traversal through it, so the next step
   can reach `audit` *only if* the modification persisted and is live.
2. **Condition A — local baseline.** Agent and substrate in one process. The
   agent traverses by topology, routes by execution result, performs the
   in-place persisted self-modification, and continues. This is the golden
   reference.
3. **Condition B — networked store.** The substrate is held by a store service
   in a **separate operating-system process**, reached over a `127.0.0.1`
   loopback socket. The store is a *dumb persistence locus*: it exposes only
   read and write operations and performs no routing, no execution, and no edge
   selection. The **same agent** reads nodes and outgoing edges, and writes its
   self-modification, entirely over the boundary; it then re-reads the outgoing
   edges over the boundary and the next step walks the freshly-persisted edge.
4. **Condition C — distributed store.** The substrate is sharded across **two**
   separate store services; nodes (and the edges originating at them) are
   partitioned by a deterministic hash. The same agent self-modifies, and a
   subsequent step observes the persisted change even though it was written to
   whichever shard owns the new topology.
5. **Measure**, per condition: topology-determination; result-driven routing;
   in-traversal self-modification; **persistence + affect-subsequent-traversal
   across the boundary**; **structural liveness across the boundary** (no
   recompile/redeploy between the remote write and its effect); and **functional
   equivalence** to the local baseline A. A negative control suppresses the
   across-boundary write and confirms the equivalence/liveness check then goes
   RED.

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, the across-the-boundary structural-liveness argument, results, §101 caution, claim mapping |
| graph_initial.json | Shared starting graph substrate (deterministic; branching topology + a conditional edge + a self-modification trigger) |
| baseline_local.py | Condition A (local baseline) + the shared mechanism: op interpreter, result-driven edge selector, the agent, and the dumb store contract |
| networked_store.py | Condition B — a separate-process store service over a loopback socket + the agent's client |
| distributed_store.py | Condition C — the substrate sharded across two store services (reuses Condition B) |
| test_network_equivalence.py | Cross-condition equivalence + across-boundary liveness + store-is-dumb + real-boundary + the RED-capable negative control; generates results.json |
| results.json | Machine-readable per-condition metrics + equivalence + liveness verdicts (generated, never hand-authored) |

## Key Mechanism

### The across-the-boundary structural-liveness argument

Structural liveness — *"the modification is immediately structurally live, with
no parsing, compilation, or interpretation step separating the modification from
its effect on subsequent traversal"* — is the property the as-filed disclosure
defines for a **local** graph. The hard question this study answers is whether it
**survives a network boundary**.

The proof is concrete. The `mutate` node has no outgoing edge in the starting
substrate. When the agent executes it, the agent writes a topology
modification — a new `audit` node and the edges `mutate → audit` and
`audit → end` — to the store **over the boundary**. The agent then re-reads
`mutate`'s outgoing edges **over the boundary**, finds the freshly-persisted
`mutate → audit` edge, and walks it. The next traversal step therefore operates
on the substrate *as modified and persisted in the remote store*, not on the
original. There is no recompile, redeploy, or restart between the remote write
and its effect: the store service is the same running process throughout
(verified by an unchanging process identity across the write), and the modified
topology is live on the very next read. The test suite isolates this property
directly (`TestBoundaryLiveness`), separate from the final-state equivalence
check, because final-state equivalence alone would not prove that *liveness*
crossed the boundary.

### Embodiment-only: the agent owns the mechanism, the store is a dumb locus

The study moves only **where** the substrate is persisted. The mechanism — the
op interpreter, the result-driven edge selector, the agent — is **byte-for-byte
identical** across all three conditions (the test asserts the agent class is the
same object). The store exposes only read and write operations; its wire
protocol has **no** routing, selection, or execution command, and the store
refuses any such request. Result-driven edge selection happens in the agent, not
the store. This is the single most important invariant of the study: if the store
computed routing, the experiment would demonstrate a *different* mechanism over
the wire and would prove nothing about the claimed mechanism surviving the
boundary.

## Results

All conditions were run by `test_network_equivalence.py`; `results.json` is
generated from that run.

| Metric | A (local) | B (networked) | C (distributed) |
|---|---|---|---|
| Topology determines sequence | yes | yes | yes |
| Result-driven routing | yes | yes | yes |
| In-traversal self-modifications | 1 | 1 | 1 |
| Node-count delta | +1 | +1 | +1 |
| Edge-count delta | +2 | +2 | +2 |
| Persistence affects subsequent traversal | yes | yes (across boundary) | yes (across boundary) |
| Structural liveness across the boundary | n/a (local) | **yes** | **yes** |
| Functional equivalence to A | reference | **yes** | **yes** |

Traversal sequence (all conditions): `start → gate → odd_branch → mutate → audit → end`.
The `audit` node exists only because of the in-traversal self-modification; its
presence in B and C proves the next step ran on the remotely-persisted, modified
substrate.

**Negative control.** Suppressing the across-boundary write makes the agent
unable to reach `audit`, and the final state diverges from A — the
equivalence/liveness check goes RED. The green result above is therefore not
vacuous.

## Conclusions

### Core Finding

**The self-superseding graph-substrate mechanism — topology-is-execution,
result-driven edge selection, and in-traversal persisted self-modification with
no authoring→execution boundary — is locus-independent across a real network
boundary, including a substrate distributed across two services; structural
liveness survives the boundary.**

### Properties Demonstrated

1. **Functional equivalence across the boundary** — B and C produce a final
   graph state structurally identical to the local baseline A.
2. **Structural liveness across the boundary** — a remote write is immediately
   live for the next traversal step, with no recompile/redeploy/restart.
3. **Embodiment-only** — the mechanism (the agent) is unchanged; only the
   storage locus moved. The store is a dumb persistence locus.
4. **Distributed locus** — the property holds even when the substrate is sharded
   across two separate store services.

## Honesty and claim-mapping notes

- **§101 caution (do-it-over-a-network).** Network/service framing strengthens
  the *Alice* Step-2A "do-it-over-a-network = abstract" attack
  (*Electric Power Group v. Alstom*, 830 F.3d 1350). The novelty of this study is
  **not** "remote versus local." It is that **traversal is execution** and that
  **in-traversal persisted self-modification stays structurally live across the
  boundary** — a specific, concrete improvement in how a computational substrate
  is executed and modified, not the generic application of a known process over a
  network. The distinguishing weight stays there, never on the locus.
- **Reduction to practice, not enablement.** This study supplies a dated
  reduction to practice and an embodiment shape for the networked species. It is
  **not** the patent's written description; authoring the §112(a) support across
  the network boundary is counsel's work in the continuation-in-part.
- **The §102 sweep is owed, not discharged here.** A networked or distributed
  store walks into the largely-unsearched graph-database and distributed-store
  prior-art class — the sharpest §102 threat to the storage-independent genus.
  That clearance is **counsel's CIP gate**; this study does not clear it and
  must not be read as if it did.
- **Self-contained.** The network boundary is a loopback socket to an in-repo
  store service run as a separate process, using only the Python standard
  library. There is no external server and no third-party dependency: "a
  networked storage service" is described and exercised as a primitive, so the
  artifact is reproducible by anyone with a standard Python install.

## Related Studies

- **STUDY-204** (Storage-Independent Substrate): proved storage- and
  access-independence for in-process loci (a relational store, a mediation
  layer) and **explicitly deferred** the network-boundary species. STUDY-209 is
  the study that picks up exactly what STUDY-204 left owed.
- **STUDY-208** (Substrate-Genus Conformance): the local-genus spine. STUDY-209
  and STUDY-208 are designed to share one canonical `graph_initial.json` for
  cross-study comparability. **Baseline authorship:** at authoring time
  STUDY-208 was not yet on the main line, so **STUDY-209 authored this study's
  baseline** (`baseline_authored_by: STUDY-209`), with its node-op vocabulary
  aligned to the STUDY-208 substrate contract; when STUDY-208 lands, the
  cross-study check confirms shared vocabulary.
- **Condition C decision:** Condition C (distributed) was **built** — it adds a
  genuine "substrate split across two services" datapoint at modest,
  compositional cost over Condition B, matching the study's "Networked /
  Distributed" scope and the distributed framing of claim 9.

---

> ⛔ Internal note for maintainers: this study is reduction-to-practice evidence
> for the EGS-979 patent program. Engineering work product — **not legal
> advice**. Claim mapping is verified with counsel before any filing.
