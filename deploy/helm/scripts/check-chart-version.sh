#!/usr/bin/env bash
# The chart's `version` and `appVersion` must equal the service version in
# backend/pyproject.toml. With an argument (a release tag such as v1.2.3), the tag
# must match as well. Exits non-zero on any mismatch.
#
#   bash deploy/helm/scripts/check-chart-version.sh [vX.Y.Z]
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
chart="$root/deploy/helm/to-herd-cats-ai/Chart.yaml"
pyproject="$root/backend/pyproject.toml"

[[ -f $chart ]] || { echo "FAIL: $chart is missing" >&2; exit 1; }

# `version = "..."` inside the [project] table of pyproject.toml.
service=$(awk '
  /^\[/ { in_project = ($0 == "[project]") }
  in_project && /^version[[:space:]]*=/ { gsub(/^version[[:space:]]*=[[:space:]]*"|"[[:space:]]*$/, ""); print; exit }
' "$pyproject")
# Top-level `version:` / `appVersion:` of Chart.yaml, quotes removed.
field() { sed -n -E "s/^$1:[[:space:]]*\"?([^\"[:space:]]+)\"?[[:space:]]*$/\1/p" "$chart" | head -1; }
version=$(field version)
app_version=$(field appVersion)

status=0
[[ -n $service ]] || { echo "FAIL: no [project] version in $pyproject" >&2; exit 1; }
[[ $version == "$service" ]] || { echo "FAIL: Chart.yaml version '$version' != pyproject version '$service'" >&2; status=1; }
[[ $app_version == "$service" ]] || { echo "FAIL: Chart.yaml appVersion '$app_version' != pyproject version '$service'" >&2; status=1; }
if [[ $# -gt 0 ]]; then
  [[ $1 == "v$service" ]] || { echo "FAIL: tag '$1' != v$service" >&2; status=1; }
fi
[[ $status -eq 0 ]] && echo "chart version OK: $service"
exit $status
