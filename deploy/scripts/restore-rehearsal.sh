#!/usr/bin/env bash
# Restore rehearsal (plan M9 task 2): back up a running installation and restore it
# into an empty one, then prove that it works. Without Docker: the app runs as
# processes (role all, worker included) from backend/ with uv, against a PostgreSQL
# server reached with the PG* variables (default localhost:5433, user herd).
#
# Like every shipped stack (review M9b F2-1), the apps and every `python -m app.ops`
# command connect as a role of their own that owns the databases and is no superuser
# (LOGIN only, made here; the PG* role needs CREATEROLE and CREATEDB). The PG* role
# only creates and drops; a replace as that role, if it is a superuser, is refused
# with restore.superuser_refused.
#
#   1. database A, app A, demo data (scripts/demo_seed.py) and an attachment, a login;
#   2. `python -m app.ops backup create` while A runs;
#   3. empty database B and empty file storage: `restore check` (no problem),
#      `restore apply`;
#   4. A stopped, scripts/compare_databases.py A B before B serves anything (every
#      table but sessions, flows, the audit log and backup runs: rows and a checksum
#      of their content);
#   5. app B: /ready, the demo admin signs in, A's session cookie does not, the
#      attachment downloaded from B has A's SHA-256;
#   6. B changed (a page "Nach der Sicherung"), then replaced while it runs (plan M9
#      task 12; first as the PG* role, refused if that is a superuser):
#      `restore apply --replace --confirm "<organisation>"` answers with the
#      safety archive, B answered 503 in between, B's session is gone, the page made
#      after the archive is gone, the attachment is still there, the safety archive
#      is listed (`backup list`, trigger pre_restore);
#   7. the replaced B backed up (review M9b F2-2: its dump names schema `public` with
#      its owner): `restore check` into empty database C (no problem), `restore apply`,
#      app C serves the demo admin and the attachment; B replaced again by that
#      archive; its safety archive passes `restore check` against an empty C too;
#   8. a manipulated copy of the archive fails `restore check` with
#      archive.member_checksum;
#   9. every app stopped, every database and the owner role dropped, the scratch
#      directory removed.
#
# Prints "REHEARSAL OK" and exits 0 only if every step holds.
#
# With HERD_STORAGE=s3 and HERD_S3_ENDPOINT, HERD_S3_BUCKET, HERD_S3_ACCESS_KEY_ID and
# HERD_S3_SECRET_ACCESS_KEY in the environment (an S3-compatible store, e.g. a local
# SeaweedFS), the attachments of A and B live in that bucket, each installation under a
# prefix of its own (rehearsal/<database>), and no attachment may reach a data directory.
#
#   bash deploy/scripts/restore-rehearsal.sh
#   REHEARSAL_PORT=18480 PGHOST=localhost PGPORT=5433 PGUSER=herd PGPASSWORD=herd \
#     bash deploy/scripts/restore-rehearsal.sh
set -euo pipefail
cd "$(dirname "$0")/../../backend"

export PGHOST="${PGHOST:-localhost}" PGPORT="${PGPORT:-5433}" PGUSER="${PGUSER:-herd}"
export PGPASSWORD="${PGPASSWORD:-herd}"
port="${REHEARSAL_PORT:-18480}"
suffix="$$_$RANDOM"
db_a="herd_rehearsal_a_${suffix}"
db_b="herd_rehearsal_b_${suffix}"
db_c="herd_rehearsal_c_${suffix}"
owner="herd_rehearsal_owner_${suffix}"
owner_password="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
work="$(mktemp -d)"
pids=()
admin_email="admin@rehearsal.example"
# The first owner's password passes the password checks too (no "admin", "rehearsal").
admin_password="lantern-orbit-$RANDOM-$RANDOM"
# No context word of the demo people (their domain demo.example makes "demo" one).
demo_password="rehearsal-people-$RANDOM-$RANDOM"
# The backend's interpreter itself (not `uv run`), so that stopping an app reaches it.
py="$(uv run --quiet python -c 'import sys; print(sys.executable)')"
secret_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

say() { printf '== %s\n' "$*"; }
fail() { printf 'REHEARSAL FAILED: %s\n' "$*" >&2; exit 1; }

cleanup() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
  dropdb --if-exists --force "$db_a" 2>/dev/null || true
  dropdb --if-exists --force "$db_b" 2>/dev/null || true
  dropdb --if-exists --force "$db_c" 2>/dev/null || true
  dropuser --if-exists "$owner" 2>/dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT

