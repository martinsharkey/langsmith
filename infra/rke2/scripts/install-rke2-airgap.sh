#!/usr/bin/env bash
# Installs RKE2 from local artefacts (no internet). Run as root on each node, the first server first:
#   ARTEFACT_DIR=/opt/rke2-artifacts ./install-rke2-airgap.sh
# The node's role, pool and registration address come from /etc/innovox/node.env, written by OpenTofu through
# cloud-init (RKE2_ROLE, NODE_POOL, RKE2_FIRST_SERVER, RKE2_SERVER_URL, RKE2_TLS_SAN). Variables set in the
# environment (ROLE, POOL, FIRST_SERVER, SERVER_URL, TLS_SAN) take precedence; see render-rke2-config.sh.
# ARTEFACT_DIR must hold, for the version in versions.yaml:
#   rke2.linux-amd64.tar.gz, rke2-images.linux-amd64.tar.zst, sha256sum-amd64.txt, install.sh
set -euo pipefail
: "${ARTEFACT_DIR:?set ARTEFACT_DIR}"
NODE_ENV="${NODE_ENV:-/etc/innovox/node.env}"
if [ -f "$NODE_ENV" ]; then
  # The file is written by cloud-init on this node, so its path is only known at run time.
  # shellcheck disable=SC1090
  . "$NODE_ENV"
fi
export ROLE="${ROLE:-${RKE2_ROLE:-}}" POOL="${POOL:-${NODE_POOL:-}}"
export FIRST_SERVER="${FIRST_SERVER:-${RKE2_FIRST_SERVER:-false}}"
export SERVER_URL="${SERVER_URL:-${RKE2_SERVER_URL:-}}" TLS_SAN="${TLS_SAN:-${RKE2_TLS_SAN:-}}"
: "${ROLE:?set ROLE to server or agent}"
here="$(cd "$(dirname "$0")/.." && pwd)"

echo "Verifying artefact checksums, install.sh included"
"$here/scripts/verify-rke2-artefacts.sh" "$ARTEFACT_DIR"

echo "Preparing CIS prerequisites"
id etcd >/dev/null 2>&1 || useradd -r -c "etcd user" -s /sbin/nologin -M etcd -U
mkdir -p /var/lib/rancher/rke2/agent/images
"$here/scripts/render-rke2-config.sh"
cp "$ARTEFACT_DIR/rke2-images.linux-amd64.tar.zst" /var/lib/rancher/rke2/agent/images/
[ -f /etc/rancher/rke2/token ] || { echo "Missing /etc/rancher/rke2/token (hand over securely first)"; exit 1; }

INSTALL_RKE2_ARTIFACT_PATH="$ARTEFACT_DIR" INSTALL_RKE2_TYPE="$ROLE" sh "$ARTEFACT_DIR/install.sh"
for f in /usr/local/share/rke2/rke2-cis-sysctl.conf /usr/share/rke2/rke2-cis-sysctl.conf; do
  [ -f "$f" ] && cp -f "$f" /etc/sysctl.d/60-rke2-cis.conf && break
done
systemctl restart systemd-sysctl
if [ "$ROLE" = server ]; then
  mkdir -p /var/lib/rancher/rke2/server/manifests
  cp "$here/manifests/rke2-cilium-config.yaml" /var/lib/rancher/rke2/server/manifests/
fi
systemctl enable --now "rke2-${ROLE}.service"
echo "RKE2 ${ROLE} started"
