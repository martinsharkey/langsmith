"""Configuration from the environment. Nothing here is a secret; secrets arrive as environment variables set by
the deployment (LangSmith workspace secrets), never from files in the repository."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
    )
