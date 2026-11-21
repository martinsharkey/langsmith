#!/usr/bin/env bash
# Runs garak probes against a served model class. Usage: VLLM_API_KEY=... ./run.sh [model-class]
# The endpoint and model name come from the class (issue 52): http://vllm-<class>.models.svc:8000/v1 serving
# <class>. Override with VLLM_BASE_URL and SERVED_MODEL. The run stops before any probe if the endpoint does not
# serve that model, and the evidence directory records the endpoint and its /v1/models response.
set -euo pipefail
class="${1:-class-m}"
case "$class" in
  class-[a-z0-9]*) ;;
  *) echo "model class must look like class-<name>, got '$class'" >&2; exit 2 ;;
esac
base="${VLLM_BASE_URL:-http://vllm-$class.models.svc:8000/v1}"
model="${SERVED_MODEL:-$class}"
out="${OUT_DIR:-./evidence/garak-$class}"
mkdir -p "$out"
printf '%s\n' "$base" >"$out/endpoint.txt"
curl -fsS -H "Authorization: Bearer $VLLM_API_KEY" "$base/models" >"$out/models.json"
if ! python3 -c 'import json, sys; ids = [m["id"] for m in json.load(open(sys.argv[1]))["data"]]; sys.exit(sys.argv[2] not in ids)' \
    "$out/models.json" "$model"; then
  echo "$base does not serve model '$model' (see $out/models.json); nothing was probed" >&2
  exit 1
fi
# garak reads the generator from an options file; written per run so it always names this class.
python3 -c 'import json, sys; json.dump({"openai": {"OpenAICompatible": {"uri": sys.argv[1], "model": sys.argv[2],
  "api_key": "env:VLLM_API_KEY", "suppressed_params": ["n"]}}}, open(sys.argv[3], "w"), indent=2)' \
  "$base" "$model" "$out/garak-generator.json"
garak --model_type openai.OpenAICompatible \
      --generator_option_file "$out/garak-generator.json" \
      --probes promptinject,dan,encoding,leakreplay,latentinjection \
      --report_prefix "$out/garak"
echo "Report: $out"
