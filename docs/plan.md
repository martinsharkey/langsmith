# Pre-deployment plan

Work that can be finished and tested in CI before any cluster or LangSmith licence exists. One pull request per
workstream (more where a stream is large). Status is updated in the pull request that changes it.

| ID | Workstream | Outcome | Status |
| --- | --- | --- | --- |
| W1 | Render every chart in CI and policy-check the output | Bad values and policy conflicts found before deployment | In progress |
| W2 | Close known repository gaps | Kyverno policy migration, enclave OCI overlay, Zarf image lists, OpenTelemetry Collector, Dependency-Track, Valkey HA, SmithDB through the mesh | Not started |
| W3 | Template deep agent | Custom auth, per-user store auth, gateway model classes, approval step, tests, `langgraph.json` | Not started |
| W4 | Workbench | Next.js back end for front end on `useStream`: chat, plan, subagents, approvals, files | Not started |
| W5 | End-to-end test in CI | Workbench to agent to stub model to example MCP server, browser-driven | Not started |
| W6 | Agent release pipeline | `langgraph build`, signature, SBOM, evaluations | Not started |
| W7 | Assurance paperwork | Threat model, risk register, CAF first pass, catalogue and annex aligned to v2.0 | Not started |

## What this plan cannot prove

- Anything that needs a LangSmith licence key: LangSmith itself, SmithDB, the LLM Gateway, production Agent Server
  deployments.
- Behaviour on real infrastructure: storage performance, GPUs, the air gap.

Those follow in delivery stages 2 to 4 (`docs/status.md`).
