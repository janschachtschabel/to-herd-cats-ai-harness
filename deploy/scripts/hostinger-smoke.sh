#!/usr/bin/env bash
# Smoke test of the Hostinger stack (root docker-compose.yml, docs/HOSTINGER.md) the way
# the Docker Manager runs it: a folder holding only docker-compose.yml, with
# .env.example as .env, and a Traefik in the host's network in front.
#
#  1. `docker compose config -q` without .env and with .env.example as .env.
#  2. First deploy with that empty .env: init ends with 0, db, app and backup run, no
#     port is published.
#  3. DOMAIN with https:// is refused by init with a clear message, and the stack stays
#     stopped (depends_on init restart: true stops db, app and backup first;
#     docs/HOSTINGER.md says so).
#  4. DOMAIN fixed and the one-time admin set, `up -d` again: everything runs again with
#     the same secrets, a Traefik (docker provider, host network, the labels' entrypoint
#     and resolver names) routes https://DOMAIN to the app, the admin signs in with a
#     __Host- cookie that is Secure, the live events (SSE) and the live editing's
#     WebSocket (101 for the right Origin, 403 for a foreign one) pass Traefik, and the
#     backup service is healthy and makes a good backup into its volume.
#  5. ADMIN_PASSWORD cleared, `up -d`: the app restarts (depends_on init restart: true),
#     its password file is empty, the admin still signs in, the secrets stay the same.
#
# Needs the image ghcr.io/janschachtschabel/to-herd-cats-ai:$HOSTINGER_SMOKE_TAG locally
# (CI tags the image it built), Docker with Compose v2, curl and openssl. Uses the
# default network herd-web and host ports $HOSTINGER_SMOKE_PORT (18443) and 18081;
# removes everything it made. Ends with "HOSTINGER SMOKE OK".
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
export HERD_IMAGE_TAG="${HOSTINGER_SMOKE_TAG:-ci}"
port="${HOSTINGER_SMOKE_PORT:-18443}"
domain=wiki.example.org
project=herd-hostinger-smoke
traefik="$project-traefik"
traefik_image="traefik:v3.7.19@sha256:aa942a00bce033c909bf1f7e861d93761be4b31a035f10d2410d33e38a8f41cf"
work="$(mktemp -d)"
cp "$root/docker-compose.yml" "$work/docker-compose.yml"
compose=(docker compose -p "$project" --project-directory "$work" -f "$work/docker-compose.yml")

cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "HOSTINGER SMOKE FAILED; logs:" >&2
    "${compose[@]}" ps -a >&2 || true
    "${compose[@]}" logs --no-color --tail 60 >&2 || true
    docker logs --tail 40 "$traefik" >&2 2>&1 || true
  fi
  docker rm -f "$traefik" >/dev/null 2>&1 || true
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$work"
  exit $status
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
started() { docker inspect -f '{{.State.StartedAt}}' "$("${compose[@]}" ps -q app)" 2>/dev/null || true; }
secrets() { "${compose[@]}" exec -T app sh -c 'cat /secrets/secret_key /secrets/internal_token /db-secret/db_password | sha256sum'; }

# Wait until app runs a container started after $1 (empty: any) and reports healthy.
wait_app() {
  local before="$1" health
  for _ in $(seq 1 120); do
    id="$("${compose[@]}" ps -q app || true)"
    if [[ -n $id && "$(started)" != "$before" ]]; then
      health="$(docker inspect -f '{{.State.Health.Status}}' "$id")"
      [[ $health == healthy ]] && return 0
    fi
    sleep 2
  done
  fail "app did not become healthy (started before: ${before:-none})"
}

# init has ended with 0; every other service runs; nothing is published.
check_states() {
  local states
  states="$("${compose[@]}" ps -a --format '{{.Service}} {{.State}} {{.ExitCode}}')"
  grep -qx 'init exited 0' <<<"$states" || fail "init did not end with 0: $states"
  for service in db app backup; do
    grep -q "^$service running" <<<"$states" || fail "$service is not running: $states"
  done
  local ports
  ports="$("${compose[@]}" ps --format '{{.Ports}}')"
  if grep -q -- '->' <<<"$ports"; then
    fail "a port is published: $ports"
  fi
}

