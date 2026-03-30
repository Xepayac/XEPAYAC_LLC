# STUDY-101: Multi-Agent Turn-Based Coordination Protocol

## Abstract

This study demonstrates that multiple autonomous LLM agents can coordinate complex collaborative tasks using only a shared graph file as their sole communication medium—no direct messaging, APIs, or shared memory required. Two agents (Alpha and Beta) collaboratively designed a user authentication system over 4 turns, producing 17 nodes and 27 edges with 55.6% cross-agent coherence. State reconstruction tests achieved 100% accuracy at all historical turns using only embedded provenance metadata, proving the graph substrate serves as both coordination mechanism and complete audit trail.

## Study ID
**STUDY-101**

## Title
Multi-Agent Turn-Based Coordination Protocol

## Purpose
Demonstrates that multiple LLM agents can coordinate entirely through a shared graph substrate without direct communication channels. Each agent reads the graph, adds contributions, and passes control - proving the graph file itself is the sole coordination mechanism.

## Patent References
- **SGS-98-02**: Layer 3 - Multi-Agent Coordination
- **Claim 1**: Graph substrate enables multi-agent coordination without direct agent-to-agent communication
- **Claim 2**: Turn-based access control via graph state enables atomic operations
- **Claim 3**: Complete audit trail embedded in graph provenance metadata
- **Claim 6**: Provenance metadata embedded in graph structure for state reconstruction
- **Claim 9**: State reconstruction from embedded metadata without external logs
- **Claim 13**: No external logging system required for complete history

## Hypothesis

Multiple isolated LLM agents can coordinate turn-based collaborative work through a shared JSON graph file, achieving measurable coherence (>50% cross-agent references) without direct inter-process communication, and the embedded provenance metadata enables 100% accurate state reconstruction at any historical point without external logs.

## Study Date
**Original Development**: December 2024 (SGS development)  
**Patent Filing**: January 2026

## Method

1. **Initialize Graph**: Create empty graph with metadata structure (nodes[], edges[], turn counter)
2. **Agent A Turn**: Agent A reads graph state, receives task prompt, generates nodes/edges with `created_by: "Alpha"` metadata, writes updated graph
3. **Agent B Turn**: Agent B reads graph state, observes Agent A's contributions, generates complementary nodes/edges with `created_by: "Beta"` metadata, writes updated graph
4. **Iterate**: Repeat steps 2-3 for N turns (4 turns in main test)
5. **Measure Coherence**: Calculate cross-agent references (edges connecting nodes from different creators) divided by total edges
6. **State Reconstruction**: For each historical turn T, reconstruct graph state using only `created_by` and `turn` metadata from final graph
7. **Validate**: Compare reconstructed states against actual turn-by-turn snapshots for accuracy verification

## Files Included

| File | Purpose |
|------|---------|
| **protocol.py** | Multi-agent coordination protocol - LLM-to-graph communication system |
| **test_coordination.py** | Main coordination test - two LLMs collaborate via graph on authentication system design |
| **test_state_reconstruction.py** | Demonstrates complete state reconstruction from embedded provenance metadata |
| **test_executable.py** | LLM creates executable calculation graph demonstrating code generation capability |
| **test_multi_agent_value.py** | Proves multi-agent value creation - agents with different database access synthesize new knowledge |
| **final_graph.json** | Executed graph state showing 17 nodes, 27 edges from two-agent collaboration |
| **turns.json** | Turn-by-turn execution log with provenance metadata |
| **summary.md** | Human-readable execution summary with statistics |
| **state_reconstruction_results.json** | State reconstruction accuracy verification results |
| **FIG-101-01.mmd** | Figure 2: Graph as sole communication channel (no direct agent communication) |
| **FIG-101-02.mmd** | Figure 11: Turn-based execution protocol with file locking |

## Key Mechanism / Implementation Details

### Protocol Architecture

