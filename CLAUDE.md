# CLAUDE.md — to-herd-cats-ai (project constitution)

Arbeite nach den Superpowers-Skills (https://github.com/obra/superpowers): brainstorming → writing-plans → subagent-driven-development/executing-plans, TDD, verification-before-completion.

Knowledge & agent cockpit for companies. The authority is the design spec
`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (German). M1 to M4, M4b,
M5 Tasks 1–7, M6, M7 and M8 (plans `docs/superpowers/plans/2026-11-12-m1-fundament.md`,
`…-m2-wiki.md`, `2026-11-13-m3-nachrichten.md`, `2026-11-13-m4-tickets.md`,
`2026-11-13-m4b-boards-sprints.md`, `2026-11-13-m5-ki-grundlage.md`,
`2026-11-14-m6-agenten-als-mitarbeiter.md`, `2026-11-14-m7-automatisierung.md`,
`2026-11-15-m8-oeffnung.md`) are built; next are M5 Tasks 8–12 and M9 (spec 14). Present: identity, groups, spaces, roles,
`can()`, audit (M1); the wiki: pages and tree, Markdown and live editor (`collab/`
process, generations), versions, trash, tags, attachments (`HERD_DATA_DIR`), full-text
search, import/export (M2); messaging: event outbox and worker role, channels, direct
messages (2–9 people), threads, mentions, reactions, read state, page threads with a
system timeline, notifications and the activity view, message search, live delivery over
SSE (LISTEN/NOTIFY, several API nodes), audited admin inspection of DMs (M3); tickets:
key `HC-<n>` numbered per org, kinds epic/story/task/bug with a three-level hierarchy,
statuses per space whose category alone drives logic, assignment, list and "my tickets",
board, epic overview, a ticket thread with a system timeline, ticket cards in messages
(client-side, nothing written to channels), page links, tags, search (M4); sprints per
space (at most one active; closing moves the unfinished to the next sprint or the backlog
and keeps a tally), backlog, "my board" across spaces by status category, the board's
daily view grouped by person with what changed status since the last working day (UTC,
Monday to Friday) (M4b); AI connections (OpenAI protocol, `env:`/`enc:` secrets, SSRF
guard, optional egress proxy), model assignment and the derived `ai.use`, usage per
call, AI policy per space and the `no_ai` lock, agents as principals with a run loop in
the worker (M5 Tasks 1–7); agents as colleagues: levels 1–3 and a 22-tool catalog with
per-agent grants, the read and write scope per place, mention/ticket/handover triggers,
one open run per thread, approvals and questions, the run journal with replay after a
lost worker, run view and cancel, page and skill proposals, skills (SKILL.md only),
memory pages per agent and space, personal agents (M6); automations: one-off,
recurring (cron in the automation's time zone), heartbeat and event-rule kinds fired
exactly once by the worker's due loop (no DBOS, spec E10), a log of every term, pausing
and take-over, budgets per org/person/agent and UTC day, the wiki's review interval and
its daily pass (M7); opening over MCP: access tokens (personal and agent, hashed,
shown once) and the right `mcp.use`, the stateless endpoint `/mcp` serving the
catalog's tools within the person's rights, the token's spaces and the AI policy,
external agents with ticket pick-up, external MCP servers with per-tool approval and
fingerprints (write tools level 4, always released), connectors (bearer/header, OAuth
with PKCE; shared or personal), the catalogue (GitHub, GitLab, operator files), a cap
on external calls per run (M8). Planned, not present: embeddings, hybrid search,
Docling conversion (M5 Tasks 8–11), S3, collab with Redis, OIDC (M9). Operations: `README.md` (Betriebshinweise),
`docs/STECKBRIEF.md` (update its measurements each milestone), `docs/WIKI.md` (wiki use
and reverse-proxy operation), `docs/NACHRICHTEN.md` (messaging use, worker/outbox, SSE
behind a proxy), `docs/TICKETS.md` (ticket use and operation, sprints and the new
boards), `docs/KI.md` (connections, keys, egress, assignment, usage, policy, the stub),
`docs/AGENTEN.md` (agents and automations: use, admin, worker runs and the due loop,
limits, metrics and alerts), `docs/MCP.md` (tokens, `/mcp` with Claude Code and Codex,
external agents, servers, connectors, catalogue, operation, metrics and alerts).
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
  views for board/epics/counts, search part; `base.py` holds what its services share;
  M4b: `sprints.py`, `my_board.py`, `daily.py` with their repositories, routers and
  schemas; `work_item.status_changed_at` is set by a trigger),
  thread kind `thread_ticket` in `modules/messaging`, handlers `ticket_timeline` and
  `notify_on_ticket`; the key prefix is the constant `KEY_PREFIX` (`tickets/models.py`)
  and `TICKET_PREFIX` (`frontend/src/features/tickets/refs.ts`). Frontend
  `features/tickets` (board with `@dnd-kit/core`, no sortable; `sprints/`, `my-board/`,
  `daily/`); what to offer comes from `ticketAbilities(my_role)`. Sprint events go live
  as one SSE name, `sprint.changed` (`space_id`, `sprint_id`).
- AI (`modules/ai`): connections (`provider.py` makes the provider calls, through
  `core/egress.py` or `HERD_AI_EGRESS_PROXY`), secrets (`core/secrets.py`: `env:HERD_AI_*`
  or `enc:` under `HERD_SECRET_KEY`; `scripts/rotate_secrets.py`), assignments and the
  derived `ai.use`, usage per call (`usage_record`), policy (`policy.py`,
  `policy_filters.py`: what AI may read, filtered in SQL with the rights), budgets
  (`budgets.py` checks before every model call, `budget_repository.py` sums the UTC
  day's usage).
- Agents (`modules/agents`): agents and personal agents, the read and write scope per
  place (`scope.py`), triggers and places (`triggers.py`, `place.py`), runs (`runs.py`,
  `executor.py`, `step_host.py`, journal `journal.py`, cancel and waiting
  `control.py`), the tool catalog and tools (`toolbox/`, grants `grants.py`), approvals
  and questions (`approvals/`), memory (`memory.py`), run view (`run_view.py`), gauges
  (`gauge_repository.py`); a step's checks (`step_checks.py`) and an external tool's
  call in two transactions around the send (`external_step.py`, metric and cap:
  `external_metrics.py`, `external_repository.py`); external agents (`agent.kind`,
  no runs). The worker's run loop is `app/worker/runs.py` (claims with
  `SKIP LOCKED` and a lease, renewed every third).
- Automations (`modules/automations`): terms and schedules (`term.py`, `terms.py`,
  `schedule.py`, `heartbeat_terms.py`), firing one term (`firing.py`, `runs.py`),
  heartbeats, event rules (`event_rules.py`, handler in `handlers.py`), pausing and
  take-over (`pausing.py`, `takeover.py`, `standing.py`), `sight.py` (who sees one),
  gauges and retention SQL (`metrics.py`, `upkeep_repository.py`). The due loop is
  `app/worker/due.py` (`SKIP LOCKED`, one transaction per term, unique
  `(automation_id, due_at)`; it also runs the wiki's review pass,
  `modules/wiki/review_pass.py`, and the log's retention). Time comes from
  `core/clock.py`. Frontend `features/automations`.
- MCP (M8): `app/mcp/` is the only code that imports the MCP SDK (`mcp`, `mcp_types`;
  `tests/test_mcp_imports.py`): the endpoint (`endpoint.py`: Origin, token, POST only;
  `server.py`: one stateless SDK server per request, JSON answers), the client
  (`client.py`) and the shipped catalogue files (`catalog/*.yaml`). Modules: `tokens`
  (hash, resolve to an actor per call, reach in SQL, `mcp.use`), `mcp_tools` (what
  `/mcp` offers per token, one call, `mcp_call`), `connectors` (stored access; plaintext
  only in `credentials.headers_for`), `oauth` (clients, flow, renewal under a row
  lock), `mcp_servers` (servers, tools, fingerprints, `calls.py`), `mcp_catalog`.
  Egress allow-list for private hosts: `core/egress_allowance.py`. Stubs:
  `tests/support/mcp_stub.py`, `oauth_stub.py`. Frontend `features/{tokens,mcp}` and
  the agents' external tools.
- Runtime (`app/runtime/`): the only code that imports Pydantic AI (`loop.py` drives one
  step, `tools.py`, `models.py`, `context.py`; `untrusted.py` frames tool results);
  `tests/test_runtime_imports.py` enforces it.
- Proposals (`modules/proposals`): page proposals by agents, three-way merge on accept,
  visible with `page.edit` in the space. Skills (`modules/skills`): SKILL.md skills
  (org-wide or per space, versions, import/export as SKILL.md or ZIP), assignment to
  agents, skill proposals (`sight.py` is the one visibility rule for routes and
  activity). Frontend `features/{ai,agents,runs,approvals,proposals,skills}`.
- Collab (`collab/`, Node 22, ESM): Hocuspocus server, talks only to the API's
  `/internal/collab/*` (token); `collab/schema.mjs` is the one editor schema shared with
  the frontend.
- Browser tests (`e2e/`, Node 22, ESM): Playwright (`@playwright/test`), live editing,
  messaging, tickets, agents, automations and MCP in the real app (role all, worker
  included) on a throwaway database, with the OpenAI stub
  (`backend/tests/support/openai_stub.py`) and the MCP and OAuth stubs (over https)
  started by `global-setup.mjs`; a CI job of its own. Helpers per area
  (`tests/helpers.mjs`, `messaging-helpers.mjs`, `live-typing-helpers.mjs`,
  `tickets-helpers.mjs`, `ai-helpers.mjs`, `agents-helpers.mjs`,
  `automations-helpers.mjs`, `mcp-helpers.mjs`); wait on concrete elements or
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
# The app runs under the e2e clock (`python -m tests.support.e2e_clock` in place of
# `app.launch`; a test moves time with `POST /clock` on the control port); never in production.
```

```bash
docker build -t to-herd-cats-ai:local .                 # the image (SPA + API + collab, uid 10001)
bash deploy/compose/smoke.sh                            # compose reference: build, start, check, tear down
SMOKE_NODES=1 bash deploy/compose/smoke.sh              # compose.nodes.yml: api-a, api-b, worker; message A → SSE B
                                                        # (both modes also: a ticket's system entries from the worker
                                                        # and a one-off automation fired exactly once by the due loop)
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
  A ticket's sprint belongs to its space (foreign key `(sprint_id, space_id)`); lock
  sprints before tickets.
- Demo data: `backend/scripts/demo_seed.py` (+ `demo_tickets.py`, `demo_sprints.py`,
  `demo_messaging.py`, `demo_ai.py`, `demo_ai_model.py`, `demo_automations.py`,
  `demo_mcp.py`, shared API helpers in `demo_api.py`) goes through the public API only;
  extend it and its test with each milestone.
- AI and agents:
  - Only `app/runtime/` imports Pydantic AI (and DBOS, should it ever come); nothing
    else does.
  - A write tool's effect and its `run_event` commit in one transaction; replay after a
    lost worker reads the journal and never calls the provider or a tool again for a
    committed step.
  - Tool results, skills, memory pages and anything an agent reads are untrusted data,
    framed `<untrusted …>`; they never grant a tool, a level or an approval. The host
    checks grants, rights, policy and `no_ai` before every model and tool call.
  - Content (prompts, answers, tool arguments and results, skill and memory text) never
    goes into logs, outbox payloads, `NOTIFY` or metric labels: ids, counts and codes
    only. It lives in `run_event` and the messages.
  - The read scope of a run is the asker's rights ∩ the agent's memberships and open
    spaces ∩ the audience of the place; the write scope is the place's space (in a DM
    alone with the agent, no limit beyond rights). `core/access.py` applies both to any
    actor without knowing agents. Nothing read in a run goes into a space whose
    audience may not see it.
  - Hiding: whatever a caller may not see answers exactly like an unknown id (404 with
    the area's `not_found` code); people without `ai.use` see no agents, runs, skills or
    proposals; run results from spaces a reader cannot read come redacted.
  - New settings with the `HERD_AI_` prefix are refused as `env:` key references
    automatically (`RESERVED_NAMES`); add every new AI setting to Compose, the chart and
    `docs/AGENTEN.md`.
- MCP (M8):
  - Tokens: only the SHA-256 of 256 random bits is stored (`herd_pat_`/`herd_agt_`); the
    clear text is shown once and never logged, audited, put in a URL or an error. Every
    failure answers the same 401 `token.invalid`; rights are resolved on every call.
  - `/mcp` answers like the REST API would for an unknown id: never drafts, `no_ai`
    content, spaces the policy for its data location excludes, or anything outside the
    token's scope; no tool that needs a run or a release, no `assign_ticket`.
  - What an external server returns (results, descriptions) is untrusted, framed and
    cut; it never grants anything. A tool is callable only with its approved
    fingerprint; a changed one is blocked until re-approved; the catalogue only
    suggests. Write tools are level 4 and wait for the asker's release of the exact
    arguments; a lost worker never sends a call again (`external_outcome_unknown`).
  - A result through the asker's own connector marks the run (`Reads.personal`, like
    the draft mark): it writes nothing others may read.
  - Settings use the `HERD_MCP_` prefix (never `HERD_AI_`); add each to both Compose
    files, the chart (values, schema, chart rule) and `docs/MCP.md`.
- Automations:
  - Code that schedules reads the time from a `Clock` (`core/clock.py`), never
    `datetime.now()`; tests pass a `SettableClock` (`tests/support/clock.py`) and never
    sleep for a term to come due.
  - One transaction per term: the term's log row, its run (or skip), the next due time
    and its events commit together, or not at all.
  - Events written inside a run's step carry the run (`caused_by(run_id)`, column
    `event_outbox.run_id`); event rules read it for chain depth and the own-effect
    rule.
  - `automations/sight.py` is the one rule for who sees an automation (routes, activity,
    live events); do not restate it.
  - A handler's `after_commit` actions (metrics, live notes) run once its lane batch has
    committed, never for a rolled-back savepoint.
- Test databases: backend tests drop and recreate every table per session, so never run
  two pytest sessions on one database; parallel work uses its own database (`createdb`,
  then `HERD_TEST_DATABASE_URL`).
- e2e on the board: dnd-kit's keyboard sensor listens for keys only after a timer of its
  own; after picking a card up, wait one turn of the page's timers before an arrow key.

## Definition of done (per task)

Failing test first → minimal implementation → tests green → ruff/mypy clean →
docs updated if behaviour changed → commit.
