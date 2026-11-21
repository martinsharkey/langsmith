#!/usr/bin/env python3
"""Checks that identity, secrets and GitOps configuration agree across files before anything reaches a cluster.

Each check names the issue it guards. Static checks always run; the others run when their input is given:

  check_platform.py                                   static checks only
  check_platform.py --rendered out/rendered-b1        also checks rendered OpenBao and Argo CD charts
  check_platform.py --built overlay-b1.yaml ...       also checks Applications built by kustomize

Inputs come from the CI entry points: scripts/render_charts.py writes the rendered charts and
`kubectl kustomize platform/overlays/<mode>` (and `platform/argocd/<mode>`) writes the built Applications.

Parsing note (owner rules 3): the runbook check reads shell commands out of a Markdown runbook. It uses the
standard library tokenizer (shlex) on the `bao kv put` lines only; no other tool reads runbooks, and the check
was requested in issue #46. Kubernetes objects are read with PyYAML, as the other repository checks do.
"""
from __future__ import annotations

import argparse
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs/runbooks/install-b1.md"
RELEASE = ROOT / "platform/overlays/release/kustomization.yaml"
# Values the Application files carry for this repository; the release component replaces them at build time.
PLACEHOLDER_REPO = "https://git.invalid/platform.git"
PLACEHOLDER_REVISION = "platform-release"
RELEASE_TAG = re.compile(r"^platform-v\d+\.\d+\.\d+$")

errors: list[str] = []


def fail(check: str, message: str) -> None:
    errors.append(f"[{check}] {message}")


def load_all(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]


def manifests(*dirs: str) -> list[tuple[Path, dict]]:
    found = []
    for d in dirs:
        for path in sorted((ROOT / d).rglob("*.yaml")):
            found += [(path, doc) for doc in load_all(path)]
    return found


# --- #46: every OpenBao path and property an ExternalSecret reads is written by the runbook --------------------

def runbook_writes(text: str) -> set[tuple[str, str]]:
    """(path, property) pairs written by `bao kv put` commands in the runbook's shell blocks."""
    joined = re.sub(r"\\\n\s*", " ", text)
    writes = set()
    paths: list[str] = []
    for line in joined.splitlines():
        if "bao kv put" not in line:
            continue
        tokens = shlex.split(line[line.index("bao kv put"):], comments=True)
        path = tokens[3]
        paths.append(path)
        for token in tokens[4:]:
            if "=" in token and not token.startswith("-"):
                writes.add((path, token.split("=", 1)[0]))
    for path in sorted({p for p in paths if paths.count(p) > 1}):
        # `bao kv put` replaces the whole secret: a second put to a path drops the first put's properties.
        fail("#46 runbook-secrets", f"runbook writes {path} more than once; the last write replaces the others")
    return writes


def check_runbook_secrets() -> None:
    check = "#46 runbook-secrets"
    stores = {doc["metadata"]["name"]: doc["spec"]["provider"]["vault"]["path"]
              for _, doc in manifests("platform/manifests") if doc.get("kind") == "ClusterSecretStore"}
    written = runbook_writes(RUNBOOK.read_text())
    needed = 0
    for path, doc in manifests("platform/manifests"):
        if doc.get("kind") != "ExternalSecret":
            continue
        mount = stores.get(doc["spec"]["secretStoreRef"]["name"])
        for item in doc["spec"].get("data", []):
            ref = item["remoteRef"]
            needed += 1
            pair = (f"{mount}/{ref['key']}", ref["property"])
            if pair not in written:
                fail(check, f"{path.relative_to(ROOT)} ExternalSecret {doc['metadata']['name']} reads "
                            f"{pair[0]} property {pair[1]}, which {RUNBOOK.relative_to(ROOT)} never writes")
    print(f"{check}: {needed} secret references, {len(written)} runbook writes")


# --- #60: the gateway route to Keycloak reaches a port that speaks what the mesh delivers ----------------------

