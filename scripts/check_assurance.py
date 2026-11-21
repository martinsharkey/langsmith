#!/usr/bin/env python3
"""Keeps the assurance records consistent with the repository: every file a control names exists, every risk
names real controls and threats, and risk scores are in range."""
from __future__ import annotations

import re
import subprocess
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

# Issue 64: every identifier the repository cites is defined, and the product has one name.
# Defined here: AD- (docs/adr, by number), CTL- (docs/controls.yaml), T- (threat model), SR- (risk register).
# Defined in the design documents and listed in docs/glossary.md: earlier AD- decisions and the D-, I- and R- open
# items. Words are matched with regular expressions over tracked text files; no other tool indexes these IDs.

glossary = (root / "docs/glossary.md").read_text() if (root / "docs/glossary.md").exists() else ""
external = set(re.findall(r"^\| ((?:AD|D|I|R)-\d+) \|", glossary, flags=re.M))
adr_ids = {f"AD-{int(p.name[:4])}" for p in (root / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md")}
defined = {"AD": adr_ids | {x for x in external if x.startswith("AD-")}, "CTL": control_ids, "T": threat_ids,
           "SR": seen, "D": external, "I": external, "R": external}
tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split()
skip = ("/vendor/", ".lock", "package-lock.json", ".png", ".svg", ".tgz")
reference = re.compile(r"(?<![A-Za-z0-9-])(AD|CTL|T|SR|D|I|R)-(\d{2,3})(?!\d)")
old_names = re.compile(r"LangSmith Defence [Pp]latform|dp-ai-001-c|(?i:sovereign agentic platform)(?<!Sovereign Agentic Platform)")
for name in tracked:
    if any(s in name for s in skip) or name == "scripts/check_assurance.py":
        continue
    try:
        text = (root / name).read_text()
    except (UnicodeDecodeError, IsADirectoryError):
        continue
    for number, line in enumerate(text.splitlines(), 1):
        for prefix, digits in reference.findall(line):
            ref = f"{prefix}-{digits}"
            if ref not in defined[prefix]:
                errors.append(f"{name}:{number}: {ref} is not defined (docs/adr, controls, threat model, risk "
                              "register or docs/glossary.md)")
        if old_names.search(line):
            errors.append(f"{name}:{number}: old product name; use Sovereign Agentic Platform or sap (issue 64)")
labels = {v for v in re.findall(r"innovox\.uk/platform: (\S+)",
                                "".join((root / n).read_text() for n in tracked if n.startswith("platform/")
                                        and n.endswith(".yaml") and "/vendor/" not in n))}
if labels - {"sap"}:
    errors.append(f"label innovox.uk/platform has values {sorted(labels)}; use sap (issue 64)")

for line in errors:
    print("ERROR", line)
print(f"{len(controls)} controls, {len(threat_ids)} threats, {len(risks)} risks checked")
sys.exit(1 if errors else 0)
