# STUDY-109: LLM-Directed Graph Mutation

## Abstract

This study demonstrates the propose-validate-apply pattern for LLM-directed graph mutations, where LLM outputs are parsed as structured JSON instructions, validated against schema rules, and applied atomically with rollback on failure. The mutation engine supports 5 operations (ADD_NODE, ADD_EDGE, UPDATE_NODE, DELETE_NODE, DELETE_EDGE) and validates required fields, node types (TASK, DECISION, CONTEXT, AGENT_OUTPUT, DATA), target existence, and duplicate prevention. Test results show: valid mutations correctly expanded graph (3→4 nodes, 2→3 edges), invalid mutations correctly rejected with detailed errors, and batch failures triggered atomic rollback restoring checkpoint state.

## Study ID
**STUDY-109**

## Title
LLM-Directed Graph Mutation

## Purpose

Demonstrate how LLM outputs are parsed and applied as graph mutations with:
- Structured output parsing
- Mutation validation
- Atomic rollback on failure
- Mutation protocol definition

## Patent References
- **SGS-98-01**: Layer 2 - Context Extension
- **SGS-98-03**: Layer 4 - LLM Orchestration
- **Claim 1**: System for applying LLM-generated mutations to graph
- **Claim 3**: Structured output parsing
- **Claim 5**: Validation before application
- **Claim 7**: Atomic rollback on failure

## Hypothesis

LLM outputs can be safely integrated into deterministic graph systems through a mutation protocol that parses structured JSON, validates against schema constraints before application, and provides atomic rollback on failure—ensuring the LLM proposes changes while the graph substrate controls all actual state modifications.

## Study Date
December 2024

## Method

1. **Define Mutation Protocol**: Create JSON schema supporting ADD_NODE, ADD_EDGE, UPDATE_NODE, DELETE_NODE, DELETE_EDGE operations
2. **Implement Mutation Parser**: Parse LLM JSON output into typed MutationInstruction objects
3. **Create Validation Layer**: Check required fields (id, type), valid node types (TASK, DECISION, CONTEXT, AGENT_OUTPUT, DATA), target existence for updates/deletes, no duplicates for additions
4. **Build Checkpoint System**: Snapshot graph state before applying batch mutations
5. **Test Valid Mutations**: Add node "new_task" (TASK), add edge, update task_1 with priority=high and assignee=Agent-A; verify graph expanded 3→4 nodes, 2→3 edges
6. **Test Invalid Mutations**: Submit mutations with missing type field, invalid node type, nonexistent update target; verify all rejected with detailed error messages
7. **Test Atomic Rollback**: Submit batch with 1 valid + 1 invalid mutation; verify valid applied then rolled back, final state equals checkpoint (3 nodes unchanged)
8. **Validate Audit Trail**: Confirm all mutation proposals and outcomes recorded for traceability

## Files Included

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `mutation_engine.py` | Core mutation engine with validation and rollback | 274 |
| `demo_mutations.py` | Demonstration script showing three test scenarios | 207 |
| `results.json` | Test results output (PASS status) | 10 |
| `FIG-109-01.mmd` | Mutation pipeline diagram | - |
| `FIG-109-02.mmd` | Validation flow diagram | - |
| `FIG-109-03.mmd` | Atomic rollback mechanism diagram | - |

## Key Mechanism

The mutation engine implements a propose-validate-apply pattern:

1. **Parse**: LLM outputs JSON with mutation instructions
2. **Validate**: Check schema, types, constraints before applying
3. **Apply**: Execute mutations on graph state
4. **Rollback**: On failure, restore checkpoint state

**Mutation Protocol** supports 5 operations:
- `ADD_NODE` - Create new node with type validation
- `ADD_EDGE` - Connect nodes with source/target
- `UPDATE_NODE` - Modify existing node data
- `DELETE_NODE` - Remove node and connected edges
- `DELETE_EDGE` - Remove specific connection

**Validation checks**:
- Required fields present (id, type)
- Valid node types (TASK, DECISION, CONTEXT, AGENT_OUTPUT, DATA)
- Target exists for updates/deletes
- No duplicates for additions

## Key Results

**Test 1: Valid Mutations** - PASS
- Added node "new_task" with type TASK
- Added edge new_task → task_1 with type depends_on
- Updated task_1 with priority=high and assignee=Agent-A
- Graph expanded: 3→4 nodes, 2→3 edges

