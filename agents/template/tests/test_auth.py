import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from langgraph_sdk import Auth

from innovox_agent import auth as auth_module

ISSUER = "https://keycloak.test/realms/langsmith"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, **overrides):
    now = int(time.time())
    claims = {"sub": "user-1", "preferred_username": "alice", "iss": ISSUER, "aud": "workbench",
              "iat": now, "exp": now + 300, "realm_access": {"roles": ["agent-user"]}}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setattr(auth_module, "_signing_key", lambda _token: KEY.public_key())


async def test_valid_token_returns_identity_and_roles():
    user = await auth_module.authenticate(f"Bearer {token()}")
    assert user["identity"] == "user-1"
    assert user["permissions"] == ["agent-user"]


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer not-a-jwt"])
async def test_missing_or_malformed_header_is_401(header):
    with pytest.raises(Auth.exceptions.HTTPException) as err:
        await auth_module.authenticate(header)
    assert err.value.status_code == 401


@pytest.mark.parametrize("bad", [
    {"exp": int(time.time()) - 10},
    {"aud": "another-client"},
    {"iss": "https://evil.example/realms/langsmith"},
])
async def test_expired_wrong_audience_or_issuer_is_401(bad):
    with pytest.raises(Auth.exceptions.HTTPException) as err:
        await auth_module.authenticate(f"Bearer {token(**bad)}")
    assert err.value.status_code == 401


async def test_token_signed_by_another_key_is_401():
    with pytest.raises(Auth.exceptions.HTTPException):
        await auth_module.authenticate(f"Bearer {token(key=OTHER_KEY)}")


def ctx(identity="user-1", permissions=(), action="create"):
    return SimpleNamespace(user=SimpleNamespace(identity=identity), permissions=list(permissions), action=action)


async def test_threads_are_stamped_and_filtered_by_owner():
    value = {"metadata": {}}
    assert await auth_module.own_threads(ctx(), value) == {"owner": "user-1"}
    assert value["metadata"] == {"owner": "user-1"}


async def test_store_namespace_is_forced_under_the_caller():
    value = {"namespace": ("memories",)}
    await auth_module.scope_store(ctx(), value)
    assert value["namespace"] == ("user-1", "memories")
    stolen = {"namespace": ("user-2", "memories")}
    await auth_module.scope_store(ctx(), stolen)
    assert stolen["namespace"] == ("user-1", "user-2", "memories")


async def test_only_admins_change_assistants():
    assert await auth_module.assistants(ctx(action="read"), {}) is True
    with pytest.raises(Auth.exceptions.HTTPException) as err:
        await auth_module.assistants(ctx(action="update"), {})
    assert err.value.status_code == 403
    assert await auth_module.assistants(ctx(action="update", permissions=["agent-admin"]), {}) is True


async def test_unlisted_resources_are_denied():
    with pytest.raises(Auth.exceptions.HTTPException) as err:
        await auth_module.deny_everything_else(ctx(), {})
    assert err.value.status_code == 403