def check_keycloak_route() -> None:
    check = "#60 keycloak-route"
    keycloak = next(d for _, d in manifests("platform/manifests/keycloak") if d.get("kind") == "Keycloak")
    http = keycloak["spec"].get("http", {})
    hostname = keycloak["spec"].get("hostname", {}).get("hostname", "")
    host = urlparse(hostname).hostname if "://" in hostname else hostname
    mesh = [d for _, d in manifests("platform/manifests/istio")]
    routes = [d for d in mesh if d.get("kind") == "VirtualService" and host in d["spec"].get("hosts", [])]
    if len(routes) != 1:
        fail(check, f"expected one VirtualService for {host}, found {len(routes)}")
        return
    port = routes[0]["spec"]["http"][0]["route"][0]["destination"]["port"]["number"]
    target = routes[0]["spec"]["http"][0]["route"][0]["destination"]["host"]
    http_port = http.get("httpPort", 8080)
    if port != http_port or http.get("httpEnabled") is not True or http.get("tlsSecret"):
        fail(check, f"gateway sends HTTP (inside mesh mutual TLS) to {target}:{port}, but Keycloak does not serve "
                    f"plain HTTP there (httpEnabled={http.get('httpEnabled')}, httpPort={http_port}, "
                    f"tlsSecret={http.get('tlsSecret')})")
    if not hostname.startswith("https://"):
        fail(check, f"Keycloak hostname '{hostname}' must be the full https:// URL the gateway serves, so the "
                    "issuer does not depend on forwarded headers")
    print(f"{check}: route {host} -> {target}:{port}")


# --- #53: one place sets the repository and release every Application syncs from --------------------------------

def release_source() -> tuple[str, str] | None:
    if not RELEASE.exists():
        fail("#53 gitops-source", f"{RELEASE.relative_to(ROOT)} does not exist: nothing sets the release in one place")
        return None
    values = {}
    for rep in yaml.safe_load(RELEASE.read_text()).get("replacements", []):
        for target in rep["targets"]:
            for field in target.get("fieldPaths", []):
                values[field.rsplit(".", 1)[-1]] = rep.get("sourceValue")
    repo, revision = values.get("repoURL"), values.get("targetRevision")
    if not repo or not revision:
        fail("#53 gitops-source", "release component must set both repoURL and targetRevision")
        return None
    if not RELEASE_TAG.match(str(revision)):
        fail("#53 gitops-source", f"release targetRevision '{revision}' is not a platform-vX.Y.Z tag (owner ruling, #63)")
    return repo, str(revision)


def this_repo_sources(app: dict) -> list[dict]:
    """Git sources that read this repository: a `ref: values` source, or a plain path that exists here."""
    spec = app["spec"]
    return [s for s in (spec.get("sources") or [spec["source"]]) if "chart" not in s and
            (s.get("ref") == "values" or ("path" in s and (ROOT / s["path"]).is_dir()))]


def check_gitops_files() -> None:
    check = "#53 gitops-source"
    source = release_source()
    apps = 0
    for path, doc in manifests("platform/apps", "platform/argocd", "platform/overlays"):
        if doc.get("kind") != "Application":
            continue
        apps += 1
        for src in this_repo_sources(doc):
            if src["repoURL"] != PLACEHOLDER_REPO or str(src["targetRevision"]) != PLACEHOLDER_REVISION:
                fail(check, f"{path.relative_to(ROOT)} Application {doc['metadata']['name']} sets its own "
                            f"{src['repoURL']}@{src['targetRevision']}; use {PLACEHOLDER_REPO}@{PLACEHOLDER_REVISION} "
                            f"and let {RELEASE.relative_to(ROOT)} set it")
    if source:
        print(f"{check}: {apps} Applications in files, release {source[0]}@{source[1]}")


def check_built(files: list[Path]) -> None:
    check = "#53 gitops-built"
    source = release_source()
    if not source:
        return
    checked = 0
    for path in files:
        for doc in load_all(path):
            if doc.get("kind") != "Application":
                continue
            for src in this_repo_sources(doc):
                checked += 1
                if (src["repoURL"], str(src["targetRevision"])) != source:
                    fail(check, f"{path.name}: Application {doc['metadata']['name']} syncs "
                                f"{src['repoURL']}@{src['targetRevision']}, not the release {source[0]}@{source[1]}")
    print(f"{check}: {checked} sources of this repository in {len(files)} built files")


# --- #45 and #59: rendered OpenBao and Argo CD -------------------------------------------------------------------

