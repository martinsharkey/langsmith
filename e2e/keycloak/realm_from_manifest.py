#!/usr/bin/env python3
"""Builds the end-to-end Keycloak import directory from the realm that ships, so CI tests that realm (issue #44).

Reads `spec.realm` from the production KeycloakRealmImport manifest and writes it as `<realm>-realm.json`, with only
the changes a local, plain-HTTP test run needs (listed in TEST_ONLY below). Client scopes, roles, protocol mappers
and client secrets placeholders are kept as they are: Keycloak resolves `${NAME}` placeholders from environment
variables at import, as the Keycloak operator does from Secrets. Test users come from a separate file next to this
script, `<realm>-users-0.json`, which Keycloak imports with the realm (Keycloak guide "Importing and exporting
realms": file naming conventions).

    python3 e2e/keycloak/realm_from_manifest.py <manifest.yaml> <public workbench URL> <output directory>
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent

# Test-only changes, and why:
# - sslRequired "none": the e2e stack runs over plain HTTP on localhost.
# - the workbench client's URLs point at the local workbench instead of the site's hostname.
# - TOTP enrolment is not a default action: a scripted browser cannot enrol an authenticator.
TEST_ONLY = ("sslRequired", "workbench redirectUris/webOrigins/post.logout.redirect.uris", "CONFIGURE_TOTP default")


def test_realm(manifest: Path, public_url: str) -> dict:
    docs = [d for d in yaml.safe_load_all(manifest.read_text()) if d and d.get("kind") == "KeycloakRealmImport"]
    if len(docs) != 1:
        raise SystemExit(f"{manifest}: expected one KeycloakRealmImport, found {len(docs)}")
    realm = docs[0]["spec"]["realm"]
    realm["sslRequired"] = "none"
    workbench = next(c for c in realm["clients"] if c["clientId"] == "workbench")
    workbench["redirectUris"] = [f"{public_url}/api/auth/callback"]
    workbench["webOrigins"] = [public_url]
    workbench.setdefault("attributes", {})["post.logout.redirect.uris"] = public_url
    for action in realm.get("requiredActions", []):
        if action.get("alias") == "CONFIGURE_TOTP":
            action["defaultAction"] = False
    return realm


def main(manifest: str, public_url: str, out: str) -> None:
    realm = test_realm(Path(manifest), public_url.rstrip("/"))
    target = Path(out)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    name = realm["realm"]
    (target / f"{name}-realm.json").write_text(json.dumps(realm, indent=2))
    shutil.copy(HERE / f"{name}-users-0.json", target / f"{name}-users-0.json")
    print(f"realm {name} from {manifest} -> {target} (test-only changes: {', '.join(TEST_ONLY)})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
