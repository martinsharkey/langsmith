# AD-57 Custom auth and store auth on every Agent Server deployment

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

Each deployment ships a custom auth handler validating Keycloak tokens, resource ownership filters, and a store auth handler scoping memory per user. Production deployments set disable_studio_auth.

## Reason

A standalone Agent Server has no default auth, store namespaces are shared by default, and Studio is allowed by default.