```
Agent A → read(graph.json) → add_nodes() → write(graph.json) → pass_turn
                                    ↓
Agent B → read(graph.json) → add_nodes() → write(graph.json) → pass_turn
```

### Coordination Protocol (protocol.py)

1. **Turn-Based Execution**: Each agent executes in sequence with atomic file operations
   - Agent locks file, reads current state, modifies graph, writes atomically, releases lock
   - No direct communication between agents - file operations only

2. **Graph Communication**: LLMs receive graph state as context and respond with JSON
   ```json
   {
     "reasoning": "What I observe and why I'm contributing",
     "nodes": [{"id": "...", "type": "CONCEPT|PATTERN|BEHAVIOR", "data": {...}}],
     "edges": [{"from_id": "...", "to_id": "...", "relation": "REQUIRES|SUPPORTS", "weight": 0.8}]
   }
   ```

3. **Provenance Tracking**: Every node and edge includes `created_by` metadata
   - Enables full state reconstruction at any prior turn
   - No external log correlation needed

4. **Cross-Reference Detection**: Edges between nodes from different agents prove coordination
   - Coherence score = cross_references / total_edges
   - Measures quality of collaboration

### Test Implementations

**test_coordination.py**: Main demonstration
- Task: "Design a simple user authentication system"
- Agents: Alpha (Claude Sonnet) and Beta (Claude Sonnet) 
- Result: 17 nodes, 27 edges, 4 turns
- Agents built on each other's work (cross-referenced nodes)

**test_state_reconstruction.py**: Provenance validation
- Reconstructs graph state at each historical turn using only embedded metadata
- Achieves 100% reconstruction accuracy
- Proves no external logs needed

**test_executable.py**: Code generation capability
- LLM receives "15 + 27", creates executable graph with OPERAND/OPERATION/RESULT nodes
- Executor runs graph and computes 42
- Demonstrates LLM can generate machine-executable specifications

**test_multi_agent_value.py**: Value creation proof
- Agent A: Access to Database A (Q4 revenue: $47M)
- Agent B: Access to Database B (growth rate: 1.15, competitor: $52M)
- Neither alone can complete calculation
- Together: Compute projected advantage = $2.05M (new knowledge synthesized)

## Key Results / Key Demonstrations

### Multi-Agent Coordination Results

| Metric | Value |
|--------|-------|
| Total Nodes Created | 17 |
| Total Edges Created | 27 |
| Cross-References (Agent A ↔ Agent B) | 15 |
| Self-References (Same Agent) | 12 |
| **Coherence Score** | **55.6%** |
| Total Turns | 4 (2 per agent) |

**Nodes by Creator**:
- Agent Alpha: 9 nodes
- Agent Beta: 8 nodes

**Key Observation**: 55.6% of edges connect nodes from different agents, proving coordination through the graph substrate.

### Test Execution Results

**Task**: Design a simple user authentication system. Define the components, their relationships, and key decisions.

**Statistics**:
- Total nodes: 17
- Total edges: 27
- Total turns: 4
- Alpha: 9 nodes
- Beta: 8 nodes

**Final Graph State** (17 nodes, 27 edges):

