# to-herd-cats-ai with Docker Compose

The reference deployment: PostgreSQL (`db`) and the app (`app`, `HERD_ROLE=all`:
migrate, then serve, with the live-editing process as a child) in one container. The
app runs as user 10001 with a read-only filesystem (writable: `/tmp` and the volume
`app-data` on `/data`, the attachments) and no capabilities. Only port 8080 is
published; port 9090 (`/health`, `/ready`, `/metrics`, the collab process's internal
API) stays inside the compose network.

Live editing needs `HERD_INTERNAL_TOKEN` (at least 32 characters, `openssl rand -hex
32`). Set `HERD_PUBLIC_URL` to the address browsers use (e.g. `https://wiki.example`
behind a reverse proxy); empty, a WebSocket's Origin must match the host it was sent
to. The reverse proxy must pass WebSocket upgrades on `/collab/`.

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

## Smoke test

`bash smoke.sh` builds the image, starts its own compose project on port 18080 with
throwaway volumes (and a throwaway `.env` if there is none), logs in, checks
`/ready`, the user id and the published ports, creates a page with an attachment (the
files volume), opens the page's live-editing WebSocket with the owner's cookie (the
collab process authenticates it) and without one (closed with 4401), and tears
everything down again. It
ends with `SMOKE OK`. `SMOKE_SKIP_BUILD=1` uses an image built beforehand.

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
| `HERD_HOST_PORT` | no | `8080` | Host port for the app |
| `HERD_FORWARDED_ALLOW_IPS` | no | `127.0.0.1` | Reverse proxies whose `X-Forwarded-For`/`-Proto` are believed (IPs or networks, comma separated) |
| `HERD_COOKIE_SECURE` | no | `false` | Always mark the session cookie `Secure` (it is anyway when the request came over https) |
| `HERD_LOG_LEVEL` | no | `INFO` | Log level |
| `HERD_IMAGE_TAG` | no | `local` | Tag of the `to-herd-cats-ai` image to run |
