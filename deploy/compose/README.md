# to-herd-cats-ai with Docker Compose

The reference deployment: PostgreSQL (`db`) and the app (`app`, `HERD_ROLE=all`:
migrate, then serve, with the worker and the live-editing process) in one container.
The worker hands the events of every change (outbox) to notifications, page
timelines and live updates; in `all` it runs in the API's process and shares its
database pool. The
app runs as user 10001 with a read-only filesystem (writable: `/tmp` and the volume
`app-data` on `/data`, the attachments) and no capabilities. Only port 8080 is
published; port 9090 (`/health`, `/ready`, `/metrics`, the collab process's internal
API) stays inside the compose network.

For a Hostinger VPS (Docker Manager, "Compose from URL") or any server with a Traefik on
80/443, the simpler variant is the root [`docker-compose.yml`](../../docker-compose.yml):
the published image, every secret generated on the first start, HTTPS through Traefik
labels, no published port ([`docs/HOSTINGER.md`](../../docs/HOSTINGER.md)). This
directory stays the build and reference variant.

Live editing needs `HERD_INTERNAL_TOKEN` (at least 32 characters, `openssl rand -hex
32`). Set `HERD_PUBLIC_URL` to the address browsers use (e.g. `https://wiki.example`
behind a reverse proxy); empty, a WebSocket's Origin must match the host it was sent
to. The reverse proxy must pass WebSocket upgrades on `/collab/`.

Live updates (new messages, reactions, activity) reach the browser as Server-Sent
Events on `GET /api/stream`: one response per tab that stays open for hours. The reverse
proxy must not buffer it and must allow a read timeout of at least an hour. The app
sends `X-Accel-Buffering: no` (nginx then passes the stream through unbuffered) and a
comment line every 15 s. nginx, for example:

```nginx
location /api/stream {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 1h;
    proxy_send_timeout 1h;
}
```

A cut stream is no data loss: the browser reconnects after 5 s and reloads what it
shows.