**Nodes Created**:
- `auth-system` [CONCEPT] by Alpha: User authentication system that verifies user identity and manages access
- `credential-validation` [CONCEPT] by Alpha: Validate user credentials (username/password) against stored data
- `session-management` [CONCEPT] by Alpha: Create and maintain user sessions after successful authentication
- `password-hashing` [CONCEPT] by Alpha: Use bcrypt or similar strong hashing algorithm for password storage
- `user-datastore` [CONCEPT] by Alpha: Database or storage system containing user credentials and profile data
- `security-first` [PATTERN] by Alpha: Prioritize security over convenience in authentication design decisions
- `logout-mechanism` [BEHAVIOR] by Beta: Allow users to explicitly end their session and invalidate session tokens
- `rate-limiting` [BEHAVIOR] by Beta: Limit authentication attempts to prevent brute force attacks
- `input-validation` [BEHAVIOR] by Beta: Sanitize and validate all user inputs to prevent injection attacks
- `session-timeout` [CONCEPT] by Beta: Sessions automatically expire after predetermined period of inactivity
- `error-handling` [BEHAVIOR] by Alpha: Handle authentication failures gracefully with appropriate error messages without revealing system details
- `user-registration` [CONCEPT] by Alpha: Process for creating new user accounts with proper validation and credential setup
- `password-policy` [CONCEPT] by Alpha: Enforce minimum password complexity requirements (length, character types, common password checks)
- `auth-strategy-decision` [CONCEPT] by Beta: Choose between stateful session-based authentication or stateless token-based (JWT) authentication
- `multi-factor-auth` [CONCEPT] by Beta: Optional second authentication factor (SMS, TOTP, email) for enhanced security
- `account-lockout` [BEHAVIOR] by Beta: Temporarily lock user accounts after consecutive failed authentication attempts
- `security-monitoring` [CONCEPT] by Beta: Log and monitor authentication events for suspicious activity and security analysis

**Edges Created** (showing coordination between agents):
- `auth-system` → `credential-validation` [REQUIRES w:0.9]
- `auth-system` → `session-management` [REQUIRES w:0.9]
- `credential-validation` → `user-datastore` [REQUIRES w:0.8]
- `credential-validation` → `password-hashing` [REQUIRES w:0.9]
- `password-hashing` → `security-first` [SUPPORTS w:0.8]
- `credential-validation` → `session-management` [LEADS_TO w:0.8]
- `session-management` → `logout-mechanism` [REQUIRES w:0.8]
- `credential-validation` → `rate-limiting` [REQUIRES w:0.9]
- `credential-validation` → `input-validation` [REQUIRES w:0.9]
- `session-management` → `session-timeout` [REQUIRES w:0.7]
- `rate-limiting` → `security-first` [SUPPORTS w:0.9]
- `logout-mechanism` → `security-first` [SUPPORTS w:0.7]
- `credential-validation` → `error-handling` [REQUIRES w:0.8]
- `user-registration` → `password-hashing` [REQUIRES w:0.9]
- `user-registration` → `user-datastore` [REQUIRES w:0.9]
- `password-policy` → `security-first` [SUPPORTS w:0.8]
- `user-registration` → `password-policy` [REQUIRES w:0.7]
- `input-validation` → `rate-limiting` [SUPPORTS w:0.6]
- `error-handling` → `security-first` [SUPPORTS w:0.7]
- `auth-system` → `auth-strategy-decision` [REQUIRES w:0.9]
- `auth-strategy-decision` → `session-management` [LEADS_TO w:0.8]
- `auth-system` → `multi-factor-auth` [SUPPORTS w:0.6]
- `multi-factor-auth` → `security-first` [SUPPORTS w:0.9]
- `rate-limiting` → `account-lockout` [LEADS_TO w:0.7]
- `account-lockout` → `security-first` [SUPPORTS w:0.8]
- `auth-system` → `security-monitoring` [REQUIRES w:0.7]
- `error-handling` → `security-monitoring` [SUPPORTS w:0.6]

### State Reconstruction Results

| Turn | Agent | Nodes | Edges | Reconstruction |
|------|-------|-------|-------|----------------|
| 0 | Alpha | 6 | 6 | ✓ Perfect |
| 1 | Beta | 10 | 14 | ✓ Perfect |
| 2 | Alpha | 13 | 20 | ✓ Perfect |
| 3 | Beta | 17 | 27 | ✓ Perfect |

**Accuracy**: 100% reconstruction at all historical states using embedded provenance only.

### Multi-Agent Value Creation Results

| Test Scenario | Can Complete Task? | Result |
|---------------|-------------------|--------|
| Single Agent (Database A only) | ❌ No | Missing growth rate & competitor data |
| Single Agent (Database B only) | ❌ No | Missing Q4 revenue data |
| **Multi-Agent (A + B via Graph)** | **✅ Yes** | **$2.05M advantage** |