# The app's settings for database $1, files in $2 (as the owner role, never PG*).
app_vars() {
  vars=(HERD_DATABASE_URL="postgresql+asyncpg://${owner}@${PGHOST}:${PGPORT}/$1"
    HERD_DATABASE_PASSWORD="$owner_password" HERD_DATA_DIR="$2" HERD_SECRET_KEY="$secret_key"
    HERD_BACKUP_DIR="$work/backups" HERD_LOG_FORMAT=text HERD_LOG_LEVEL=WARNING
    HERD_ENVIRONMENT=development)
  if [[ $s3 == 1 ]]; then vars+=(HERD_S3_PREFIX="rehearsal/$1"); fi
}
s3=0
[[ ${HERD_STORAGE:-local} == s3 ]] && s3=1
# No attachment in data directory $1 (with S3 they live in the store).
no_local_files() {
  if [[ $s3 == 1 && -n $(find "$1" -path '*/attachments/*' -type f 2>/dev/null) ]]; then
    fail "an attachment reached $1 with HERD_STORAGE=s3"
  fi
}
app_env() { app_vars "$1" "$2"; env "${vars[@]}" "${@:3}"; }

# App on database $1 with files in $2 on public port $3 (internal port $3+1); `env`
# execs the interpreter, so the recorded pid is the app's own.
start_app() {
  app_vars "$1" "$2"
  env "${vars[@]}" HERD_ROLE=all HERD_PUBLIC_PORT="$3" HERD_INTERNAL_PORT="$(($3 + 1))" \
    HERD_BOOTSTRAP_ADMIN_EMAIL="$admin_email" HERD_BOOTSTRAP_ADMIN_PASSWORD="$admin_password" \
    "$py" -m app.launch >"$work/app-$1.log" 2>&1 &
  pids+=("$!")
  for _ in $(seq 1 120); do
    if curl -fs -o /dev/null "http://127.0.0.1:$(($3 + 1))/ready"; then return 0; fi
    sleep 0.5
  done
  tail -20 "$work/app-$1.log" >&2
  fail "app on $1 did not become ready"
}

login() {  # base, cookie jar: the HTTP status of the admin's login
  curl -s -o /dev/null -w '%{http_code}' -c "$2" -X POST "$1/api/auth/login" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: herd' \
    --data "{\"email\": \"$admin_email\", \"password\": \"$admin_password\"}"
}

say "role $owner (no superuser), database A ($db_a), app A, storage ${HERD_STORAGE:-local}"
# The password as a SCRAM verifier, so that its clear text never reaches the server.
verifier="$("$py" -c 'import sys; from app.stack.db_owner import scram_verifier; print(scram_verifier(sys.argv[1]))' "$owner_password")"
psql -d postgres -v ON_ERROR_STOP=1 -q -v owner="$owner" -v verifier="$verifier" \
  <<<"CREATE ROLE :\"owner\" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'verifier';" \
  || fail "cannot create the role $owner (the PG* role needs CREATEROLE)"
[[ $(psql -d postgres -Atc "SELECT rolsuper FROM pg_roles WHERE rolname = '$owner'") == f ]] \
  || fail "$owner is a superuser"
createdb -O "$owner" "$db_a"
createdb -O "$owner" "$db_b"
base_a="http://127.0.0.1:${port}"
start_app "$db_a" "$work/data-a" "$port"
[[ $(login "$base_a" "$work/jar-a") == 200 ]] || fail "login on A"

say "demo data and an attachment on A"
HERD_DEMO_ADMIN_PASSWORD="$admin_password" HERD_DEMO_PASSWORD="$demo_password" \
  "$py" -m scripts.demo_seed --base "$base_a" --admin "$admin_email" \
  >"$work/seed.log" 2>&1 || { tail -20 "$work/seed.log" >&2; fail "demo_seed"; }
api_a() { curl -s -b "$work/jar-a" -H 'X-Requested-With: herd' "$@"; }
space_id="$(api_a "$base_a/api/spaces" | python3 -c 'import json, sys; print(json.load(sys.stdin)["items"][0]["id"])')"
page_id="$(api_a -H 'Content-Type: application/json' -X POST "$base_a/api/spaces/$space_id/pages" \
  --data '{"title": "Probe", "content_md": "# Probe"}' | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')"
head -c 200000 /dev/urandom | base64 >"$work/attachment.txt"
attachment_url="$(api_a -H 'Content-Type: application/octet-stream' --data-binary "@$work/attachment.txt" \
  -X POST "$base_a/api/pages/$page_id/attachments?filename=probe.txt" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["url"])')"
sha_a="$(api_a "$base_a$attachment_url" | sha256sum | cut -d' ' -f1)"
[[ $sha_a == "$(sha256sum <"$work/attachment.txt" | cut -d' ' -f1)" ]] || fail "download from A"
no_local_files "$work/data-a"

