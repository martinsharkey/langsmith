# AD-51 Every platform service is an open-source container on RKE2

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

The host provides only VMs, networks, disks and an admin entry point; everything else runs on upstream-conformant Kubernetes (RKE2).

## Reason

Full portability between hosts, including air-gapped sites.
