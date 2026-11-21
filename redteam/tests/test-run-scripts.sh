#!/usr/bin/env bash
# Runs redteam/garak/run.sh and redteam/inspect/run.sh with stub garak, inspect and curl on PATH, and checks that
# the requested model class is the one tested and recorded (issue 52). Usage: redteam/tests/test-run-scripts.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
mkdir -p "$root/out"
work="$(mktemp -d "$root/out/redteam-test.XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin"

# Each stub records its arguments and the environment the scripts set, one item per line.
cat >"$work/bin/garak" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$STUB_LOG/garak.args"
while [ $# -gt 0 ]; do
  if [ "$1" = --generator_option_file ]; then cp "$2" "$STUB_LOG/garak-options.json"; fi
  shift
done
EOF
cat >"$work/bin/inspect" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >>"$STUB_LOG/inspect.args"
printf '%s\n' "$OPENAI_BASE_URL" >>"$STUB_LOG/inspect.base-url"
EOF
cat >"$work/bin/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >>"$STUB_LOG/curl.args"
printf '{"object":"list","data":[{"id":"%s","object":"model"}]}\n' "$STUB_SERVED_MODEL"
EOF
chmod +x "$work/bin/"*

failures=0
check() {  # check <description> <command...>
  if "${@:2}"; then echo "ok   $1"; else echo "FAIL $1"; failures=$((failures + 1)); fi
}

run() {  # run <tool> <class> [served model]
  local tool="$1" class="$2" served="${3:-$2}"
  export STUB_LOG="$work/log-$tool-$class-$served" STUB_SERVED_MODEL="$served"
  mkdir -p "$STUB_LOG"
  PATH="$work/bin:$PATH" VLLM_API_KEY=test OUT_DIR="$work/evidence-$tool-$class-$served" \
    "$root/redteam/$tool/run.sh" "$class" >"$STUB_LOG/stdout" 2>&1
}

want="http://vllm-class-s.models.svc:8000/v1"

if run garak class-s; then status=0; else status=$?; fi
log="$work/log-garak-class-s-class-s"
check "garak run for class-s succeeds" test "$status" -eq 0
check "garak targets the class-s endpoint" grep -q "\"uri\": *\"$want\"" "$log/garak-options.json"
check "garak asks for the class-s model" grep -q '"model": *"class-s"' "$log/garak-options.json"
check "garak never targets class-m" bash -c "! grep -rq class-m '$log'"
check "garak evidence records the endpoint" grep -qx "$want" "$work/evidence-garak-class-s-class-s/endpoint.txt"
check "garak evidence records /v1/models" grep -q '"id":"class-s"' "$work/evidence-garak-class-s-class-s/models.json"

if run inspect class-s; then status=0; else status=$?; fi
log="$work/log-inspect-class-s-class-s"
check "inspect run for class-s succeeds" test "$status" -eq 0
check "inspect targets the class-s endpoint" grep -qx "$want" "$log/inspect.base-url"
check "inspect asks for the class-s model" grep -qx "openai/class-s" "$log/inspect.args"
check "inspect never targets class-m" bash -c "! grep -rq class-m '$log'"
check "inspect evidence records the endpoint" grep -qx "$want" "$work/evidence-inspect-class-s-class-s/endpoint.txt"
check "inspect evidence records /v1/models" grep -q '"id":"class-s"' "$work/evidence-inspect-class-s-class-s/models.json"

# An endpoint that does not serve the requested model must stop the run before any probe is sent.
for tool in garak inspect; do
  if run "$tool" class-s class-m; then status=0; else status=$?; fi
  check "$tool refuses an endpoint serving another model" test "$status" -ne 0
  check "$tool sent no probe to the wrong model" test ! -e "$work/log-$tool-class-s-class-m/$tool.args"
done

echo "$failures failed"
exit $((failures > 0))
