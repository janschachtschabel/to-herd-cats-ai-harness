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
only; change the password afterwards in the app.

This reference serves plain http for local trials, so the session cookie is not
`Secure` by default. Behind a TLS reverse proxy, set `HERD_BIND_ADDRESS` /
`HERD_HOST_PORT` to where the proxy connects, `HERD_FORWARDED_ALLOW_IPS` to the
proxy's address (otherwise every client has the proxy's address, in the audit and
for the login limits) and `HERD_COOKIE_SECURE=true`.

## Stop

```bash
docker compose down         # keeps the data (volumes db-data and app-data)
docker compose down -v      # deletes the data as well
```

## Backup

The data is the PostgreSQL database and the attachments on `app-data`; back up both,
for example:

```bash
docker compose exec -T db pg_dump -U herd -Fc herd > herd-$(date +%F).dump
docker compose exec -T app tar -C /data -c attachments > herd-files-$(date +%F).tar
```

Restore only into an empty database (a fresh installation, before its first start:
`docker compose up -d --wait db`, then `docker compose exec -T db pg_restore -U herd
-d herd < herd.dump`). The attachments go back with `docker compose exec -T app tar -C
/data -x < herd-files.tar`. Test the restore regularly.

## Two API nodes and a worker

`compose.nodes.yml` replaces `app` with the roles one by one, as the Helm chart runs
them: `migrate` (once, then exits), `api-a` and `api-b` (role `api`, published on
`HERD_HOST_PORT` and `HERD_HOST_PORT_B`, default 8081), `worker` (role `worker`, the only
outbox dispatcher) and `collab` (role `collab`). A message written on one node arrives
live on the other through PostgreSQL (`LISTEN`/`NOTIFY`). It is the acceptance setup for
live delivery across nodes, not a production layout (one host, one database).

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
collab process authenticates it) and without one (closed with 4401), opens the live
stream (`/api/stream`), posts a message in `#allgemein` and waits for its
`message.created` event, checks that the worker counted the delivery
(`herd_outbox_dispatch_total{handler="publish_live",result="ok"}`), lets a one-off
automation come due 15 s after it was made (an agent on an AI connection to a closed
local port: only the term counts) and checks that its log holds exactly one started term
and the worker counted one (`herd_automation_firings_total{outcome="started"}`), and
tears everything down again. It ends with `SMOKE OK`. `SMOKE_SKIP_BUILD=1` uses an image built
beforehand. `SMOKE_NODES=1` runs the same on `compose.nodes.yml` (project
`to-herd-cats-ai-smoke-nodes`, ports `SMOKE_PORT`/`SMOKE_PORT_B`, default 18080/18081):
`/ready` of both API nodes and the worker, the message posted on node A and received on
a stream of node B.

## Load measurement

`bash load.sh` starts its own compose project on port 18081 from the image built
beforehand (`LOAD_BUILD=1` builds it), samples `docker stats` idle, warm and under
load (20 clients logging in and listing spaces for 60 s), prints the latencies and
tears everything down. It uses `hey`, else `oha`, else `loadgen.py` (run with the
backend's environment); `LOAD_TOOL`, `LOAD_CONCURRENCY`, `LOAD_DURATION` and
`LOAD_SETTLE` override the defaults. The results go into `docs/STECKBRIEF.md`.

## Environment

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POSTGRES_PASSWORD` | yes | | Database password; the app gets it as `HERD_DATABASE_PASSWORD`, never inside `HERD_DATABASE_URL` |
| `HERD_BOOTSTRAP_ADMIN_PASSWORD` | yes | | Password of the first owner, used on the first start only |
| `HERD_BOOTSTRAP_ADMIN_EMAIL` | no | `admin@example.com` | Email of the first owner |
| `HERD_BIND_ADDRESS` | no | `127.0.0.1` | Host address port 8080 is published on |
| `HERD_HOST_PORT` | no | `8080` | Host port for the app (node A in `compose.nodes.yml`) |
| `HERD_HOST_PORT_B` | no | `8081` | Host port for node B (`compose.nodes.yml` only) |
| `HERD_FORWARDED_ALLOW_IPS` | no | `127.0.0.1` | Reverse proxies whose `X-Forwarded-For`/`-Proto` are believed (IPs or networks, comma separated) |
| `HERD_COOKIE_SECURE` | no | `false` | Always mark the session cookie `Secure` (it is anyway when the request came over https) |
| `HERD_LOG_LEVEL` | no | `INFO` | Log level |
| `HERD_IMAGE_TAG` | no | `local` | Tag of the `to-herd-cats-ai` image to run |
| `HERD_AI_CHECK_TIMEOUT_SECONDS` | no | `20` | Longest wait (s) for a provider when a connection is tested or its models listed (`app`, API nodes) |
| `HERD_AI_PERSONAL_AGENTS_MAX` | no | `5` | Personal agents per person, 0 to 100 (`app`, API nodes) |
| `HERD_AI_AUTOMATIONS_MAX` | no | `20` | Automations per person (not counting done or deleted ones), 0 to 1000 (`app`, API nodes) |
| `HERD_AI_APPROVAL_HOURS` | no | `72` | Hours a run waits for a release or an answer before it ends (`app`, `worker`) |
| `HERD_RUN_CONCURRENCY` | no | `4` | Agent runs one process works on at once, 1 to 64 (`app`, `worker`) |
| `HERD_RUN_LEASE_SECONDS` | no | `30` | A running run's lease (s), at least 3; after a crash another process takes the run up after it (`app`, `worker`) |

The AI keys (`HERD_SECRET_KEY`, `HERD_SECRET_KEY_PREVIOUS`, `HERD_AI_EGRESS_PROXY`,
`HERD_AI_<NAME>`) belong in `ai.env`, not in `.env`: they are passed to the containers
as they are, not through `environment`.
