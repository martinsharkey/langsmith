# Pre-deployment plan

Work that can be finished and tested in CI before any cluster or LangSmith licence exists. One pull request per
workstream (more where a stream is large). Status is updated in the pull request that changes it.

| ID | Workstream | Outcome | Status |
| --- | --- | --- | --- |
| W1 | Render every chart in CI and policy-check the output | Bad values and policy conflicts found before deployment | Done (findings below) |
| W2 | Close known repository gaps | Kyverno policy migration, enclave OCI overlay, Zarf image lists, OpenTelemetry Collector, Dependency-Track, Valkey HA, SmithDB through the mesh | In progress: enclave overlay, Zarf packages and image lists done (findings below); policy migration, OpenTelemetry Collector, Dependency-Track and Valkey HA remain |
| W3 | Template deep agent | Custom auth, per-user store auth, gateway model classes, approval step, tests, `langgraph.json` | Done |
| W4 | Workbench | Next.js back end for front end on `useStream`: chat, plan, subagents, approvals, files | Done |
| W5 | End-to-end test in CI | Workbench to agent to stub model, browser-driven, with a real Keycloak | Done (issue 24 closed) |
| W6 | Agent release pipeline | `langgraph build`, signature, SBOM, evaluations | Done to the limit of CI: build, SBOM, scan, evaluations, signed release workflow. Deployment through the control plane is issue 14 |
| W7 | Assurance paperwork | Threat model, risk register, CAF first pass, catalogue and annex aligned to v2.0 | Threat model, risk register and CAF first pass done (`docs/assurance`). Catalogue and annex alignment remain |

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

## W2 findings (fixed in the same pull request)

Found by rendering Argo CD itself and by listing every image the enclave must carry.

| Finding | Effect if deployed | Fix |
| --- | --- | --- |
| Argo CD's Dex and Redis images were not on the admission allowlist, and its namespace had no Pod Security level | Argo CD pods refused once Kyverno enforces | Dex disabled (sign-in is OIDC to Keycloak); Redis image allowed; namespace set to `restricted` |
| The LangGraph operator starts a `redis:7` and an unqualified `pgvector/pgvector:pg15` pod for every agent deployment | Every agent deployment's stores refused at admission; Redis 7 is source-available, against AD-52; neither image would be in the enclave | Operator templates overridden, as LangChain documents: Valkey, and pgvector with its registry |
| The local-path provisioner's helper image was `busybox:latest` | Volume provisioning refused (floating tag) | Pinned Rancher mirror image |
| Argo CD Helm sources named upstream repositories in the enclave overlay | Nothing could sync in a disconnected enclave | Generated OCI chart sources, following Zarf's Argo CD pattern |
| The Zarf package had Zarf install charts that Argo CD also manages, and no image list | Two owners for each release; missing images | One generated package definition: Zarf installs only Argo CD and carries everything else |

## What this plan cannot prove

- Anything that needs a LangSmith licence key: LangSmith itself, SmithDB, the LLM Gateway, production Agent Server
  deployments.
- Behaviour on real infrastructure: storage performance, GPUs, the air gap.

Those follow in delivery stages 2 to 4 (`docs/status.md`).

Each of these is recorded as a GitHub issue so it can be picked up during deployment. The tracker is
[issue 25](https://github.com/martinsharkey/langsmith/issues/25).

| Issue | Subject | Needs |
| --- | --- | --- |
| 7 | LangSmith licence or trial, online and offline | LangChain |
| 8 | First cluster deployment of the open-source layer (B1, gate E1) | Cluster |
| 9 | SmithDB-only install on RKE2, Rook-Ceph and CloudNativePG | Cluster, licence |
| 10 | SmithDB traffic through the Istio mesh | Cluster, licence |
| 11 | Valkey versus Redis | Cluster, licence |
| 12 | LLM Gateway with real model classes | Cluster, licence |
| 13 | Keycloak single sign-on and group sync with LangSmith | Cluster, licence |
| 14 | Template agent through the deployment control plane | Cluster, licence |
| 15 | LangChain image signatures at admission | Cluster, LangChain |
| 16 | Disconnected enclave (B2) | Cluster, offline licence |
| 17 | Host checks: Nutanix, GPUs, storage, FIPS | Host |
| 18 | Real model through the intake gate, served on vLLM | Cluster, GPUs |
| 19 | Istio ingress namespace to the restricted level | Cluster |
| 20 | Observability on a live platform | Cluster |
| 21 | Backup, restore and upgrade rehearsal | Cluster, licence |
| 22 | Red teaming and CHECK penetration test (gates E2, P1) | Deployed platform |
| 23 | Workbench lockfile, shared session store and deployment | Partly now, partly cluster |
| 24 | End-to-end test: MCP tool server and async subagent | Nothing; can be done now |
