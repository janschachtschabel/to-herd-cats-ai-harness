#!/usr/bin/env bash
# Behaviour of the chart that lint and kubeconform cannot see. Exits non-zero on the
# first rule that does not hold.
#
#   bash deploy/helm/scripts/check-chart-rules.sh
#   HELM="docker run --rm -v $PWD:$PWD -w $PWD alpine/helm:3.19.0" bash deploy/helm/scripts/check-chart-rules.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$root"
chart=deploy/helm/to-herd-cats-ai
read -r -a helm <<<"${HELM:-helm}"

fail() { echo "FAIL: $*" >&2; exit 1; }
render() { "${helm[@]}" template t "$chart" "$@" 2>&1; }

# The session cookie is Secure by default.
out=$(render)
grep -A1 -- "- name: HERD_COOKIE_SECURE" <<<"$out" | grep -q 'value: "true"' \
  || fail "HERD_COOKIE_SECURE is not true by default"

# With an Ingress the trusted proxies must be named, and are then passed on.
if out=$(render --set ingress.enabled=true); then
  fail "ingress.enabled without api.forwardedAllowIps rendered"
fi
grep -q "api.forwardedAllowIps is required" <<<"$out" || fail "unexpected error: $out"
out=$(render --set ingress.enabled=true --set api.forwardedAllowIps=10.0.0.0/8)
grep -A1 -- "- name: HERD_FORWARDED_ALLOW_IPS" <<<"$out" | grep -q '"10.0.0.0/8"' \
  || fail "HERD_FORWARDED_ALLOW_IPS is not passed on"

echo "chart rules OK"
