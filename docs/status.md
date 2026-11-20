# Status

| Area | State | Gate reached |
| --- | --- | --- |
| Solution architecture (DP-AI-001 v2.0) and assurance annex (DP-AI-001-C v0.2) | Drafted | Stage 1 in progress |
| Repository validation (lint, render, schema, policy tests, unit tests) | Automated in CI | PR |
| User journey end to end (Keycloak sign-in, workbench, template deep agent, approvals, per-user isolation, MCP tools, background subagent) | Proven in CI against a stub model (`e2e/`) | PR |
| Agent release lane (image build, SBOM, scan, release evaluations) | Automated in CI; publish and sign on a release tag | PR |
| Threat model, security risk register, CAF first pass (`docs/assurance`) | First pass, checked for consistency in CI | Stage 1 |
| Test-workspace deployment (B1) | Not yet run | E1 pending |
| Enclave deployment (B2) | Not yet run | Zero-egress test pending |
| Red teaming, CHECK penetration test | Not started | E2 pending |

## Open items that can stop the build (stage 1 go or no-go)

| ID | Item | Owner |
| --- | --- | --- |
| D-06 | Offline (air-gapped) LangSmith licence terms; SmithDB-only install with ClickHouse disabled; offline behaviour of Gateway, Insights, Chat, Fleet, Engine | LangChain |
| I-12 | SmithDB on RKE2 with Rook-Ceph S3 and PostgreSQL 18 under CloudNativePG | LangChain |
| I-15 | Valkey vs Redis 8 for Agent Server (conflicting LangChain guidance) | LangChain |
| D-08 | Nutanix platform version, GPU passthrough, air-gapped hall, classifications supported | Hosting provider |
| R-27 | FIPS coverage of each open-source component | Innovox |
| R-32 | Enterprise plan entitlements for LangSmith Deployment, RBAC and SCIM | LangChain |

## Known gaps in this repository (planned work)

| Gap | Stage |
| --- | --- |
| Kyverno rule to verify LangChain's keyless image signatures, once LangChain confirms the signing identity | 2 |
| OpenSearch HTTP certificates issued by the platform CA (Fluent Bit already verifies against `opensearch-ca`) | 2 |
| Dependency-Track deployment for SBOM and ML-BOM analysis | 2 |
| Valkey high availability (currently one replica with persistence) | 2 |
| Red-team scripts run against a deployed platform; CHECK penetration test | 4 |
| Workbench: Valkey-backed session store for more than one replica; npm lockfile; container image and Argo CD application | 2 |
| Prove SmithDB pod-IP traffic through the Istio mesh, e.g. headless Services or sidecar exclusion (I-16) | 2 |
| Import LangChain's dashboard bundle into Grafana (chart ships Grafana 13.3.1, confirmed by CI render) | 2 |
| OpenTelemetry Collector for SmithDB OTLP traces | 2 |
| Prove Keycloak SSO and group-to-role sync with LangSmith (R-31); Rook-Ceph S3 for blobs and SmithDB (R-30) | 2 |
| Mirrored package index for agent builds in the enclave (D-12) | 3 |
| Images that operators pull at run time (Ceph CSI and others) listed from a running B1 cluster into `airgap/zarf/images-extra.txt` | 3 |

Open work that needs a deployment is tracked as GitHub issues; see the table in `docs/plan.md` and
[issue 25](https://github.com/martinsharkey/langsmith/issues/25).
