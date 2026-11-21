# AD-63 Dependency-Track runs on its own PostgreSQL cluster

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

Dependency-Track 5 uses a two-instance CloudNativePG cluster in the `supply-chain` namespace, separate from LangSmith's cluster.

## Reason

Neither system's upgrade, load or failure should affect the other, and LangSmith's cluster follows LangChain's upgrade cadence (AD-40).
