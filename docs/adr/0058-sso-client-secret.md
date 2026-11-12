# AD-58 LangSmith SSO uses OIDC with a client secret

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

authType mixed with a confidential Keycloak client; PKCE is not enforced.

## Reason

LangChain recommends the client-secret flow and deprecates PKCE from v16.
