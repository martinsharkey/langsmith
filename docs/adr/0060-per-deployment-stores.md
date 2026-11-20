# AD-60 Per-deployment stores use the operator's templates, overridden only for the images

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

The LangGraph operator starts a Redis pod and a PostgreSQL (pgvector) pod for each agent deployment from templates in the chart values. `platform/values/langsmith/values.yaml` overrides `operator.templates.redis` and `operator.templates.db`, as LangChain documents, changing only the images: Valkey for Redis 7, and pgvector named with its registry. The templates are re-copied from the chart at every LangSmith upgrade.

## Reason

Redis 7 is source-available from 7.4 and so fails AD-52; neither default image was on the admission allowlist or in the enclave image list. Changing only the image keeps the override upgrade-safe (AD-40). To be proven on a cluster (issues 11 and 14). These operator-created stores are single pods with no backup, so they are for development; AD-65 covers production.
