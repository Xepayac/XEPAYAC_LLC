# STUDY-201: Agent Negotiation Protocol

## Classification: PUBLIC

## Abstract

This study demonstrates a formal negotiation protocol for multi-agent coordination via append-only JSONL streams. Seven typed message actions (propose, critique, modify, approve, reject, query, answer) enable structured negotiation between autonomous agents and human reviewers. Convergence detection is deterministic — computable from the message log alone without re-executing any agent. Tests confirm: 3-party negotiation (two agents + human) converges in 3 rounds; approval invalidation on modify/reject is correct; escalation triggers at configurable round limits; human-in-the-middle participation is first-class, not observational. The wire format is observable, auditable, and replay-able.

## Study ID
**STUDY-201**

## Title
Agent Negotiation Protocol — JSONL-Based Multi-Agent Coordination

## Purpose
Demonstrates a formal protocol for multi-agent negotiation where autonomous agents and human reviewers reach consensus through structured message exchange. The protocol uses an append-only JSONL file as the sole communication channel — observable from outside, auditable without re-execution, and deterministically verifiable.

## Study Date
**March 2026**

## Patent References
- **EGS-979** (Application 19/575,491): System and Method for Executable Graph-Based Computation with Self-Modification by Autonomous Agents
  - **Claim 1**: System — graph substrate traversal constitutes execution, self-modification by writing changes to serialized file
  - **Claim 2**: Method — traversal, execution, and modification during execution
  - **Claim 5**: Execution state written into nodes — graph is simultaneously program and execution record
  - **Claim 8**: Modifications include adding nodes/edges, persist in serialized file, affect subsequent traversals
  - **Claim 11**: Execution completes when agent reaches node with no traversable outgoing edges — halting via topology

## Hypothesis

A structured negotiation protocol with typed message actions and deterministic convergence rules enables multiple autonomous agents to reach consensus on a shared plan, with full audit trail, without requiring direct inter-process communication, shared memory, or external orchestration infrastructure.

## Method

1. **Define Protocol**: 7 typed message actions covering the full negotiation lifecycle
2. **Define Wire Format**: Each message serialized as a single JSONL line with explicit sender, timestamp, action, plan version, and payload
3. **Define Convergence Rule**: All required participants must approve the same plan version with no subsequent modify or reject
4. **Implement Stream I/O**: Append-only JSONL with file locking (flock) for concurrent process safety
5. **Test 3-Party Negotiation**: Two autonomous agents + one human reviewer negotiate a shared plan
6. **Verify Convergence Detection**: Confirm convergence is deterministic from message log alone
7. **Verify Approval Invalidation**: Confirm modify/reject correctly invalidates prior approvals
8. **Verify Escalation**: Confirm escalation triggers when round limit exceeded without convergence

## Key Mechanism

### The Seven Message Actions

| Action | Purpose | Effect on Convergence |
|--------|---------|----------------------|
| **propose** | Submit initial or revised plan | Creates plan version; mandatory first action |
| **critique** | Identify issues without rejecting | Non-blocking feedback; does not reset approvals |
| **modify** | Submit revised plan addressing critiques | Increments plan version; invalidates ALL prior approvals |
| **approve** | Signal acceptance of current plan version | Version-specific; approval of v1 does not count toward v2 |
| **reject** | Signal unacceptability of current approach | Invalidates approver's own prior approval |
| **query** | Ask clarifying question | Enables threaded Q&A via response linking |
| **answer** | Respond to a prior query | Linked to originating query by message ID |

### Wire Format

Each message is a single JSON object on one JSONL line:

```
{"id":"<12-char-hex>","ts":"<ISO-8601-UTC>","agent":"<sender>","action":"<action>","plan_version":<int>,"payload":{...},"in_response_to":null}
```

Fields:
- `id` — unique 12-character hex identifier
- `ts` — UTC timestamp (temporal ordering)
- `agent` — explicit sender identification (no implicit "current agent")
- `action` — one of 7 typed actions
- `plan_version` — monotonically increasing integer
- `payload` — action-specific data (issues, summary, reason, etc.)
- `in_response_to` — optional message ID for Q&A threading

