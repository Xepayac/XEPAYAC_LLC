# STUDY-203: Decomposed Agent Systems — Multi-Process Graph Substrate Execution

## Classification: PUBLIC

## Abstract

This study demonstrates that the graph substrate governs computation independent of process boundaries. One shared, deterministic starting graph is executed under three embodiments: **A**, a single process that traverses, executes, and self-modifies the on-disk serialized graph; **B**, three cooperating operating-system processes that decompose those steps (traversal, execution, and a sole-modifier writer) and communicate over inter-process queues; and **C**, an external dispatch process that schedules which agent acts and when but does not itself decide where execution goes next. In every condition the on-disk serialized graph file is the shared executed medium, the execution result (not any coordinating or dispatch logic) selects the next edge, and a self-modification triggered during execution persists and affects subsequent traversal. Conditions B and C produce a final graph state **functionally equivalent** to baseline A — identical canonical graph and identical content hash. The embodiment changed; the mechanism did not.

## Study ID
**STUDY-203**

## Title
Decomposed Agent Systems — Multi-Process Graph Substrate Execution

## Purpose

Demonstrate that the three mechanism-axis properties of an executable graph substrate — (1) topology-as-program, (2) result-driven edge selection, and (3) structural liveness (in-execution self-modification that persists) — survive a shift in *who and how many* agents operate the substrate. Specifically, a single in-process agent, a decomposed multi-process agent system, and an externally-dispatched agent all produce the same final substrate state. The decomposition and the external dispatcher are deployment details, not substrate properties.

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
  - **Claim 1** (System) / **Claim 2** (Method): execution of a graph substrate with self-modification by writing changes during execution — shown here to hold across single-process, multi-process, and externally-dispatched embodiments.
  - **Claim 3**: result-dependent edge selection during traversal — shown here to be driven by the execution result against the substrate's edge conditions in every condition, including under external dispatch.
  - **Claim 7**: in-traversal persistence — the next traversal step operates on the modified-and-persisted graph; demonstrated across the multi-writer decomposition via a sole-modifier discipline.
  - **Claim 8**: modifications add nodes and edges that persist and affect subsequent traversals — the `grow` node adds an `audit` node and two edges that the traversal then follows.
- **CIP Broadening #2** (multi-process / decomposed agents): the agent-count sub-dimension of the embodiment axis — *one agent ⊆ many*. This study is a reduction-to-practice of that broadening direction.

## Hypothesis

**H1**: A decomposed system of three cooperating processes (Condition B), where no single process performs traversal, execution, and modification, produces a final graph state identical to the single-process baseline (Condition A).

**H2**: An external dispatch process (Condition C) can coordinate which agent acts and when while the execution result — not the dispatcher — selects the next node, producing a final graph state identical to baseline A.

**H3**: In all conditions the on-disk serialized graph file is the shared executed medium; the inter-process channels carry coordination messages only, never the substrate as an in-memory object.

**H4**: Routing all writes through a single sole-modifier process with an atomic replace makes the decomposed run bit-for-bit deterministic across repeated runs (multi-writer consistency).

## Study Date
**June 2026**

## Method

1. **Shared baseline**: `graph_initial.json` defines one deterministic branching topology with a result-dependent (conditional) edge at `branch` and a data-driven self-modification trigger at `grow`. It is authored with a generic node/edge schema so it can be reused unchanged by STUDY-204.
2. **Condition A (single process)**: one process reads the graph from disk, executes the current node against its own execution state, persists any self-modification, and selects the next edge from the execution result against the on-disk edge conditions. This fixes the canonical "equivalent" final-state contract.
3. **Condition B (decomposed)**: three OS processes over `multiprocessing.Queue` IPC — Process-1 traversal, Process-2 execution, Process-3 sole-modifier. No single process performs all three steps. Every write is serialized through Process-3 with an atomic replace.
4. **Condition C (external dispatch)**: a dispatcher reads the topology to schedule who/when but never evaluates an edge condition; the agent executes, modifies the on-disk file, and selects the next node from its result against the edge conditions.
5. **Measure**: for each condition, capture seven metrics — topology determination, result-dependent routing, self-modification, modification persistence, functional equivalence, node-count delta, edge-count delta — and assert B == A and C == A by structural diff and content hash of the final on-disk graph.

## Files Included

| File | Purpose |
|------|---------|
| README.md | This file — study description, results, analysis |
| graph_initial.json | Shared deterministic starting graph substrate (reused by STUDY-204) |
| baseline_single_process.py | Condition A + the shared substrate primitives imported by B and C |
| decomposed_agents.py | Condition B — three cooperating processes (traversal / execution / sole modifier) |
| external_dispatch.py | Condition C — external dispatcher (no routing) + executing agent |
| test_equivalence.py | Equivalence/conformance harness; captures the 7 metrics, asserts B == A and C == A |
| results.json | Machine-readable results (metrics per condition + verdicts) |

## Key Mechanism

The substrate *semantics* — how a node executes, how the execution result selects an outgoing edge, how a self-modification is applied and atomically persisted — are defined once (in `baseline_single_process.py`) and shared by all three conditions. What differs between conditions is only the *embodiment*: a single process, a three-process decomposition, or an external dispatcher plus an agent. Isolating the embodiment this way is what makes the equivalence result meaningful: the same mechanism is exercised under each arrangement, so an identical final state shows the mechanism is process-architecture-independent.

