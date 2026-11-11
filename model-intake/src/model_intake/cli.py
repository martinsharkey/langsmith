"""model-intake: check -> evaluate -> decide. Every step writes JSON evidence to the output directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .decision import decide
from .evaluate import check_thresholds
from .files import scan_weights, write_manifest
from .mlbom import build_mlbom
from .policy import load_json, load_policy, validate_request
from .signature import verify


def _write(out: Path, name: str, data: dict) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def cmd_check(args) -> int:
    policy = load_policy(args.policy)
    request = load_json(args.request)
    out = Path(args.out)
    problems = validate_request(request)
    if not problems:
        if request["origin_country"].upper() not in policy.allowed_origins:
            problems.append(f"origin {request['origin_country']} is not on the customer's approved list")
        if request["licence"] not in policy.allowed_licences:
            problems.append(f"licence {request['licence']} is not on the approved list")
        if request["classification"] not in policy.allowed_classifications:
            problems.append(f"classification {request['classification']} is not allowed by this policy")
    weights = Path(args.weights)
    records, file_problems = scan_weights(weights, policy.weight_extensions, policy.allowed_aux_extensions,
                                          policy.forbidden_extensions)
    problems += file_problems
    manifest_path = out / "manifest.sha256"
    out.mkdir(parents=True, exist_ok=True)
    manifest_sha = write_manifest(records, manifest_path) if records else ""
    sig = verify(policy.signature_command, manifest=str(manifest_path), signature=args.signature or "",
                 public_key=args.public_key or "", weights_dir=str(weights))
    if not sig.verified:
        problems.append(f"signature not verified: {sig.detail}")
    report = {
        "tool": f"model-intake {__version__}",
        "request": request,
        "manifest_sha256": manifest_sha,
        "files": [r.__dict__ for r in records],
        "signature": {"verified": sig.verified, "detail": sig.detail},
        "problems": problems,
        "passed": not problems,
    }
    _write(out, "check-report.json", report)
    if records and not validate_request(request):
        _write(out, "ml-bom.cdx.json", build_mlbom(request, records, manifest_sha))
    print(("PASS" if report["passed"] else "FAIL") + f": {len(records)} files, {len(problems)} problems")
    for p in problems:
        print(f"  - {p}")
    return 0 if report["passed"] else 1


def cmd_evaluate(args) -> int:
    policy = load_policy(args.policy)
    passed, outcome = check_thresholds(load_json(args.results), policy.evaluations)
    _write(Path(args.out), "evaluation-report.json", {"passed": passed, "results": outcome})
    print("PASS" if passed else "FAIL")
    for o in outcome:
        print(f"  - {o['evaluation']}.{o['metric']}: {o['value']} (minimum {o['minimum']})")
    return 0 if passed else 1


def cmd_decide(args) -> int:
    check_report = load_json(args.check_report)
    evaluation = load_json(args.evaluation_report) if args.evaluation_report else None
    try:
        record = decide(check_report, evaluation, decision=args.decision, approver=args.approver,
                        role=args.role, reason=args.reason)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    _write(Path(args.out), "decision.json", record)
    print(f"{record['decision'].upper()}" + (f" {record['id']}" if "id" in record else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="model-intake", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="provenance, file and licence checks; writes manifest, ML-BOM and report")
    c.add_argument("--request", required=True)
    c.add_argument("--policy", required=True)
    c.add_argument("--weights", required=True)
    c.add_argument("--signature")
    c.add_argument("--public-key")
    c.add_argument("--out", required=True)
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("evaluate", help="compare evaluation results with policy minimums")
    e.add_argument("--policy", required=True)
    e.add_argument("--results", required=True)
    e.add_argument("--out", required=True)
    e.set_defaults(func=cmd_evaluate)

    d = sub.add_parser("decide", help="record the risk owner's decision")
    d.add_argument("--check-report", required=True)
    d.add_argument("--evaluation-report")
    d.add_argument("--decision", choices=["approve", "reject"], required=True)
    d.add_argument("--approver", required=True)
    d.add_argument("--role", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_decide)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
