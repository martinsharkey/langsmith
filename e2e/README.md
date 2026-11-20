# End-to-end test

Proves the user journey with nothing deployed: sign-in through a real Keycloak, the workbench, the template deep
agent on LangChain's local developer server, and a deterministic stub in place of the LLM Gateway.

| Check | What it proves |
| --- | --- |
| Unauthenticated request refused | The workbench proxy and Keycloak redirect |
| Signed-in user gets an answer | OIDC sign-in, token forwarding, Agent Server custom auth, streaming through `useStream` |
| Plan panel fills | Deep agent planning state reaches the UI |
| Publication pauses, then runs on approval | Human-in-the-loop interrupt and resume |
| Rejected publication never runs | The tool is not executed without approval |
| Agent answers with a tool from the MCP server | LangChain's MCP adapter, with the allowlist withholding the server's other tool |
| Background task reports back | Async subagent on its own thread in the same deployment; status and result reach the UI |
| Bob cannot read Alice's thread | Owner-scoped threads (AD-57) |

```bash
pip install -e "agents/template[dev]" -r mcp-servers/reference/requirements.txt
(cd workbench && npm install && npm run build)
e2e/run-stack.sh
(cd e2e && npm install && npx playwright install chromium && npm test)
```

The realm, client secret and passwords in `e2e/keycloak` are for this test only and exist nowhere else.
