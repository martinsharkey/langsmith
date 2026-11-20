#!/usr/bin/env bash
# Connected side only. Copies every pinned chart from its upstream Helm repository into an OCI registry, from
# which `zarf package create --set CHART_REGISTRY=<registry>` collects them for carry-in.
#   airgap/push-charts.sh harbor.example.internal/platform
# Charts land at oci://<registry>/charts/<chart>:<version>. Log in first with `helm registry login`.
set -euo pipefail
registry="${1:?usage: push-charts.sh <registry[/project]>}"
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
grep -v '^#' "$here/charts.txt" | while read -r chart repo version; do
  [ -n "$chart" ] || continue
  helm pull "$chart" --repo "$repo" --version "$version" --destination "$work"
  helm push "$work/$chart-${version}.tgz" "oci://$registry/charts"
done
