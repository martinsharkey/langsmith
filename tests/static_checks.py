#!/usr/bin/env python3
"""Repository checks for the data, model, logging and egress-test controls (issues 34, 38, 39, 47, 48, 49, 57, 58
and 61). Each check reads the manifests and values as committed; none needs a cluster.

Usage: tests/static_checks.py            exit 1 and one ERROR line per finding
Requires: PyYAML. Run from any directory; paths resolve from the repository root.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATEWAY = "cluster.local/ns/langsmith/sa/langsmith-agent-gateway"
CHAT_PATHS = {"/v1/chat/completions", "/v1/completions"}
# Namespaces the zero-egress probe runs in (tests/run-e2-checks.sh). Keep the two lists the same.
PROBE_NAMESPACES = ["egress-probe", "observability"]


def docs(path: pathlib.Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]


def yaml_files(*dirs: str) -> list[pathlib.Path]:
    return sorted(p for d in dirs for p in (ROOT / d).rglob("*.yaml"))


def rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT))


def walk(node, key: str):
    """Every value stored under `key`, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item, key)


def check_vllm_callers() -> list[str]:
    """#38: chat and completions only from the LLM Gateway's identity; no namespace-wide grants."""
    errors = []
    for path in yaml_files("platform/manifests/models"):
        for doc in docs(path):
            if doc.get("kind") != "AuthorizationPolicy":
                continue
            name = doc["metadata"]["name"]
            for rule in doc["spec"].get("rules", []):
                sources = [f.get("source", {}) for f in rule.get("from", [])]
                paths = {p for t in rule.get("to", []) for p in t.get("operation", {}).get("paths", [])}
                if not sources or any("namespaces" in s or not s.get("principals") for s in sources):
                    errors.append(f"#38 {rel(path)} {name}: every rule must name principals, not namespaces")
                principals = {p for s in sources for p in s.get("principals", [])}
                if paths & CHAT_PATHS and principals - {GATEWAY}:
                    errors.append(f"#38 {rel(path)} {name}: chat paths allowed to {sorted(principals - {GATEWAY})}")
    return errors


def check_s3_https() -> list[str]:
    """#39: the object gateway serves TLS only, and no client names it over plain HTTP."""
    errors = []
    for path in yaml_files("platform"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"http://rook-ceph-rgw", line):
                errors.append(f"#39 {rel(path)}:{number}: S3 endpoint over plain HTTP")
        for doc in docs(path):
            if doc.get("kind") == "CephObjectStore":
                gateway = doc["spec"].get("gateway", {})
                if gateway.get("port") or not gateway.get("securePort") or not gateway.get("sslCertificateRef"):
                    errors.append(f"#39 {rel(path)}: CephObjectStore {doc['metadata']['name']} must serve "
                                  "securePort with sslCertificateRef and no plain port")
    return errors


def produced_secrets() -> set[tuple[str, str]]:
    """(namespace, name) of every Secret the repository creates, including chart extraObjects in values files.
    trust-manager Bundles are written to every namespace, so they are returned with namespace '*'."""
    made = set()
    for path in yaml_files("platform/manifests", "platform/values"):
        found = docs(path)
        extra = [o for values in found for o in values.get("extraObjects") or [] if isinstance(o, dict)]
        for doc in found + extra:
            kind, meta = doc.get("kind"), doc.get("metadata", {})
            ns = meta.get("namespace", "")
            if kind == "Secret":
                made.add((ns, meta["name"]))
            elif kind == "ExternalSecret":
                made.add((ns, doc["spec"].get("target", {}).get("name", meta["name"])))
            elif kind == "Certificate":
                made.add((ns, doc["spec"]["secretName"]))
            elif kind == "Bundle":
                made.add(("*", meta["name"]))
    return made


def check_shipper_secrets() -> list[str]:
    """#47: every Secret the log and trace shippers mount exists; #57: neither holds the OpenSearch admin password."""
    errors = []
    made = produced_secrets()
    for chart in ("fluent-bit", "otel-collector"):
        path = ROOT / "platform/values" / chart / "values.yaml"
        values = docs(path)[0]
        names = {v for v in walk(values, "secretName")} | {v.get("name") for v in walk(values, "secretKeyRef")}
        for name in sorted(names):
            if ("observability", name) not in made and ("*", name) not in made:
                errors.append(f"#47 {rel(path)}: Secret {name} is mounted but nothing in the repository creates it")
            if name == "opensearch-admin":
                errors.append(f"#57 {rel(path)}: mounts the OpenSearch admin password")
        for user in walk(values, "username"):
            if user == "admin":
                errors.append(f"#57 {rel(path)}: authenticates as the OpenSearch admin user")
        if re.search(r"HTTP_User\s+admin\b", path.read_text()):
            errors.append(f"#57 {rel(path)}: authenticates as the OpenSearch admin user")
    return errors