say "backup of A while it runs"
archive="$(app_env "$db_a" "$work/data-a" "$py" -m app.ops backup create | tail -1)"
[[ -f $archive ]] || fail "backup create printed $archive"
verified="$(app_env "$db_a" "$work/data-a" "$py" -m app.ops backup verify "$archive")" \
  || fail "backup verify: $verified"
grep -qx ok <<<"$verified" || fail "backup verify: $verified"
echo "   $(basename "$archive"): $(stat -c %s "$archive") bytes"
# A stops, so that what it does from now on (none expected) cannot blur the comparison.
kill "${pids[0]}" && wait "${pids[0]}" || true

say "restore check and apply into empty B ($db_b)"
app_env "$db_b" "$work/data-b" "$py" -m app.ops restore check "$archive" \
  >"$work/check.out" || { cat "$work/check.out" >&2; fail "restore check"; }
[[ "$(tail -1 "$work/check.out")" == ok ]] || fail "restore check: $(cat "$work/check.out")"
app_env "$db_b" "$work/data-b" "$py" -m app.ops restore apply "$archive" \
  | tail -1 | tee "$work/apply.out"
grep -q '^restored ' "$work/apply.out" || fail "restore apply"
no_local_files "$work/data-b"

say "compare A and B"
url() { echo "postgresql+asyncpg://${owner}@${PGHOST}:${PGPORT}/$1"; }
HERD_DATABASE_PASSWORD="$owner_password" "$py" -m scripts.compare_databases \
  "$(url "$db_a")" "$(url "$db_b")" \
  --ignore user_session oauth_flow audit_log backup_run || fail "A and B differ"

say "app B: ready, login, A's cookie refused"
base_b="http://127.0.0.1:$((port + 2))"
start_app "$db_b" "$work/data-b" "$((port + 2))"
[[ $(login "$base_b" "$work/jar-b") == 200 ]] || fail "login on B"
code="$(curl -s -o /dev/null -w '%{http_code}' -b "$work/jar-a" "$base_b/api/auth/me")"
[[ $code == 401 ]] || fail "A's session on B answered $code"

sha_b="$(curl -s -b "$work/jar-b" -H 'X-Requested-With: herd' "$base_b$attachment_url" | sha256sum | cut -d' ' -f1)"
[[ $sha_b == "$sha_a" ]] || fail "the attachment from B differs"
echo "   attachment sha256 $sha_b on both"

say "replace B while it runs, from the same archive"
api_b() { curl -s -b "$work/jar-b" -H 'X-Requested-With: herd' "$@"; }
json() { python3 -c "import json, sys; print(json.load(sys.stdin)$1)"; }
org_name="$(api_b "$base_b/api/auth/me" | json '["org"]["name"]')"
if [[ $(psql -d postgres -Atc "SELECT rolsuper FROM pg_roles WHERE rolname = current_user") == t ]]; then
  if app_env "$db_b" "$work/data-b" HERD_DATABASE_URL="postgresql+asyncpg://${PGUSER}@${PGHOST}:${PGPORT}/$db_b" \
    HERD_DATABASE_PASSWORD="$PGPASSWORD" "$py" -m app.ops restore apply "$archive" --replace \
    --confirm "$org_name" >"$work/super.out" 2>&1; then
    fail "a replace as the superuser $PGUSER was not refused"
  fi
  grep -qx restore.superuser_refused "$work/super.out" || fail "superuser replace: $(cat "$work/super.out")"
  echo "   as the superuser $PGUSER: restore.superuser_refused"
fi
later_id="$(api_b -H 'Content-Type: application/json' -X POST "$base_b/api/spaces/$space_id/pages" \
  --data '{"title": "Nach der Sicherung"}' | json '["id"]')"
code="$(curl -s -o /dev/null -w '%{http_code}' -b "$work/jar-b" "$base_b/api/pages/$later_id")"
[[ $code == 200 ]] || fail "the page made on B answered $code"
# What B answers meanwhile, twice a second.
(while :; do
  curl -s -o /dev/null -w '%{http_code}\n' -b "$work/jar-b" "$base_b/api/auth/me" || true
  sleep 0.5
done) >"$work/watch.out" 2>/dev/null &
watch=$!
pids+=("$watch")
app_env "$db_b" "$work/data-b" "$py" -m app.ops restore apply "$archive" --replace \
  --confirm "$org_name" | tail -1 | tee "$work/replace.out"
kill "$watch" 2>/dev/null || true
grep -q '^replaced by .*safety archive herd-' "$work/replace.out" || fail "replace"
grep -qx 503 "$work/watch.out" || fail "B never answered 503 during the replace"
echo "   B answered $(sort "$work/watch.out" | uniq -c | paste -sd' ') meanwhile"
for _ in $(seq 1 20); do  # the cache follows the NOTIFY of maintenance's end
  code="$(curl -s -o /dev/null -w '%{http_code}' -b "$work/jar-b" "$base_b/api/auth/me")"
  [[ $code == 503 ]] || break
  sleep 0.5