**Test 2: Invalid Mutations** - PASS (correctly rejected)
- Missing type field → validation failed
- Invalid node type "INVALID_TYPE" → validation failed  
- Update to nonexistent node → validation failed

**Test 3: Atomic Rollback** - PASS
- Batch with 1 valid + 1 invalid mutation
- Valid mutation applied, then invalid triggered rollback
- Graph state restored to checkpoint (3 nodes unchanged)

## Key Insight

**The LLM PROPOSES, the graph substrate VALIDATES and APPLIES** - the LLM never directly modifies state. This separation enables:
- Schema validation before changes
- Atomic rollback on failure
- Complete audit trail of who proposed what
- Safe integration of LLM outputs into deterministic systems

The mutation protocol creates a clear contract between the non-deterministic LLM layer and the deterministic graph substrate.

## Patent Implications

This study provides evidence for multiple patent claims:

1. **Structured Output Parsing** (Claim 3) - Demonstrates parsing of LLM JSON into typed MutationInstruction objects with validation
2. **Mutation Validation** (Claim 5) - Shows pre-application validation against schema with detailed error reporting
3. **Atomic Rollback** (Claim 7) - Proves checkpoint-restore mechanism prevents partial state corruption
4. **Mutation Protocol** (Claim 1) - Implements complete CRUD protocol for graph modification

The propose-validate-apply pattern is novel in combining:
- Non-deterministic LLM outputs
- Deterministic state management
- Transactional semantics (atomicity)
- Structured mutation protocol

## How to Run

```bash
cd PATENT/LAB/STUDIES/STUDY-109-Graph-Mutation
python demo_mutations.py
```

**Requirements**: Python 3.7+ (uses dataclasses, standard library only)

## Expected Output

```
============================================================
STUDY-95: LLM-Directed Graph Mutation Demo
============================================================

Initial graph: 3 nodes, 2 edges
Nodes: ['task_1', 'task_2', 'decision_1']

----------------------------------------
Test 1: Valid mutations
----------------------------------------
LLM Output:
{"mutations": [{"type": "ADD_NODE", "target": "new_task", "payload": {"type": "TASK", "content": "Implement feature B"}}, {"type": "ADD_EDGE", "target": "edge_1", "payload": {"source": "new_task"...
Parsed 3 mutations
✅ ADD_NODE: new_task
✅ ADD_EDGE: edge_1
✅ UPDATE_NODE: task_1

After mutations: 4 nodes, 3 edges

----------------------------------------
Test 2: Invalid mutations (validation)
----------------------------------------
❌ ADD_NODE: bad_node
   Error: Missing required field: type
❌ ADD_NODE: bad_node_2
   Error: Invalid node type: INVALID_TYPE
❌ UPDATE_NODE: nonexistent
   Error: Node not found: nonexistent

----------------------------------------
Test 3: Atomic rollback on failure
----------------------------------------
Before: 3 nodes
After (with rollback): 3 nodes
All success: False
Rollback occurred: True
✅ ADD_NODE: will_be_rolled_back
❌ (triggered rollback) ADD_NODE: will_fail

============================================================
SUMMARY: LLM-Directed Graph Mutation Proven
============================================================

✅ Structured output parsing - JSON to MutationInstruction
✅ Mutation validation - schema and constraint checking
✅ Mutation protocol - ADD, UPDATE, DELETE for nodes and edges
✅ Atomic rollback - failed batch restores previous state

Evidence supports SGS-71 patent claims.
Results saved to results.json
```

## Related Studies

- **STUDY-108**: LLM Context Management - Shows how context flows into LLM layer
- **STUDY-110**: Graph State Persistence - Demonstrates saving/loading graph state
- **STUDY-95**: Basic Mutation Engine - Earlier prototype of this concept
- **STUDY-71**: LLM Output Validation - General validation patterns for LLM outputs

## Date Evidence / GitHub Issue

**Study Date**: December 2024  
**Last Updated**: January 2026  
**GitHub Issue**: SGS-71 (LLM-Directed Graph Mutation Protocol)  
**Related Issues**: SGS-98 (Multi-Layer Architecture)  
**Git History**: Available in repository commit log  
**Patent Application**: PROVISIONAL_PATENT_03 (SGS System)
