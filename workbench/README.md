# Workbench

The business user's console (AD-55): hand a task to a deep agent, follow its plan and subagents, approve or reject
sensitive steps, and open the files it writes.

- **Next.js back end for front end.** The browser talks only to this app. Sign-in is OpenID Connect against Keycloak
  (authorization code with PKCE, confidential client) using the certified `openid-client` library. Tokens stay on
  the server; the browser holds an opaque HttpOnly session cookie.
- **LangChain's frontend SDK.** Streaming, interrupts, plan and subagent views come from `useStream`
  (`@langchain/react`); nothing is reimplemented.
- **Agents never run here.** `/api/agent/*` attaches the user's access token and forwards to Agent Server, which
  validates it again (AD-57). Only Agent Server resource paths are forwarded; cookies never are.

| Variable | Purpose |
| --- | --- |
| `AGENT_SERVER_URL` | Agent Server deployment, reachable from the workbench pod |
| `ASSISTANT_ID` | Assistant or graph id (default `agent`) |
| `WORKBENCH_PUBLIC_URL` | The URL users open; used for redirects and the same-origin check |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | Keycloak realm and the workbench's confidential client |
| `SESSION_TTL_SECONDS` | Session lifetime (default 8 hours) |

```bash
npm install
npm test          # proxy rules
npm run build
```

Known limits (see `docs/status.md`): sessions are held in memory, so run one replica until a Valkey-backed store is
added; there is no lockfile yet.
