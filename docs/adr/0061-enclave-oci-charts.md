# AD-61 Enclave charts are OCI artefacts carried by Zarf, generated from the applications

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

`scripts/gen_airgap.py` generates the B2 overlay, the chart list, both Zarf package definitions and the image lists from `platform/apps` and the rendered charts. Zarf installs only Argo CD; every other chart is an OCI artefact that Argo CD pulls from the enclave registry, following Zarf's Argo CD pattern.

## Reason

Argo CD in a zero-egress enclave cannot reach a Helm repository, and the Zarf agent rewrites only OCI and git sources. Generating the enclave definition from the connected one keeps the two modes one code base (AD-44). To be proven on a Zarf registry (issue 16).
