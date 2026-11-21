#!/usr/bin/env python3
"""Keeps the assurance records consistent with the repository: every file a control names exists, every risk
names real controls and threats, and risk scores are in range."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
errors: list[str] = []

controls = yaml.safe_load((root / "docs/controls.yaml").read_text())["controls"]
control_ids = {c["id"] for c in controls}
for control in controls:
    for path in control.get("implemented_by", []):
        if not (root / path).exists():
            errors.append(f"{control['id']}: implemented_by path does not exist: {path}")

threat_model = (root / "docs/assurance/threat-model.md").read_text()
threat_ids = set(re.findall(r"^\| (T-\d+) \|", threat_model, flags=re.M))
# Issue 66: a "CI" claim in the Proven column names the gate PR jobs or test files that fail without the control.
ci_jobs = set(yaml.safe_load((root / ".github/workflows/ci.yml").read_text())["jobs"])
for row in re.findall(r"^\| (T-\d+) \|.*\| ([^|]*) \|$", threat_model, flags=re.M):
    tid, proven = row
    for claim in re.finditer(r"\bCI\b(\s*\(([^)]*)\))?", proven):
        names = re.findall(r"`([^`]+)`", claim.group(2) or "")
        if not names:
            errors.append(f"threat model {tid}: '{proven}' claims CI without naming a gate PR job or test file")
        for name in names:
            if name not in ci_jobs and not (root / name).exists():
                errors.append(f"threat model {tid}: '{name}' is neither a gate PR job nor a file in this repository")
for ref in set(re.findall(r"CTL-\d+", threat_model)) - control_ids:
    errors.append(f"threat model names unknown control {ref}")

risks = yaml.safe_load((root / "docs/assurance/risk-register.yaml").read_text())["risks"]
seen: set[str] = set()
for risk in risks:
    rid = risk["id"]
    if rid in seen:
        errors.append(f"duplicate risk id {rid}")
    seen.add(rid)
    for ref in risk.get("controls", []):
        if ref not in control_ids:
            errors.append(f"{rid}: unknown control {ref}")
    for ref in risk.get("threats", []):
        if ref not in threat_ids:
            errors.append(f"{rid}: unknown threat {ref}")
    for field in ("likelihood", "impact"):
        if not 1 <= int(risk[field]) <= 5:
            errors.append(f"{rid}: {field} must be 1 to 5")
    if risk["status"] not in {"open", "built-unproven", "partly-proven", "proven", "accepted"}:
        errors.append(f"{rid}: unknown status {risk['status']}")

for line in errors:
    print("ERROR", line)
print(f"{len(controls)} controls, {len(threat_ids)} threats, {len(risks)} risks checked")
sys.exit(1 if errors else 0)