def check_rendered_openbao(rendered: Path) -> None:
    check = "#45 openbao-tls"
    docs = load_all(rendered / "openbao.yaml")
    config = next((d["data"]["extraconfig-from-values.hcl"] for d in docs
                   if d.get("kind") == "ConfigMap" and "extraconfig-from-values.hcl" in d.get("data", {})), "")
    listener = re.search(r'listener\s+"tcp"\s*\{(.*?)\n\s*\}', config, flags=re.S)
    body = listener.group(1) if listener else ""
    if not listener:
        fail(check, "rendered OpenBao configuration has no tcp listener")
    if re.search(r'^\s*tls_disable\s*=\s*("?(1|true)"?)', body, flags=re.M):
        fail(check, "OpenBao listener sets tls_disable: secrets would cross the network in clear text, and "
                    "External Secrets (https) cannot connect")
    for key in ("tls_cert_file", "tls_key_file"):
        if key not in body:
            fail(check, f"OpenBao listener has no {key}")
    if "retry_join" not in config or "leader_ca_cert_file" not in config:
        fail(check, "Raft storage has no retry_join with leader_ca_cert_file: standby nodes cannot join over TLS")
    sts = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
    env = {e["name"]: e.get("value", "") for e in sts["spec"]["template"]["spec"]["containers"][0]["env"]} if sts else {}
    if not env.get("BAO_ADDR", "").startswith("https://"):
        fail(check, f"OpenBao BAO_ADDR is '{env.get('BAO_ADDR')}', not https")
    store = next(d for _, d in manifests("platform/manifests/secrets") if d.get("kind") == "ClusterSecretStore")
    store_host = urlparse(store["spec"]["provider"]["vault"]["server"]).hostname
    certs = [d for d in docs if d.get("kind") == "Certificate"]
    mounted = {v.get("secret", {}).get("secretName") for v in
               (sts["spec"]["template"]["spec"].get("volumes", []) if sts else [])}
    if not any(c["spec"]["secretName"] in mounted and store_host in c["spec"].get("dnsNames", []) for c in certs):
        fail(check, f"no Certificate for {store_host} (the ClusterSecretStore server) is mounted into OpenBao")
    print(f"{check}: listener checked, {len(certs)} certificate(s)")


def check_rendered_argocd(rendered: Path) -> None:
    check = "#59 argocd-oidc"
    docs = load_all(rendered / "argo-cd.yaml")
    cm = next((d.get("data", {}) for d in docs if d.get("kind") == "ConfigMap"
               and d["metadata"]["name"] == "argocd-cm"), {})
    rbac = next((d.get("data", {}) for d in docs if d.get("kind") == "ConfigMap"
                 and d["metadata"]["name"] == "argocd-rbac-cm"), {})
    oidc = yaml.safe_load(cm.get("oidc.config", "")) or {}
    langsmith = yaml.safe_load((ROOT / "platform/values/langsmith/values.yaml").read_text())
    issuer = next(v for k, v in walk(langsmith) if k == "oauthIssuerUrl")
    if not oidc:
        fail(check, "argocd-cm has no oidc.config: the local admin account is the only way in")
    else:
        if oidc.get("issuer") != issuer:
            fail(check, f"Argo CD issuer {oidc.get('issuer')} differs from the platform issuer {issuer}")
        if not oidc.get("clientID"):
            fail(check, "oidc.config has no clientID")
        if "groups" not in oidc.get("requestedScopes", ["groups"]):
            fail(check, "oidc.config does not request the groups scope the RBAC policy maps")
        root_ca = str(oidc.get("rootCA", ""))
        if not root_ca:
            fail(check, "oidc.config has no rootCA: the platform CA is not a public CA")
        elif root_ca.startswith("$") and ":" in root_ca:
            # `$<secret>:<key>` resolves only from a Secret labelled app.kubernetes.io/part-of=argocd.
            secret = root_ca[1:].split(":", 1)[0]
            bundles = [d for _, d in manifests("platform/manifests/pki") if d.get("kind") == "Bundle"
                       and d["metadata"]["name"] == secret]
            labels = (bundles[0]["spec"]["target"]["secret"].get("metadata", {}).get("labels", {})
                      if bundles else {})
            if labels.get("app.kubernetes.io/part-of") != "argocd":
                fail(check, f"rootCA reads Secret {secret}, but its trust-manager Bundle does not label the Secret "
                            "app.kubernetes.io/part-of: argocd, so Argo CD cannot resolve it")
    if str(cm.get("admin.enabled", "true")).lower() != "false":
        fail(check, "local admin account is enabled (admin.enabled)")
    if "resource.customizations.health.argoproj.io_Application" not in cm:
        fail(check, "no Application health check: the root app does not wait for one wave to be healthy "
                    "before the next (Argo CD health docs, 'Argocd App')")
    if not rbac.get("policy.csv", "").strip():
        fail(check, "argocd-rbac-cm policy.csv is empty: no group is mapped to a role")
    print(f"{check}: argocd-cm keys {sorted(k for k in cm if not k.startswith('resource.exclusions'))[:12]}")


# --- #59: with the Application health check, a wave waits for the one before it; nothing may need a later wave ---

