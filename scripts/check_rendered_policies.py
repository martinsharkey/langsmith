#!/usr/bin/env python3
"""Apply the platform's admission policies to every rendered chart.

A policy that would refuse the platform's own workloads is found in CI, not at deployment. Helm test hooks are
dropped first: Argo CD does not apply them. Signature verification needs a registry and is checked at gate E1.

Usage: check_rendered_policies.py <rendered dir>   (env KYVERNO = path to the kyverno CLI, default ./kyverno)
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import yaml

POLICIES = ["policies/kyverno/policies/restrict-image-sources.yaml",
            "policies/kyverno/policies/disallow-latest-tag.yaml"]


class Loader(yaml.SafeLoader):
    """SafeLoader that also accepts the bare '=' scalar some charts emit."""


Loader.add_constructor("tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node))


def images(doc: dict) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("containers", "initContainers", "ephemeralContainers") and isinstance(value, list):
                    found.extend(str(c.get("image")) for c in value if isinstance(c, dict))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return found


def main() -> int:
    rendered = pathlib.Path(sys.argv[1])
    kyverno = os.environ.get("KYVERNO", "./kyverno")
    work = rendered / "_policy-input"
    work.mkdir(exist_ok=True)
    status = 0
    for path in sorted(rendered.glob("[a-z]*.yaml")):
        docs, by_name = [], {}
        for doc in yaml.load_all(path.read_text(), Loader=Loader):
            if not isinstance(doc, dict) or "kind" not in doc:
                continue
            hook = str((doc.get("metadata", {}).get("annotations") or {}).get("helm.sh/hook", ""))
            if "test" in hook:
                continue
            docs.append(doc)
            by_name[f"{doc['kind']}/{doc.get('metadata', {}).get('name')}"] = images(doc)
        target = work / path.name
        target.write_text(yaml.safe_dump_all(docs))
        res = subprocess.run([kyverno, "apply", *POLICIES, "--resource", str(target)],
                             capture_output=True, text=True, check=False)
        out = res.stdout + res.stderr
        summary = next((line for line in reversed(out.splitlines()) if line.startswith("pass:")), "no result")
        print(f"{path.name}: {summary.strip()}")
        if res.returncode != 0:
            status = 1
            failed = sorted(set(re.findall(r"-> resource \S+?/(\w+/\S+) failed", out)))
            for name in failed:
                print(f"  refused {name}: {', '.join(by_name.get(name, ['?']))}")
            if not failed:
                print("  " + "\n  ".join(out.strip().splitlines()[-5:]))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
