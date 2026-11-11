# Security policy

## Reporting a vulnerability

Do not open a public issue. Report privately through GitHub's
[private vulnerability reporting](../../security/advisories/new) for this repository. We acknowledge within five
working days and agree a fix and disclosure date with the reporter.

## What this repository must never contain

- Secrets, tokens, passwords, private keys or the LangSmith licence key.
- Hostnames, IP ranges or names of real customer or defence sites.
- Customer data, prompts, traces or model outputs.
- Information classified above OFFICIAL.

gitleaks runs on every pull request (gate PR). A finding blocks the merge.

## Supported versions

Only the latest tagged release receives fixes. Pinned third-party versions are listed in `versions.yaml`.
