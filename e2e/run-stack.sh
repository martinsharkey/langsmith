#!/usr/bin/env bash
# Starts the end-to-end stack on localhost: Keycloak (test realm), the stub model, the example MCP server, the template agent on LangChain's
# local developer server, and the workbench. Logs go to e2e/logs. Used by CI and for local runs.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
logs="$root/e2e/logs"; mkdir -p "$logs"
KEYCLOAK_IMAGE="${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.8.2}"

wait_for() {  # wait_for <name> <url> [seconds]
  local name="$1" url="$2" limit="${3:-180}"
  for _ in $(seq 1 "$limit"); do
    if curl -fsS -o /dev/null "$url"; then echo "ready: $name"; return 0; fi
    sleep 1
  done
  echo "timed out waiting for $name ($url)"; return 1
}

docker rm -f e2e-keycloak >/dev/null 2>&1 || true
docker run -d --name e2e-keycloak -p 8080:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  -v "$root/e2e/keycloak:/opt/keycloak/data/import:ro" \
  "$KEYCLOAK_IMAGE" start-dev --import-realm >/dev/null

python3 "$root/e2e/stub_model.py" 9000 >"$logs/stub-model.log" 2>&1 &
python3 "$root/mcp-servers/reference/server.py" >"$logs/mcp-reference.log" 2>&1 &

(
  cd "$root/agents/template"
  LANGSMITH_TRACING=false \
  LANGSMITH_GATEWAY=http://127.0.0.1:9000/v1 LANGSMITH_GATEWAY_API_KEY=e2e \
  OIDC_ISSUER=http://localhost:8080/realms/langsmith OIDC_AUDIENCE=workbench \
  MCP_SERVERS='{"reference":{"transport":"http","url":"http://127.0.0.1:9100/mcp"}}' \
  MCP_ALLOWED_TOOLS=lookup_reference \
  langgraph dev --no-browser --host 127.0.0.1 --port 2024 >"$logs/agent.log" 2>&1 &
)

wait_for keycloak http://localhost:8080/realms/langsmith/.well-known/openid-configuration 240
wait_for stub-model http://127.0.0.1:9000/health 30
for _ in $(seq 1 30); do (exec 3<>/dev/tcp/127.0.0.1/9100) 2>/dev/null && { echo "ready: mcp-reference"; break; }; sleep 1; done

(
  cd "$root/workbench"
  AGENT_SERVER_URL=http://127.0.0.1:2024 WORKBENCH_PUBLIC_URL=http://localhost:3000 \
  OIDC_ISSUER=http://localhost:8080/realms/langsmith OIDC_CLIENT_ID=workbench OIDC_CLIENT_SECRET=e2e-test-only \
  NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=localhost \
  npm start >"$logs/workbench.log" 2>&1 &
)

wait_for agent http://127.0.0.1:2024/ok 120
wait_for workbench http://localhost:3000/api/healthz 120
echo "stack is up"
