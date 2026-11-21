"""Configuration from the environment. Nothing here is a secret; secrets arrive as environment variables set by
the deployment (LangSmith workspace secrets), never from files in the repository."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Settings:
    # LangSmith LLM Gateway (AD-59): the only route to a model.
    gateway_base_url: str
    gateway_api_key: str
    model_class: str
    subagent_model_class: str
    # Keycloak realm that issues user tokens (AD-57).
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    # MCP servers that supply tools, and the only tool names the agent may use from them (default: none).
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    mcp_allowed_tools: frozenset[str] = frozenset()
    # Allowlisted MCP tools the deployment declares read-only. Every other MCP tool pauses for approval (CTL-14).
    mcp_read_only_tools: frozenset[str] = frozenset()
    # Development only (`langgraph dev` without sign-in): lets runs without a user share one memory namespace.
    allow_anonymous_memory: bool = False


def _names(variable: str) -> frozenset[str]:
    return frozenset(name.strip() for name in os.environ.get(variable, "").split(",") if name.strip())


def load() -> Settings:
    issuer = os.environ.get("OIDC_ISSUER", "https://keycloak.site.example/realms/langsmith").rstrip("/")
    return Settings(
        gateway_base_url=os.environ.get("LANGSMITH_GATEWAY", "https://langsmith.site.example/gateway/v1"),
        gateway_api_key=os.environ.get("LANGSMITH_GATEWAY_API_KEY", ""),
        model_class=os.environ.get("MODEL_CLASS", "custom/class-m"),
        subagent_model_class=os.environ.get("SUBAGENT_MODEL_CLASS", "custom/class-s"),
        oidc_issuer=issuer,
        oidc_audience=os.environ.get("OIDC_AUDIENCE", "workbench"),
        oidc_jwks_url=os.environ.get("OIDC_JWKS_URL", f"{issuer}/protocol/openid-connect/certs"),
        mcp_servers=json.loads(os.environ.get("MCP_SERVERS") or "{}"),
        mcp_allowed_tools=_names("MCP_ALLOWED_TOOLS"),
        mcp_read_only_tools=_names("MCP_READ_ONLY_TOOLS"),
        allow_anonymous_memory=os.environ.get("INNOVOX_ALLOW_ANONYMOUS_MEMORY") == "1",
    )
