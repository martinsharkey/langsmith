#!/usr/bin/env bash
# Installs RKE2 from local artefacts (no internet). Run as root on each node.
#   ROLE=server|agent  ARTEFACT_DIR=/opt/rke2-artifacts  ./install-rke2-airgap.sh
# ARTEFACT_DIR must hold, for the version in versions.yaml:
#   rke2.linux-amd64.tar.gz, rke2-images.linux-amd64.tar.zst, sha256sum-amd64.txt, install.sh
set -euo pipefail
: "${ROLE:?set ROLE to server or agent}"
: "${ARTEFACT_DIR:?set ARTEFACT_DIR}"
here="$(cd "$(dirname "$0")/.." && pwd)"

echo "Verifying artefact checksums"
(cd "$ARTEFACT_DIR" && grep -E 'rke2(-images)?\.linux-amd64\.tar\.(gz|zst)$' sha256sum-amd64.txt | sha256sum -c -)

echo "Preparing CIS prerequisites"
id etcd >/dev/null 2>&1 || useradd -r -c "etcd user" -s /sbin/nologin -M etcd -U
mkdir -p /etc/rancher/rke2 /var/lib/rancher/rke2/agent/images
install -m 0600 "$here/config/${ROLE}.yaml" /etc/rancher/rke2/config.yaml
[ "$ROLE" = server ] && install -m 0600 "$here/config/audit-policy.yaml" /etc/rancher/rke2/audit-policy.yaml
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
