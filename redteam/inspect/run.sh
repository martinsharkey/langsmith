#!/usr/bin/env bash
# Runs UK AISI Inspect evaluations against a local vLLM model class (OpenAI-compatible API), fully offline.
# Usage: VLLM_API_KEY=... ./run.sh [model-class] [task...]
# The endpoint and model name come from the class (issue 52): http://vllm-<class>.models.svc:8000/v1 serving
# <class>. Override with VLLM_BASE_URL and SERVED_MODEL. The run stops before any task if the endpoint does not
# serve that model, and the evidence directory records the endpoint and its /v1/models response.
set -euo pipefail
class="${1:-class-m}"; shift || true
case "$class" in
  class-[a-z0-9]*) ;;
  *) echo "model class must look like class-<name>, got '$class'" >&2; exit 2 ;;
esac
tasks=("${@:-inspect_evals/gsm8k}")
base="${VLLM_BASE_URL:-http://vllm-$class.models.svc:8000/v1}"
model="${SERVED_MODEL:-$class}"
out="${OUT_DIR:-./evidence/inspect-$class}"
mkdir -p "$out"
printf '%s\n' "$base" >"$out/endpoint.txt"
curl -fsS -H "Authorization: Bearer $VLLM_API_KEY" "$base/models" >"$out/models.json"
if ! python3 -c 'import json, sys; ids = [m["id"] for m in json.load(open(sys.argv[1]))["data"]]; sys.exit(sys.argv[2] not in ids)' \
    "$out/models.json" "$model"; then
  echo "$base does not serve model '$model' (see $out/models.json); nothing was evaluated" >&2
  exit 1
fi
export OPENAI_BASE_URL="$base"
export OPENAI_API_KEY="$VLLM_API_KEY"
for t in "${tasks[@]}"; do
  inspect eval "$t" --model "openai/$model" --log-dir "$out"
done
echo "Logs: $out"
