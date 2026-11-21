#!/usr/bin/env python3
"""versions.yaml is the single source of pinned versions (issue 65). This check fails when a pin elsewhere in the
repository disagrees with it, or is missing from it:

  - every Argo CD Application source that is not this repository (Helm chart or git tag);
  - every image named in platform/manifests (outside vendored upstream releases);
  - every vendored upstream release under platform/manifests/**/vendor/, by SHA-256 of the file;
  - every *_VERSION variable in the GitHub workflows;
  - every package pinned in .github/requirements/*.txt that versions.yaml names.

Keys are looked up across all groups of versions.yaml, so each key must be unique.

Usage: check_versions.py           run the check
       check_versions.py --get KEY print one pinned value (for the Makefile)
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
THIS_REPO = "https://github.com/martinsharkey/langsmith.git"


def load_versions() -> tuple[dict[str, str], list[str]]:
    flat: dict[str, str] = {}
    errors = []
    for group, entries in yaml.safe_load((ROOT / "versions.yaml").read_text()).items():
        for key, value in (entries or {}).items():
            if key in flat:
                errors.append(f"versions.yaml: key '{key}' appears in more than one group ({group})")
            flat[key] = str(value)
    return flat, errors


def same(a: str, b: str) -> bool:
    """Versions written with and without a leading 'v' are the same pin (GitHub release tags vs file names)."""
    return a.removeprefix("v") == b.removeprefix("v")


def stem(key: str) -> str:
    for suffix in ("-charts", "-chart"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def check_applications(versions: dict[str, str]) -> list[str]:
    errors = []
    for path in sorted((ROOT / "platform" / "apps").glob("*.yaml")):
        for app in yaml.safe_load_all(path.read_text()):
            if not app or app.get("kind") != "Application":
                continue
            name = app["metadata"]["name"]
            spec = app["spec"]
            for src in spec.get("sources") or [spec["source"]]:
                if src["repoURL"] == THIS_REPO:
                    continue
                chart = src.get("chart", "")
                revision = str(src["targetRevision"])
                # Exact key first (cert-manager-chart for chart cert-manager); then a shared key for a family of
                # applications (istio-charts for istio-base, istio-ingress and istiod).
                keys = [k for k in versions if stem(k) in (name, chart)] or \
                       [k for k in versions if name.startswith(stem(k)) and not k.endswith("-sha256")]
                if not keys:
                    errors.append(f"{path.relative_to(ROOT)}: {name} pins {revision}, but versions.yaml has no "
                                  f"entry for it")
                elif not any(same(versions[k], revision) for k in keys):
                    pinned = ", ".join(f"{k}={versions[k]}" for k in keys)
                    errors.append(f"{path.relative_to(ROOT)}: {name} pins {revision}; versions.yaml has {pinned}")
    return errors


def images(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("image", "imageName") and isinstance(value, str):
                found.append(value)
            else:
                found += images(value)
    elif isinstance(node, list):
        for item in node:
            found += images(item)
    return found


def check_manifests(versions: dict[str, str]) -> list[str]:
    errors = []
    pinned_images = set(versions.values())
    for path in sorted((ROOT / "platform" / "manifests").rglob("*.yaml")):
        rel = path.relative_to(ROOT)
        if "vendor" in path.parts:
            key = f"{path.stem}-sha256"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if key not in versions:
                errors.append(f"{rel}: vendored release has no '{key}' in versions.yaml")
            elif versions[key] != digest:
                errors.append(f"{rel}: SHA-256 {digest} differs from versions.yaml {key}={versions[key]}")
            continue
        for doc in yaml.safe_load_all(path.read_text()):
            for image in images(doc):
                if image not in pinned_images:
                    errors.append(f"{rel}: image {image} is not pinned in versions.yaml")
    return errors


def check_workflows(versions: dict[str, str]) -> list[str]:
    errors = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        scopes = [workflow.get("env") or {}] + [job.get("env") or {} for job in workflow.get("jobs", {}).values()]
        for env in scopes:
            for var, value in env.items():
                if not var.endswith("_VERSION"):
                    continue
                key = var.removesuffix("_VERSION").lower().replace("_", "-")
                if key not in versions:
                    errors.append(f"{path.relative_to(ROOT)}: {var}={value} has no '{key}' in versions.yaml")
                elif not same(str(value), versions[key]):
                    errors.append(f"{path.relative_to(ROOT)}: {var}={value}; versions.yaml has {key}={versions[key]}")
    return errors


def check_requirements(versions: dict[str, str]) -> list[str]:
    """Hashed requirement files. Each pin is one 'name==version --hash=...' line written by hand or by a lock
    tool; pip's own requirements parser is not a public API, so the line is split on '==' and whitespace. Only
    names that versions.yaml lists are compared; pip refuses any line that is malformed (--require-hashes)."""
    errors = []
    for path in sorted((ROOT / ".github" / "requirements").glob("*.txt")):
        for line in path.read_text().splitlines():
            spec = line.split("#")[0].strip().split(" ")[0]
            if "==" not in spec:
                continue
            name, version = spec.split("==", 1)
            if name in versions and not same(version, versions[name]):
                errors.append(f"{path.relative_to(ROOT)}: {name}=={version}; versions.yaml has {versions[name]}")
    return errors


def main() -> int:
    versions, errors = load_versions()
    if sys.argv[1:2] == ["--get"]:
        print(versions[sys.argv[2]])
        return 0
    errors += check_applications(versions) + check_manifests(versions) + check_workflows(versions) \
        + check_requirements(versions)
    for line in errors:
        print(f"ERROR {line}")
    print(f"{len(versions)} pins in versions.yaml checked; {len(errors)} disagreements")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
