#!/usr/bin/env bash
# Applies the platform's admission policies to every rendered chart, so a policy that would refuse the platform's
# own workloads is found in CI, not at deployment. Signature verification needs a registry and is checked at E1.
set -uo pipefail
dir="${1:?rendered directory}"
kyverno="${KYVERNO:-./kyverno}"
status=0
for f in "$dir"/[a-z]*.yaml; do
  out=$("$kyverno" apply policies/kyverno/policies/restrict-image-sources.yaml policies/kyverno/policies/disallow-latest-tag.yaml \
        --resource "$f" 2>&1)
  rc=$?
  summary=$(echo "$out" | grep -E '^pass:' | tail -1)
  echo "$(basename "$f"): ${summary:-no result}"
  if [ $rc -ne 0 ]; then
    echo "$out" | grep -E 'fail|FAIL|->|image' | sort -u | head -40
    status=1
  fi
done
exit $status
