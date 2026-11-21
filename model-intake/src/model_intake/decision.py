"""Decision records. Only an approval issues an ID that Kyverno accepts (INT-YYYYMMDD-xxxxxxxx).

An approval is bound to two things (issue 35):
- the evaluation must be of the same model and the same weights as the intake checks (name, version and the
  manifest SHA-256 recorded by `evaluate --check-report`);
- the weights artefact that will be served: an OCI image, signed and mounted as an image volume (owner ruling on
  issue 49), named by digest. Admission (policies/kyverno/policies/require-model-intake-record.yaml) accepts a
  model pod only when its decision ID is in ConfigMap kyverno/model-intake-decisions and its image volume is
  exactly the artefact that the decision names.
"""

from __future__ import annotations

import datetime as dt
import re

DECISION_ID = re.compile(r"^INT-\d{8}-[0-9a-f]{8}$")
# Hand-written match, justified: the weights reference is compared byte for byte at admission, so the tool only
# needs to know it ends in a full SHA-256 digest; resolving or normalising the reference is left to the registry
# client at admission. An OCI reference pinned by digest ends in "@sha256:" and 64 lowercase hex characters
# (OCI image spec, descriptor digests).
PINNED_REFERENCE = re.compile(r"^[^@\s]+@(sha256:[0-9a-f]{64})$")
DECISIONS_CONFIGMAP = "kyverno/model-intake-decisions"
SUBJECT_FIELDS = ("model_name", "model_version", "manifest_sha256")


def decision_id(manifest_sha256: str, when: dt.date | None = None) -> str:
    day = (when or dt.datetime.now(dt.timezone.utc).date()).strftime("%Y%m%d")
    return f"INT-{day}-{manifest_sha256[:8]}"


def subject_of(check_report: dict) -> dict:
    """What an evaluation must be about: the model and weights the intake checks passed."""
    return {"model_name": check_report["request"]["model_name"],
            "model_version": check_report["request"]["model_version"],
            "manifest_sha256": check_report["manifest_sha256"]}


def evaluation_mismatch(check_report: dict, evaluation_report: dict) -> str | None:
    subject = evaluation_report.get("subject")
    if not isinstance(subject, dict):
        return "evaluation report names no subject (run evaluate with --check-report)"
    expected = subject_of(check_report)
    for field in SUBJECT_FIELDS:
        if subject.get(field) != expected[field]:
            what = "weights manifest" if field == "manifest_sha256" else field.replace("_", " ")
            return f"evaluation is of another {what}: {subject.get(field)!r}, intake checked {expected[field]!r}"
    return None


def decide(check_report: dict, evaluation_report: dict | None, *, decision: str, approver: str, role: str,
           reason: str, weights_image: str = "") -> dict:
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")
    if not approver.strip() or not role.strip():
        raise ValueError("approver and role are required")
    blockers = []
    if not check_report.get("passed"):
        blockers.append("intake checks did not pass")
    if evaluation_report is None or not evaluation_report.get("passed"):
        blockers.append("evaluation thresholds not met or not run")
    elif mismatch := evaluation_mismatch(check_report, evaluation_report):
        blockers.append(mismatch)
    pinned = PINNED_REFERENCE.match(weights_image or "")
    if decision == "approve" and not pinned:
        blockers.append("the weights image must be named by digest (<repository>@sha256:<64 hex>)")
    if decision == "approve" and blockers:
        raise ValueError("cannot approve: " + "; ".join(blockers))
    now = dt.datetime.now(dt.timezone.utc)
    record = {
        "decision": decision,
        **subject_of(check_report),
        "origin_country": check_report["request"]["origin_country"],
        "approver": approver,
        "role": role,
        "reason": reason,
        "decided_at": now.replace(microsecond=0).isoformat(),
        "blockers": blockers,
    }
    if decision == "approve":
        record["id"] = decision_id(check_report["manifest_sha256"], now.date())
        record["weights_image"] = weights_image
        record["weights_digest"] = pinned.group(1)
        # The entry to add, through review, to policies/kyverno/policies/model-intake-decisions.yaml.
        record["admission"] = {"configmap": DECISIONS_CONFIGMAP, "key": record["id"], "value": weights_image}
    return record
