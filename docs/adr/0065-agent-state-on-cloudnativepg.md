# AD-65 Production agent deployments keep their state on CloudNativePG

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

A production agent deployment sets `POSTGRES_URI_CUSTOM` to its own database on a CloudNativePG cluster, as LangChain documents for self-hosted deployments (one database per deployment; an instance may be shared). The PostgreSQL pod the operator creates by default is used only in development and test.

## Reason

An agent's checkpoints, threads and long-term memory are what let a task pause for approval for days and resume. The operator's default store is a single pod with no replica, backup or point-in-time recovery. Not built or proven yet (issue 14); until it is, agent state in a deployed platform has no backup.
