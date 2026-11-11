# Status

| Area | State | Gate reached |
| --- | --- | --- |
| Design (DP-AI-001-C v0.2) | Drafted and independently reviewed | Stage 1 in progress |
| Repository validation (lint, render, schema, policy tests, unit tests) | Automated in CI | PR |
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

## Known gaps in this repository (planned work)

| Gap | Stage |
| --- | --- |
| Kyverno rule to verify LangChain's keyless image signatures, once LangChain confirms the signing identity | 2 |
| OpenSearch HTTP certificates issued by the platform CA (Fluent Bit already verifies against `opensearch-ca`) | 2 |
| Dependency-Track deployment for SBOM and ML-BOM analysis | 2 |
| Valkey high availability (currently one replica with persistence) | 2 |
| B2 overlay pointing Argo CD Helm sources at the enclave registry's OCI charts | 3 |
| Zarf image lists generated with `make zarf-images` | 3 |
| Migrate Kyverno `ClusterPolicy` (deprecated) to `ValidatingPolicy` / `ImageValidatingPolicy` | 3 |
| Red-team scripts run against a deployed platform; CHECK penetration test | 4 |
