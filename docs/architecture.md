# Architecture summary

The full design is the Innovox document **DP-AI-001-C Defence Profile and Assurance Framework v0.2**, an overlay
on DP-AI-001 (LangSmith Platform HLD v1.4). This page summarises what the code implements.

## Hosting contract (AD-43, AD-51)

The host provides only virtual machines (with GPU passthrough and local NVMe where needed), private networks with
no default route to the internet, disks, and one admin entry point. Everything else is a container on RKE2.
The reference host is a UK sovereign data centre on Nutanix AHV; a cloud workspace is used only for build and test.

## Two modes, one code base (AD-44)

| Concern | B1 connected, OFFICIAL-SENSITIVE | B2 disconnected enclave |
| --- | --- | --- |
| Egress | Only the LLM Gateway, only to approved UK endpoints (`policies/egress/b1/`) | None (`policies/egress/b2/`) |
| Software intake | Harbor, images signed by the pipeline and verified by Kyverno | Zarf packages carried in to the enclave's Harbor, verified by Kyverno |
| LangSmith licence | Online licence | Offline licence (to be confirmed with LangChain) |
| Models | Customer-approved frontier models through the LLM Gateway | Sovereign models on vLLM after the intake gate |

Selecting a mode is a single overlay: `platform/overlays/b1` or `platform/overlays/b2`.

## Data stores

| Store | Implementation | Notes |
| --- | --- | --- |
| LangSmith operational database | CloudNativePG cluster `langsmith-pg`, database `langsmith` | PostgreSQL 18 |
| SmithDB metastore | Same cluster, dedicated empty database `smithdb` | LangChain requires a dedicated database |
| SmithDB objects and LangSmith blobs | Rook-Ceph S3 buckets, path-style addressing | |
| Evidence and audit logs | Rook-Ceph bucket with Object Lock (compliance mode) | Cannot be altered |
| Cache and run queue | Valkey (I-15) | Redis 8 (AGPL-3.0) is the fallback |
| ClickHouse | Not deployed (`clickhouse.enabled: false`) | SmithDB replaces it |

## Decisions

See `docs/adr/`. AD-24 (model server as shipped), AD-30 (Argo CD for add-ons only), AD-31 (models as gateway
configurations) and AD-40 (native, upgrade-safe) come from the parent HLD.
