#!/usr/bin/env bash
# Runs the in-cluster E2 checks against the current kubectl context and writes results to ./evidence.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${OUT_DIR:-./evidence/e2-$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$out"
status=0

# The repository as committed: the cluster checks below assume its configuration is complete.
if python3 "$here/static_checks.py" >"$out/static-checks.log" 2>&1; then
  echo "ok   repository checks"
else
  echo "FAIL repository checks (static-checks.log)"; status=1
fi

for f in "$here"/admission/*.yaml; do
  if kubectl apply --dry-run=server -f "$f" >"$out/$(basename "$f").log" 2>&1; then
    echo "FAIL admitted: $(basename "$f")"; status=1
  else
    echo "ok   refused:  $(basename "$f")"
  fi
done

# Issue 38: only the LLM Gateway may call a chat model. Any other LangSmith workload must get HTTP 403 from the
# model's sidecar, whatever the request body or key.
probe='import urllib.request, urllib.error
req = urllib.request.Request("http://vllm-class-m.models.svc:8000/v1/chat/completions", data=b"{}",
                             headers={"Content-Type": "application/json"})
try:
    print(urllib.request.urlopen(req, timeout=10).status)
except urllib.error.HTTPError as e:
    print(e.code)'
code="$(kubectl exec -n langsmith deploy/langsmith-backend -- python3 -c "$probe" 2>"$out/model-access.log")"
if [ "$code" = 403 ]; then
  echo "ok   chat model refused a workload other than the gateway"
else
  echo "FAIL chat model answered langsmith-backend with '$code' (expected 403)"; status=1
fi

# Issue 61: the Valkey password is not on the server's command line.
if kubectl exec -n langsmith valkey-0 -- cat /proc/1/cmdline >"$out/valkey-cmdline.log" 2>&1 \
   && ! grep -q requirepass "$out/valkey-cmdline.log"; then
  echo "ok   valkey password not on the command line"
else
  echo "FAIL valkey command line (valkey-cmdline.log)"; status=1
fi

# Issue 34: the zero-egress probe runs where no namespace policy restricts egress, so only the cluster-wide policy
# can block it: a namespace created for the test, and a privileged platform namespace. Keep this list the same as
# PROBE_NAMESPACES in static_checks.py.
if [ "${MODE:-b2}" = b2 ]; then
  kubectl apply -f "$here/egress/namespace.yaml" >/dev/null
  for ns in egress-probe observability; do
    kubectl delete job zero-egress-test -n "$ns" --ignore-not-found >/dev/null
    kubectl apply -n "$ns" -f "$here/egress/zero-egress-job.yaml" >/dev/null
    if kubectl wait --for=condition=complete job/zero-egress-test -n "$ns" --timeout=120s >/dev/null 2>&1; then
      echo "ok   zero egress from $ns"
    else
      echo "FAIL zero egress from $ns"; status=1
    fi
    kubectl logs job/zero-egress-test -n "$ns" >"$out/zero-egress-$ns.log" 2>&1
    kubectl delete job zero-egress-test -n "$ns" --ignore-not-found >/dev/null
  done
  kubectl delete -f "$here/egress/namespace.yaml" --ignore-not-found --wait=false >/dev/null
fi
echo "Evidence: $out"
exit $status
