# AD-62 MCP tools reach a model only through a per-deployment allowlist

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.1, chapter 14

## Decision

MCP servers come only from deployment configuration (`MCP_SERVERS`). A tool is offered to the model only if its name is in `MCP_ALLOWED_TOOLS`; with no allowlist no MCP tool is offered.

## Reason

A server that later adds or changes a tool must not widen what an agent can do (threat T-10). Default deny makes every tool a recorded choice.
