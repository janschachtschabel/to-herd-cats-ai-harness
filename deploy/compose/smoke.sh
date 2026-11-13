#!/usr/bin/env bash
# Smoke test of the compose reference: build, start, log in, check probes and user,
# create a page with an attachment (the files volume), open its live-editing
# WebSocket with and without the session cookie, tear down. Runs as its own compose project on its own port, with throwaway volumes,
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
    echo "HERD_INTERNAL_TOKEN=$(openssl rand -hex 32)"
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

# The wiki: a page in the first space, an attachment on the files volume (/data).
api() {
  curl -s -b "$jar" -H 'Content-Type: application/json' -H 'X-Requested-With: herd' "$@"
}
space_id="$(api "$base/api/spaces" | python3 -c 'import json, sys; print(json.load(sys.stdin)["items"][0]["id"])')"
page="$(api -X POST "$base/api/spaces/$space_id/pages" --data '{"title": "Smoke", "content_md": "# Smoke"}')"
read -r page_id generation < <(python3 -c \
  'import json, sys; p = json.loads(sys.argv[1]); print(p["id"], p["collab_generation"])' "$page") \
  || fail "creating a page answered $page"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" -X POST -H 'X-Requested-With: herd' \
  -H 'Content-Type: application/octet-stream' --data-binary 'smoke' \
  "$base/api/pages/$page_id/attachments?filename=smoke.txt")
[[ $code == 201 ]] || fail "uploading an attachment answered $code"

# Live editing: the WebSocket through the API's relay to the collab process. With the
# owner's cookie the collab process authenticates the Hocuspocus client (answer:
# Auth/Authenticated); without a cookie the relay closes with 4401.
cookie="$(awk '$6 == "herd_session" {print $6 "=" $7}' "$jar")"
origin="$(value HERD_PUBLIC_URL || true)"
"${compose[@]}" exec -T -e COOKIE="$cookie" -e PAGE="$page_id" -e GENERATION="$generation" \
  -e ORIGIN="${origin:-http://127.0.0.1:8080}" app python - <<'PY' \
  || fail "the live-editing WebSocket did not behave"
import os
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect


def varstring(text: str) -> bytes:
    data = text.encode()
    return bytes([len(data)]) + data  # lengths below 128: one varuint byte


url = f"ws://127.0.0.1:8080/collab/{os.environ['PAGE']}?generation={os.environ['GENERATION']}"
origin = {"Origin": os.environ["ORIGIN"]}
name = f"page:{os.environ['PAGE']}"
# Hocuspocus: document name, message type 2 (auth), 0 (token), the token.
auth = varstring(name) + bytes([2, 0]) + varstring("session-cookie")
with connect(url, additional_headers={**origin, "Cookie": os.environ["COOKIE"]}) as ws:
    ws.send(auth)
    for _ in range(10):
        reply = ws.recv(timeout=10)
        assert isinstance(reply, bytes)
        rest = reply[1 + reply[0] :]
        if rest[:2] == bytes([2, 2]):  # auth, authenticated
            break
        assert rest[:2] != bytes([2, 1]), "permission denied"
    else:
        raise AssertionError("not authenticated")
with connect(url, additional_headers=origin) as ws:
    try:
        ws.recv(timeout=10)
        raise AssertionError("a frame without a cookie")
    except ConnectionClosed as closed:
        assert closed.rcvd is not None and closed.rcvd.code == 4401, closed.rcvd
PY

echo "SMOKE OK"
