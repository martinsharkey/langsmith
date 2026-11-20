# NCSC Cyber Assessment Framework: first pass

An honest position before any deployment, at principle level. It shows what the platform contributes to each
principle and what remains with the organisation that operates it. It is not a CAF assessment: indicators of good
practice are assessed against a running service, by the operating organisation, using the current published CAF
text.

Position: **Designed** the answer is in the architecture; **Built** it is in this repository; **Proven** a test in
CI shows it; **Operator** it depends on the operating organisation.

| Principle | Platform contribution | Position | Remaining |
| --- | --- | --- | --- |
| A1 Governance | Decisions recorded as ADRs; gates PR, E1, E2, P1 | Built | Operator: named SRO and security roles |
| A2 Risk management | Threat model and risk register in `docs/assurance` | Built | Review at each gate; operator risk appetite |
| A3 Asset management | Versions pinned in one file; SBOM per image; ML-BOM per model | Built, part Proven | Dependency-Track (issue 20) |
| A4 Supply chain | Signed images, registry allowlist, model intake gate, SBOMs | Built, part Proven | LangChain signatures (issue 15); supplier assurance (CTL-18) |
| B1 Policies and processes | SDLC mapped to NIST SSDF; runbooks | Built | Operator procedures |
| B2 Identity and access control | Keycloak with MFA; custom auth on every agent; owner-scoped data | Built, part Proven | LangSmith SSO and roles (issue 13) |
| B3 Data security | Mutual TLS, encrypted volumes, keys in OpenBao, egress control | Built | Prove on a cluster (issues 8, 16) |
| B4 System security | CIS-profile RKE2, Pod Security, admission policy, vulnerability scans | Built, part Proven | Host hardening and FIPS (issue 17) |
| B5 Resilient networks and systems | Replicated data services; GitOps rebuild | Designed | Backup, restore, upgrade rehearsal (issue 21) |
| B6 Staff awareness and training | None | Operator | Operator |
| C1 Security monitoring | Audit logs, Falco, OpenSearch, evidence bucket | Built | Prove log flow and alerts (issue 20) |
| C2 Threat hunting | LangSmith traces of every agent step support investigation | Designed | Operator; needs a licence |
| D1 Response and recovery planning | Run cancellation; rebuild from Git | Designed | Incident runbooks; operator plan |
| D2 Lessons learned | Findings recorded back into the repository (`docs/plan.md`) | Built | Operator process |
