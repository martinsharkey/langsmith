# End-to-end test

Proves the user journey with nothing deployed: sign-in through a real Keycloak, the workbench, the template deep
agent on LangChain's local developer server, and a deterministic stub in place of the LLM Gateway.

Keycloak imports the realm that ships (`platform/manifests/keycloak/realm-langsmith.yaml`), converted by
`keycloak/realm_from_manifest.py` with only the changes a local plain-HTTP run needs (listed in that script), and the
test users in `keycloak/langsmith-users-0.json`. So the client scopes, roles and mappers under test are the
production ones.

| Check | What it proves |
| --- | --- |
| Unauthenticated request refused | The workbench proxy and Keycloak redirect |
| Signed-in user gets an answer | OIDC sign-in, a production-realm token accepted by Agent Server custom auth, streaming through `useStream` |
| Scripts only by nonce | The page's Content-Security-Policy has no `'unsafe-inline'` for scripts, and the page still works |
| A message mentioning task notifications is shown | Only notification metadata, never message text, hides a message |
| Plan panel fills | Deep agent planning state reaches the UI |
| Publication pauses, then runs on approval | Human-in-the-loop interrupt and resume |
| Rejected publication never runs | The tool is not executed without approval |
| Two publications, one approved and one rejected | One decision per action; only the approved one runs |
| Read-only MCP tool runs without a pause; the unlisted tool is never offered | MCP allowlist and `MCP_READ_ONLY_TOOLS`, checked through the stub model's record of offered tools |
| A writing MCP tool pauses for approval | MCP tools need approval unless declared read-only |
| Background task reports back | Async subagent on its own thread in the same deployment; status and result reach the UI |
| Bob cannot read Alice's thread | Owner-scoped threads (AD-57) |
| Only an agent administrator changes assistants | `realm_access.roles` reaches Agent Server; `agent-admin` may, `agent-user` may not |

```bash
pip install -e "agents/template[dev]" -r mcp-servers/reference/requirements.txt
(cd workbench && npm install && npm run build)
e2e/run-stack.sh
(cd e2e && npm install && npx playwright install chromium && npm test)
```

The client secret, users and passwords in `e2e/` are for this test only and exist nowhere else.
