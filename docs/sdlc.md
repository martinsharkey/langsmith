# Secure development lifecycle

The repository uses one lifecycle that satisfies NIST SSDF (SP 800-218 v1.1 and the generative AI profile
SP 800-218A), MOD Secure by Design (JSP 440 Leaflet 5C) and the IBM agent development lifecycle (ADLC) phases used
in DP-AI-001. Delivery is trunk-based with short-lived branches; every change reaches production only through the
four gates below.

## Gates

| Gate | Where | What must pass | Evidence kept |
| --- | --- | --- | --- |
| **PR** | GitHub Actions on every pull request | YAML lint, Helm render, Kubernetes schema validation (kubeconform), Kyverno policy tests, Trivy IaC scan, gitleaks secret scan, OpenTofu validate, unit tests, independent review | CI logs, SARIF results |
| **E1** | Dev installation | Argo CD sync healthy; functional tests; image signatures verified at admission; SBOMs and SLSA provenance recorded | Tekton Chains attestations, admission decisions |
| **E2** | Test (pre-production) | Red teaming (garak, PyRIT, Inspect) against OWASP LLM Top 10 2026 and Agentic Top 10 2026; zero-egress test (B2); unsigned-image test; restore test | Red-team reports, test job logs |
| **P1** | Production promotion | CHECK penetration test findings closed or accepted by the SRO; Statement of Assurance signed | CHECK report, SRO decision |

## Lifecycle mapping

| Delivery stage | CADMID/T | ADLC phase | SSDF focus | Gate |
| --- | --- | --- | --- | --- |
| 1 Discovery | Concept | Plan | PO.1 requirements, PO.3 toolchain | Go or no-go |
| 2 Alpha, B1 | Assessment | Code and build; Test and release | PS.1-PS.3, PW.4, PW.6 | E1 |
| 3 Alpha, B2 | Demonstration | Test and release; Deploy | PW.4 third-party components (images, model weights) | Zero egress |
| 4 Beta readiness | Demonstration into Manufacture | Test and release; Deploy | PW.7, PW.8, RV.1 | E2 |
| 5 Release, then Live | In-Service | Deploy; Operate; Monitor | RV.1-RV.3 | P1 |

## SSDF practices in this repository

| Practice | Implementation |
| --- | --- |
| PO.1 Define security requirements | `docs/controls.yaml` (CTL-01..CTL-18) |
| PO.3 Implement supporting toolchains | `.github/workflows/ci.yml`, `Makefile`, Tekton pipelines |
| PO.5 Secure environments | Separate installations per environment; no shared credentials |
| PS.1 Protect code | Branch protection, CODEOWNERS, signed commits recommended |
| PS.2 Verify integrity | cosign signatures, Kyverno `verifyImages`, model signature check in `model-intake/` |
| PS.3 Archive and protect releases | Tagged releases; SBOMs and provenance in Object Lock storage |
| PW.4 Reuse well-secured software | Pinned versions (`versions.yaml`), Renovate with a 14-day release age |
| PW.7 / PW.8 Review and test | Pull request review; policy tests; unit tests; red teaming |
| RV.1-RV.3 Vulnerabilities | Trivy in CI and Harbor; Falco at runtime; private reporting (`SECURITY.md`) |
| 800-218A model integrity | `model-intake/`: safetensors only, signature verification, CycloneDX ML-BOM, evaluation thresholds |

Secure by Design: the customer's CAAT record is updated at every stage from the evidence above, at least every
three months and on every significant change.
