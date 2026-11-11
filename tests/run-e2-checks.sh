#!/usr/bin/env bash
# Runs the in-cluster E2 checks against the current kubectl context and writes results to ./evidence.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${OUT_DIR:-./evidence/e2-$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$out"
status=0
for f in "$here"/admission/*.yaml; do
  if kubectl apply --dry-run=server -f "$f" >"$out/$(basename "$f").log" 2>&1; then
    echo "FAIL admitted: $(basename "$f")"; status=1
  else
    echo "ok   refused:  $(basename "$f")"
  fi
done
if [ "${MODE:-b2}" = b2 ]; then
  kubectl delete job zero-egress-test -n langsmith --ignore-not-found >/dev/null
  kubectl apply -f "$here/egress/zero-egress-job.yaml" >/dev/null
  if kubectl wait --for=condition=complete job/zero-egress-test -n langsmith --timeout=120s >/dev/null 2>&1; then
    echo "ok   zero egress"
  else
    echo "FAIL zero egress"; status=1
  fi
  kubectl logs job/zero-egress-test -n langsmith >"$out/zero-egress.log" 2>&1
fi
echo "Evidence: $out"
exit $status
