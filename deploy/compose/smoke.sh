#!/usr/bin/env bash
# Smoke test of the compose reference: build, start, log in, check probes and user,
# create a page with an attachment (the files volume), open its live-editing
# WebSocket with and without the session cookie, receive a posted message over the
# live stream (/api/stream: outbox, worker, NOTIFY, SSE), create a ticket and change its
# status and find the worker's two system entries in its thread, let a one-off automation
# come due (15 s) and find exactly one term, read the page through /mcp with an access
# token (tools listed on node A, read_page called on node B), back up in the service backup
# and restore the archive into a second database, copy one with restic, tear down. Runs as its own
# compose project on its own ports, with throwaway volumes, so a running installation
# next to it is not touched. Ends with "SMOKE OK".
#
#   bash deploy/compose/smoke.sh            (SMOKE_PORT=18080 by default)
#   SMOKE_SKIP_BUILD=1 bash deploy/compose/smoke.sh   (use an image built beforehand,
#                                            tagged to-herd-cats-ai:${HERD_IMAGE_TAG:-local})
#   SMOKE_NODES=1 bash deploy/compose/smoke.sh        (compose.nodes.yml: two API nodes,
#       a worker, collab and a migration run in place of role all; the message is posted
#       on node A and must arrive on a stream of node B, SMOKE_PORT_B=18081 by default)
#   SMOKE_S3=1 bash deploy/compose/smoke.sh           (compose.s3.yml: attachments in
#       SeaweedFS; the file must not reach /data, `storage check` passes, the restore puts
#       the files under another prefix and `storage copy --to local` reads them back)
set -euo pipefail
cd "$(dirname "$0")"

export HERD_HOST_PORT="${SMOKE_PORT:-18080}"
export HERD_HOST_PORT_B="${SMOKE_PORT_B:-18081}"
export HERD_BIND_ADDRESS=127.0.0.1
base="http://127.0.0.1:${HERD_HOST_PORT}"
work="$(mktemp -d)"
stream_pid=""

# One node in role all (app), or two API nodes, a worker and collab (SMOKE_NODES=1).
project=to-herd-cats-ai-smoke
files=(-f compose.yml)
node_a=app
servers=(app)
worker=app
base_b="$base"
if [[ ${SMOKE_NODES:-0} == 1 ]]; then
  project=to-herd-cats-ai-smoke-nodes
  files+=(-f compose.nodes.yml)
  node_a=api-a
  servers=(api-a api-b worker)
  worker=worker
  base_b="http://127.0.0.1:${HERD_HOST_PORT_B}"
fi
s3=${SMOKE_S3:-0}
if [[ $s3 == 1 ]]; then
  [[ ${SMOKE_NODES:-0} == 1 ]] && { echo "SMOKE_S3 runs with role all only" >&2; exit 2; }
  project=to-herd-cats-ai-smoke-s3
  files+=(-f compose.s3.yml)
fi

# The secrets: .env if there is one, else a throwaway one (removed again below).
env_file=.env
if [[ ! -f "$env_file" ]]; then
  env_file="$work/env"
  {
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
    echo "HERD_BOOTSTRAP_ADMIN_EMAIL=admin@example.com"
    echo "HERD_BOOTSTRAP_ADMIN_PASSWORD=$(openssl rand -hex 24)"
    echo "HERD_INTERNAL_TOKEN=$(openssl rand -hex 32)"
    echo "HERD_S3_ACCESS_KEY_ID=herd$(openssl rand -hex 8)"
    echo "HERD_S3_SECRET_ACCESS_KEY=$(openssl rand -hex 24)"
  } >"$env_file"
fi
compose=(docker compose -p "$project" --env-file "$env_file" "${files[@]}")

