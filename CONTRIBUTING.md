# Contributing to Xepayac LLC / SGS

Thanks for your interest in contributing. This repo holds Xepayac LLC's Superseding Graph Substrate (SGS) and related research. Before opening a PR, read this guide.

## License and CLA

SGS is **AGPL-3.0**. By contributing, you agree to the Contributor License Agreement in [`CLA.md`](CLA.md), which grants Xepayac LLC dual-license rights. This lets us continue offering commercial licenses alongside the open source.

If you can't sign the CLA, we can't accept the contribution — but we're happy to work from a written proposal or bug report.

## Types of contribution

| Change | Path |
|---|---|
| **Typo, doc clarity, one-line fix** | Branch → PR. No issue required. |
| **Bug fix with non-obvious cause** | Issue first. Tests required. |
| **New SGS feature** | Issue first. Full AAA planning applies. |
| **New study** | Issue first. Follow `studies/STUDY_TEMPLATE.md`. |

## Workflow

1. **Fork + branch.** Branch naming: `fix/<desc>`, `feat/<desc>`, `chore/<desc>`, `docs/<desc>`, `study/<desc>`.
2. **Write TRUG/L-commented tests.** Every behavior change needs a test. Every test needs an `AGENT SHALL VALIDATE ...` TRUG/L comment.
3. **Run local checks.**
   ```bash
   pip install -e .
   pytest tests/
   trugs-folder-check .
   ```
   All must pass.
4. **Commit** using Conventional Commits: `<type>(<scope>): <imperative summary>`.
5. **Open a PR.** Link the issue, include a test plan. A human will review and merge.

## Quality gates (CI enforces)

- `trugs-folder-check` reports 0 errors. Compliance baseline may not decrease.
- `pytest tests/` passes.
- No agent pushes directly to `main` — humans merge.

## Human-in-the-middle

Automated agents (Claude Code, etc.) open PRs but never merge. This is non-negotiable.

## Reporting vulnerabilities

Security issues go through private disclosure — see [`SECURITY.md`](SECURITY.md). Do not file in the public issue tracker.

## Code of conduct

Be decent. Assume good faith. Criticize ideas, not people. We reserve the right to remove contributions and contributors that make the project less welcoming.

## Questions

Open a discussion or an issue. Either works.
