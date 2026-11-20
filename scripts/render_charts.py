#!/usr/bin/env python3
"""Render every Helm source of the Argo CD applications with this repository's values.

Usage: render_charts.py <mode: b1|b2> <output dir>
Requires: helm, kubectl (for kustomize), PyYAML. Reads the mode overlay so patches (extra value files) apply.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kw)


def main() -> int:
    mode, out = sys.argv[1], pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    built = run(["kubectl", "kustomize", str(ROOT / "platform" / "overlays" / mode)])
    if built.returncode != 0:
        print(built.stderr, file=sys.stderr)
        return 1
    failures, summary, namespaces = [], [], {}
    # The enclave overlay names charts as OCI artefacts on a placeholder host (scripts/gen_airgap.py). CI renders
    # them from the upstream repository named in platform/apps, which is where the carried-in copy comes from.
    upstream = {}
    for path in sorted((ROOT / "platform" / "apps").glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if doc and doc.get("kind") == "Application":
                upstream[doc["metadata"]["name"]] = doc["spec"].get("sources") or [doc["spec"]["source"]]
    apps = [a for a in yaml.safe_load_all(built.stdout) if a and a.get("kind") == "Application"]
    # Argo CD itself is installed before Argo CD exists (helm in B1, Zarf in B2); render it so its images are
    # policy-checked and carried in like the rest.
    versions = yaml.safe_load((ROOT / "versions.yaml").read_text())
    apps.append({"metadata": {"name": "argo-cd"}, "spec": {
        "destination": {"namespace": "argocd"},
        "source": {"repoURL": "https://argoproj.github.io/argo-helm", "chart": "argo-cd",
                   "targetRevision": versions["gitops"]["argo-cd-chart"], "helm": {"releaseName": "argocd"}}}})
    for app in apps:
        name = app["metadata"]["name"]
        spec = app["spec"]
        namespace = spec["destination"].get("namespace", "default")
        for index, src in enumerate(spec.get("sources") or [spec["source"]]):
            if src["repoURL"].startswith("oci://chart-registry.invalid/"):
                original = upstream[name][index]
                src = {**src, "repoURL": original["repoURL"], "chart": original["chart"]}
                src.pop("path", None)
            helm = src.get("helm")
            if "chart" not in src and not (helm and "path" in src):
                continue  # plain manifests are validated by the schemas job
            release = (helm or {}).get("releaseName", name)
            cmd = ["helm", "template", release, "--namespace", namespace, "--include-crds",
                   "--kube-version", "1.37.2"]
            if "chart" in src:
                cmd += [src["chart"], "--repo", src["repoURL"], "--version", str(src["targetRevision"])]
            else:
                checkout = out / f"_src-{name}"
                clone = run(["git", "clone", "--quiet", "--depth", "1", "--branch", str(src["targetRevision"]),
                             src["repoURL"], str(checkout)])
                if clone.returncode != 0:
                    failures.append((name, clone.stderr.strip()))
                    continue
                cmd.insert(3, str(checkout / src["path"]))
            for vf in (helm or {}).get("valueFiles", []):
                cmd += ["-f", str(ROOT / vf.replace("$values/", ""))]
            if (helm or {}).get("valuesObject"):
                vo = out / f"_values-{name}.json"
                vo.write_text(json.dumps(helm["valuesObject"]))
                cmd += ["-f", str(vo)]
            res = run(cmd)
            if res.returncode != 0:
                detail = res.stderr.strip()
                if "not found in" in detail and "chart" in src:
                    run(["helm", "repo", "add", f"dbg-{name}", src["repoURL"]])
                    avail = run(["helm", "search", "repo", f"dbg-{name}/{src['chart']}", "--versions", "--devel"])
                    detail += " | available: " + ", ".join(
                        line.split()[1] for line in avail.stdout.splitlines()[1:9] if len(line.split()) > 1)
                failures.append((name, detail))
                continue
            (out / f"{name}.yaml").write_text(res.stdout)
            namespaces[name] = namespace
            kinds = sum(1 for line in res.stdout.splitlines() if line.startswith("kind:"))
            summary.append((name, kinds))
    (out / "_namespaces.json").write_text(json.dumps(namespaces, indent=2))
    for name, kinds in sorted(summary):
        print(f"rendered {name}: {kinds} objects")
    for name, err in failures:
        print(f"::error title=helm template failed::{name}: {err.splitlines()[-1] if err else 'unknown error'}")
        print(err, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
