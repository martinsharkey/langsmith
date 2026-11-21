# AD-45 Connected frontier models only with UK processing

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

Connected frontier models are used only with UK processing and only once the customer approves them. The LLM Gateway is the only workload with egress.

## Reason

OFFICIAL-SENSITIVE handling; several providers offer no UK inference residency.

## Egress in mode B1

Owner ruling on issue 33 (2026-11-21): "Argo CD". The LLM Gateway is the only workload that reaches model
endpoints. Besides it, mode B1 lets three kinds of workload reach the internet, each to named hosts only:

- LangSmith services that hold the licence, to `beacon.langchain.com`, which an online licence requires;
- Argo CD's repo server, to the git and Helm sources its Applications name;
- CoreDNS, to the site's resolvers on port 53 (also in mode B2).

Every other pod is denied the internet (`policies/egress/b1/deny-world-egress.yaml`), including Harbor's proxy
cache, Dependency-Track's vulnerability feeds and Falco's rule downloads. `tests/config/check_platform.py` checks
the selectors in gate PR; the zero-egress probe (`tests/run-e2-checks.sh`) proves them on a cluster.
