"""Checks for the node and cluster install files (issues #40, #42, #51).

Run from the repository root: python3 -m unittest discover -s infra/tests -v
The break-glass check (#43) renders the real cloud-init template with OpenTofu:
infra/opentofu/nutanix/tests/cloud_init.tftest.hcl, run by `tofu test`.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RKE2 = ROOT / "infra/rke2"
RENDER = RKE2 / "scripts/render-rke2-config.sh"
VERIFY = RKE2 / "scripts/verify-rke2-artefacts.sh"
# Working folders live in the git-ignored out/ directory, never in the system temp directory.
WORK = ROOT / "out/test-infra"

# Generic test values; real ones come from the OpenTofu variables at install time.
SERVER_URL = "https://cp.cluster.example:9345"
SAN = "cp.cluster.example"


def merged_config(conf_dir: Path) -> dict:
    """Merges config.yaml and config.yaml.d/*.yaml as RKE2 documents it (docs.rke2.io/install/configuration):
    files in alphabetical order, the last value of a key wins, and a key ending in "+" appends to a list."""
    files = [conf_dir / "config.yaml"] + sorted((conf_dir / "config.yaml.d").glob("*.yaml"))
    merged: dict = {}
    for f in files:
        if not f.exists():
            continue
        for key, value in (yaml.safe_load(f.read_text()) or {}).items():
            if key.endswith("+"):
                base = key[:-1]
                merged[base] = list(merged.get(base, [])) + list(value)
            else:
                merged[key] = value
    return merged


def workdir(test: unittest.TestCase) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=WORK))
    # Cleanups run last-in first-out: the case's folder goes first, then WORK once it is empty.
    test.addCleanup(lambda: next(WORK.iterdir(), None) is None and WORK.rmdir())
    test.addCleanup(shutil.rmtree, path, True)
    return path


class Rke2JoinTest(unittest.TestCase):
    """#42: every node except the first server joins through the fixed registration address."""

    def render(self, **env: str) -> tuple[subprocess.CompletedProcess, Path]:
        dest = workdir(self) / "rke2"
        full_env = {"PATH": os.environ["PATH"], "DEST": str(dest), **env}
        result = subprocess.run(["bash", str(RENDER)], env=full_env, capture_output=True, text=True)
        return result, dest

    def assert_rendered(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_first_server_starts_the_cluster(self):
        result, dest = self.render(ROLE="server", FIRST_SERVER="true", TLS_SAN=SAN, POOL="control")
        self.assert_rendered(result)
        config = merged_config(dest)
        self.assertNotIn("server", config)
        self.assertEqual(config["token-file"], "/etc/rancher/rke2/token")
        self.assertIn(SAN, config["tls-san"])
        self.assertIn("innovox.uk/pool=control", config["node-label"])
        self.assertTrue((dest / "audit-policy.yaml").exists())

    def test_joining_server_names_the_registration_address(self):
        result, dest = self.render(ROLE="server", SERVER_URL=SERVER_URL, TLS_SAN=SAN, POOL="control")
        self.assert_rendered(result)
        config = merged_config(dest)
        self.assertEqual(config["server"], SERVER_URL)
        self.assertEqual(config["token-file"], "/etc/rancher/rke2/token")
        self.assertIn(SAN, config["tls-san"])

    def test_agent_names_the_registration_address(self):
        result, dest = self.render(ROLE="agent", SERVER_URL=SERVER_URL, POOL="storage")
        self.assert_rendered(result)
        config = merged_config(dest)
        self.assertEqual(config["server"], SERVER_URL)
        self.assertEqual(config["token-file"], "/etc/rancher/rke2/token")
        self.assertEqual(config["node-label"], ["innovox.uk/pool=storage"])
        self.assertNotIn("node-taint", config)
        self.assertFalse((dest / "audit-policy.yaml").exists())

    def test_gpu_agent_gets_the_gpu_label_and_taint(self):
        result, dest = self.render(ROLE="agent", SERVER_URL=SERVER_URL, POOL="gpu")
        self.assert_rendered(result)
        config = merged_config(dest)
        self.assertEqual(config["server"], SERVER_URL)
        self.assertEqual(config["node-label"], ["innovox.uk/pool=gpu"])
        self.assertEqual(config["node-taint"], ["innovox.uk/gpu=true:NoSchedule"])

    def test_server_without_address_and_not_first_is_refused(self):
        result, _ = self.render(ROLE="server", TLS_SAN=SAN, POOL="control")
        self.assertNotEqual(result.returncode, 0, "a second server without SERVER_URL would start its own cluster")

    def test_agent_without_address_is_refused(self):
        result, _ = self.render(ROLE="agent", POOL="general")
        self.assertNotEqual(result.returncode, 0)

    def test_server_without_tls_san_is_refused(self):
        result, _ = self.render(ROLE="server", FIRST_SERVER="true", POOL="control")
        self.assertNotEqual(result.returncode, 0)

    def test_no_install_time_placeholders_left(self):
        for f in (RKE2 / "config").glob("*.yaml"):
            self.assertNotIn("CONTROL_PLANE_VIP", f.read_text(), f.name)


class Rke2ArtefactTest(unittest.TestCase):
    """#42: install.sh is verified before it runs, like the tarballs."""

    def artefacts(self, install_sh: bytes) -> Path:
        d = workdir(self)
        sums = []
        for name in ("rke2.linux-amd64.tar.gz", "rke2-images.linux-amd64.tar.zst"):
            data = f"generic test artefact {name}".encode()
            (d / name).write_bytes(data)
            sums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
        # The release file lists more artefacts than a node needs; only the needed ones are checked.
        sums.append(f"{'0' * 64}  rke2-images.linux-amd64.tar.gz")
        (d / "sha256sum-amd64.txt").write_text("\n".join(sums) + "\n")
        (d / "install.sh").write_bytes(install_sh)
        return d

    def verify(self, artefact_dir: Path, pinned: bytes) -> subprocess.CompletedProcess:
        pin = artefact_dir / "install.sh.sha256"
        pin.write_text(f"{hashlib.sha256(pinned).hexdigest()}  install.sh\n")
        env = {"PATH": os.environ["PATH"], "INSTALL_SH_SHA256_FILE": str(pin)}
        return subprocess.run(["bash", str(VERIFY), str(artefact_dir)], env=env, capture_output=True, text=True)

    def test_matching_artefacts_pass(self):
        d = self.artefacts(b"#!/bin/sh\necho pinned\n")
        result = self.verify(d, b"#!/bin/sh\necho pinned\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_install_script_is_refused(self):
        d = self.artefacts(b"#!/bin/sh\necho changed\n")
        result = self.verify(d, b"#!/bin/sh\necho pinned\n")
        self.assertNotEqual(result.returncode, 0)

    def test_changed_tarball_is_refused(self):
        script = b"#!/bin/sh\necho pinned\n"
        d = self.artefacts(script)
        (d / "rke2.linux-amd64.tar.gz").write_bytes(b"changed")
        self.assertNotEqual(self.verify(d, script).returncode, 0)

    def test_tarball_missing_from_the_release_list_is_refused(self):
        script = b"#!/bin/sh\necho pinned\n"
        d = self.artefacts(script)
        sums = d / "sha256sum-amd64.txt"
        sums.write_text("".join(l for l in sums.read_text().splitlines(True) if "rke2-images" in l))
        self.assertNotEqual(self.verify(d, script).returncode, 0)

    def test_pinned_checksum_is_in_the_repository(self):
        line = (RKE2 / "install.sh.sha256").read_text().strip()
        self.assertRegex(line, r"^[0-9a-f]{64}  install\.sh$")


class AuditPolicyTest(unittest.TestCase):
    """#40: changes to every policy kind kept in policies/ are logged with their bodies."""

    WRITE_VERBS = {"create", "update", "patch", "delete"}
    # Files in policies/ that are not served by the cluster's API.
    NOT_SERVED = {"kustomize.config.k8s.io", "cli.kyverno.io"}

    def policy_groups(self) -> set[str]:
        groups = set()
        for f in (ROOT / "policies").rglob("*.yaml"):
            if "tests" in f.relative_to(ROOT / "policies").parts:
                continue
            for doc in yaml.safe_load_all(f.read_text()):
                if doc and "apiVersion" in doc:
                    group = doc["apiVersion"].rpartition("/")[0]
                    if group not in self.NOT_SERVED:
                        groups.add(group)
        return groups

    def first_rule_for(self, group: str) -> dict:
        """The first rule that matches a write to any resource of the group (kubernetes.io audit docs: the first
        matching rule sets the level). Only group-wide entries count, so a rule naming some resources does not."""
        policy = yaml.safe_load((RKE2 / "config/audit-policy.yaml").read_text())
        for rule in policy["rules"]:
            if rule.get("users") or rule.get("userGroups") or rule.get("nonResourceURLs"):
                continue
            if not self.WRITE_VERBS & set(rule.get("verbs") or self.WRITE_VERBS):
                continue
            for gr in rule.get("resources") or [{"group": "*"}]:
                if gr.get("group") in (group, "*"):
                    if gr.get("resources") and group != "":
                        continue
                    return rule
        return {}

    def test_policy_groups_are_found(self):
        self.assertIn("policies.kyverno.io", self.policy_groups())

    def test_every_policy_group_is_logged_with_bodies(self):
        for group in sorted(self.policy_groups() - {""}):
            with self.subTest(group=group):
                rule = self.first_rule_for(group)
                self.assertEqual(rule.get("level"), "RequestResponse", f"{group}: first matching rule {rule}")
                self.assertTrue(self.WRITE_VERBS <= set(rule.get("verbs") or self.WRITE_VERBS))

    def test_trust_and_deployment_boundaries_are_logged_with_bodies(self):
        policy = yaml.safe_load((RKE2 / "config/audit-policy.yaml").read_text())
        rule = next(r for r in policy["rules"] if r["level"] == "RequestResponse")
        scoped = {gr["group"]: set(gr.get("resources", [])) for gr in rule["resources"]}
        self.assertEqual(scoped["cert-manager.io"], {"issuers", "clusterissuers"})
        self.assertEqual(scoped["external-secrets.io"], {"secretstores", "clustersecretstores"})
        self.assertEqual(scoped["argoproj.io"], {"appprojects"})
        self.assertFalse(rule.get("namespaces") or rule.get("users") or rule.get("userGroups"))

    def test_secret_contents_never_logged(self):
        policy = yaml.safe_load((RKE2 / "config/audit-policy.yaml").read_text())
        first = policy["rules"][0]
        self.assertEqual(first["level"], "Metadata")
        self.assertIn("secrets", first["resources"][0]["resources"])


class RegistryMirrorTest(unittest.TestCase):
    """#51: every registry on the image allowlist is pulled through a Harbor proxy-cache project."""

    def allowlisted_registries(self) -> set[str]:
        # Reads the string literals of the "allowed" CEL list in the admission policy. No CEL evaluator is
        # installed in this repository, and adding one is a new dependency that needs the owner's approval, so
        # this test-only check takes the quoted entries. It fails loudly if the list cannot be found.
        policy = yaml.safe_load((ROOT / "policies/kyverno/policies/restrict-image-sources.yaml").read_text())
        expression = next(v["expression"] for v in policy["spec"]["variables"] if v["name"] == "allowed")
        prefixes = re.findall(r'^\s*"([^"]+)",?\s*$', expression, flags=re.M)
        self.assertGreater(len(prefixes), 10, "allowlist not found")
        return {p.split("/", 1)[0] for p in prefixes}

    def registries(self) -> dict:
        return yaml.safe_load((RKE2 / "config/registries.yaml.example").read_text())

    def test_every_allowlisted_registry_has_a_mirror(self):
        config = self.registries()
        site_registries = set(config.get("configs", {}))
        for registry in sorted(self.allowlisted_registries() - site_registries):
            with self.subTest(registry=registry):
                self.assertIn(registry, config["mirrors"])

    def test_every_mirror_points_at_a_proxy_cache_project(self):
        config = self.registries()
        site_registries = set(config.get("configs", {}))
        for registry, mirror in config["mirrors"].items():
            with self.subTest(registry=registry):
                hosts = {e.split("://", 1)[1].split("/", 1)[0] for e in mirror["endpoint"]}
                self.assertTrue(hosts <= site_registries, f"{registry}: endpoint is not the site registry")
                self.assertEqual(mirror.get("rewrite"), {"^(.*)$": f"{registry}/$1"},
                                 f"{registry}: must rewrite into the proxy-cache project named after it")


if __name__ == "__main__":
    unittest.main()
