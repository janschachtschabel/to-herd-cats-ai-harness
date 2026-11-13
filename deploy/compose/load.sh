#!/usr/bin/env bash
# Resource and latency measurement of the compose reference, for docs/STECKBRIEF.md.
#
# Starts its own compose project (to-herd-cats-ai-load, port 18081, throwaway volumes
# and secrets) from an image built beforehand, then samples `docker stats` in three
# phases and tears everything down again:
#   idle  after start and LOAD_SETTLE seconds without requests;
#   warm  after a short warm-up (every endpoint touched), again without requests;
#   load  every 2 s while LOAD_CONCURRENCY clients log in and list spaces for
#         LOAD_DURATION seconds.
#
#   bash deploy/compose/load.sh
#   LOAD_TOOL=hey|oha|python  (default: hey, else oha, else the python fallback)
#   LOAD_DURATION=60 LOAD_CONCURRENCY=20 LOAD_SETTLE=30 LOAD_PORT=18081
#   LOAD_BUILD=1              (build the image first; default: use to-herd-cats-ai:local)
#
# hey and oha cannot chain requests, so they run two streams side by side: half the
# clients log in, the other half list spaces with one session. The python fallback
# (loadgen.py, run with the backend's environment) gives every client its own loop
# of login, then list.
#
# The login rate limits (HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE, 30 per address;
# HERD_LOGIN_RATE_LIMIT_PER_MINUTE, 5 failures per address and email) are raised in this
# throwaway project only: otherwise nearly every load login would be a cheap 429
# instead of a real argon2 verification.
set -euo pipefail
cd "$(dirname "$0")"
here="$(pwd)"

duration="${LOAD_DURATION:-60}"
concurrency="${LOAD_CONCURRENCY:-20}"
settle="${LOAD_SETTLE:-30}"
export HERD_HOST_PORT="${LOAD_PORT:-18081}"
export HERD_BIND_ADDRESS=127.0.0.1
base="http://127.0.0.1:${HERD_HOST_PORT}"
work="$(mktemp -d)"

tool="${LOAD_TOOL:-}"
if [[ -z $tool ]]; then
  if command -v hey >/dev/null; then tool=hey
  elif command -v oha >/dev/null; then tool=oha
  else tool=python; fi
fi

email=admin@example.com
password="$(openssl rand -hex 24)"
{
  echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
  echo "HERD_BOOTSTRAP_ADMIN_EMAIL=$email"
  echo "HERD_BOOTSTRAP_ADMIN_PASSWORD=$password"
  echo "HERD_INTERNAL_TOKEN=$(openssl rand -hex 24)"
} >"$work/env"
cat >"$work/override.yml" <<'EOF'
services:
  app:
    environment:
      HERD_LOGIN_RATE_LIMIT_PER_MINUTE: "1000000"
      HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE: "1000000"
EOF
project=to-herd-cats-ai-load
compose=(docker compose -p "$project" --env-file "$work/env" -f compose.yml -f "$work/override.yml")
containers=("$project-app-1" "$project-db-1")

cleanup() {
  status=$?
  [[ -n ${sampler:-} ]] && kill "$sampler" 2>/dev/null || true
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$work"
  exit $status
}
trap cleanup EXIT

sample() {  # phase: one `docker stats` line per container, tab separated
  docker stats --no-stream --format "$1\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    "${containers[@]}" >>"$work/stats"
}
quiet_samples() { for _ in 1 2 3 4 5; do sample "$1"; sleep 2; done; }

build=()
[[ ${LOAD_BUILD:-0} == 1 ]] && build=(--build)
"${compose[@]}" up -d "${build[@]}" --wait --wait-timeout 180

echo "idle: waiting ${settle}s"
sleep "$settle"
quiet_samples idle

# Log in once, keep the session for the space list, and create 20 team spaces so the
# list has something to show.
jar="$work/cookies"
curl -sf -o /dev/null -c "$jar" -X POST "$base/api/auth/login" \
  -H 'Content-Type: application/json' -H 'X-Requested-With: herd' \
  --data "{\"email\": \"$email\", \"password\": \"$password\"}"
token="$(awk '$6 == "herd_session" {print $7}' "$jar")"
for i in $(seq 1 20); do
  curl -sf -o /dev/null -b "$jar" -X POST "$base/api/spaces" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: herd' \
    --data "{\"name\": \"Team $i\", \"kind\": \"team\"}"
done

run_load() {  # seconds clients
  local login seconds=$1 clients=$2 half=$(( $2 / 2 > 0 ? $2 / 2 : 1 ))
  local body="{\"email\": \"$email\", \"password\": \"$password\"}"
  case $tool in
    hey)
      hey -z "${seconds}s" -c "$half" -m POST -T application/json -H 'X-Requested-With: herd' \
        -d "$body" "$base/api/auth/login" >"$work/login.txt" &
      login=$!
      hey -z "${seconds}s" -c "$(( clients - half ))" -H "Cookie: herd_session=$token" \
        "$base/api/spaces?limit=50" >"$work/spaces.txt"
      wait "$login" ;;
    oha)
      oha --no-tui -z "${seconds}s" -c "$half" -m POST -T application/json \
        -H 'X-Requested-With: herd' -d "$body" "$base/api/auth/login" >"$work/login.txt" &
      login=$!
      oha --no-tui -z "${seconds}s" -c "$(( clients - half ))" \
        -H "Cookie: herd_session=$token" "$base/api/spaces?limit=50" >"$work/spaces.txt"
      wait "$login" ;;
    python)
      uv run --quiet --project ../../backend python "$here/loadgen.py" run \
        "$base" "$email" "$password" "$clients" "$seconds" >"$work/python.txt" ;;
    *) echo "unknown LOAD_TOOL $tool" >&2; exit 1 ;;
  esac
}

echo "warm: warm-up with 2 clients for 10s"
run_load 10 2
sleep 10
quiet_samples warm

echo "load: $concurrency clients for ${duration}s with $tool"
( while true; do sample load; sleep 1; done ) &
sampler=$!
run_load "$duration" "$concurrency"
kill "$sampler"; wait "$sampler" 2>/dev/null || true
sampler=

echo
echo "== docker stats (machine: $(nproc) CPUs, $(free -m | awk '/^Mem:/ {print $2}') MiB) =="
uv run --quiet --project ../../backend python "$here/loadgen.py" stats "$work/stats"
echo
echo "== latency ($tool) =="
if [[ $tool == python ]]; then
  cat "$work/python.txt"
else
  for name in login spaces; do
    echo "-- $name"
    grep -E 'Requests/sec|Total:|Slowest|Fastest|Average|(10|50|90|99)(\.00)?% in|\[[0-9]{3}\][[:space:]]+[0-9]+ responses|Success rate|Error' \
      "$work/$name.txt" || cat "$work/$name.txt"
  done
fi