# Wait until a service's container reports healthy.
wait_healthy() {
  local id
  for _ in $(seq 1 60); do
    id="$("${compose[@]}" ps -q "$1" || true)"
    [[ -n $id && "$(docker inspect -f '{{.State.Health.Status}}' "$id")" == healthy ]] && return 0
    sleep 2
  done
  fail "$1 did not become healthy"
}

# The status of a WebSocket handshake on the live editing's path with Origin $1.
collab_handshake() {
  curl -sk --http1.1 --max-time 5 --resolve "$domain:$port:127.0.0.1" -o /dev/null \
    -w '%{http_code}' -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    -H "Origin: $1" \
    "https://$domain:$port/collab/00000000-0000-4000-8000-000000000000?generation=1" || true
}

login() {
  curl -sk --resolve "$domain:$port:127.0.0.1" -o /dev/null -D "$work/headers" -c "$work/jar" \
    -w '%{http_code}' \
    -X POST "https://$domain:$port/api/auth/login" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: herd' \
    --data "{\"email\": \"chef@example.org\", \"password\": \"$admin_password\"}"
}

# 1. The configuration without .env and with .env.example as .env.
"${compose[@]}" config -q
cp "$root/.env.example" "$work/.env"
"${compose[@]}" config -q
echo "config ok: without .env and with .env.example"

# 2. The first deploy with nothing filled in.
"${compose[@]}" up -d --pull never
wait_app ""
check_states
grep -q 'DOMAIN is empty: skipped' <<<"$("${compose[@]}" logs init)" || fail "init did not skip DOMAIN"
first_secrets="$(secrets)"
echo "first deploy ok: every container runs or ended with 0"

# 3. A URL in DOMAIN stops the deploy with a clear message.
cp "$root/.env.example" "$work/.env"
sed -i "s|^DOMAIN=$|DOMAIN=https://$domain|" "$work/.env"
if "${compose[@]}" up -d --pull never >"$work/refused.log" 2>&1; then
  fail "a DOMAIN with https:// was accepted"
fi
grep -q 'DOMAIN must be a bare host name' <<<"$("${compose[@]}" logs init)" \
  || fail "init did not explain the DOMAIN"
states="$("${compose[@]}" ps -a --format '{{.Service}} {{.State}} {{.ExitCode}}')"
grep -qx 'init exited 2' <<<"$states" || fail "init did not end with 2: $states"
if grep -qE '^(db|app|backup) running' <<<"$states"; then
  fail "a service still runs after the refusal; docs/HOSTINGER.md says the stack stops: $states"
fi
echo "DOMAIN with https:// refused with a clear message; the stack stays stopped"

# 4. DOMAIN and the one-time admin, then Traefik in front.
admin_password="$(openssl rand -hex 16)"
cp "$root/.env.example" "$work/.env"
sed -i -e "s|^DOMAIN=$|DOMAIN=$domain|" -e 's|^ADMIN_EMAIL=$|ADMIN_EMAIL=chef@example.org|' \
  -e "s|^ADMIN_PASSWORD=\$|ADMIN_PASSWORD=$admin_password|" "$work/.env"
before="$(started)"
"${compose[@]}" up -d --pull never
wait_app "$before"
check_states
[[ "$(secrets)" == "$first_secrets" ]] || fail "the secrets changed on the second deploy"
echo "the value fixed: everything runs again with the same secrets"

# Hostinger's Traefik: host network, docker provider, exposedbydefault=false, entrypoints
# web and websecure, resolver letsencrypt (here without a reachable CA: default cert).
docker run -d --name "$traefik" --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro "$traefik_image" \
  --providers.docker=true --providers.docker.exposedbydefault=false \
  --entrypoints.web.address=:18081 --entrypoints.websecure.address=":$port" \
  --certificatesresolvers.letsencrypt.acme.storage=/tmp/acme.json \
  --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web \
  --certificatesresolvers.letsencrypt.acme.caserver=https://127.0.0.1:1/directory >/dev/null
