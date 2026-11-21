#!/usr/bin/env python3
"""Run the admission signature policy (policies/kyverno/policies/verify-innovox-signatures.yaml) against real
images with the Kyverno CLI, so CI verifies a signature with the same attestor configuration admission uses.

Only two fields of the policy are replaced, because neither can be reached outside a cluster:
  - attestor `platform`: the public key comes from --public-key instead of Secret kyverno/cosign-public-key
    (`kms: k8s://...`), as inline `key.data`;
  - matchImageReferences: --glob instead of the site Harbor path, so images in the CI registry are matched.
Everything else (validations, ctlog settings, digest and `required` settings) is the policy as committed.

The pods to test come from --resources. Each pod names its expected result in annotation
`test.innovox.uk/expect` (pass or fail); the script writes a Kyverno CLI test from those and runs `kyverno test`.

Usage: verify_signatures.py --public-key cosign.pub --glob 'ghcr.io/org/repo/*' --resources pods.yaml
Env:   KYVERNO  path to the kyverno CLI (default ./kyverno)
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "kyverno" / "policies" / "verify-innovox-signatures.yaml"
EXPECT = "test.innovox.uk/expect"


def policy_for(public_key: str, glob: str) -> dict:
    policy = yaml.safe_load(POLICY.read_text())
    spec = policy["spec"]
    spec["matchImageReferences"] = [{"glob": glob}]
    platform = [a for a in spec["attestors"] if a["name"] == "platform"]
    if len(platform) != 1 or "kms" not in platform[0]["cosign"]["key"]:
        raise SystemExit(f"{POLICY}: expected one attestor 'platform' with a cosign key from kms")
    platform[0]["cosign"]["key"] = {"data": public_key}
    return policy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--glob", required=True)
    parser.add_argument("--resources", required=True)
    args = parser.parse_args()

    pods = [d for d in yaml.safe_load_all(pathlib.Path(args.resources).read_text()) if d]
    results: dict[str, list[str]] = {"pass": [], "fail": []}
    for pod in pods:
        expect = (pod["metadata"].get("annotations") or {}).get(EXPECT)
        if expect not in results:
            raise SystemExit(f"pod {pod['metadata']['name']}: annotation {EXPECT} must be pass or fail")
        results[expect].append(pod["metadata"]["name"])

    work = ROOT / "out" / "verify-signatures"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    policy = policy_for(pathlib.Path(args.public_key).read_text(), args.glob)
    (work / "policy.yaml").write_text(yaml.safe_dump(policy, sort_keys=False))
    (work / "resources.yaml").write_text(yaml.safe_dump_all(pods, sort_keys=False))
    test = {
        "apiVersion": "cli.kyverno.io/v1alpha1",
        "kind": "Test",
        "metadata": {"name": "verify-innovox-signatures"},
        "policies": ["policy.yaml"],
        "resources": ["resources.yaml"],
        "results": [{"policy": policy["metadata"]["name"], "isImageValidatingPolicy": True, "kind": "Pod",
                     "resources": names, "result": result} for result, names in results.items() if names],
    }
    (work / "kyverno-test.yaml").write_text(yaml.safe_dump(test, sort_keys=False))
    kyverno = os.environ.get("KYVERNO", "./kyverno")
    res = subprocess.run([kyverno, "test", str(work), "--registry", "--detailed-results", "--remove-color"],
                         check=False)
    shutil.rmtree(work, ignore_errors=True)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
