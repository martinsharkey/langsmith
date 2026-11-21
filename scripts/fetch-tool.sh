#!/usr/bin/env bash
# Downloads a release asset, refuses it unless its SHA-256 matches the entry in .github/tool-checksums.txt, then
# installs it into the current directory (issue 41, SSDF PO.3 / PS.2). The checksum file is in sha256sum format,
# so coreutils `sha256sum --check` does the comparison; no hand-written matching decides anything here.
#
# Usage: scripts/fetch-tool.sh <url> <name>...
#   For a .tar.gz asset, each <name> is a member to extract. Otherwise the asset is installed as the one <name>.
# Env:   TOOL_CHECKSUMS  alternative checksum file (used by the CI self-test)
set -euo pipefail
url="$1"; shift
root="$(cd "$(dirname "$0")/.." && pwd)"
src="${TOOL_CHECKSUMS:-$root/.github/tool-checksums.txt}"
sums="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"
asset="${url##*/}"
work="$(mktemp -d "${RUNNER_TEMP:-$root/out}/fetch-tool.XXXXXX")"
trap 'rm -rf "$work"' EXIT

curl -sSfL --retry 3 -o "$work/$asset" "$url"
# --ignore-missing skips the other tools' lines; sha256sum still fails when no line names this asset.
(cd "$work" && sha256sum --check --strict --ignore-missing "$sums")

case "$asset" in
  *.tar.gz) tar -xzf "$work/$asset" -C . "$@" ;;
  *) install -m 0755 "$work/$asset" "./$1" ;;
esac
