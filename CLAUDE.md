# CLAUDE.md — to-herd-cats-ai (project constitution)

Arbeite nach den Superpowers-Skills (https://github.com/obra/superpowers): brainstorming → writing-plans → subagent-driven-development/executing-plans, TDD, verification-before-completion.

Knowledge & agent cockpit for companies. The authority is the design spec
`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (German). M1 to M4 (plans
`docs/superpowers/plans/2026-11-12-m1-fundament.md`, `…-m2-wiki.md`,
`2026-11-13-m3-nachrichten.md`, `2026-11-13-m4-tickets.md`) are built; the next
milestone is M5 "KI-Grundlage" (spec 14), its plan is not written yet. Present:
identity, groups, spaces, roles, `can()`, audit (M1); the wiki: pages and tree, Markdown
and live editor (`collab/` process, generations), versions, trash, tags, attachments
(`HERD_DATA_DIR`), full-text search, import/export (M2); messaging: event outbox and
worker role, channels, direct messages (2–9 people), threads, mentions, reactions, read
state, page threads with a system timeline, notifications and the activity view, message
search, live delivery over SSE (LISTEN/NOTIFY, several API nodes), audited admin
inspection of DMs (M3); tickets: key `HC-<n>` numbered per org, kinds
epic/story/task/bug with a three-level hierarchy, statuses per space whose category
alone drives logic, assignment, list and "my tickets", board, epic overview, a ticket
thread with a system timeline, ticket cards in messages (client-side, nothing written to
channels), page links, tags, search (M4). Planned, not present: AI and agents (agent
assignees and their ticket rules come in M6), DBOS (M6: the outbox dispatcher is a plain
loop until then), embeddings, S3, collab with Redis. Operations: `README.md`
(Betriebshinweise), `docs/STECKBRIEF.md` (update its measurements each milestone),
`docs/WIKI.md` (wiki use and reverse-proxy operation), `docs/NACHRICHTEN.md` (messaging
use, worker/outbox, SSE behind a proxy), `docs/TICKETS.md` (ticket use and operation).
Demos per milestone in `docs/demo/m*.md` (each executed and logged).

## Stack (present)

- Backend: Python 3.13, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2,
  PostgreSQL only. Tooling: `uv`, `ruff`, `mypy` (strict), `pytest`.
- Frontend (`frontend/`): React 19, TypeScript strict, Vite, Tailwind 4, shadcn/ui
  (Radix), TanStack Router (code-based routes in `src/app/router`) and Query, i18next,
  react-hook-form + zod (schemas derived from `openapi.json`), next-themes. Tooling:
  `npm`, `oxlint`, `prettier`, `vitest` + Testing Library. Wiki view: react-markdown +
  remark-gfm (never rehype-raw); live editor: Tiptap 3, Yjs, `@hocuspocus/provider`.
- Messaging: outbox in `core/outbox.py` (`emit()` in the changing transaction, ids
  only), dispatcher and role `worker` in `app/worker/`, handlers per module
  (`modules/messaging/handlers.py`), live hub `modules/messaging/live.py` (asyncpg
  LISTEN via `core/listen.py`, SSE `GET /api/stream`); frontend one `EventSource` per
  tab (`src/lib/live.ts`), events only invalidate TanStack Query keys.
- Tickets: module `modules/tickets` (statuses, hierarchy, assignment, links, tagging,
  views for board/epics/counts, search part; `base.py` holds what its services share),
  thread kind `thread_ticket` in `modules/messaging`, handlers `ticket_timeline` and
  `notify_on_ticket`; the key prefix is the constant `KEY_PREFIX` (`tickets/models.py`)
  and `TICKET_PREFIX` (`frontend/src/features/tickets/refs.ts`). Frontend
  `features/tickets` (board with `@dnd-kit/core`, no sortable); what to offer comes from
  `ticketAbilities(my_role)`.
- Collab (`collab/`, Node 22, ESM): Hocuspocus server, talks only to the API's
  `/internal/collab/*` (token); `collab/schema.mjs` is the one editor schema shared with
  the frontend.
- Browser tests (`e2e/`, Node 22, ESM): Playwright (`@playwright/test`), live editing,
  messaging and tickets in the real app (role all, worker included) on a throwaway
  database; a CI job of its own. Helpers per area (`tests/helpers.mjs`,
  `messaging-helpers.mjs`, `tickets-helpers.mjs`); wait on concrete elements or
  responses (`openLive()` waits for the page's `/api/stream`), never fixed sleeps.
- Dependencies (runtime): only MIT, MIT-0, BSD-2-Clause, BSD-3-Clause, 0BSD, Apache-2.0,
  ISC, PostgreSQL, PSF-2.0, Python-2.0, MPL-2.0 (unmodified use), Unlicense, CC0-1.0,
  BlueOak-1.0.0 or OFL-1.1 (fonts). CI checks it (`backend/scripts/check_licenses.py`).

## Hard rules

1. Postgres only. No SQLite code paths. Tests run against a real Postgres (`herd_test`).
2. `org_id` on every domain table; every query is scoped by the actor's org.
3. Layers: `router → service → repository`. Routers validate and translate; services
   own rules; repositories own SQL. No SQL in services, no rules in routers, no
   business logic in React components.
4. Files ≤ ~300 lines; split by responsibility.
5. Every persisted field is read by a code path covered by a test. No fields "for later".
6. Every list endpoint is paginated (`limit` ≤ 100, `cursor`); every write that can
   race uses a `version` column and answers 409 on conflict.
7. Error shape: `{"error": {"code": "<area.reason>", "message": "...", "trace_id": "<32 hex>"}}`.
8. Service id `to-herd-cats-ai` (log field `service`, `OTEL_SERVICE_NAME`, image, chart).
   Env vars use the `HERD_` prefix; ports `HERD_PUBLIC_PORT=8080`, `HERD_INTERNAL_PORT=9090`.
9. Logs never contain header values, cookies, passwords or request bodies.
10. Secrets never in plaintext columns, URLs or logs.
11. Every user-facing string goes through i18n (`de` default, `en` complete), semantic
    keys (`spaces.create.title`).
12. The frontend decides what to show only from `/auth/me` `permissions` and a space's
    `my_role`, never from a role name. API calls live in feature `queries.ts` hooks.

## Commands

```bash
cd backend && uv sync
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy app scripts
cd backend && uv export --frozen --no-dev --no-hashes --no-emit-project > /tmp/runtime.txt \
  && uv run python scripts/check_licenses.py python /tmp/runtime.txt \
  && uv run python scripts/check_licenses.py npm ../frontend/package-lock.json \
  && uv run python scripts/check_licenses.py npm ../collab/package-lock.json \
  && uv run python scripts/check_licenses.py npm ../e2e/package-lock.json
```

```bash
cd frontend && npm ci
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && node scripts/check-i18n.mjs
cd frontend && npm run generate:api   # after API changes: openapi.json + src/lib/api-types.ts
cd frontend && npm run check:api      # fails if those files are stale
cd frontend && npm run dev            # proxies /api and /collab to http://localhost:8080
```

```bash
cd collab && npm ci && npm run lint && npm test   # live-editing process (Hocuspocus, node 22)
cd collab && npm run test:integration             # real API on a throwaway database (psql, uv)
```

```bash
# Browser tests of live editing and messaging (Playwright; own package, `@playwright/test`
# only): the built SPA and the real app in role all (worker included) on a throwaway
# database (psql, uv). HERD_E2E_PORT moves the ports; `--output <dir>` keeps results apart.
cd frontend && npm run build
cd e2e && npm ci && npx playwright install chromium && npx playwright test
# With a Chromium already installed: PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chrome
```

```bash
docker build -t to-herd-cats-ai:local .                 # the image (SPA + API + collab, uid 10001)
bash deploy/compose/smoke.sh                            # compose reference: build, start, check, tear down
SMOKE_NODES=1 bash deploy/compose/smoke.sh              # compose.nodes.yml: api-a, api-b, worker; message A → SSE B
                                                        # (both modes also: a ticket's system entries from the worker)
bash deploy/compose/load.sh                             # docker stats idle/warm/load + latency (Steckbrief)
```

```bash
bash deploy/helm/scripts/check-chart-version.sh         # chart version = appVersion = pyproject version
bash deploy/helm/scripts/check-chart-rules.sh           # chart behaviour (HELM="docker run ... alpine/helm" works too)
helm lint --strict deploy/helm/to-herd-cats-ai          # also with -f deploy/helm/to-herd-cats-ai/ci/*-values.yaml
helm template t deploy/helm/to-herd-cats-ai | kubeconform -strict -summary
promtool test rules deploy/helm/to-herd-cats-ai/tests/rules-test.yaml
```

CI (`.github/workflows/ci.yml`, pull requests and pushes to `main`; tags through
`release.yml`) runs all of the above plus `pip-audit`, `npm audit --audit-level=high`,
the image build, `smoke.sh` (single and `SMOKE_NODES=1`) and Trivy. A tag `vX.Y.Z`
(`release.yml`) publishes `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z`/`:X.Y` and the chart
as OCI under `ghcr.io/<owner>/charts`; tag, pyproject and chart versions must match.

The backend serves the built SPA when `HERD_STATIC_DIR` points at `frontend/dist`
(`backend/app/web/spa.py`: CSP, cache headers, index.html fallback outside `/api`).

Tests need Postgres; `HERD_TEST_DATABASE_URL` defaults to
`postgresql+asyncpg://herd:herd@localhost:5433/herd_test`. Backend tests create a
fresh schema per session and roll back per test. The two-node live test
(`tests/test_live_two_nodes.py`) creates a scratch database with the test URL's role:
locally the role `herd` needs CREATEDB (`ALTER ROLE herd CREATEDB` as a superuser; in
CI it is the superuser).

```bash
# Demo data on a fresh test installation (worker must run; passwords from the env only)
cd backend && HERD_DEMO_ADMIN_PASSWORD=… HERD_DEMO_PASSWORD=… \
  uv run python -m scripts.demo_seed --base http://127.0.0.1:8080 --admin admin@example.com
```

## Conventions

- Identifiers, comments, docstrings, commit messages in English.
- Commit messages: `<area>: <imperative summary>`; ported code adds a trailer
  `Ported-from: to-herd-cats-ai@<sha>:<path>`.
- Alembic: one migration per slice, never edited after merge.
- Alembic: migrations must stay backward compatible with the previous release (expand
  first, contract in a later release). `/ready` stays ready when the database is at a
  revision this code does not know (a newer release migrated before its pods rolled
  out); it is not ready only with no revision or a known older one.
- Outbox handlers: register with `@handler(...)` from `app.worker.registry` in the
  module's `handlers.py`, and import that module in `backend/app/worker/handlers.py` —
  the worker knows only handlers whose module it imported. Handlers run at least once
  per event, in the delivery's transaction: idempotent, never commit themselves.
- Message content never goes into logs, outbox payloads, `NOTIFY` payloads (< 4,000
  bytes) or metric labels; live events carry ids only. The same holds for ticket titles
  and descriptions: ticket events carry ids, field names and old/new ids or enum values.
- Tickets: logic reads a status's category, never its name. A ticket one may not see
  answers exactly like a free number (404 `ticket.not_found`, same shape and time
  class); lists, board, counts and search filter visible spaces in SQL. Nothing about a
  ticket is ever written into a channel or DM (acceptance M4; `e2e/tests/tickets-quiet`).
- Demo data: `backend/scripts/demo_seed.py` (+ `demo_tickets.py`, shared API helpers in
  `demo_api.py`) goes through the public API only; extend it and its test with each
  milestone.
- e2e on the board: dnd-kit's keyboard sensor listens for keys only after a timer of its
  own; after picking a card up, wait one turn of the page's timers before an arrow key.

## Definition of done (per task)

Failing test first → minimal implementation → tests green → ruff/mypy clean →
docs updated if behaviour changed → commit.
