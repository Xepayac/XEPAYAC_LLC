# Security Policy

## Reporting a vulnerability

**Do not open a public issue for security problems.** Report privately via GitHub Security Advisories:

1. Go to [github.com/Xepayac/XEPAYAC_LLC/security/advisories/new](https://github.com/Xepayac/XEPAYAC_LLC/security/advisories/new)
2. Fill in: the bug, impact, reproduction
3. We respond within 5 business days

If GitHub Security Advisories aren't an option, email `xepayacllc@gmail.com` with `[SGS SECURITY]` in the subject.

## What counts as a security issue

- Arbitrary code execution in `sgs.executor` via crafted graph input
- Path traversal / arbitrary file read in graph-loading code
- Denial-of-service through pathological graph structures (unbounded recursion, memory blowup)
- Bypass of constraint validation that allows invalid state to persist
- Sensitive data exposure through provenance or executor logs
- Dependency vulnerabilities with a plausible exploitation path

Not security issues (just file a normal bug):
- A performance regression without an exploitation path
- A test failure on a specific OS or Python version
- A type error in a constraint rule

## Supported versions

Only the latest minor version of `sgs` on PyPI receives security fixes. SGS is pre-1.0; breaking changes can land at any minor version.

| Version | Supported |
|---------|-----------|
| Latest on PyPI | Yes |
| Prior versions | No — upgrade |

## Commitment

- Acknowledge receipt within 5 business days
- Keep you informed during investigation
- Credit you in the advisory and CHANGELOG (unless you prefer anonymity)
- Publish a fix within 30 days for high/critical findings

## Scope

This policy covers `Xepayac/XEPAYAC_LLC` — SGS library, studies, examples, tooling. Upstream TRUGS specification issues go to `TRUGS-LLC/TRUGS`.