Two disciplines carry the decomposition:

- **Sole-modifier write serialization (Condition B).** Three processes cooperate, but only Process-3 ever writes the graph file, and it writes with an atomic replace. The next traversal step always reads the modified-and-persisted graph. Because writes are serialized through one modifier, repeated runs are bit-for-bit identical — the empirical signature of multi-writer consistency, not merely an incidental match.
- **Dispatch without routing (Condition C).** The dispatcher reads topology only to decide who acts and when. It never reads node content to compute a path and never evaluates an outgoing-edge condition; it follows whatever next node the agent reports. The routing decision is the execution result against the substrate's edge conditions — the agent's, not the orchestrator's.

## Results

### Test 1: Functional equivalence (acceptance gate)

All three conditions traverse `start → compute → branch → grow → audit → finalize`, take the `branch → grow` edge from the `classify` result `high`, add the `audit` node and the `grow → audit` and `audit → finalize` edges by self-modification, and end with the identical canonical final graph.

| Condition | Embodiment | Final graph == A | Node Δ | Edge Δ |
|-----------|------------|------------------|--------|--------|
| A | single process | baseline | +1 | +2 |
| B | three processes | **yes** (identical hash) | +1 | +2 |
| C | external dispatch | **yes** (identical hash) | +1 | +2 |

**Result**: B == A and C == A by structural diff and content hash — functional equivalence holds across the embodiment shift.

### Test 2: Mechanism-axis properties survive the shift

For every condition the seven metrics record: topology determination = true, result-dependent routing = true, self-modification = true, modification persistence = true, functional equivalence = true.

**Result**: The three mechanism-axis properties are present and identical in all three embodiments.

### Test 3: Multi-writer consistency (Condition B)

Condition B was run repeatedly; every run produced the identical final graph hash, with exactly one writer process (the sole modifier).

**Result**: The decomposed run is deterministic across runs — writes are serialized, not racing.

### Test 4: Dispatch does not route (Condition C)

The dispatcher never evaluated an edge condition; the next node it followed equals the substrate's result-against-edge-condition selection.

**Result**: Routing came from the execution result against the substrate, not from the dispatcher's logic.

## Conclusions

### Core Finding

**The graph substrate governs computation independent of process boundaries: decomposing the agent across cooperating processes, or fronting it with an external dispatcher, produces a final substrate state functionally equivalent to a single in-process agent.**

### Properties Demonstrated

1. **Topology-as-program across the decomposition**: in every condition the on-disk serialized graph file is the shared executed medium; the IPC and dispatch channels carry only coordination messages, never the substrate as an in-memory object.
2. **Result-driven edge selection across the decomposition**: the execution result against the substrate's edge conditions selects the next node in every condition; the dispatcher in Condition C is explicitly forbidden from routing from its own logic.
3. **Structural liveness across the decomposition**: a self-modification triggered during execution persists to the on-disk file and affects subsequent traversal, including under a three-writer decomposition mediated by a sole-modifier discipline.

### Distinguishing note

This study demonstrates that the substrate, not the process arrangement, is the locus of computation. Throughout each run the program **is** the on-disk serialized graph file: each process reads the current graph from that file and writes modifications back to it, and traversing the file is executing it. This is distinct from orchestration approaches in which a topology is compiled into a fixed runtime before execution and inter-step state is passed as ephemeral in-memory values, and distinct from agent-network approaches whose shared state lives in a message or token space rather than in a persisted, self-modifiable serialized file. Here the coordinating or dispatching process does **not** drive routing — the execution result against the substrate's own edge conditions does — and the substrate is modified in place and persisted during execution.

### Scope of the claim demonstrated

This is a reduction-to-practice of the **specific demonstrated species**: a three-process decomposition (traversal / execution / sole modifier) and a single external dispatcher with one executing agent. It does **not** assert an unbounded "any multi-agent system" or "any orchestrator" genus, and it does not by itself establish enablement for an unbounded number of concurrent writers. Patent claim drafting and the scope of any genus claim are out of scope for this engineering study and are the patent counsel's responsibility.

## How to Run

```bash
cd studies/STUDY-203-Decomposed-Agent-Systems
python baseline_single_process.py    # Condition A (single process)
python decomposed_agents.py          # Condition B (three processes)
python external_dispatch.py          # Condition C (external dispatch)
python test_equivalence.py           # run all three + regenerate results.json
pytest test_equivalence.py -v        # run the equivalence test suite
```

**Requirements**: Python 3.10+ (standard library only — no external dependencies).

## Related Studies

- **STUDY-204** (storage independence): reuses this study's `graph_initial.json` baseline unchanged — the fixture is authored with a generic node/edge schema for that cross-study dependency.
- **STUDY-202** (multi-file substrate): demonstrates the multi-FILE broadening (spawn-and-supersede); cited here only as the deliverable-shape pattern. It relocates a different limitation (file identity) and is not evidence for the multi-process broadening this study proves.

## Date Evidence

**Study Date**: June 2026
**Git History**: Available in repository commit log
**Patent Application**: 19/575,491 (Non-Provisional) — Patent Pending; this study is published under AGPL-3.0.