done
[[ $code == 401 ]] || fail "B's session after the replace answered $code"
[[ $(login "$base_b" "$work/jar-b") == 200 ]] || fail "login on B after the replace"
code="$(curl -s -o /dev/null -w '%{http_code}' -b "$work/jar-b" "$base_b/api/pages/$later_id")"
[[ $code == 404 ]] || fail "the page made after the archive answered $code"
sha_r="$(curl -s -b "$work/jar-b" -H 'X-Requested-With: herd' "$base_b$attachment_url" | sha256sum | cut -d' ' -f1)"
[[ $sha_r == "$sha_a" ]] || fail "the attachment after the replace differs"
runs="$(app_env "$db_b" "$work/data-b" "$py" -m app.ops backup list)" || fail "backup list on B failed"
grep -q $'\tpre_restore\tok\t' <<<"$runs" || fail "the safety archive is not listed: $runs"

say "back up the replaced B, restore that into empty C ($db_c), replace B with it again"
archive_r="$(app_env "$db_b" "$work/data-b" "$py" -m app.ops backup create | tail -1)"
[[ -f $archive_r ]] || fail "backup create on the replaced B printed $archive_r"
createdb -O "$owner" "$db_c"
app_env "$db_c" "$work/data-c" "$py" -m app.ops restore check "$archive_r" \
  >"$work/check-r.out" || { cat "$work/check-r.out" >&2; fail "restore check of B's backup"; }
[[ "$(tail -1 "$work/check-r.out")" == ok ]] || fail "restore check of B's backup: $(cat "$work/check-r.out")"
app_env "$db_c" "$work/data-c" "$py" -m app.ops restore apply "$archive_r" \
  | tail -1 | tee "$work/apply-r.out"
grep -q '^restored ' "$work/apply-r.out" || fail "restore apply of B's backup"
no_local_files "$work/data-c"
base_c="http://127.0.0.1:$((port + 4))"
start_app "$db_c" "$work/data-c" "$((port + 4))"
[[ $(login "$base_c" "$work/jar-c") == 200 ]] || fail "login on C"
sha_c="$(curl -s -b "$work/jar-c" -H 'X-Requested-With: herd' "$base_c$attachment_url" | sha256sum | cut -d' ' -f1)"
[[ $sha_c == "$sha_a" ]] || fail "the attachment from C differs"
kill "${pids[-1]}" && wait "${pids[-1]}" || true
app_env "$db_b" "$work/data-b" "$py" -m app.ops restore apply "$archive_r" --replace \
  --confirm "$org_name" | tail -1 | tee "$work/replace-r.out"
grep -q '^replaced by .*safety archive herd-' "$work/replace-r.out" || fail "the second replace"
safety_r="$work/backups/$(sed 's/.*safety archive //' "$work/replace-r.out")"
[[ -f $safety_r ]] || fail "the second safety archive $safety_r is missing"
dropdb --force "$db_c" && createdb -O "$owner" "$db_c"
app_env "$db_c" "$work/data-c2" "$py" -m app.ops restore check "$safety_r" \
  >"$work/check-s.out" || { cat "$work/check-s.out" >&2; fail "restore check of the safety archive"; }
[[ "$(tail -1 "$work/check-s.out")" == ok ]] || fail "the safety archive: $(cat "$work/check-s.out")"
echo "   $(basename "$archive_r") restored into C and B; safety archive $(basename "$safety_r") ok"

say "a manipulated archive is refused"
cp "$archive" "$work/spoiled.tar"
cp "${archive%.tar}.manifest.json" "$work/spoiled.manifest.json"
python3 - "$work/spoiled.tar" <<'PY'
import sys, tarfile
path = sys.argv[1]
with tarfile.open(path) as tar:
    info = next(m for m in tar.getmembers() if m.name.startswith("herd/files/"))
with open(path, "r+b") as handle:
    handle.seek(info.offset_data + 10)
    byte = handle.read(1)
    handle.seek(info.offset_data + 10)
    handle.write(bytes([byte[0] ^ 0xFF]))
PY
if app_env "$db_b" "$work/data-b" "$py" -m app.ops restore check "$work/spoiled.tar" \
  >"$work/spoiled.out"; then
  fail "a manipulated archive passed the check"
fi
grep -qx archive.member_checksum "$work/spoiled.out" || fail "spoiled: $(cat "$work/spoiled.out")"
echo "   $(paste -sd' ' "$work/spoiled.out")"

echo "REHEARSAL OK"
