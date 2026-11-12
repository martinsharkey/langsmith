# AD-59 Agents reach models only through the LLM Gateway

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

Agents call custom/<class> model configurations on the gateway with a workspace-scoped service key holding gateway:invoke. Store embeddings call a vLLM embedding model directly because the gateway serves chat formats only.

## Reason

One place for routing, fallbacks, access, spend and data policy; provider changes need no agent code.
