# AGENT.md — Xepayac LLC

Instructions for LLM agents working in this repository.

## What this repo is

`Xepayac/XEPAYAC_LLC` is the Xepayac LLC company repository. It ships:

- **Superseding Graph Substrate (SGS)** — `src/sgs/` — Python library for graph-as-executable-program (v0.3.0, AGPL-3.0)
- **Studies** — `studies/` — research experiments validating SGS capabilities
- **Examples** — `examples/` — usage patterns
- **Company-facing README** — the landing page for Xepayac LLC's technology and licensing

## Licensing

- Code is **AGPL-3.0**. This is intentional — commercial adoption requires a separate license from Xepayac LLC
- `CLA.md` is the Contributor License Agreement — contributors grant dual-license rights so Xepayac LLC can offer commercial terms
- Upstream dependencies like `TRUGS` (Apache-2.0) are consumed but not absorbed

## Working conventions

- **TRUG/L vocabulary** — all `<trl>` preambles and prose use TRUG/L (190 words, closed set). The spec lives at `TRUGS-LLC/TRUGS`. Never invent new TRUG/L words; use existing vocabulary.
- **folder.trug.json** — machine-readable index of the repo. Must validate against `trugs-folder-check`. Any file/folder added to disk also gets a node here.
- **CI enforces polish** — `.github/workflows/compliance.yml` runs on every PR. Passing checks is non-negotiable.
- **HITM rule** — agents open PRs, humans merge. Never push directly to `main`.
- **Conventional commits** — `<type>(<scope>): <summary>` — `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

## AAA protocol

Non-trivial changes follow AAA: VISION → FEASIBILITY → SPECIFICATIONS → ARCHITECTURE → VALIDATION (HITM) → CODING → TESTING → AUDIT (HITM) → DEPLOYMENT. Trivial fixes (typos, one-line bug fixes) follow CHORE: branch → PR → merge.

See [`TRUGS-LLC/TRUGS/REFERENCE/PAPER_how_to_code_with_trugs.md`](https://github.com/TRUGS-LLC/TRUGS/blob/main/REFERENCE/PAPER_how_to_code_with_trugs.md) §5 for the full protocol.

## Public API contracts

Every public `def` or `class` in `src/sgs/` carries a TRUG/L preamble stating its obligation:

```python
# PROCESS executor SHALL TRANSFORM ALL RECORD node THEN ROUTE RESULT TO ENDPOINT sink.
def execute(graph: Graph) -> Result:
    ...
```

Absence of a preamble on a public contract is a compliance violation.

## Quality gates

- `trugs-folder-check .` — 0 errors, 0 warnings
- `pytest tests/` — all tests pass
- No decrease in compliance %
- No PR merged without a passing CI gate

## Reference

- `README.md` — company overview, SGS thesis, licensing
- `CONTRIBUTING.md` — branch naming, workflow, CI gates
- `SECURITY.md` — private vulnerability disclosure
- `CHANGELOG.md` — Keep-a-Changelog, SemVer discipline
- `folder.trug.json` — machine-readable repo index
- `CLA.md` — Contributor License Agreement
- `NOTICE` — AGPL-3.0 attribution
- `LICENSE` — full AGPL-3.0 text