def check_cnpg_backup() -> list[str]:
    """#48: a volume-snapshot ScheduledBackup needs the Cluster's backup.volumeSnapshot.className."""
    errors = []
    snapshot_classes = {d["metadata"]["name"] for p in yaml_files("platform/manifests") for d in docs(p)
                        if d.get("kind") == "VolumeSnapshotClass"}
    for path in yaml_files("platform/manifests/data"):
        found = docs(path)
        clusters = {d["metadata"]["name"]: d for d in found if d.get("kind") == "Cluster"}
        for doc in found:
            if doc.get("kind") == "ScheduledBackup" and doc["spec"].get("method") == "volumeSnapshot":
                cluster = clusters.get(doc["spec"]["cluster"]["name"], {})
                cls = cluster.get("spec", {}).get("backup", {}).get("volumeSnapshot", {}).get("className")
                if cls not in snapshot_classes:
                    errors.append(f"#48 {rel(path)}: Cluster {doc['spec']['cluster']['name']} has no "
                                  "backup.volumeSnapshot.className naming a VolumeSnapshotClass in the repository")
    return errors


def check_major_only_tags() -> list[str]:
    """#58: a tag that names only a major version (`:18`, `:pg15`) moves; pin a full version and a digest."""
    errors = []
    pattern = re.compile(r"^\s*-?\s*(?:image|imageName):\s*[\"']?([^\s\"'#]+)")
    for path in yaml_files("platform"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = pattern.match(line)
            if not match:
                continue
            name = match.group(1).split("@")[0]
            tag = name.rsplit(":", 1)[1] if ":" in name.split("/")[-1] else ""
            if re.fullmatch(r"(pg)?\d+", tag):
                errors.append(f"#58 {rel(path)}:{number}: {match.group(1)} names only a major version")
    return errors


def check_model_weights() -> list[str]:
    """#49 (owner ruling 2026-11-21): weights are a signed OCI artefact mounted as an image volume, by digest."""
    errors = []
    for path in yaml_files("platform/manifests/models"):
        for doc in docs(path):
            if doc.get("kind") == "PersistentVolumeClaim":
                errors.append(f"#49 {rel(path)}: model weights must not come from a PersistentVolumeClaim")
            if doc.get("kind") != "Deployment":
                continue
            volumes = {v["name"]: v for v in doc["spec"]["template"]["spec"].get("volumes", [])}
            weights = volumes.get("weights", {})
            reference = weights.get("image", {}).get("reference", "")
            if "@sha256:" not in reference:
                errors.append(f"#49 {rel(path)} {doc['metadata']['name']}: weights must be an image volume "
                              "referenced by digest")
    return errors


def check_valkey() -> list[str]:
    """#61: the Valkey password is not on any command line (server arguments or probe)."""
    errors = []
    path = ROOT / "platform/manifests/data/valkey.yaml"
    for doc in docs(path):
        if doc.get("kind") != "StatefulSet":
            continue
        for container in doc["spec"]["template"]["spec"]["containers"]:
            argv = [str(a) for a in container.get("command", []) + container.get("args", [])]
            probe = [str(a) for a in container.get("readinessProbe", {}).get("exec", {}).get("command", [])]
            if any("requirepass" in a or "$(" in a for a in argv):
                errors.append(f"#61 {rel(path)}: Valkey password passed on the command line")
            if any(re.search(r"(^|\s)-a\s", a) for a in probe):
                errors.append(f"#61 {rel(path)}: Valkey password passed on the probe's command line")
    return errors


def check_harbor_offline() -> list[str]:
    """#61: in the enclave (B2) Harbor's Trivy neither downloads its database nor calls out while scanning."""
    errors = []
    b2 = ROOT / "platform/values/harbor/values-b2.yaml"
    trivy = docs(b2)[0].get("trivy", {}) if b2.exists() else {}
    if not (trivy.get("offlineScan") and trivy.get("skipUpdate") and trivy.get("skipJavaDBUpdate")):
        errors.append(f"#61 {rel(b2)}: must set trivy.offlineScan, skipUpdate and skipJavaDBUpdate")
    overlay = (ROOT / "platform/overlays/b2/kustomization.yaml").read_text()
    if "platform/values/harbor/values-b2.yaml" not in overlay:
        errors.append("#61 platform/overlays/b2/kustomization.yaml: does not add platform/values/harbor/values-b2.yaml "
                      "to the harbor application")
    return errors


def check_egress_probe() -> list[str]:
    """#34: the zero-egress probe must run where no namespace egress policy would block it anyway."""
    errors = []
    governed = {d["metadata"].get("namespace") for p in yaml_files("policies/egress") for d in docs(p)
                if d.get("kind") == "CiliumNetworkPolicy" and "egress" in d.get("spec", {})}
    for path in yaml_files("tests/egress"):
        for doc in docs(path):
            if doc.get("kind") == "Job" and doc["metadata"].get("namespace"):
                errors.append(f"#34 {rel(path)}: the probe Job names namespace {doc['metadata']['namespace']}; "
                              "run-e2-checks.sh sets it")
    for ns in PROBE_NAMESPACES:
        if ns in governed:
            errors.append(f"#34 probe namespace {ns} has its own egress policy, so the probe proves nothing")
    script = (ROOT / "tests/run-e2-checks.sh").read_text()
    for ns in PROBE_NAMESPACES:
        if ns not in script:
            errors.append(f"#34 tests/run-e2-checks.sh: does not run the zero-egress probe in {ns}")
    return errors


CHECKS = [check_vllm_callers, check_s3_https, check_shipper_secrets, check_cnpg_backup, check_major_only_tags,
          check_model_weights, check_valkey, check_harbor_offline, check_egress_probe]


def main() -> int:
    errors = [e for check in CHECKS for e in check()]
    for line in errors:
        print("ERROR", line)
    print(f"{len(CHECKS)} checks, {len(errors)} findings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
