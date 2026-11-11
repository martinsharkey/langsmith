"""Decision records. Only an approval issues an ID that Kyverno accepts (INT-YYYYMMDD-xxxxxxxx)."""

from __future__ import annotations

import datetime as dt
import re

DECISION_ID = re.compile(r"^INT-\d{8}-[0-9a-f]{8}$")


def decision_id(manifest_sha256: str, when: dt.date | None = None) -> str:
    day = (when or dt.datetime.now(dt.timezone.utc).date()).strftime("%Y%m%d")
    return f"INT-{day}-{manifest_sha256[:8]}"


def decide(check_report: dict, evaluation_report: dict | None, *, decision: str, approver: str, role: str,
           reason: str) -> dict:
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")
    if not approver.strip() or not role.strip():
        raise ValueError("approver and role are required")
    blockers = []
    if not check_report.get("passed"):
        blockers.append("intake checks did not pass")
    if evaluation_report is None or not evaluation_report.get("passed"):
        blockers.append("evaluation thresholds not met or not run")
    if decision == "approve" and blockers:
        raise ValueError("cannot approve: " + "; ".join(blockers))
    now = dt.datetime.now(dt.timezone.utc)
    record = {
        "decision": decision,
        "model_name": check_report["request"]["model_name"],
        "model_version": check_report["request"]["model_version"],
        "origin_country": check_report["request"]["origin_country"],
        "manifest_sha256": check_report["manifest_sha256"],
        "approver": approver,
        "role": role,
        "reason": reason,
        "decided_at": now.replace(microsecond=0).isoformat(),
        "blockers": blockers,
    }
    if decision == "approve":
        record["id"] = decision_id(check_report["manifest_sha256"], now.date())
    return record