AI and agents (`docs/KI.md`, `docs/AGENTEN.md`) need no extra service: in `all` the
agent runs work in the same process, in `compose.nodes.yml` in `worker`. Their keys go
into the optional file `ai.env` next to `compose.yml` (copy `ai.env.example`; it is
ignored by git): `HERD_SECRET_KEY` (at least 32 characters; needed to store a
connection's key encrypted), `HERD_SECRET_KEY_PREVIOUS` (only during a key rotation),
`HERD_AI_EGRESS_PROXY` (optional proxy for provider calls; `HTTPS_PROXY` and the like
are ignored on purpose) and the provider keys that connections reference as
`env:HERD_AI_<NAME>`. The services that call providers read it whole as their
environment (`app`; in `compose.nodes.yml` `api-a`, `api-b` and `worker`, never
`migrate` or `collab`). Without `ai.env` the app starts as before. The tunables of
runs are ordinary variables in `.env` (table below). To try agents without a provider,
see "KI ausprobieren" in the main README (the local stub provider).

## Start

```bash
cd deploy/compose
cp .env.example .env        # then replace every value, e.g. with `openssl rand -hex 24`
docker compose up -d --build --wait
```

Open <http://127.0.0.1:8080> and log in with `HERD_BOOTSTRAP_ADMIN_EMAIL` and
`HERD_BOOTSTRAP_ADMIN_PASSWORD`. The first owner is created on the first start
only (its password must pass the password rules, or the start stops with "bootstrap
refused"); change the password afterwards in the app.

This reference serves plain http for local trials, so the session cookie is not
`Secure` by default. Behind a TLS reverse proxy, set `HERD_BIND_ADDRESS` /
`HERD_HOST_PORT` to where the proxy connects, `HERD_FORWARDED_ALLOW_IPS` to the
proxy's address (otherwise every client has the proxy's address, in the audit and
for the login limits) and `HERD_COOKIE_SECURE=true`. With an `https://`
`HERD_PUBLIC_URL` the image (production) refuses to start without it.

## Stop

```bash
docker compose down         # keeps the data (volumes db-data and app-data)
docker compose down -v      # deletes the data as well
```

## Backup

The service `backup` (same image, `python -m app.ops backup schedule`) backs up the
database and the attachments together, on `HERD_BACKUP_SCHEDULE` (cron, UTC, default
`30 2 * * *`), into the volume `backups` (`/backups`, mode 0700): one checked archive
`herd-<UTC time>-<version>.tar` per run with its `.manifest.json`, the newest of the
last 7 days, 4 weeks and 6 months kept (`HERD_BACKUP_KEEP_*`). It mounts the
attachments read-only and serves no port; its health check asks whether `/backups` is
there and writable (so `up --wait` waits for it too). With the optional file `backup.env` (copy
`backup.env.example`; ignored by git) it copies every archive offsite with restic
(`HERD_BACKUP_OFFSITE_REPOSITORY`, `HERD_BACKUP_OFFSITE_PASSWORD` and the storage's
credentials, which go to restic alone). It reads `HERD_SECRET_KEY` from `ai.env` only
to name the key's id in the archive.

```bash
docker compose exec backup python -m app.ops backup run     # one now (with retention and offsite)
docker compose exec backup python -m app.ops backup list    # the last runs, their state and offsite
docker compose exec backup python -m app.ops backup verify /backups/<archive>.tar
```

The archives are not encrypted: protect the volume, or rely on the offsite copy
(restic encrypts). Restore only into an empty installation, with the app stopped:
`python -m app.ops restore check <archive>`, then `restore apply <archive>`
(docs/SICHERUNG.md, "Wiederherstellen"; `deploy/scripts/restore-rehearsal.sh` rehearses
it). A one-off `docker compose run -v` mounts the backups as
`-v to-herd-cats-ai_backups:/backups` (the project's volume); a bare `backups` would
mount a new, empty volume of that name. The worker (`app`; `worker` in `compose.nodes.yml`) exports the backups' gauges,
`HerdBackupTooOld` fires after `HERD_BACKUP_ALERT_AFTER_HOURS`.

## Attachments in S3

By default the attachments live on the volume `app-data` (`/data`). With
`HERD_STORAGE=s3` they live in an S3-compatible store instead (AWS S3, SeaweedFS, Ceph,
Garage, ...); `/data` then holds temporary files of uploads, imports and exports only.
`compose.s3.yml` runs SeaweedFS (Apache-2.0) next to the app, creates the bucket
(`HERD_S3_BUCKET`, default `herd`) and switches `app` and `backup` to it; it needs
only `HERD_S3_ACCESS_KEY_ID` and `HERD_S3_SECRET_ACCESS_KEY` in `.env` (`openssl rand
-hex 24` each), which SeaweedFS takes as its one identity:

```bash
docker compose -f compose.yml -f compose.s3.yml up -d --build --wait
docker compose -f compose.yml -f compose.s3.yml exec app python -m app.ops storage check   # "ok s3"
```

For an external store set `HERD_STORAGE=s3`, `HERD_S3_ENDPOINT` (`scheme://host[:port]`,
https outside a private network), `HERD_S3_BUCKET` (it must exist), `HERD_S3_REGION`
and the two keys in `.env`, and optionally `HERD_S3_PREFIX` (several installations in
one bucket). Moving an installation's files from the volume into the store, without
stopping it first (the copy skips what is already there):

```bash
docker compose exec app python -m app.ops storage copy --to s3   # copied N, present M, ...
# set HERD_STORAGE=s3 (and the rest) in .env, then
docker compose up -d                                             # app and backup restart on S3
docker compose exec app python -m app.ops storage copy --to s3   # once more: what came meanwhile
```

`storage copy --to local` moves them back. Backups take the files from the store and a
restore writes them there (docs/SICHERUNG.md, "Anhänge in S3"); `SMOKE_S3=1 bash
smoke.sh` runs the smoke test on `compose.s3.yml`.

## Two API nodes and a worker

`compose.nodes.yml` replaces `app` with the roles one by one, as the Helm chart runs
them: `migrate` (once, then exits), `api-a` and `api-b` (role `api`, published on
`HERD_HOST_PORT` and `HERD_HOST_PORT_B`, default 8081), `worker` (role `worker`, the only
outbox dispatcher) and two collab instances, `collab-a` and `collab-b` (role `collab`,
each announcing its own address in `HERD_COLLAB_ADVERTISE_URL`; the API binds every page
to one of them and relays all of its browsers there, `docs/WIKI.md`). A message written
on one node arrives live on the other through PostgreSQL (`LISTEN`/`NOTIFY`). It is the
acceptance setup for live delivery across nodes, not a production layout (one host, one
database).

Only processes that run a worker (`app` in role `all`, `worker` here) report the outbox
gauges on `/metrics` (`herd_outbox_pending`, `herd_outbox_oldest_pending_seconds`,
`herd_outbox_failed`, `herd_worker_last_pass_timestamp_seconds`); the API nodes do not.
A worker's `/ready` turns not ready when it has made no progress for four handler time
limits. Two settings are not passed through from `.env`; to change them, add them to the
`environment` of the services concerned: `HERD_WORKER_HANDLER_TIMEOUT_SECONDS` (default
30, the time limit of one handler call; worker) and `HERD_LIVE_MAX_LAG_SECONDS` (default
5, how far an API process's live delivery may fall behind before it drops what waits
and tells the browsers to reload; API nodes). See `docs/NACHRICHTEN.md`.

```bash
docker compose -f compose.yml -f compose.nodes.yml up -d --build --wait
docker compose -f compose.yml -f compose.nodes.yml down -v
```

## Smoke test

`bash smoke.sh` builds the image, starts its own compose project on port 18080 with
throwaway volumes (and a throwaway `.env` if there is none), logs in, checks
`/ready`, the user id and the published ports, creates a page with an attachment (the
files volume), opens the page's live-editing WebSocket with the owner's cookie (the
collab process authenticates it) and without one (closed with 4401), checks that the
live collab instances announced themselves (one in role `all`, two with
`compose.nodes.yml`) and that the page is bound to exactly one of them, opens the live
stream (`/api/stream`), posts a message in `#allgemein` and waits for its
`message.created` event, checks that the worker counted the delivery
(`herd_outbox_dispatch_total{handler="publish_live",result="ok"}`), lets a one-off
automation come due 15 s after it was made (an agent on an AI connection to a closed
local port: only the term counts) and checks that its log holds exactly one started term
and the worker counted one (`herd_automation_firings_total{outcome="started"}`), and
makes a backup in the service `backup` (`backup run`, offsite off), waits for the
worker's gauge of it, restores the archive into a second database (`herd_restore`) and
finds the page and its file there, makes a second backup with restic into a repository
in the container's `/tmp` (`offsite=ok`, one snapshot), and tears everything down again. It ends with `SMOKE OK`. `SMOKE_SKIP_BUILD=1` uses an image built
beforehand. `SMOKE_NODES=1` runs the same on `compose.nodes.yml` (project
`to-herd-cats-ai-smoke-nodes`, ports `SMOKE_PORT`/`SMOKE_PORT_B`, default 18080/18081):
`/ready` of both API nodes and the worker, the message posted on node A and received on
a stream of node B. `SMOKE_S3=1` runs it on `compose.s3.yml` (project
`to-herd-cats-ai-smoke-s3`, role `all` only): the attachment must not reach `/data`,
`storage check` answers `ok s3`, the restore writes the files under the prefix
`restored` and `storage copy --to local` reads them back.

## Load measurement

`bash load.sh` starts its own compose project on port 18081 from the image built
beforehand (`LOAD_BUILD=1` builds it), samples `docker stats` idle, warm and under
load (20 clients logging in and listing spaces for 60 s), prints the latencies and
tears everything down. It uses `hey`, else `oha`, else `loadgen.py` (run with the
backend's environment); `LOAD_TOOL`, `LOAD_CONCURRENCY`, `LOAD_DURATION` and
`LOAD_SETTLE` override the defaults. The results go into `docs/STECKBRIEF.md`.

The reference scenario of the Steckbrief (plan M9, decision 20: 200 people at once)
runs against any installation, without Docker, with the backend's environment:

```bash
# people, teams, pages, channels and tickets through the public API (login limits raised)
LOAD_ADMIN_PASSWORD=… LOAD_PASSWORD=… uv run --project ../../backend python loadsetup.py \
  http://127.0.0.1:8080 admin@example.com /tmp/load-state.json
# 200 people with an open stream each and the mix of reads and writes, for 180 s
LOAD_PASSWORD=… uv run --project ../../backend python loadmix.py /tmp/load-state.json 180 \
  --bases http://127.0.0.1:8080,http://127.0.0.1:8081
# CPU, RSS and database connections per process from /proc, while it runs
bash ../scripts/measure-processes.sh sample /tmp/m.tsv load 170 2 api-a=PID api-b=PID worker=PID
bash ../scripts/measure-processes.sh summary /tmp/m.tsv
```

`loadmix.py` prints each endpoint's percentiles, the live delivery delay and the
verdicts against the targets (`loadreport.py`: reads P95 ≤ 300 ms, writes ≤ 500 ms,
live P95 ≤ 2 s, no 5xx).

## Environment

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POSTGRES_PASSWORD` | yes | | Database password; the app gets it as `HERD_DATABASE_PASSWORD`, never inside `HERD_DATABASE_URL` |
| `HERD_BOOTSTRAP_ADMIN_PASSWORD` | yes | | Password of the first owner, used on the first start only; it must pass the password rules (no breached password, no word of the organisation or the address; `docs/ANMELDUNG.md`), or the start stops with exit status 4 |
| `HERD_BOOTSTRAP_ADMIN_EMAIL` | no | `admin@example.com` | Email of the first owner |
| `HERD_BIND_ADDRESS` | no | `127.0.0.1` | Host address port 8080 is published on |
| `HERD_HOST_PORT` | no | `8080` | Host port for the app (node A in `compose.nodes.yml`) |
| `HERD_HOST_PORT_B` | no | `8081` | Host port for node B (`compose.nodes.yml` only) |
| `HERD_FORWARDED_ALLOW_IPS` | no | `127.0.0.1` | Reverse proxies whose `X-Forwarded-For`/`-Proto` are believed (IPs or networks, comma separated) |
| `HERD_COOKIE_SECURE` | no | `false` | Always mark the session cookie `Secure` and name it `__Host-herd_session` (both happen anyway when the request came over https) |
| `HERD_LOG_LEVEL` | no | `INFO` | Log level |
| `HERD_IMAGE_TAG` | no | `local` | Tag of the `to-herd-cats-ai` image to run |
| `HERD_AI_CHECK_TIMEOUT_SECONDS` | no | `20` | Longest wait (s) for a provider when a connection is tested or its models listed (`app`, API nodes) |
| `HERD_AI_PERSONAL_AGENTS_MAX` | no | `5` | Personal agents per person, 0 to 100 (`app`, API nodes) |
| `HERD_AI_AUTOMATIONS_MAX` | no | `20` | Automations per person (not counting done or deleted ones), 0 to 1000 (`app`, API nodes) |
| `HERD_AI_APPROVAL_HOURS` | no | `72` | Hours a run waits for a release or an answer before it ends (`app`, `worker`) |
| `HERD_RUN_CONCURRENCY` | no | `4` | Agent runs one process works on at once, 1 to 64 (`app`, `worker`) |
| `HERD_RUN_LEASE_SECONDS` | no | `30` | A running run's lease (s), at least 3; after a crash another process takes the run up after it (`app`, `worker`) |
| `HERD_MCP_RATE_PER_MINUTE` | no | `120` | Calls one access token may make to `/mcp` per minute, 1 to 10,000, counted across all nodes (`app`, API nodes) |
| `HERD_MCP_ALLOWED_HOSTS` | no | empty | Private hosts external MCP servers may run on: exact host names or private networks (CIDR), comma separated; empty: public addresses only (`app`, API nodes, `worker`) |
| `HERD_MCP_CATALOG_DIR` | no | empty | Directory inside the container with the operator's own catalogue entries (`*.yaml`, see `docs/MCP.md`, "Katalog"); mount it read-only, e.g. `./catalog:/etc/herd/mcp-catalog:ro` in `compose.override.yml`; a broken file is reported and skipped; empty: the shipped entries only (`app`, API nodes) |
| `HERD_MCP_MAX_CALLS_PER_RUN` | no | `20` | Calls one agent run may send to tools of external MCP servers, 1 to 500; the next is refused as the tool's result and nothing is sent (`app`, `worker`) |
| `HERD_BACKUP_SCHEDULE` | no | `30 2 * * *` | When the service `backup` backs up: cron, five fields, UTC (`backup`) |
| `HERD_BACKUP_KEEP_DAILY` | no | `7` | Days whose newest good archive stays, 0 to 1000 (`backup`) |
| `HERD_BACKUP_KEEP_WEEKLY` | no | `4` | Older weeks whose newest good archive stays, 0 to 1000 (`backup`) |
| `HERD_BACKUP_KEEP_MONTHLY` | no | `6` | Older months whose newest good archive stays, 0 to 1000 (`backup`) |
| `HERD_BACKUP_ALERT_AFTER_HOURS` | no | `26` | Age (h) of the last good backup at which `HerdBackupTooOld` fires, exported by the worker (`app`, `worker`) |
| `HERD_BACKUP_UPLOAD_MAX_BYTES` | no | `2147483648` | Largest archive an owner may upload under Verwaltung → Sicherung, in bytes (`app`, API nodes; they and the worker mount the volume `backups` for that page) |
| `HERD_BACKUP_OFFSITE_REPOSITORY`, `HERD_BACKUP_OFFSITE_PASSWORD` | no | empty | restic repository and its password, in `backup.env` (`backup`); empty: no offsite copy |
| `HERD_STORAGE` | no | `local` | Where attachments live: `local` (the volume `app-data`) or `s3` (`app`, API nodes, `worker`, `backup`; `compose.s3.yml` sets it) |
| `HERD_S3_ENDPOINT` | with `s3` | empty | The store's address, `scheme://host[:port]` without a path; requests are path-style and pass the egress guard with this host as the one private target (`compose.s3.yml`: `http://s3:8333`) |
| `HERD_S3_REGION` | no | `us-east-1` | The region the store signs for; most S3-compatible stores accept `us-east-1` |
| `HERD_S3_BUCKET` | with `s3` | empty | The bucket, 3 to 63 of `a-z 0-9 . -`; it must exist (`compose.s3.yml` creates `herd`) |
| `HERD_S3_ACCESS_KEY_ID`, `HERD_S3_SECRET_ACCESS_KEY` | with `s3` | empty | The bucket's keys; the secret key never appears in logs, errors or URLs (only its signature travels). Outside compose `HERD_S3_SECRET_ACCESS_KEY_FILE` can name a file with it instead |
| `HERD_S3_PREFIX` | no | empty | Keys go under this prefix inside the bucket (lower-case segments separated by `/`) |

The AI keys (`HERD_SECRET_KEY`, `HERD_SECRET_KEY_PREVIOUS`, `HERD_AI_EGRESS_PROXY`,
`HERD_AI_<NAME>`) belong in `ai.env`, not in `.env`: they are passed to the containers
as they are, not through `environment`.
