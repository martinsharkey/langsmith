"""Authentication and authorisation for this Agent Server deployment (AD-57).

A standalone Agent Server has no authentication by default, its store namespaces are shared by all callers, and
Studio access is allowed unless disabled. This module closes all three:

- every request must carry a Keycloak access token, verified against the realm's signing keys;
- threads and scheduled runs belong to the user who created them;
- store (long-term memory) operations are confined to the caller's own namespace;
- assistants can be read by any signed-in user but changed only by agent administrators.

Studio access is disabled in langgraph.json (`disable_studio_auth`).
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import jwt
from langgraph_sdk import Auth

from innovox_agent import settings

ADMIN_ROLE = "agent-admin"
ALGORITHMS = ["RS256", "ES256", "PS256"]

auth = Auth()


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def _signing_key(token: str) -> Any:
    return _jwks_client(settings.load().oidc_jwks_url).get_signing_key_from_jwt(token).key


def verify_token(token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience and expiry. Raises jwt.PyJWTError on any failure."""
    cfg = settings.load()
    return jwt.decode(
        token,
        _signing_key(token),
        algorithms=ALGORITHMS,
        issuer=cfg.oidc_issuer,
        audience=cfg.oidc_audience,
        options={"require": ["exp", "iat", "sub"]},
    )


def _roles(claims: dict[str, Any]) -> list[str]:
    return sorted(set((claims.get("realm_access") or {}).get("roles") or []))


@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = await asyncio.to_thread(verify_token, token)
    except Exception as exc:  # any verification failure is a 401; details stay in the server log
        raise Auth.exceptions.HTTPException(status_code=401, detail="Invalid token") from exc
    return {
        "identity": claims["sub"],
        "display_name": claims.get("preferred_username", claims["sub"]),
        "is_authenticated": True,
        "permissions": _roles(claims),
    }


def _own(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict[str, str]:
    """Stamp the caller as owner on anything being written and filter everything to the caller."""
    owner = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.update(owner)
    return owner


@auth.on.threads
async def own_threads(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict[str, str]:
    return _own(ctx, value)


@auth.on.crons
async def own_crons(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict[str, str]:
    return _own(ctx, value)


@auth.on.assistants
async def assistants(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    if ctx.action in ("read", "search"):
        return True
    if ADMIN_ROLE in ctx.permissions:
        return True
    raise Auth.exceptions.HTTPException(status_code=403, detail="Only agent administrators can change assistants")


@auth.on.store
async def scope_store(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> None:
    """Confine store operations to the caller by prefixing the namespace with their identity."""
    namespace = tuple(value["namespace"]) if value.get("namespace") else ()
    if not namespace or namespace[0] != ctx.user.identity:
        namespace = (ctx.user.identity, *namespace)
    value["namespace"] = namespace


@auth.on
async def deny_everything_else(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """Any resource without a specific rule above is refused."""
    raise Auth.exceptions.HTTPException(status_code=403, detail="Not permitted")
