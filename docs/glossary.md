# Glossary

One name for each thing (issue 64). `scripts/check_assurance.py` fails on an old product name, on a namespace label
other than `sap`, and on any `AD-`, `CTL-`, `T-`, `SR-`, `D-`, `I-` or `R-` identifier that is not defined in this
repository or listed below.

## Names

| Term | Use |
| --- | --- |
| Innovox Sovereign Agentic Platform | The product's title. In running text, "Sovereign Agentic Platform" or "the platform". |
| `sap` | The product's short identifier: label `innovox.uk/platform: sap` on every namespace, and the Zarf packages `sap-platform` and `sap-langsmith`. |
| DP-AI-001, DP-AI-001-C, DP-AI-001-A | The design documents, cited only as documents: the solution architecture, its Defence assurance annex and its catalogue. `docs/status.md` gives the revisions this repository follows. |

## Modes, stages and gates

| Term | Meaning |
| --- | --- |
| Mode B1 | Connected installation for OFFICIAL-SENSITIVE work. Online LangSmith licence; egress limited as in ADR 0045. |
| Mode B2 | Disconnected enclave. No egress; software carried in as signed Zarf packages; offline licence (D-06). |
| Delivery stage 1 to 5 | Discovery; Alpha, B1; Alpha, B2; Beta readiness; Release, then Live. Defined in `docs/sdlc.md` ("Lifecycle mapping"). |
| Gate PR, E1, E2, P1 | The gates in `docs/sdlc.md` ("Gates"): every pull request; the first installation; pre-production tests; production promotion. Stage 3 ends with the zero-egress test. |

## Model classes

A model class is what an agent asks the LLM Gateway for; the gateway decides where it runs (AD-31, AD-59).

| Form | Where |
| --- | --- |
| `class-m` | The identifier in configuration and code (vLLM service name, intake class). |
| `custom/class-m` | The model name an agent sends to the LLM Gateway (`agents/template/src/innovox_agent/models.py`). |
| class M | In running text. Only class M is defined so far (`docs/status.md`). |

## Identifiers

| Prefix | What | Defined in |
| --- | --- | --- |
| `AD-` | Architecture decisions | `docs/adr/` from AD-42; earlier decisions in the design documents (below) |
| `CTL-` | Controls | `docs/controls.yaml` |
| `T-` | Threats | `docs/assurance/threat-model.md` |
| `SR-` | Security risks | `docs/assurance/risk-register.yaml` |
| `D-`, `I-`, `R-` | Open items: decisions, integration questions and risks of the design documents | The design documents; those this repository depends on are below |

## Design-document identifiers cited here

These are defined in the design documents, not in this repository. The second column says only how this
repository uses each one.

| ID | As used in this repository |
| --- | --- |
| AD-24 | The sovereign model service: the upstream vLLM image serving weights that passed intake (`platform/manifests/models/vllm.yaml`). |
| AD-31 | Agents reach models only through the LLM Gateway, by model class (`agents/template/src/innovox_agent/models.py`). |
| AD-39 | One platform installation per client (`docs/architecture.md`). |
| AD-40 | Vendor components are used as shipped and configured through documented values; never rebuilt or patched (`CONTRIBUTING.md`). |
| D-06 | Offline (air-gapped) LangSmith licence terms, and offline behaviour of Gateway, Insights, Chat, Fleet and Engine (`docs/status.md`). |
| D-08 | Nutanix platform version, GPU passthrough, air-gapped hall and classifications supported (`docs/status.md`). |
| D-12 | A mirrored package index for agent builds in the enclave (`docs/status.md`). |
| I-11 | Whether LangSmith supports a SmithDB-only install (`platform/values/langsmith/values.yaml`). |
| I-12 | SmithDB on RKE2 with Rook-Ceph S3 and PostgreSQL 18 under CloudNativePG (`docs/status.md`). |
| I-13 | Fleet integrations call external OAuth endpoints, so Fleet is off in mode B2 (`platform/values/langsmith/values-b2.yaml`). |
| I-14 | Numbering of the OWASP LLM Top 10 2026 items (`redteam/`). |
| I-15 | Valkey or Redis 8 for Agent Server (`docs/status.md`). |
| I-16 | SmithDB pod-IP traffic through the Istio mesh (`docs/status.md`). |
| I-17 | LangChain's image-mirroring script is out of date after 0.16.21 (`airgap/zarf/images-langsmith-extra.txt`). |
| R-21 | The offline licence needed for mode B2 (`platform/values/langsmith/values-b2.yaml`). |
| R-27 | FIPS coverage of each open-source component (`docs/status.md`). |
| R-30 | Rook-Ceph S3 for LangSmith blobs and SmithDB (`docs/status.md`). |
| R-31 | Keycloak single sign-on and group-to-role sync with LangSmith (`docs/status.md`). |
| R-32 | Enterprise plan entitlements for LangSmith Deployment, RBAC and SCIM (`docs/status.md`). |