for _ in $(seq 1 60); do
  code="$(curl -sk --resolve "$domain:$port:127.0.0.1" -o /dev/null -w '%{http_code}' \
    "https://$domain:$port/api/auth/me" || true)"
  [[ $code == 401 ]] && break
  sleep 1
done
[[ $code == 401 ]] || fail "Traefik did not route https://$domain to the app (got $code)"
spa="$(curl -sk --resolve "$domain:$port:127.0.0.1" "https://$domain:$port/spaces")" \
  || fail "https://$domain/spaces did not answer through Traefik"
grep -q 'id="root"' <<<"$spa" || fail "the SPA is not served through Traefik"
[[ "$(login)" == 200 ]] || fail "the one-time admin cannot sign in"
session_cookie="$(grep -i '^set-cookie: __Host-herd_session=' "$work/headers" || true)"
grep -qiE ';[[:space:]]*secure' <<<"$session_cookie" \
  || fail "the session cookie is not a Secure __Host- cookie: $(grep -i '^set-cookie' "$work/headers" | cut -d= -f1)"
echo "second deploy ok: https://$domain through Traefik, admin signs in (__Host-, Secure)"

# The live events: an SSE stream through Traefik (curl ends it after 3 s).
curl -sk --resolve "$domain:$port:127.0.0.1" --max-time 3 -b "$work/jar" -o /dev/null \
  -D "$work/sse" "https://$domain:$port/api/stream" || true
grep -qi '^content-type: text/event-stream' "$work/sse" \
  || fail "no event stream through Traefik: $(head -1 "$work/sse")"
# The live editing: the relay's WebSocket handshake, by Origin.
code="$(collab_handshake "https://$domain")"
[[ $code == 101 ]] || fail "the collab WebSocket with the right Origin answered $code"
code="$(collab_handshake "https://elsewhere.example.net")"
[[ $code == 403 ]] || fail "the collab WebSocket with a foreign Origin answered $code"
echo "live events (SSE) and live editing (WebSocket 101/403) pass Traefik"

# The backup service: healthy, and a backup now lands in its volume.
wait_healthy backup
made="$("${compose[@]}" exec -T backup python -m app.ops backup run | tr -d '\r' | tail -1)"
[[ $made == *" offsite=off" ]] || fail "backup run printed: $made"
runs="$("${compose[@]}" exec -T backup python -m app.ops backup list)" || fail "backup list failed"
grep -q $'\tok\t' <<<"$runs" || fail "backup list shows no good run: $runs"
"${compose[@]}" exec -T backup sh -c 'ls /backups/herd-*.tar /backups/herd-*.manifest.json' \
  >/dev/null || fail "no archive with its manifest in the volume"
echo "backup ok: healthy, a good backup with its manifest in the volume"

# 5. The one-time password cleared: the app restarts, nothing is left of it.
sed -i 's|^ADMIN_PASSWORD=.*$|ADMIN_PASSWORD=|' "$work/.env"
before="$(started)"
"${compose[@]}" up -d --pull never
wait_app "$before"
check_states
"${compose[@]}" exec -T app sh -c 'test -f /secrets/bootstrap_admin_password && test ! -s /secrets/bootstrap_admin_password' \
  || fail "the bootstrap password file is not empty"
[[ "$(secrets)" == "$first_secrets" ]] || fail "the secrets changed on the third deploy"
for _ in $(seq 1 30); do
  code="$(login || true)"
  [[ $code == 200 ]] && break
  sleep 1
done
[[ $code == 200 ]] || fail "the admin cannot sign in after the password was cleared ($code)"
echo "third deploy ok: password file empty, admin still signs in"

echo "HOSTINGER SMOKE OK"
