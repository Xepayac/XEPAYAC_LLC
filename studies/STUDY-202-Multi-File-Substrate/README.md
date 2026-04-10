# STUDY-202: Multi-File Graph Substrate

## Classification: PUBLIC

## Abstract

This study demonstrates that a graph substrate is not a single serialized file — it is the connected set of all files linked by cross-file edges. An agent executing graph-A creates graph-B with a SUPERSEDES edge pointing at graph-A. The original file is never modified. The program governing the agent changed during execution. The substrate grew. This is self-modification of the substrate through indirection: spawn-and-supersede.

## Study ID
**STUDY-202**

## Title
Multi-File Graph Substrate

## Purpose

Demonstrate that:
1. A graph substrate can span multiple serialized files connected by cross-file edges
2. An agent can change the executing program by spawning a new file rather than modifying the original
3. Spawn-and-supersede is functionally equivalent to single-file self-modification
4. The substrate is the connected graph, not the file

## Patent References
- **Patent Application 19/575,491**: System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
- **Claim 1**: System — self-modification by writing changes during execution
- **Claim 2**: Method — self-modification by writing changes during execution
- **Claim 8**: Modifications include adding new nodes and edges that persist and affect subsequent traversals

## Hypothesis

**H1**: An agent can create a new graph file with a SUPERSEDES edge that changes which graph governs execution, without modifying the original file.

**H2**: The connected set of graph files constitutes a single substrate whose topology changes when new files are added.

**H3**: Single-file self-modification and spawn-and-supersede produce the same functional outcome: the program governing the agent changed during execution.

**H4**: Chained supersession (A→B→C) produces unbounded substrate growth with zero modification of existing files.

## Study Date
**April 2026**

## Method

### Scenario 1: Single-File Self-Modification (Baseline)

Agent executes a graph stored in one file. During execution, agent adds a node and edges to the same file. The file is modified. This is classic self-modification as described in the patent.

### Scenario 2: Spawn-and-Supersede

Agent executes graph-A from file-A. During execution, agent creates graph-B in file-B. Graph-B contains a SUPERSEDES edge pointing at graph-A. Agent switches execution to graph-B. File-A is never modified.

Verified:
- File-A is byte-identical before and after
- The substrate (connected set of both files) grew
- The active graph changed from A to B
- The program governing the agent changed

### Scenario 3: Chain of Supersessions

Three graphs: A, B, C. Each supersedes the previous. No file is ever modified after creation. The substrate grows with each spawn. The active graph progresses: A → B → C.

Verified:
- Neither A nor B is modified when C is created
- Cross-file SUPERSEDES edges form a chain
- The substrate spans 3 files with 12 total nodes
- The active graph is always the latest in the chain

## Files Included

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `multi_file_substrate.py` | Core implementation: Substrate class, 3 scenarios | 260 |
| `test_multi_file_substrate.py` | 12 pytest tests validating all hypotheses | 195 |
| `results.json` | Test results (PASS status) | 42 |

## Key Mechanism

The `Substrate` class models the connected set of graph files:

- `register(graph_id, path)` — adds a file to the substrate
- `total_nodes` / `total_edges` — counts across all files
- `cross_file_edges()` — finds edges that reference nodes across files
- `active_graph_id()` — determines which graph governs execution by following SUPERSEDES edges

A SUPERSEDES edge means: "this graph replaces that graph as the governing program." The target of SUPERSEDES is the old graph. The source is the new graph. The substrate resolves governance by finding which graph is not superseded.

## Key Results

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| H1: Spawn-and-supersede without file modification | **PASS** | File-A byte-identical after graph-B creation. Active graph changed to B. |
| H2: Multi-file substrate | **PASS** | Substrate spans 2 files. 9 total nodes, 7 total edges. 1 cross-file edge. |
| H3: Functional equivalence | **PASS** | Both single-file and spawn-and-supersede result in program change during execution. |
| H4: Chained supersession | **PASS** | 3 files, 12 nodes, 2 cross-file edges. Active graph is C. No file modified after creation. |

### Validation Checks (9/9 PASS)

- Original file unmodified
- Substrate spans multiple files
- Cross-file SUPERSEDES edge exists
- Active graph changed to graph_b
- Program changed without modifying original
- Substrate grew (new nodes added)
- Chain: 3 files in substrate
- Chain: active graph is latest
- Chain: program changed twice

## Key Insight

**The substrate is the connected graph, not the file.**

Current patent claim language says "a graph substrate stored as a serialized file." This study demonstrates that the substrate can span multiple serialized files. The SUPERSEDES edge connects them into a single substrate. Writing a new file with cross-file edges is modification of the substrate — the topology changed, the governance changed, the program changed.

Spawn-and-supersede achieves the same functional outcome as single-file self-modification:
- The program governing the agent changed during execution
- No process restart or code redeployment occurred
- The change persists and affects subsequent traversals

The only difference is mechanism: same-file write vs. new-file write with cross-file edge. The substrate grew in both cases. The program evolved in both cases.

## Patent Implications

This study provides evidence that:

1. **Self-modification is a substrate property, not a file property.** The substrate is the connected set of all graph files. Modification of the substrate includes creating new files with edges that change the topology.

2. **SUPERSEDES is a self-modification primitive.** When graph-B SUPERSEDES graph-A, the program that governs the agent changed. This is self-modification even though file-A was not touched.

3. **Chained supersession is unbounded self-modification.** Each spawn adds nodes and edges to the substrate. The program evolves through a chain of supersessions with no file ever modified after creation.

4. **The mechanism (same-file vs. new-file) does not change the outcome.** Both produce a program that changed itself during execution. Both require no restart. Both persist.

## How to Run

```bash
cd studies/STUDY-202-Multi-File-Substrate
python multi_file_substrate.py           # Run demo with validation
pytest test_multi_file_substrate.py -v   # Run 12 tests
```

**Requirements**: Python 3.10+ (standard library only — no external dependencies)

## Related Studies

- **STUDY-109**: Graph Mutation — single-file self-modification via propose-validate-apply
- **STUDY-180**: Living Graph — persistent accumulating graph state across sessions
- **STUDY-201**: Agent Negotiation Protocol — multi-agent coordination on shared graph state

## Date Evidence

**Study Date**: April 4, 2026
**Git History**: Available in repository commit log
**Patent Application**: 19/575,491 (Non-Provisional)
