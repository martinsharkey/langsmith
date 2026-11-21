#!/usr/bin/env bash
# Writes the RKE2 configuration for one node into DEST (default /etc/rancher/rke2). Called by
# install-rke2-airgap.sh; the values come from /etc/innovox/node.env, which OpenTofu writes through cloud-init.
#   ROLE=server|agent         node role
#   FIRST_SERVER=true         only on the one server that starts the cluster
#   SERVER_URL=https://<registration address>:9345   every other server and every agent
#   TLS_SAN="<address> ..."   servers: the registration address, added to the server certificate
#   POOL=<pool>               node label innovox.uk/pool=<pool>; POOL=gpu adds the GPU taint (gpu-agent.yaml)
# Layout and merge rules: docs.rke2.io/install/configuration (config.yaml, then config.yaml.d/*.yaml in order;
# a key ending in "+" appends) and docs.rke2.io/install/ha (server, token and tls-san).
set -euo pipefail
: "${ROLE:?set ROLE to server or agent}"
: "${POOL:?set POOL to the node pool}"
DEST="${DEST:-/etc/rancher/rke2}"
FIRST_SERVER="${FIRST_SERVER:-false}"
SERVER_URL="${SERVER_URL:-}"
TLS_SAN="${TLS_SAN:-}"
here="$(cd "$(dirname "$0")/.." && pwd)"

fail() { echo "$*" >&2; exit 1; }
case "$ROLE" in server | agent) ;; *) fail "ROLE must be server or agent" ;; esac
if [ "$FIRST_SERVER" = true ]; then
  [ "$ROLE" = server ] || fail "FIRST_SERVER is only for a server"
  [ -z "$SERVER_URL" ] || fail "the first server starts the cluster and takes no SERVER_URL"
else
  [ -n "$SERVER_URL" ] || fail "SERVER_URL is required: without it a server starts its own cluster and an agent cannot join"
fi
[ "$ROLE" = agent ] || [ -n "$TLS_SAN" ] || fail "TLS_SAN is required on servers (the registration address)"
[ "$POOL" != gpu ] || [ "$ROLE" = agent ] || fail "POOL=gpu is for agents"

mkdir -p "$DEST/config.yaml.d"
install -m 0600 "$here/config/${ROLE}.yaml" "$DEST/config.yaml"
[ "$ROLE" = server ] && install -m 0600 "$here/config/audit-policy.yaml" "$DEST/audit-policy.yaml"

node="$DEST/config.yaml.d/10-node.yaml"
{
  echo "# Written by render-rke2-config.sh for this node."
  [ -n "$SERVER_URL" ] && echo "server: \"$SERVER_URL\""
  if [ "$ROLE" = server ]; then
    echo "tls-san:"
    for san in $TLS_SAN; do echo "  - \"$san\""; done
  fi
  echo "node-label+:"
  echo "  - \"innovox.uk/pool=$POOL\""
} > "$node"
chmod 0600 "$node"

[ "$POOL" = gpu ] && install -m 0600 "$here/config/gpu-agent.yaml" "$DEST/config.yaml.d/20-gpu.yaml"
echo "RKE2 ${ROLE} configuration written to $DEST"
