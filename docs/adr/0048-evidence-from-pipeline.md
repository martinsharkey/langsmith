# AD-48 Evidence from the pipeline, kept in Object Lock storage

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

Pipeline outputs (SBOMs, provenance, scans, test results) are written to a Rook-Ceph bucket with Object Lock in compliance mode.

## Reason

Evidence stays current with each release and cannot be altered.
