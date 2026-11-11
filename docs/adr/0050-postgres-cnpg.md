# AD-50 PostgreSQL 18 under CloudNativePG

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

PostgreSQL 18 runs under the CloudNativePG operator, with a dedicated database for the SmithDB metastore.

## Reason

No managed services; SmithDB needs PostgreSQL 18 or later and its own database.