cleanup() {
  status=$?
  if [[ -n $stream_pid ]]; then kill "$stream_pid" 2>/dev/null || true; fi
  if [[ $status -ne 0 ]]; then
    echo "SMOKE FAILED; logs:" >&2
    "${compose[@]}" logs --no-color --tail 80 >&2 || true
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

for url in "$base" "$base_b"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" "$url/api/auth/me")
  [[ $code == 200 ]] || fail "$url/api/auth/me answered $code"
done

# Every process of the app answers /ready on its internal port (a worker only while its
# loop reaches the database) and runs as 10001.
for service in "${servers[@]}"; do
  "${compose[@]}" exec -T "$service" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/ready', timeout=5)" \
    || fail "/ready on 9090 of $service is not 200"
  uid="$("${compose[@]}" exec -T "$service" id -u | tr -d '\r')"
  [[ $uid == 10001 ]] || fail "$service runs as uid $uid"
done

# Only the API nodes publish a port, and only 8080.
ports="$("${compose[@]}" ps "$node_a" --format '{{.Ports}}')"
grep -q -- '->8080/tcp' <<<"$ports" || fail "port 8080 is not published ($ports)"
for service in $("${compose[@]}" ps --services); do
  ports="$("${compose[@]}" ps "$service" --format '{{.Ports}}')"
  if grep -q -- '->9090\|->1234\|->5432' <<<"$ports"; then fail "$service publishes $ports"; fi
done

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
if [[ $s3 == 1 ]]; then
  stored="$("${compose[@]}" exec -T app find /data -path '*/attachments/*' -type f | wc -l)"
  (( stored == 0 )) || fail "the attachment went to /data, not to S3"
  checked="$("${compose[@]}" exec -T app python -m app.ops storage check | tr -d '\r' | tail -1)"
  [[ $checked == "ok s3" ]] || fail "storage check printed: $checked"
fi

# Live editing: the WebSocket through the API's relay to the collab process. With the
# owner's cookie the relay hands the collab process a grant for the page, which
# authenticates the Hocuspocus client (answer: Auth/Authenticated); without a cookie
# the relay closes with 4401.
cookie="$(awk '$6 == "herd_session" {print $6 "=" $7}' "$jar")"
origin="$(value HERD_PUBLIC_URL || true)"
"${compose[@]}" exec -T -e COOKIE="$cookie" -e PAGE="$page_id" -e GENERATION="$generation" \
  -e ORIGIN="${origin:-http://127.0.0.1:8080}" "$node_a" python - <<'PY' \
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

# Messages, live: a stream on node B (the one node without SMOKE_NODES), a message in
# #allgemein posted on node A. The worker hands the outbox event to publish_live, which
# NOTIFYs every node; node B's hub finds the stream and sends `message.created`.
channel_id="$(api "$base/api/channels" | python3 -c \
  'import json, sys; print(next(c["id"] for c in json.load(sys.stdin)["items"] if c["name"] == "allgemein"))')" \
  || fail "no channel #allgemein"
stream="$work/stream"
curl -sN -b "$jar" --max-time 120 "$base_b/api/stream" >"$stream" 2>/dev/null &
stream_pid=$!
for _ in $(seq 50); do grep -q '^retry: ' "$stream" && break; sleep 0.2; done
grep -q '^retry: ' "$stream" || fail "the live stream on $base_b did not open"
message="$(api -X POST "$base/api/conversations/$channel_id/messages" --data '{"body_md": "Smoke"}')"
message_id="$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])["id"])' "$message")" \
  || fail "posting a message answered $message"
received() {
  python3 - "$stream" "$message_id" <<'PY'
import json
import sys

for frame in open(sys.argv[1], encoding="utf-8").read().split("\n\n"):
    fields = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
    if fields.get("event") == "message.created":
        if json.loads(fields["data"]).get("message_id") == sys.argv[2]:
            sys.exit(0)
sys.exit(1)
PY
}
for _ in $(seq 100); do received && break; sleep 0.2; done
received || fail "message $message_id did not arrive on the live stream of $base_b"
kill "$stream_pid" 2>/dev/null || true
stream_pid=""

# Tickets: one created and moved on node A. The worker writes a system entry for each
# change into the ticket's thread, read on node B; #allgemein still holds only "Smoke".
json() { python3 -c "import json, sys; d = json.loads(sys.argv[1]); print($1)" "$2"; }
ticket="$(api -X POST "$base/api/spaces/$space_id/tickets" --data '{"title": "Smoke"}')"
read -r number version < <(json 'd["number"], d["version"]' "$ticket") \
  || fail "creating a ticket answered $ticket"
active="$(json 'next(s["id"] for s in d["items"] if s["category"] == "active")' \
  "$(api "$base/api/spaces/$space_id/ticket-statuses")")" || fail "no status of category active"
moved="$(api -X PATCH "$base/api/tickets/$number" \
  --data "{\"status_id\": \"$active\", \"version\": $version}")"
[[ "$(json 'd["status"]["category"]' "$moved" 2>/dev/null)" == active ]] \
  || fail "changing the ticket's status answered $moved"
thread_id="$(json 'd["id"]' "$(api "$base_b/api/tickets/$number/thread")")" \
  || fail "no thread for ticket $number on $base_b"
timeline() {
  json '" ".join(sorted(m["system"]["key"] for m in d["items"] if m["kind"] == "system"))' \
    "$(api "$base_b/api/conversations/$thread_id/messages?limit=100")"
}
for _ in $(seq 100); do
  [[ "$(timeline)" == "ticket.created ticket.status_changed" ]] && break
  sleep 0.2
done
[[ "$(timeline)" == "ticket.created ticket.status_changed" ]] \
  || fail "ticket $number's thread holds \"$(timeline)\", not its two system entries"
in_channel="$(json 'len(d["items"])' "$(api "$base/api/conversations/$channel_id/messages")")"
[[ $in_channel == 1 ]] || fail "#allgemein holds $in_channel messages after the ticket changes"

# MCP: the organisation's switch on, a read token through the API (its clear text shown
# once), then stateless JSON-RPC over POST /mcp: the tools listed on node A, the wiki's
# page (published: a token never reads drafts) read with read_page on node B. Without a
# token: 401 in the MCP form.
shown="$(api "$base/api/pages/$page_id")"
published="$(api -X POST "$base/api/pages/$page_id/publish" --data "{\"version\": $(json 'd["version"]' "$shown")}")"
[[ "$(json 'd["status"]' "$published" 2>/dev/null)" == published ]] || fail "publishing the page answered $published"
settings="$(api "$base/api/ai/mcp")"
switched="$(api -X PUT "$base/api/ai/mcp" --data \
  "{\"enabled\": true, \"data_location\": \"external\", \"version\": $(json 'd["version"]' "$settings")}")"
[[ "$(json 'd["enabled"]' "$switched")" == True ]] || fail "switching MCP on answered $switched"
token="$(api -X POST "$base/api/tokens" --data '{"name": "Smoke", "mode": "read", "expires_in_days": 1}')"
secret="$(json 'd["secret"]' "$token")" || fail "creating an access token answered $token"
mcp() {
  curl -s -X POST "$1/mcp" -H "Authorization: Bearer $secret" -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2025-06-18' --data "$2"
}
listed="$(mcp "$base" '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}')"
[[ "$(json '" ".join(sorted(t["name"] for t in d["result"]["tools"]))' "$listed" 2>/dev/null)" \
  == "list_tree list_versions read_page read_ticket search search_tickets" ]] \
  || fail "/mcp on $base listed $listed"
read_call="{\"jsonrpc\": \"2.0\", \"id\": 2, \"method\": \"tools/call\", \"params\": {\"name\": \"read_page\", \"arguments\": {\"page_id\": \"$page_id\"}}}"
called="$(mcp "$base_b" "$read_call")"
[[ "$(json 'd["result"]["isError"] is False and "# Smoke" in d["result"]["content"][0]["text"]' "$called" 2>/dev/null)" == True ]] \
  || fail "read_page through /mcp on $base_b answered $called"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base_b/mcp" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' --data '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}')
[[ $code == 401 ]] || fail "/mcp without a token answered $code"

# Automations: a one-off automation due in 15 s fires exactly once, from the worker's due
# loop (with SMOKE_NODES the worker service alone), read on node B. The agent's connection
# points at a closed local port: the term and its run count here, not an answer.
connection="$(api -X POST "$base/api/ai/connections" --data \
  '{"name": "Smoke", "kind": "local", "base_url": "http://127.0.0.1:9/v1", "models": ["smoke"]}')"
connection_id="$(json 'd["id"]' "$connection")" || fail "creating an AI connection answered $connection"
assignments="$(api "$base/api/ai/assignments")"
assigned="$(api -X PUT "$base/api/ai/assignments/default" --data \
  "{\"target\": {\"connection_id\": \"$connection_id\", \"model\": \"smoke\"}, \"version\": $(json 'd["version"]' "$assignments")}")"
json 'd["default"]["connection_id"]' "$assigned" >/dev/null || fail "the standard assignment answered $assigned"
me_id="$(json 'd["user"]["id"]' "$(api "$base/api/auth/me")")"
agent="$(api -X POST "$base/api/agents" --data "{\"name\": \"Smoke\", \"intro\": \"Smoke.\", \"instructions\": \"Smoke.\", \"connection_id\": \"$connection_id\", \"model\": \"smoke\", \"responsible_user_id\": \"$me_id\", \"status\": \"active\"}")"
agent_id="$(json 'd["id"]' "$agent")" || fail "creating an agent answered $agent"
at="$(python3 -c 'import datetime as t; print((t.datetime.now(t.UTC) + t.timedelta(seconds=15)).isoformat())')"
automation="$(api -X POST "$base/api/automations" --data "{\"agent_id\": \"$agent_id\", \"place\": {\"type\": \"dm\"}, \"instruction\": \"Smoke.\", \"schedule\": {\"kind\": \"once\", \"at\": \"$at\"}}")"
automation_id="$(json 'd["id"]' "$automation")" || fail "creating an automation answered $automation"
terms() {
  json '" ".join(f["outcome"] for f in d["items"])' \
    "$(api "$base_b/api/automations/$automation_id/firings?limit=100")"
}
for _ in $(seq 150); do [[ -n "$(terms)" ]] && break; sleep 0.2; done
sleep 6 # one more pass of every due loop (every 5 s): nothing more may come
[[ "$(terms)" == started ]] || fail "automation $automation_id logged \"$(terms)\", not one started term"
state="$(json 'd["state"]' "$(api "$base_b/api/automations/$automation_id")")"
[[ $state == done ]] || fail "automation $automation_id is $state after its one term"

# The worker delivered both (with SMOKE_NODES the worker service is the only dispatcher).
# Its /metrics is read whole before grep looks at it: `... | grep -q` under pipefail fails
# when grep stops at the match and the exec loses the rest of the text (over 8 KiB).
worker_metrics() {
  "${compose[@]}" exec -T "$worker" python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9090/metrics', timeout=5).read().decode())"
}
dispatched() {
  local metrics
  metrics="$(worker_metrics)" || return 1
  grep -Eq "^herd_outbox_dispatch_total\\{handler=\"$1\",result=\"ok\"\\} [1-9]" <<<"$metrics"
}
for handler in publish_live ticket_timeline; do
  for _ in $(seq 10); do dispatched "$handler" && break; sleep 0.5; done
  dispatched "$handler" || fail "$worker reports no $handler delivery"
done
metrics="$(worker_metrics)" || fail "$worker does not answer /metrics"
grep -Eq '^herd_automation_firings_total\{outcome="started"\} 1(\.0)?$' <<<"$metrics" \
  || fail "$worker does not report exactly one fired term"

# Backups (docs/SICHERUNG.md): one run in the service backup (as 10001, offsite off), the
# worker's gauge of it, and the archive restored into a second, empty database with the
# attachments into the container's /tmp; the restored page and its file are there.
uid="$("${compose[@]}" exec -T backup id -u | tr -d '\r')"
[[ $uid == 10001 ]] || fail "backup runs as uid $uid"
made="$("${compose[@]}" exec -T backup python -m app.ops backup run | tr -d '\r' | tail -1)"
[[ $made == *" offsite=off" ]] || fail "backup run printed: $made"
archive="${made%% *}"
runs="$("${compose[@]}" exec -T backup python -m app.ops backup list)" || fail "backup list failed"
grep -q $'\tok\t' <<<"$runs" || fail "backup list shows no good run: $runs"
backed_up() {
  local metrics
  metrics="$(worker_metrics)" || return 1
  grep -Eq '^herd_backup_last_success_timestamp_seconds [1-9]' <<<"$metrics"
}
for _ in $(seq 1 30); do backed_up && break; sleep 1; done
backed_up || fail "$worker does not export the backup's gauge"
"${compose[@]}" exec -T db psql -q -U herd -d herd -c 'CREATE DATABASE herd_restore' >/dev/null
target=(-e HERD_DATABASE_URL=postgresql+asyncpg://herd@db:5432/herd_restore
  -e HERD_DATA_DIR=/tmp/restore-data)
[[ $s3 == 1 ]] && target+=(-e HERD_S3_PREFIX=restored)
applied="$("${compose[@]}" exec -T "${target[@]}" backup python -m app.ops restore apply "$archive" \
  | tr -d '\r' | tail -1)" || fail "restore apply into herd_restore failed"
[[ $applied == "restored "* ]] || fail "restore apply into herd_restore printed: $applied"
if [[ $s3 == 1 ]]; then  # the restored files are under the prefix `restored`: read them back
  copied="$("${compose[@]}" exec -T "${target[@]}" backup python -m app.ops storage copy --to local \
    | tr -d '\r' | tail -1)" || fail "storage copy from S3 failed"
  [[ $copied == "copied "[1-9]* ]] || fail "storage copy from S3 printed: $copied"
fi
pages="$("${compose[@]}" exec -T db psql -tA -U herd -d herd_restore \
  -c "SELECT count(*) FROM page WHERE id = '$page_id'" | tr -d '\r')"
[[ $pages == 1 ]] || fail "the restored database lacks the page"
restored="$("${compose[@]}" exec -T backup find /tmp/restore-data -type f | wc -l)"
(( restored >= 1 )) || fail "the restore wrote no attachment file"

# restic, for real (the image's binary): a second run with a repository on the backup
# container's /tmp (offsite=ok), its snapshot read back with the same password.
offsite_password="$(openssl rand -hex 16)"
made="$("${compose[@]}" exec -T -e HERD_BACKUP_OFFSITE_REPOSITORY=/tmp/offsite \
  -e HERD_BACKUP_OFFSITE_PASSWORD="$offsite_password" backup python -m app.ops backup run \
  | tr -d '\r' | tail -1)"
[[ $made == *" offsite=ok" ]] || fail "backup run with restic printed: $made"
"${compose[@]}" exec -T -e RESTIC_REPOSITORY=/tmp/offsite -e RESTIC_PASSWORD="$offsite_password" \
  backup restic snapshots --tag herd --json \
  | python3 -c "import json, sys; sys.exit(0 if len(json.load(sys.stdin)) == 1 else 1)" \
  || fail "the restic repository holds no snapshot of the backup"

echo "SMOKE OK"
