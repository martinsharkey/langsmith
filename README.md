# Innovox LangSmith Defence Platform

Deployable reference implementation of **DP-AI-001-C: Defence Profile and Assurance Framework**: a self-hosted
[LangSmith](https://docs.langchain.com/langsmith) platform for UK defence and air-gapped sites. Everything in it is
free, open-source software, except LangSmith itself, which needs a licence from LangChain.

> Status: **alpha (delivery stage 2)**. The code is validated in CI (lint, render, schema and policy tests, unit
> tests) but has not yet been deployed end to end or penetration tested. See [docs/status.md](docs/status.md).

## What it builds

| Layer | Component | Licence |
| --- | --- | --- |
| Kubernetes | RKE2 (CIS profile, FIPS-capable, Cilium CNI) | Apache-2.0 |
| GitOps | Argo CD (app of apps) | Apache-2.0 |
| Certificates | cert-manager | Apache-2.0 |
| Secrets and keys | OpenBao + External Secrets Operator | MPL-2.0 / Apache-2.0 |
| Storage | Rook-Ceph (block + S3 object gateway, Object Lock buckets) | Apache-2.0 (Ceph LGPL) |
| PostgreSQL 18 | CloudNativePG | Apache-2.0 |
| Cache and run queue | Valkey | BSD-3-Clause |
| Registry | Harbor (Trivy scanning) | Apache-2.0 |
| Identity | Keycloak (operator) | Apache-2.0 |
| Network and mesh | Cilium policy, Istio mutual TLS and ingress gateway | Apache-2.0 |
| Admission policy | Kyverno (+ Sigstore cosign verification) | Apache-2.0 |
| Observability | OpenSearch, kube-prometheus-stack, Falco | Apache-2.0 (Grafana AGPL-3.0) |
| Model service | vLLM, upstream image as shipped | Apache-2.0 |
| Air-gap packaging | Zarf | Apache-2.0 |
| Agent platform | LangSmith (SmithDB, no ClickHouse), Agent Server | Commercial licence |

Two modes come from the same code (AD-44):

- **B1 connected, OFFICIAL-SENSITIVE**: egress only from the LLM Gateway, to customer-approved UK model endpoints.
- **B2 disconnected enclave**: no egress at all; software carried in as signed Zarf packages; sovereign models on vLLM.

## Repository layout

```
docs/            architecture summary, SDLC, ADRs (AD-42..AD-52), control catalogue, runbooks
infra/opentofu/  Nutanix AHV virtual machines for RKE2 nodes (OpenTofu)
infra/rke2/      RKE2 server and agent configuration, audit policy, Cilium settings
platform/        Argo CD applications, Helm values per component, B1/B2 overlays, raw manifests
policies/        Kyverno policies with tests; Cilium network policies
airgap/zarf/     Zarf packages for carry-in to the enclave
model-intake/    model intake gate CLI (provenance, ML-BOM, evaluation thresholds, decision record)
redteam/         garak, PyRIT and Inspect configurations for OWASP LLM and Agentic testing
tests/           in-cluster tests: zero egress, unsigned image refused
versions.yaml    every pinned version in one place
```

## Quick start

```bash
make validate            # everything CI runs, locally
make -C model-intake test
```

Deployment order and commands are in [docs/runbooks/install-b1.md](docs/runbooks/install-b1.md) and
[docs/runbooks/install-b2-airgap.md](docs/runbooks/install-b2-airgap.md).

## Secrets

This repository is public. It holds **no** secrets, licence keys, hostnames of real sites or customer data. Every
secret is created in OpenBao at install time and reaches workloads through External Secrets. CI runs gitleaks on
every pull request.

## Secure development lifecycle

The repository follows a NIST SSDF (SP 800-218 and 800-218A) secure lifecycle mapped to MOD Secure by Design and the
gates PR, E1, E2 and P1. See [docs/sdlc.md](docs/sdlc.md).

## Licence

Apache-2.0 for the code in this repository. Third-party components keep their own licences (table above).
