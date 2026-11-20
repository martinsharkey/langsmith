# Pre-deployment plan

Work that can be finished and tested in CI before any cluster or LangSmith licence exists. One pull request per
workstream (more where a stream is large). Status is updated in the pull request that changes it.

| ID | Workstream | Outcome | Status |
| --- | --- | --- | --- |
| W1 | Render every chart in CI and policy-check the output | Bad values and policy conflicts found before deployment | Done (findings below) |
| W2 | Close known repository gaps | Kyverno policy migration, enclave OCI overlay, Zarf image lists, OpenTelemetry Collector, Dependency-Track, Valkey HA, SmithDB through the mesh | Not started |
| W3 | Template deep agent | Custom auth, per-user store auth, gateway model classes, approval step, tests, `langgraph.json` | Done: `agents/template`, 19 tests. Async subagents and MCP tools follow in W5 |
| W4 | Workbench | Next.js back end for front end on `useStream`: chat, plan, subagents, approvals, files | Done: `workbench/` |
| W5 | End-to-end test in CI | Workbench to agent to stub model, browser-driven, with a real Keycloak | Done: `e2e/`, 6 browser tests. An example MCP server and an async subagent are still to add |
| W6 | Agent release pipeline | `langgraph build`, signature, SBOM, evaluations | Not started |
| W7 | Assurance paperwork | Threat model, risk register, CAF first pass, catalogue and annex aligned to v2.0 | Not started |

## W1 findings (all fixed in the same pull request)

| Finding | Fix |
| --- | --- |
| Istio chart 1.32.0 was pinned from a git tag, but the newest stable chart published is 1.30.8 | Pinned to 1.30.8 |
| The image allowlist refused the platform's own workloads: Istio, Kyverno hooks, Prometheus stack sidecars, LangSmith's bundled Insights and Chat stores | Allowlist extended; Istio's `auto` placeholder allowed |
| OpenSearch and OpenSearch Dashboards used unqualified image names; OpenSearch ran a `busybox:latest` init container | Images qualified; init container disabled |
| LangSmith's bundled Insights and Chat stores default to `redis:7`, which is source-available | Replaced with Valkey through the chart's image values (AD-52) |
| OpenBao's container did not meet the `restricted` Pod Security level of its namespace | Container security context set |
| The Istio gateway's pod template has no seccomp profile before injection | Namespace set to `baseline` until the injected pod is checked at E1 |
| Kyverno chart 3.9.2 ships Kyverno v1.19.2, not v1.20.0 | `versions.yaml` corrected |
| Grafana in kube-prometheus-stack is 13.3.1 | Meets LangChain's 13+ requirement for its dashboards |

## What this plan cannot prove

- Anything that needs a LangSmith licence key: LangSmith itself, SmithDB, the LLM Gateway, production Agent Server
  deployments.
- Behaviour on real infrastructure: storage performance, GPUs, the air gap.

Those follow in delivery stages 2 to 4 (`docs/status.md`).
