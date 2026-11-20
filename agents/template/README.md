# Template deep agent

Every Innovox agent starts from this template. It is a LangChain Deep Agent deployed to LangSmith Agent Server
through `langgraph.json`, with the platform's rules built in:

| Rule | Where |
| --- | --- |
| Models only through the LLM Gateway, by model class (AD-31, AD-59) | `models.py` |
| Keycloak token on every request; owner-scoped threads; per-user memory; Studio disabled (AD-57) | `auth.py`, `langgraph.json` |
| Human approval before any external action (CTL-14) | `tools.py` (`APPROVAL_REQUIRED`), `agent.py` |
| Per-user long-term memory under `/memories/` | `agent.py` (`StoreBackend`) |
| Research delegated to a subagent on a smaller model class | `agent.py` |

```bash
pip install -e ".[test]" && pytest          # unit tests with a scripted model, no network
pip install -e ".[dev]" && langgraph dev    # local Agent Server (LangChain's free developer server)
```

Environment: `LANGSMITH_GATEWAY`, `LANGSMITH_GATEWAY_API_KEY`, `MODEL_CLASS`, `SUBAGENT_MODEL_CLASS`,
`OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`.

The example tools are placeholders: replace them with MCP tools from the client's approved servers.