def kustomize_resources(directory: Path) -> list[dict]:
    """Objects listed under `resources:` of a plain kustomization (files or sub-directories), as Argo CD applies them."""
    kustomization = directory / "kustomization.yaml"
    if not kustomization.exists():
        return [d for p in sorted(directory.glob("*.yaml")) for d in load_all(p)]
    docs = []
    for entry in yaml.safe_load(kustomization.read_text()).get("resources", []):
        target = directory / entry
        docs += kustomize_resources(target) if target.is_dir() else load_all(target) if target.exists() else []
    return docs


class RenderedLoader(yaml.SafeLoader):
    """SafeLoader that reads a bare `=` (YAML 1.1 value tag, which some charts emit in a list) as the string '='."""


RenderedLoader.add_constructor("tag:yaml.org,2002:value", yaml.SafeLoader.construct_yaml_str)


def app_objects(app: dict, rendered: Path) -> list[dict] | None:
    """What an Application applies: its rendered chart, or the manifests at its path in this repository."""
    name = app["metadata"]["name"]
    chart = rendered / f"{name}.yaml"
    if chart.exists():
        return [d for d in yaml.load_all(chart.read_text(), Loader=RenderedLoader) if isinstance(d, dict)]
    paths = [s["path"] for s in (app["spec"].get("sources") or [app["spec"]["source"]])
             if "path" in s and (ROOT / s["path"]).is_dir()]
    return [d for p in paths for d in kustomize_resources(ROOT / p)] if paths else None


def check_sync_waves(rendered: Path) -> None:
    check = "#59 sync-waves"
    waves, objects = {}, {}
    for _, app in manifests("platform/apps"):
        if app.get("kind") != "Application":
            continue
        name = app["metadata"]["name"]
        waves[name] = int(app["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-wave", "0"))
        found = app_objects(app, rendered)
        if found is None:
            # Manifests read straight from another repository (the Keycloak operator): what they provide cannot
            # be seen here, so dependencies on them are not checked. Said plainly rather than passed silently.
            print(f"NOTE {check}: Application {name} syncs manifests from another repository; not checked")
        objects[name] = found or []
    # What each Application provides: resource types (CRDs), storage classes and cluster issuers.
    provides: dict[tuple[str, str], str] = {}
    for name, docs in objects.items():
        for d in docs:
            kind = d.get("kind")
            if kind == "List":
                # Argo CD v3.6.1 does not unwrap a List (gitops-engine kube.SplitYAML keeps it as one object).
                fail(check, f"Application {name} renders a kind: List; Argo CD applies it as one object, not its items")
            if kind == "CustomResourceDefinition":
                spec = d.get("spec", {})
                provides[("type", f"{spec.get('group')}/{spec.get('names', {}).get('kind')}")] = name
            elif kind in ("StorageClass", "ClusterIssuer"):
                provides[(kind, d["metadata"]["name"])] = name
    checked = 0
    for name, docs in objects.items():
        needs: set[tuple[str, str]] = set()
        for d in docs:
            group = str(d.get("apiVersion", "")).rpartition("/")[0]
            if group:
                needs.add(("type", f"{group}/{d.get('kind')}"))
            for key, value in walk(d):
                if key in ("storageClassName", "storageClass") and isinstance(value, str):
                    needs.add(("StorageClass", value))
                elif key == "issuerRef" and isinstance(value, dict) and value.get("kind") == "ClusterIssuer":
                    needs.add(("ClusterIssuer", value.get("name")))
        for need in sorted(needs):
            provider = provides.get(need)
            if provider is None or provider == name:
                continue  # built into Kubernetes or RKE2, bootstrapped with Argo CD, or carried by the same app
            checked += 1
            if waves[provider] >= waves[name]:
                fail(check, f"Application {name} (wave {waves[name]}) needs {need[0]} {need[1]} from {provider} "
                            f"(wave {waves[provider]}): with health gating it must come in an earlier wave")
    print(f"{check}: {checked} cross-application dependencies checked across {len(waves)} Applications")


def walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rendered", type=Path, help="directory written by scripts/render_charts.py")
    parser.add_argument("--built", type=Path, nargs="*", default=[], help="output of kubectl kustomize")
    args = parser.parse_args()
    check_runbook_secrets()
    check_keycloak_route()
    check_gitops_files()
    if args.built:
        check_built(args.built)
    if args.rendered:
        check_rendered_openbao(args.rendered)
        check_rendered_argocd(args.rendered)
        check_sync_waves(args.rendered)
    for line in errors:
        print("ERROR", line)
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
