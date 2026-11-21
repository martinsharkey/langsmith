# Template deep agent

Every Innovox agent starts from this template. It is a LangChain Deep Agent deployed to LangSmith Agent Server
through `langgraph.json`, with the platform's rules built in:

| Rule | Where |
| --- | --- |
| Models only through the LLM Gateway, by model class (AD-31, AD-59) | `models.py` |
| Keycloak token on every request; owner-scoped threads; per-user memory; Studio disabled (AD-57) | `auth.py`, `langgraph.json` |
| Human approval before any external action, including every MCP tool not declared read-only (CTL-14) | `tools.py` (`APPROVAL_REQUIRED`), `agent.py` (`approval_required`) |
| Per-user long-term memory under `/memories/` | `agent.py` (`StoreBackend`) |
| Research delegated to a subagent on a smaller model class | `agent.py` |
| MCP tools only from configured servers, and only those on the allowlist | `mcp_tools.py` |
| Long analysis as a background (async) subagent on its own thread | `analyst.py`, `agent.py` |

```bash
pip install -e ".[test]" && pytest          # unit tests with a scripted model, no network
pip install -e ".[dev]" && langgraph dev    # local Agent Server (LangChain's free developer server)
```

Environment: `LANGSMITH_GATEWAY`, `LANGSMITH_GATEWAY_API_KEY`, `MODEL_CLASS`, `SUBAGENT_MODEL_CLASS`,
`OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, `MCP_SERVERS`, `MCP_ALLOWED_TOOLS`, `MCP_READ_ONLY_TOOLS`.
Every allowlisted MCP tool pauses for approval unless it is also in `MCP_READ_ONLY_TOOLS`. Long-term memory needs a
signed-in user; `INNOVOX_ALLOW_ANONYMOUS_MEMORY=1` allows one shared namespace for local development without sign-in.

Dependencies are locked in `uv.lock`, which records a sha256 hash for every artefact. `langgraph build` installs
the locked versions (`source.kind: uv` in `langgraph.json`), but langgraph-cli 0.4.43 exports them with
`uv export --frozen --no-hashes`, so the image build does not check the hashes or that the lock matches
`pyproject.toml`. After changing `pyproject.toml`, run `uv lock` and commit both files.

## Release

| Step | Where it runs | What it does |
| --- | --- | --- |
| Unit tests | `gate-pr` job `agent` | Auth rules, approval step, memory scope, MCP allowlist |
| Release evaluations | `gate-pr` job `agent` | `evals/run.py` with LangSmith's `evaluate`; fails below `evals/thresholds.json` |
| Image build, SBOM, scan | `gate-pr` job `agent-image` | `langgraph build`; CycloneDX SBOM; fails on a critical vulnerability with a fix |
| Publish | `agent-release` workflow, on tag `agent-template-v*` | Pushes the image, signs it and attaches the SBOM (cosign) |
| Deploy | LangSmith deployment control plane | New deployment revision from the signed image (needs a licence) |

In CI the evaluations run against a scripted stub, so they prove the gate works, not the quality of a model. On a
platform, run `python evals/run.py --upload` against each model class and keep the experiment as evidence.

The in-code example tools are placeholders; real tools come from the client's approved MCP servers.
