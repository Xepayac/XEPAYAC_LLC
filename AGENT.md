# AGENT.md — Xepayac LLC / SGS

<trl>
DEFINE "xepayac_llc" AS NAMESPACE.
NAMESPACE xepayac_llc CONTAINS MODULE sgs AND MODULE studies.
MODULE sgs GOVERNS INTERFACE graph_execution.
MODULE studies REFERENCES MODULE sgs.
</trl>

## What This Repository Is

This is Xepayac LLC's research publication of the **Superseding Graph Substrate (SGS)** — graph-as-executable-program. The graph is not a description of a program; it *is* the program. A topology-driven executor walks it, agents mutate shared graph state, transforms rewrite structure, and provenance records every mutation.

- **Reference implementation** — `src/sgs/` — Python library (v0.4.0, Alpha). Executor, agent, graph, models, provenance, transform.
- **Studies** — `studies/` — 16 experiments validating SGS capabilities (multi-agent coordination, self-modification, living graphs).
- **Patent** — U.S. application **19/575,491**. The Python code is the evidence; the Go product (forthcoming) is what you buy.

<trl>
NAMESPACE xepayac_llc REFERENCES ENDPOINT "https://github.com/Xepayac/XEPAYAC_LLC".
MODULE sgs CONTAINS 16 UNIQUE RECORD study.
EACH RECORD study IMPLEMENTS A RECORD capability.
</trl>

## Rules for This Repository

<trl>
AGENT claude MAY READ FILE folder.trug.json 'for RECORD structure.
AGENT claude SHALL VALIDATE EACH RECORD change SUBJECT_TO PROCESS trugs-folder-check.
AGENT claude SHALL_NOT WRITE ANY FILE 'that 'is INVALID 'under INTERFACE TRL.
AGENT claude SHALL DEFINE RESOURCE pull_request THEN SEND RESULT TO PARTY human THEN EXIT.
AGENT claude SHALL_NOT MERGE ANY RESOURCE TO ENDPOINT main.
</trl>

Key entry points:

| Path | Content |
|------|---------|
| `folder.trug.json` | Structural truth — every file, every folder, every edge |
| `README.md` | Company-facing landing page — SGS thesis, offerings, licensing |
| `src/sgs/` | Python reference implementation |
| `studies/` | Capability proofs (STUDY-101 … STUDY-180) |
| `CONTRIBUTING.md` | Branch naming, CI gates, CLA requirement |
| `CLA.md` | Contributor License Agreement — dual-license grant |

Every public `def` or `class` in `src/sgs/` carries a TRUG/L preamble stating its obligation. Absence of a preamble on a public contract is a compliance violation.

## Companion Repositories

- [TRUGS-LLC/TRUGS](https://github.com/TRUGS-LLC/TRUGS) — TRUGS specification (CORE + TRL vocabulary, Apache-2.0). SGS consumes it as the graph storage format.
- [TRUGS-LLC/TRUGS-TOOLS](https://github.com/TRUGS-LLC/TRUGS-TOOLS) — `tg` CLI for TRUG validation and rendering.
- [TRUGS-LLC/TRUGS-STORE](https://github.com/TRUGS-LLC/TRUGS-STORE) — backend storage for TRUGs.
- [TRUGS-LLC/TRUGS-AGENT](https://github.com/TRUGS-LLC/TRUGS-AGENT) — LLM framework (TRL + AAA + EPIC + Memory).

TRUGS-LLC repos describe the open format; this repo is the proprietary research + commercial-license substrate built on top.

## License and Status

- **License:** AGPL-3.0. Commercial deployment requires a separate license from Xepayac LLC (<xepayacllc@gmail.com>).
- **Status:** Alpha, v0.4.0. Active development. CLA-gated contributions.
- **Upstream:** TRUGS (Apache-2.0) is consumed but not absorbed. See `NOTICE` for attribution.

<trl>
NAMESPACE xepayac_llc SUBJECT_TO FILE LICENSE.
FILE CLA GOVERNS EACH RECORD contribution.
AGENT claude SHALL REFERENCE FILE NOTICE 'for RECORD attribution.
</trl>