### Convergence Detection

The convergence algorithm is deterministic — given a set of messages, the result is always the same:

1. Find current plan version (max version across all messages)
2. Build approval map for current version only
3. If a modify or reject appears after an approval, that approval is invalidated
4. Check if all required participants have valid approvals on current version
5. If all present → converged. If not → list missing participants.

### Escalation

When the number of propose/modify rounds exceeds a configurable maximum and convergence has not been reached, the protocol signals escalation. The escalation target (typically a human reviewer) is called to break the deadlock.

### File I/O Safety

- **Append-only**: messages are never deleted or modified
- **File locking**: exclusive lock (flock) for writes, shared lock for reads
- **Atomic durability**: flush + fsync within lock before release
- **Concurrent safety**: multiple processes can safely read/write the same stream

## Key Results

### Test 1: 3-Party Negotiation — Happy Path

| Round | Agent | Action | Version | Outcome |
|-------|-------|--------|---------|---------|
| 1 | agent_a | propose | 1 | Initial plan submitted |
| 1 | agent_b | critique | 1 | 2 issues identified |
| 2 | agent_a | modify | 2 | Revised plan addressing critiques |
| 2 | agent_a | approve | 2 | Agent A approves own revision |
| 2 | agent_b | approve | 2 | Agent B satisfied |
| 2 | hitm | approve | 2 | Human approves |

**Result**: Converged at plan version 2, round 2. All 3 participants approved.

### Test 2: Approval Invalidation on Modify

Agent A approves version 1. Agent B modifies → version 2. Agent A's v1 approval does NOT carry to v2. Agent A must re-approve.

**Result**: Correctly requires re-approval after version change.

### Test 3: Rejection Invalidates Approval

Agent A approves version 1. Agent B rejects version 1. Agent B's approval (if any) is invalidated. Convergence requires Agent B to approve again.

**Result**: Rejection correctly resets approval state for the rejecting agent.

### Test 4: Escalation Trigger

3 rounds of propose/modify without convergence. Max rounds = 3. Escalation flag set.

**Result**: `escalation_needed = true` when round count exceeds maximum without convergence.

### Test 5: Human Override

Human reviewer (hitm) can propose, modify, critique, reject — not just approve. Human modification creates new version that agents must re-approve.

**Result**: Human is first-class participant with full action authority.

### Test 6: Convergence Without Human

Two agents negotiate without human participant. Convergence detected when both approve same version.

**Result**: Protocol works with any number of participants, human participation is optional.

## Conclusions

### Core Finding

**A 7-action typed message protocol over append-only JSONL enables deterministic multi-agent negotiation with full audit trail.** The protocol requires no direct inter-process communication, no shared memory, no message queues, and no external orchestration infrastructure.

### Properties Demonstrated

1. **Observable**: The JSONL stream is human-readable and machine-parseable. Negotiation state is visible to any process that can read the file.

2. **Deterministic**: Convergence is computable from the message log alone. No agent re-execution required to determine outcome.

3. **Auditable**: Every message has explicit sender, timestamp, and action. The complete negotiation history is preserved.

4. **Version-safe**: Plan versions are monotonically increasing. Approvals are version-scoped. Modifications invalidate prior approvals.

5. **Escalation-aware**: Deadlocks are formally detected and escalated, not silently ignored.

6. **Human-compatible**: Human reviewers participate with the same protocol as autonomous agents. No separate human interface required.

### The Wire Format as Fingerprint

The combination of 7 typed actions, version-scoped approvals, deterministic convergence, and JSONL wire format creates a distinct protocol signature. Any system implementing this negotiation pattern — regardless of programming language, agent framework, or deployment model — produces recognizable message streams.

## Related Studies
- **STUDY-101**: Multi-agent coordination via shared graph (foundational)
- **STUDY-104**: Process isolation via file coordination
- **STUDY-106**: JSON serialization with atomic writes
- **STUDY-110**: Value exchange between agents via graph operations
