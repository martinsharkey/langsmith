# AD-64 Cache high availability is a Valkey Cluster, after standalone Valkey is proven

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

LangSmith's external cache and queue stay on one standalone Valkey until Valkey is proven with LangSmith and Agent Server (I-15). High availability then moves to a Valkey Cluster.

## Reason

LangChain documents only standalone Redis and Redis Cluster, including Valkey Cluster, for external Redis (AD-53); Sentinel is not mentioned. Building a cluster before the standalone case is proven would stack two unknowns.
