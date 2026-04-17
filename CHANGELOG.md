# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-04-18

Polish release — all three Dark Code compliance layers PASS for `Xepayac/XEPAYAC_LLC`. Part of the TRUGS-LLC portfolio polish push ([`Xepayac/TRUGS-DEVELOPMENT#1526`](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1526), EPIC [`#1548`](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1548)).

### Added
- `AGENT.md` — LLM agent guide for this repo (Layer 1)
- `.github/workflows/compliance.yml` — CI gate validating `folder.trug.json` + pytest (Layer 1)
- `CONTRIBUTING.md` — branch naming, workflow, CLA requirement, quality gates (Layer 2)
- `SECURITY.md` — private disclosure via GitHub Security Advisories, SGS-specific scope (Layer 2)
- `.github/ISSUE_TEMPLATE/` — `bug_report.yml` + `feature_request.yml` + `config.yml` (Layer 2)
- `.github/PULL_REQUEST_TEMPLATE.md` — summary, linked issue, compliance + CLA checklist (Layer 2)
- This `CHANGELOG.md` — Keep-a-Changelog + SemVer discipline (Layer 2)
- README: 5 shields.io badges (PyPI, Python, license, CI, DOI-ready), mermaid architecture diagram above-the-fold, "This repo, as a TRUG" dogfooding section (Layer 2 + 3)
- `<trl>` TRUG/L preambles above every public `def`/`class` in `src/sgs/` (Layer 3)

### Changed
- `folder.trug.json` — rewritten from scratch to comply with current CORE spec: added `root` FOLDER node, valid node types (FOLDER/DOCUMENT/COMPONENT), lowercase folder-branch edge relations, nodes for every on-disk item. 6 errors + 11 warnings → 0 / 0 (Layer 3)

### Release discipline
- First GitHub Release cut for this repo. Going forward, every version bump creates a git tag and GitHub Release.

### Known limitation
CI uses an inline Python JSON-shape check for `folder.trug.json` pending publication of `trugs-tools` to PyPI (tracked in `Xepayac/TRUGS-DEVELOPMENT#1567`). The full `trugs-folder-check` will be restored once that ships.

## [0.3.0] - earlier

Superseding Graph Substrate (SGS) prior art. Details pre-date this CHANGELOG. See `git log` and the `studies/` directory for the research that shaped this version.
