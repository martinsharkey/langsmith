#!/usr/bin/env bash
# Verifies the RKE2 artefacts a node installs from, before anything runs:
#   - the tarballs against the release's sha256sum-amd64.txt;
#   - install.sh against the checksum pinned in this repository (../install.sh.sha256). The release checksum file
#     does not cover install.sh (docs.rke2.io/install/airgap), so the pin is taken from install.sh at the RKE2 tag
#     in versions.yaml: https://raw.githubusercontent.com/rancher/rke2/<tag>/install.sh. Update both together.
#   ./verify-rke2-artefacts.sh /opt/rke2-artifacts
set -euo pipefail
dir="${1:?usage: verify-rke2-artefacts.sh ARTEFACT_DIR}"
here="$(cd "$(dirname "$0")/.." && pwd)"
pin="${INSTALL_SH_SHA256_FILE:-$here/install.sh.sha256}"
pin="$(cd "$(dirname "$pin")" && pwd)/$(basename "$pin")"   # absolute, as the checks run from ARTEFACT_DIR
# Nodes have sha256sum (coreutils); shasum is the same check on developer machines that lack it.
if command -v sha256sum >/dev/null; then check=(sha256sum -c -); else check=(shasum -a 256 -c -); fi

cd "$dir"
for f in rke2.linux-amd64.tar.gz rke2-images.linux-amd64.tar.zst; do
  # Only the files this node installs: the release list names many more, which are not carried.
  line="$(awk -v f="$f" '$2 == f' sha256sum-amd64.txt)"
  [ -n "$line" ] || { echo "$f is not in sha256sum-amd64.txt" >&2; exit 1; }
  echo "$line" | "${check[@]}"
done
"${check[@]}" < "$pin"
