#!/usr/bin/env bash
# Smoke test of the compose reference: build, start, log in, check probes and user,
# tear down. Runs as its own compose project on its own port, with throwaway volumes,
# so a running installation next to it is not touched. Ends with "SMOKE OK".
#
#   bash deploy/compose/smoke.sh            (SMOKE_PORT=18080 by default)
#   SMOKE_SKIP_BUILD=1 bash deploy/compose/smoke.sh   (use an image built beforehand,
#                                            tagged to-herd-cats-ai:${HERD_IMAGE_TAG:-local})
set -euo pipefail
cd "$(dirname "$0")"

export HERD_HOST_PORT="${SMOKE_PORT:-18080}"
export HERD_BIND_ADDRESS=127.0.0.1
base="http://127.0.0.1:${HERD_HOST_PORT}"
work="$(mktemp -d)"

# The secrets: .env if there is one, else a throwaway one (removed again below).
env_file=.env
if [[ ! -f "$env_file" ]]; then
  env_file="$work/env"
  {
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
    echo "HERD_BOOTSTRAP_ADMIN_EMAIL=admin@example.com"
    echo "HERD_BOOTSTRAP_ADMIN_PASSWORD=$(openssl rand -hex 24)"
  } >"$env_file"
fi
compose=(docker compose -p to-herd-cats-ai-smoke --env-file "$env_file" -f compose.yml)

cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "SMOKE FAILED; app logs:" >&2
    "${compose[@]}" logs --no-color --tail 80 app >&2 || true
  fi
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$work"
  exit $status
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
value() { grep -E "^$1=" "$env_file" | tail -1 | cut -d= -f2-; }

build=(--build)
[[ ${SMOKE_SKIP_BUILD:-0} == 1 ]] && build=()
"${compose[@]}" up -d "${build[@]}" --wait --wait-timeout 180

email="$(value HERD_BOOTSTRAP_ADMIN_EMAIL)"
password="$(value HERD_BOOTSTRAP_ADMIN_PASSWORD)"
jar="$work/cookies"
code=$(curl -s -o /dev/null -w '%{http_code}' -c "$jar" -X POST "$base/api/auth/login" \
  -H 'Content-Type: application/json' -H 'X-Requested-With: herd' \
  --data "{\"email\": \"${email:-admin@example.com}\", \"password\": \"$password\"}")
[[ $code == 200 ]] || fail "login answered $code"

code=$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" "$base/api/auth/me")
[[ $code == 200 ]] || fail "/api/auth/me answered $code"

"${compose[@]}" exec -T app python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/ready', timeout=5)" \
  || fail "/ready on 9090 is not 200"

uid="$("${compose[@]}" exec -T app id -u | tr -d '\r')"
[[ $uid == 10001 ]] || fail "app runs as uid $uid"

ports="$("${compose[@]}" ps app --format '{{.Ports}}')"
grep -q -- '->8080/tcp' <<<"$ports" || fail "port 8080 is not published ($ports)"
if grep -q -- '->9090' <<<"$ports"; then fail "port 9090 is published ($ports)"; fi

headers="$(curl -s -D - -o "$work/index.html" "$base/spaces")"
grep -q 'id="root"' "$work/index.html" || fail "/spaces did not serve the SPA"
grep -qi '^content-security-policy: default-src' <<<"$headers" || fail "no CSP on the SPA"

echo "SMOKE OK"