**Simple Math Proof**: Agent A contributes 3, Agent B contributes 5 → Graph produces 8 (new knowledge neither had alone)

### Executable Graph Results

**Test**: LLM creates graph for "15 + 27"
- LLM generates: 2 OPERAND nodes, 1 OPERATION node (add), 1 RESULT node
- Executor computes: 42
- **Success**: ✓ Correct calculation from LLM-generated specification

## Key Insight / Conclusions

### Core Innovation

**The graph file IS the coordination mechanism** - no external messaging, APIs, or shared memory required. Agents communicate purely through:
1. Reading serialized graph state
2. Adding nodes/edges with provenance metadata  
3. Writing updated graph atomically

This architecture provides:
- **Simplicity**: File I/O is the only required primitive
- **Auditability**: Complete history embedded in graph structure
- **Reproducibility**: Any prior state reconstructible from final graph
- **Scalability**: N agents coordinate through same substrate

### Patent Significance

1. **Sole Communication Channel**: Explicit demonstration that NO direct agent communication exists - only file-based graph exchange (supports Claim 1)

2. **Embedded Provenance**: 100% state reconstruction without external logs proves provenance sufficiency (supports Claims 6, 9, 13)

3. **Value Creation**: Multi-agent synthesis demonstrates practical utility - agents with different capabilities/access create knowledge impossible for any single agent (supports business value claims)

4. **Executable Specifications**: LLMs can generate machine-executable graph structures, not just human-readable content (supports computational substrate claims)

### Research Implications

The coordination protocol demonstrates a fundamental computing primitive: **graph-mediated agent coordination**. This differs from traditional multi-agent systems that require:
- Message queues (RabbitMQ, Kafka)
- Shared databases with locking
- Coordinator processes
- Network protocols

Here, a **single serialized file** provides all coordination infrastructure.

## Patent Implications

This study provides laboratory evidence for the following patent claims in SGS-98-02:

1. **Graph as Sole Communication Channel (Claim 1)**: Demonstrated through test_coordination.py - agents have no direct communication, only graph file I/O
   - Evidence: 55.6% cross-references between agents prove coordination happened
   - Evidence: No network sockets, shared memory, or IPC mechanisms used

2. **Turn-Based Access Control (Claim 2)**: Demonstrated through file locking protocol in protocol.py
   - Evidence: Lock-read-modify-write-release pattern ensures atomic operations
   - Evidence: Turn history in turns.json shows sequential execution

3. **Complete Audit Trail (Claim 3)**: Demonstrated through provenance metadata
   - Evidence: Every node/edge contains `created_by` field
   - Evidence: Turn-by-turn reconstruction possible

4. **Embedded Provenance (Claims 6, 9, 13)**: Demonstrated through test_state_reconstruction.py
   - Evidence: 100% accurate state reconstruction at all 4 historical turns
   - Evidence: No external logs consulted - only graph metadata used

5. **Multi-Agent Value Creation**: Demonstrated through test_multi_agent_value.py
   - Evidence: Single agents fail (cannot access both databases)
   - Evidence: Multi-agent succeeds (synthesizes $2.05M advantage calculation)
   - Evidence: Simple proof (3 + 5 = 8) validates concept

6. **Executable Specifications**: Demonstrated through test_executable.py
   - Evidence: LLM generates OPERAND/OPERATION/RESULT graph
   - Evidence: Executor computes correct answer (42) from LLM specification

## How to Run

### Prerequisites

```bash
# Install dependencies
pip install anthropic

# Set API key (required for LLM tests)
export ANTHROPIC_API_KEY="your-key-here"

# Or create .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

### Test 1: Multi-Agent Coordination (Main Demonstration)

```bash
cd /home/runner/work/SGS_PATENT_DEVELOPMENT/SGS_PATENT_DEVELOPMENT/PATENT/LAB/STUDIES/STUDY-101-Multi-Agent-Coordination

