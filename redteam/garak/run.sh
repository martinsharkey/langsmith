#!/usr/bin/env bash
# Runs garak probes against a served model class. Usage: VLLM_API_KEY=... ./run.sh [model-class]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
class="${1:-class-m}"
out="${OUT_DIR:-./evidence/garak-$class}"
mkdir -p "$out"
garak --model_type openai.OpenAICompatible \
      --generator_option_file "$here/vllm-generator.json" \
      --probes promptinject,dan,encoding,leakreplay,latentinjection \
      --report_prefix "$out/garak"
echo "Report: $out"
