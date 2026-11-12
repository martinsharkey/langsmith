# AD-55 Workbench is a Next.js back end for front end on useStream

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

The workbench is a Next.js app that holds the OIDC session server-side and forwards the user's token to Agent Server; the browser streams through @langchain/react useStream. Agents never run inside the workbench.

## Reason

Agents must run on Agent Server to be durable, scaled, traced and governed; tokens stay out of browser storage.