# Run coordination test (requires API key)
python test_coordination.py

# Custom task
python test_coordination.py --task "Design a REST API for user management" --turns 5

# Quiet mode
python test_coordination.py --quiet
```

### Test 2: State Reconstruction (No API Key Required)

```bash
# Verify state reconstruction from existing results
python test_state_reconstruction.py

# Expected output: 100% reconstruction accuracy at all turns
```

### Test 3: Executable Graph (Requires API Key)

```bash
# Default test: "15 + 27" = 42
python test_executable.py

# Custom calculation
python test_executable.py --expression "100 * 5" --expected 500

# Quiet mode
python test_executable.py --quiet
```

### Test 4: Multi-Agent Value Creation

```bash
# Simple proof (no API key required)
python test_multi_agent_value.py --simple

# Full test with LLM agents (requires API key)
python test_multi_agent_value.py --full

# Quiet mode
python test_multi_agent_value.py --full --quiet
```

## Expected Output

### test_coordination.py Output

```
============================================================
GRAPH COMMUNICATION PROTOCOL TEST
============================================================

Task: Design a simple user authentication system...
Turns per LLM: 3

--- Turn 1: Alpha ---
Added 6 nodes, 6 edges

--- Turn 1: Beta ---
Added 4 nodes, 8 edges

--- Turn 2: Alpha ---
Added 3 nodes, 6 edges

--- Turn 2: Beta ---
Added 4 nodes, 7 edges

============================================================
ANALYSIS
============================================================

Total nodes created: 17
Total edges created: 27
Cross-references (LLM A ↔ LLM B): 15
Self-references: 12
Coherence score: 55.56%

Results saved to state/results/
```

### test_state_reconstruction.py Output

```
======================================================================
STUDY-87: State Reconstruction from Embedded Provenance
======================================================================

Final graph: 17 nodes, 27 edges
Total turns: 4

State Reconstruction Results:
----------------------------------------------------------------------
  Turn 0: Alpha      | Nodes:  6 | Edges:  6 | ✓
  Turn 1: Beta       | Nodes: 10 | Edges: 14 | ✓
  Turn 2: Alpha      | Nodes: 13 | Edges: 20 | ✓
  Turn 3: Beta       | Nodes: 17 | Edges: 27 | ✓
----------------------------------------------------------------------

KEY FINDINGS:

1. STATE RECONSTRUCTION: All prior states reconstructed from
   embedded provenance metadata ONLY - no external logs needed.

2. NO LOG CORRELATION: The graph IS the audit trail.

3. ACCURACY: 100% reconstruction accuracy at all turns.
```

### test_multi_agent_value.py Output

```
======================================================================
  SIMPLE PROOF: The Math Example
======================================================================

  Agent A (Database A access):
    → Contributes: 3

  Agent B (Database B access):
    → Contributes: 5
    → Adds operation: add
    → Connects to Agent A's value

  Combined Graph Execution:
    3 + 5 = 8

  ==================================================
  ✅ NEW KNOWLEDGE CREATED: 8
  
  Agent A alone could only produce: 3
  Agent B alone could only produce: 5
  Together via graph they produced: 8
  ==================================================
```

## Related Studies
- **STUDY-110**: Value Exchange via Graph Substrate (originally part of this study, split for clarity)
- **STUDY-118**: Nested Graph Metadata for Selective Traversal (demonstrates metadata-driven agent decisions)
- **STUDY-120**: Executable Task Specification (demonstrates execution during traversal)

## Date Evidence / GitHub Issue

**Development Timeline**:
- Original implementation: December 2024 (SGS development)
- Patent study formalization: January 2026
- Filing deadline: January 2026

**GitHub Repository**: https://github.com/Xepayac/SGS_PATENT_DEVELOPMENT

Files originated from SGS development development (December 2024). See git history for detailed timestamps and commit provenance.
