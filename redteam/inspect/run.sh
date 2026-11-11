#!/usr/bin/env bash
# Runs UK AISI Inspect evaluations against a local vLLM model class (OpenAI-compatible API), fully offline.
# Usage: VLLM_API_KEY=... ./run.sh [model-class] [task...]
set -euo pipefail
class="${1:-class-m}"; shift || true
tasks=("${@:-inspect_evals/gsm8k}")
out="${OUT_DIR:-./evidence/inspect-$class}"
mkdir -p "$out"
export OPENAI_BASE_URL="http://vllm-class-m.models.svc:8000/v1"
export OPENAI_API_KEY="$VLLM_API_KEY"
for t in "${tasks[@]}"; do
  inspect eval "$t" --model "openai/$class" --log-dir "$out"
done
echo "Logs: $out"
