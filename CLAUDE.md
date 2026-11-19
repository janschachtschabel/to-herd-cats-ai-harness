# CLAUDE.md — to-herd-cats-ai (project constitution)

Arbeite nach den Superpowers-Skills (https://github.com/obra/superpowers): brainstorming → writing-plans → subagent-driven-development/executing-plans, TDD, verification-before-completion.

Knowledge & agent cockpit for companies. The authority is the design spec
`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (German). M1 to M4, M4b,
M5 Tasks 1–7, M6, M7 and M8 (plans `docs/superpowers/plans/2026-11-12-m1-fundament.md`,
`…-m2-wiki.md`, `2026-11-13-m3-nachrichten.md`, `2026-11-13-m4-tickets.md`,
`2026-11-13-m4b-boards-sprints.md`, `2026-11-13-m5-ki-grundlage.md`,
`2026-11-14-m6-agenten-als-mitarbeiter.md`, `2026-11-14-m7-automatisierung.md`,
`2026-11-15-m8-oeffnung.md`) and M9a (`2026-11-15-m9-produktion.md`, Tasks 1–11 and 5b)
are built and make v1.0.0 (version 1.0.0, `backend/alembic/RELEASED` = `9e4b6d2f8a17`,
release note `docs/RELEASE-1.0.0.md`; the tag is not published: Jan tags only when the
whole app is finished); M9b (Tasks 12 to 19, closed by Task 17: docs, Steckbrief, spec,
demo `docs/demo/m9.md`) and M10 Tasks 1 and 2 (`2026-11-18-m10-kalender.md`) are built
after it, collected for operators of 1.0.0 builds in `docs/RELEASE-NEXT.md` (unreleased;
versions and `RELEASED` unchanged); next are M10 from Task 3a and M5 Tasks 8–12.
Present: identity, groups, spaces, roles, `can()`, audit (M1); the wiki: pages and tree, Markdown and live editor (`collab/`
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
on external calls per run (M8); production (M9a): backup archives (database and files
from one snapshot) with verify, schedule, grandfather-father-son retention, restic
offsite and alerts, restore into an empty installation with a rehearsal; OIDC sign-in
(Google preset, generic providers, linking) with self-registration only through a
provider that vouches for the address and only into an account that waits for an
admin's approval; collab grants instead of the session
cookie; a retention rule for every table; the full chart (HPA, PDB, backup CronJob);
the ASVS 5.0 L2 check; the 200-person load test. Built after v1.0.0 (M9b): maintenance
mode and restore into a running installation from the command line (Task 12); backups
in the administration with the maintenance page (Task 13); attachments in
S3-compatible storage (Task 14: own SigV4 client, copy between storages, backups
through the store); several collab instances, each page bound to one in Postgres, no
Redis (Task 15); optional TOTP for every password account (Task 16: profile setup,
two-step sign-in, recovery codes, admin reset, second factor for new access tokens);
the ASVS gaps J7–J14 (Task 18: idle timeout, own sessions, re-authentication before
linking, write limits, optional virus scan, database TLS, internal token rotation, OAuth
callback per app with `iss`, optional separate database roles). Calendar (M10, so
far): calendars per space with their rights and defaults (Task 1); time zones and
RFC 5545 recurrence as pure functions on `python-dateutil` (Task 2).
Planned, not present: embeddings, hybrid search, Docling conversion (M5 Tasks 8–11).
Operations: `README.md` (Betriebshinweise),
`docs/STECKBRIEF.md` (update its measurements each milestone), `docs/WIKI.md` (wiki use
and reverse-proxy operation), `docs/NACHRICHTEN.md` (messaging use, worker/outbox, SSE
behind a proxy), `docs/TICKETS.md` (ticket use and operation, sprints and the new
boards), `docs/KALENDER.md` (calendars, defaults, rights; grows with M10),
`docs/KI.md` (connections, keys, egress, assignment, usage, policy, the stub),
`docs/AGENTEN.md` (agents and automations: use, admin, worker runs and the due loop,
limits, metrics and alerts), `docs/MCP.md` (tokens, `/mcp` with Claude Code and Codex,
external agents, servers, connectors, catalogue, operation, metrics and alerts),
`docs/SICHERUNG.md` (backup, restore, retention), `docs/HOSTINGER.md` (install on a
Hostinger VPS, the simplest path), `docs/ANMELDUNG.md` (password and
OIDC sign-in, approval), `docs/SICHERHEIT.md` (ASVS rows; `tests/test_security_doc.py`),
`docs/RELEASE-<version>.md` (release notes, linked from the README; `docs/RELEASE-NEXT.md`
collects what comes after the last one until the next tag, then becomes its note).
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
- Calendars (M10, `modules/calendars`): every calendar belongs to a space (`calendar`,
  at most 20 not archived per space, 409 `calendar.limit`; archived = 404 for
  everyone), rights `calendar.read` (viewer), `calendar.write` (editor),
  `calendar.moderate` (moderator), `calendar.manage` (admins) and the derived
  `calendar.sync` (active non-guests while `calendar_setting.sync_enabled` is on,
  `calendars/standing.py`; `PUT /api/admin/calendar-settings`, audited). Defaults (one
  in the own personal space, one in „Allgemein“) are made by the first list call of a
  person acting for herself (`calendars/defaults.py`, space row lock plus a partial
  unique index); they have no stored name (`name` null, the frontend words them:
  `features/calendars/name.ts`), count toward the 20 and are never archived (409
  `calendar.default_kept`). Calendar lists filter with `access.member_space_ids`
  (`visible_space_ids` without the admin branch, C1): an admin reaches another team or
  personal space's calendars only by naming the space (`access.require`, audited),
  never in her own lists. The calendar routers include `auth/write_limits.COUNTED`
  (the admin switch, a setting, is exempt in `tests/test_write_limit_routes.py`); a new
  calendar content route does too.
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
  `modules/wiki/review_pass.py`, the log's retention and `mcp_call`'s after 90 days). Time comes from
  `core/clock.py`. Frontend `features/automations`.
- Calendar time (M10 Task 2, `modules/calendars`, pure): `zones.py` (IANA names only;
  `localise` moves a gap's wall time on by the gap and takes the first of a doubled
  one), `recurrence_rule.py` (the RRULE subset: `DAILY` up, `COUNT` ≤ 5,000, ASCII
  digits, codes `event.rrule_invalid`/`event.rrule_unsupported`, UNTIL outside
  1900–2399 `event.time_out_of_range`; the canonical text reads back as itself),
  `recurrence_series.py` (`Series`, `Occurrence`, `bounded`), `recurrence.py` (the only
  code that imports `python-dateutil`, `tests/test_calendar_imports.py` scans `app` and
  `scripts`; `recurrence_jump.py` may too). A `Series` is wall times in its zone (start,
  RDATE, EXDATE, RECURRENCE-ID; all-day: 00:00 UTC, no zone); DTSTART is always the
  first occurrence; series lie in 1900–2399 and `dateutil` runs 7,600 years ahead so its
  scan ends at our 2399; an endless rule jumps whole periods to the window
  (`recurrence_jump.jump`). Where `dateutil` departs from RFC 5545 our layer corrects it
  (BYDAY mixing plain and numbered days is one list; a weekly BYSETPOS counts in the
  whole first week); `test_calendar_recurrence_oracle.py` compares with a brute-force
  RFC expander that does not use `dateutil`. Two occurrences at one instant show once
  (the earlier id); a gap occurrence's id is the rule's wall time
  (`recurrence_id_at` maps an instant back). Every write path calls `check_series`
  (refuses a rule that never matches).
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
  `/internal/collab/*` (internal token plus, per connection, a grant `herd_cg_…` bound
  to one page and generation, `wiki/collab_grants.py`; the session cookie never leaves
  the API); `collab/schema.mjs` is the one editor schema shared with the frontend.
  Several instances (M9b Task 15, `wiki/collab_instances.py`,
  `collab_owner_repository.py`): each process announces itself every 5 s
  (`collab/instance.mjs`, `HERD_COLLAB_ADVERTISE_URL`, required; role all:
  `ws://127.0.0.1:<collab port>`; the chart: the pod IP) and counts as alive for 15 s
  (judged by the database's `clock_timestamp()`, never a node's clock);
  the relay binds each page to one live, non-draining instance (`collab_page_owner`,
  epoch rising with each new binding; least busy = fewest unexpired bindings) and dials
  it, with none 4502. Auth/load return the epoch; save and check name instance and
  epoch (409 `collab.not_owner` → 4409; the save locks the binding after the page).
  SIGTERM drains: draining, save, close 1012, release (`DELETE
  /internal/collab/instances/{id}`). There is no `HERD_COLLAB_URL` any more.
- Operations (M9, `app/ops/`): `python -m app.ops backup create|verify|list|run|schedule`
  and `restore check|apply [--replace --confirm NAME]`, `maintenance status|off`
  (dispatcher `ops/cli.py`, `run(argv, settings, clock)`);
  archive format 1 (`archive.py`, `manifest.py`), `pg_dump`/`pg_restore` only through
  `pgtools.py` (password in `PGPASSWORD` of a built environment; `pg_restore` reads
  the archive's dump as a stream, no scratch file), retention and restic (`retention.py`,
  `offsite.py`, `forget --group-by host,tags`), advisory locks `herd.backup` and
  `herd.schema` (session locks: commit right after taking one, never hold a
  transaction open; a restore holds both and marks only runs started by the archive's
  `created_at`). A backup writes only into the backup directory (`.part` files, removed
  under the lock by the next run; a killed run counts as failed). State
  in `modules/backups` (`backup_run`, gauges read by the worker). Settings in
  `core/config_ops.py` (`HERD_BACKUP_*`). Deleted files keep a tombstone for 48 h
  (`core/storage_tombstones.py`). Rehearsal `deploy/scripts/restore-rehearsal.sh` with
  `scripts/compare_databases.py` (on S3 with `HERD_STORAGE=s3` in its environment).
  Replacing a running installation (M9b, `replace.py`): safety archive (`pre_restore`),
  maintenance on, the archive's files into the configured storage, one `psql`
  transaction (`swap.py`: explicit `BEGIN`/`COMMIT`, COMMIT only after `pg_restore`
  ended well), migrate, `finish_restore`, maintenance off. A dump runs only the entries
  of its table of contents that `ops/dump_toc.py` judges ours (`archive.dump_foreign`
  otherwise; checked in every check and before every restore, restored with
  `--use-list` from a memfd), a replace needs pg_restore/psql 16.10+/17.6+ and runs
  under a random `--restrict-key` (`restore.tools_too_old`). After any failure or
  cancel the database says what it holds (`swap_outcome.py`): rolled back keeps the old
  state and audits `backup.restore_failed`; `restore.swap_broken`/`restore.swap_unknown`
  keep maintenance on (the old state may be gone). `backup.manage` is owner-only (`OWNER_ONLY_ACTIONS`;
  `modules/backups/guard.py` answers 404 `backup.not_found`).
- Backups in the administration (M9b Task 13, `modules/backups`: `router.py`,
  `service.py`, `archives.py`, `checking.py`, `jobs.py`, `replacing.py`, `live.py`):
  One request or replace starts at a time (transaction try-lock `herd.backup.admin`,
  else 409 `backup.busy`).
  "Jetzt sichern" is a `backup_run` row (`trigger=admin`, `running`) that the worker's
  `BackupJobLoop` takes up with `run_backup(..., run_id=)`; `REQUEST_GRACE` (10 min)
  spares a young request from upkeep and other backups (`spare_requests_since`), a
  restore spares none. Replacing from the UI runs in the API process that took the
  request (`ReplaceRunner`, `replace_running(via="admin", wait=False)`), at most once;
  never queue it (an archive would bring the request back). `backup.changed` goes as a
  direct `pg_notify` to each active owner (ops act as system, maybe without a worker),
  payload ids only. Archive names must match `archives.NAME`, regular files only;
  uploads stream to a `.part` (0600), are verified and refused on any problem, and are
  never touched by retention. The API and worker need `HERD_BACKUP_DIR` mounted (the
  chart only on a shareable claim: ReadWriteMany or `backup.persistence.existingClaim`,
  `chart-rules-admin.sh`); `HERD_BACKUP_UPLOAD_MAX_BYTES` (`backup.uploadMaxBytes`, API
  only). Frontend `features/backup`; a 503 `maintenance.active` on any request shows
  `features/shared/MaintenancePage.tsx` (`onMaintenance` in `lib/api.ts`), which polls
  `GET /api/maintenance` and reloads `/` once a fresh answer says it ended.
- Maintenance (M9b, `modules/maintenance`): one row per org (`maintenance`); each
  process holds the state in `cache.py` (`maintenance_cache()`, `in_maintenance()`;
  NOTIFY `herd_maintenance` and a 5 s poll; a failed read keeps the last state, and a
  starting process counts as in maintenance until its first read succeeds), started
  by the public app's lifespan and the worker. Never ask the database whether it is in
  maintenance on a request path (tables are locked during the swap). While active:
  `/api/*` and `/mcp` answer 503 `maintenance.active` with `Retry-After: 30` except
  `GET /api/maintenance` (`middleware.py`), the relay and the internal collab API
  close/refuse (4503; instance heartbeats and releases too), live streams end, the
  worker's dispatcher, run loop and due loop pause (a new loop takes
  `paused=in_maintenance`).
- Storage (M9b): `core/storage.py` is the one `Storage` protocol (`put` with size and
  SHA-256, checked: `StoredContentMismatch`; `stat`, `entries`); `get_storage()` picks
  `LocalStorage` or `S3Storage` (`core/storage_s3.py`) from `HERD_STORAGE`; backup,
  restore and replace go through it. S3 is our own client, no SDK:
  `core/s3_signing.py` (SigV4, AWS test vectors in `tests/test_s3_signing.py`),
  `core/s3_client.py` (path-style, `x-amz-content-sha256`, fixed `s3.*` codes); requests
  go through `core/egress.py` with the endpoint's host as the one private allowance.
  Settings `core/config_storage.py` (`HERD_STORAGE`, `HERD_S3_*`; the secret key as a
  value or `HERD_S3_SECRET_ACCESS_KEY_FILE`, read like every secret file by
  `core/config_files.py`, never in a repr, log, error or URL). A failing store answers
  503 `storage.unavailable`. The worker's due loop removes tombstoned files, so the
  worker mounts the files where they are local (`compose.nodes.yml`; the chart beside an
  API pod on ReadWriteOnce). `python -m app.ops storage copy --to s3|local`
  (idempotent, `ops/storage_copy.py`) and `storage check`. Tests run against
  `tests/support/s3_stub.py` (checks signatures itself; fixtures in
  `tests/factories_s3.py`); `tests/test_s3_compatible_store.py` runs against a real
  store when `HERD_TEST_S3_ENDPOINT`, `HERD_TEST_S3_ACCESS_KEY_ID` and
  `HERD_TEST_S3_SECRET_ACCESS_KEY` are set (SeaweedFS, Apache-2.0, a test binary only).
- Hostinger stack (M9b Task 19, Jan's rules `vorgaben/hostinger-docker.md`): the root
  `docker-compose.yml` with `.env.example` (every variable empty, German comments) for
  the Docker Manager's "Compose from URL": GHCR image, no build, no ports, no bind
  mounts, default network `${TRAEFIK_NETWORK:-herd-web}` (never `external`), Traefik
  labels (router/service `herd-app`), no anchors, tabs, nested variables or `$$`.
  `python -m app.stack init` (`app/stack/init.py`) generates the secrets once into the
  volumes `secrets`/`db-secret`, checks `DOMAIN` (bare lower-case host name with a dot,
  no IP address; exit 2, never corrected) and the one-time admin with the app's password
  rules, skips missing values (exit 0); `python -m app.stack set-secret-key`
  (`app/stack/secret_key.py`) puts a saved key back from stdin. The app reads every
  secret through `HERD_*_FILE` (`core/config_files.py`); the image's services pull on
  every deploy (`pull_policy: always`) and none but init disables its check. Rules are
  enforced by `tests/test_hostinger_compose.py`; CI runs
  `deploy/scripts/hostinger-smoke.sh`. `deploy/compose/` stays the build/reference variant.
- Retention (M9): `core/retention.py` holds a rule for every table (`Keep`, `Upkeep`,
  `Cleans`; `tests/test_retention.py` fails for a table without one); the due loop's
  `worker/upkeep.py` deletes expired rows.
- Sign-in (M9): `modules/oidc` (providers, flow with PKCE/state/nonce and a binding
  cookie, ID token check with PyJWT, `admission.py` decides login/link/signup/refuse,
  Google preset in `providers.py`); settings in `core/config_auth.py`
  (`HERD_OIDC_*`). Self-registration (Google, or a generic provider with
  `trust_email`) creates an inactive account waiting for approval
  (`app_user.awaiting_approval_since`; `users` approve/reject, audit, admin
  notification); rejecting deletes the never-active account and what signup created
  (`users/removal_repository.py`; the audit keeps ids only); deleting a provider ends
  its people's sessions. Nothing else creates accounts without an admin; the first
  owner's `HERD_BOOTSTRAP_ADMIN_PASSWORD` passes the password checks (exit 4 if not). Stub
  `tests/support/oidc_stub.py`.
- Second factor (M9b Task 16, `modules/totp`): RFC 6238 on `hmac` only (`codes.py`),
  the secret `enc:` under `HERD_SECRET_KEY` (rotated by `rotate_secrets`), recovery
  codes as SHA-256 (`recovery.py`); a used time step or recovery code is spent in one
  statement (`repository.py`). Checking (`factor.py`) counts wrong codes per person
  (`second-factor-fail:<id>`, the login limit); ten wrong codes within 24 h lock the
  factor for 1 h (`user_totp.locked_until`, one atomic UPDATE; 429
  `auth.second_factor_locked` even for a right code, audit `user.totp_locked`,
  notification `totp_locked`; a right code resets the count); `begin` commits, so call
  it before any lock. A password or OIDC sign-in of a person with TOTP opens no session: login
  answers 202 and leaves a `sign_in_challenge` (hash only, 5 min, 5 wrong codes) bound
  to the cookie `herd_sign_in` (`cookies.py`); `sign_in.py` is the second step.
  Whatever ends a person's sessions ends her waiting sign-ins too. Codes are judged at
  the wall time (`timing.TOTP_CLOCK`, not the e2e clock; tests swap in a
  `SettableClock` through the fixture `totp_time`). New access tokens of a person with
  TOTP need a code (`gate.py`). Frontend `features/profile/totp`, the QR code with
  `uqr`; e2e `tests/totp.spec.mjs` with an authenticator in `totp-helpers.mjs`.
- Security (M9b Task 18, ASVS J7–J14; rows in `docs/SICHERHEIT.md`):
  - Sessions are judged at the wall time (`auth/timing.SESSION_CLOCK`, not the e2e
    clock). A session unused for `HERD_SESSION_IDLE_HOURS` (24, 0 = off) ends, and the
    end is recorded on its row (expiry = the idle moment: by the request that finds it,
    a logout, the worker's upkeep), so raising the setting later revives nothing. Only
    the person's own requests count as use: the SPA marks requests after more than 60 s
    without input in the tab `X-Herd-Unattended: 1` (`lib/attention.ts`), which
    `current_auth` does not count, and while she works with no counted request for
    5 min it sends `POST /api/auth/me/touch` (204, no write; typing only in the live
    editor keeps the session). The touch in `current_auth` commits at once and never
    waits (`SKIP LOCKED`); `/api/stream` and collab's checks do not touch.
    `/api/auth/me` names `session_limits` (`idle_hours`, null when off; `ttl_hours`).
    `user_session.device` ("Browser · System", never a version, `auth/device.py`) and
    `signed_in_at` are noted by the one hand-over helper `auth/handover.py` (password,
    OIDC, second factor). `/api/auth/me/sessions` (`sessions_router.py`,
    `own_sessions.py`): list, end one, end all others (the audit counts only sessions
    still running).
  - Linking a provider account needs the password, or a fresh login at a provider the
    person already uses, at most 10 min ago (`auth/reauth.py`, 403
    `auth.reauth_required`; frontend `profile/identities/ReauthDialog.tsx`). Only a
    sign-in started for it (`?reauth=true`: `prompt=login`, `max_age=600`, an
    `auth_time` within 10 min or `oidc.reauth_stale`; `oidc/fresh.py`, column `reauth`
    on `oidc_flow` and `sign_in_challenge`) counts; an ordinary provider sign-in, maybe
    silent, does not.
  - Writes count per person/agent and minute in PostgreSQL (`core/write_limit.py`,
    `HERD_WRITE_RATE_PER_MINUTE` 120, uploads apart `HERD_UPLOAD_RATE_PER_MINUTE` 30;
    429 `rate.limited`): content routers include `auth/write_limits.COUNTED`, single
    content routes of other routers carry it at the route, upload routes carry `UPLOAD`
    besides (decided at the route, never by path); agent and `/mcp` writes count in
    `writing.effect` inside the step's transaction. `tests/test_write_limit_routes.py`
    fails for any unsafe `/api` route that is neither counted nor on its commented
    exemption list: a new write route adds `COUNTED` or an exemption with its reason.
    Bulk scripts wait out a 429 (`Retry-After`).
  - `HERD_CLAMAV_ADDRESS` (optional clamd, `core/virus_scan.py`): attachments, imports
    and skill imports are scanned before storing, never while a transaction or pooled
    connection waits; a find is 422 `attachment.rejected_by_scan`, a failed scan 503
    `attachment.scan_unavailable` (fail closed). Uploaded backup archives are not
    scanned (owner-only, a database dump; `docs/SICHERHEIT.md`). Stub
    `tests/support/clamd_stub.py`.
  - `HERD_DATABASE_SSLMODE`/`HERD_DATABASE_SSLROOTCERT` (`core/config_database.py`,
    `core/db_tls.py`) reach every engine (`make_engine` sets `connect_args`), the LISTEN
    connection and `pgtools.child_env` (`PGSSLMODE`, `PGSSLROOTCERT`; for verify-ca/-full
    without a file `PGSSLROOTCERT=system`, as asyncpg uses the system's CAs); the
    setting wins over the URL's. A failing `pg_dump`/`pg_restore`/`psql` logs only its
    connection-level error line, masked; an SQL error only as `query failed`
    (`ops/tool_errors.py`).
    `HERD_INTERNAL_TOKEN_PREVIOUS` is accepted besides the current token during a
    rotation (API only; collab sends the current one).
  - OAuth apps have their own callback `/api/ai/oauth/{oauth_client.id}/callback`
    (`oauth/callbacks.py`); a response at another callback uses the flow up (`invalid`);
    `iss` is compared with `oauth_client.issuer` when sent or promised
    (`issuer_in_response`, `issuer_mismatch`). The old shared callback only finishes
    flows whose stored `redirect_uri` is the shared one.
  - Optional separate roles: `HERD_MIGRATE_DATABASE_URL` (+ `_PASSWORD`) owns the
    schema and is used by Alembic and every `python -m app.ops` command and pg tool;
    `HERD_DATABASE_RUNTIME_ROLE` gets data rights after every migration run
    (`core/db_roles.py`, also `ALTER DEFAULT PRIVILEGES`; `alembic_version` stays
    read-only for it). With them, restoring from the administration is refused
    (`restore.not_schema_owner`). Overlay `deploy/compose/compose.roles.yml` (role all:
    the container still holds the owner's password, so the split stops SQL injection,
    not code in the container); chart `database.migrate`.
- Browser tests (`e2e/`, Node 22, ESM): Playwright (`@playwright/test`), live editing,
  messaging, tickets, agents, automations, MCP, backups and TOTP in the real app (role all, worker
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
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy app scripts \
  && uv run python -m scripts.check_migrations
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
cd collab && npm run test:integration             # real API on a throwaway database (psql, uv),
                                                  # one instance and two (integration-instances)
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
SMOKE_NODES=1 bash deploy/compose/smoke.sh              # compose.nodes.yml: api-a, api-b, worker, collab-a, collab-b;
                                                        # message A → SSE B; two collab instances, a page bound
                                                        # (both modes also: a ticket's system entries from the worker
                                                        # and a one-off automation fired exactly once by the due loop)
SMOKE_S3=1 bash deploy/compose/smoke.sh                 # compose.s3.yml (SeaweedFS): attachments in S3, restore, copy back
bash deploy/compose/load.sh                             # docker stats idle/warm/load + latency (Steckbrief)
# 200-person load test without Docker: deploy/compose/{loadsetup,loadmix,loadreport}.py,
# deploy/scripts/measure-processes.sh (RSS/CPU per role from /proc); README of compose
# Live editing under load (Steckbrief, M9b): collab/scripts/live-load.mjs BASE STATE [SECONDS] [TYPE_MS] [STOP_PID]
bash deploy/scripts/restore-rehearsal.sh                # backup A → restore into empty B → compare → replace
                                                        # running B (--replace) (PGHOST/PGPORT, REHEARSAL_PORT)
bash deploy/scripts/hostinger-smoke.sh                  # root docker-compose.yml: config, empty first deploy,
                                                        # values, host-network Traefik (image ghcr.io/…:$HOSTINGER_SMOKE_TAG)
```

```bash
bash deploy/helm/scripts/check-chart-version.sh         # chart version = appVersion = pyproject version
bash deploy/helm/scripts/check-chart-rules.sh           # chart behaviour (HELM="docker run ... alpine/helm" works too;
                                                        # sources chart-rules-scaling.sh, chart-rules-placement.sh,
                                                        # chart-rules-storage.sh and chart-rules-admin.sh)
cd backend && uv run python ../deploy/helm/scripts/check_values.py   # values files vs schema, @param vs schema
helm lint --strict deploy/helm/to-herd-cats-ai          # also with -f deploy/helm/to-herd-cats-ai/ci/*-values.yaml
                                                        # (ci/full-values.yaml switches everything on)
helm template t deploy/helm/to-herd-cats-ai | kubeconform -strict -summary
promtool test rules deploy/helm/to-herd-cats-ai/tests/rules-test.yaml
```

CI (`.github/workflows/ci.yml`, pull requests and pushes to `main`; tags through
`release.yml`) runs all of the above plus `pip-audit`, `npm audit --audit-level=high`,
the image build, `smoke.sh` (single, `SMOKE_NODES=1` and `SMOKE_S3=1`) and Trivy. A tag `vX.Y.Z`
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
  first, contract in a later release). `backend/alembic/RELEASED` names the last
  released revision (set by hand to the head when tagging; `release.yml` refuses a tag
  where it is not, `check_migrations.py --require-released-head`); `scripts/check_migrations.py`
  refuses drops, renames and type changes after it unless `contract_of` names a
  released revision, and demands one head. `/ready` stays ready when the database is at a
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
  `demo_mcp.py`, `demo_oidc.py` (only with `--oidc-stub`), `demo_totp.py` (only with
  `--totp-file PATH`: Ben with TOTP, key and recovery codes in a new 0600 file),
  `demo_pages.py`, shared API helpers in
  `demo_api.py`) goes through the public API only; extend it and its test with each
  milestone.
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
  - What an external server returns (results, descriptions, every word of a tool's
    schema) is untrusted, framed and cut; a model gets a schema's structure only
    (`mcp_servers/schema_view.py`); it never grants anything. A tool is callable only with its approved
    fingerprint; a changed one is blocked until re-approved; the catalogue only
    suggests. Write tools are level 4 and wait for the asker's release of the exact
    arguments; a lost worker never sends a call again (`external_outcome_unknown`).
  - A result through the asker's own connector marks the run (`Reads.personal`, like
    the draft mark): it writes without her release only into its own DM alone with
    her (those messages are `message.personal`); every other write (any space, her
    personal space and a space only she belongs to included, memory pages, proposals,
    tickets, channel posts, external calls) waits for the asker's release of exactly
    that content (`personal_mark.ReleaseFirst`; released, it is unmarked), its answer
    and questions where others read stay held back, and every call of an external
    server it does not use with the asker's own connector (read tools included) waits
    for the asker's release of the exact arguments (automation runs: the owner). The
    mark follows the content and is persisted (`agents/personal_mark.py`): every
    message a marked run writes is `message.personal` (only alone with the asker); a
    run is marked, journaled at once, when such content enters its context (history
    window: a `mark` event; `search_past_runs`, `read_conversation`: `read.personal`);
    never by memory alone. No marked content in its context: no mark; nothing
    unmarks by heuristic, only the asker's "Neu beginnen" in her DM alone with the
    agent (`conversation.fresh_start_at`, `agents/fresh_start.py`): runs there after it
    reach nothing from before it (history window, `read_conversation`,
    `search_past_runs`); memory she released stays. The cut is the database clock,
    serialised with her messages on the DM's row (`messaging/dating.py`). Every event
    of a marked run is the asker's alone (the run view redacts the whole run for
    anyone else); a call the release gate finds to change nothing (a preview) runs
    `previewing`, never as released, and `writing.effect` never writes for it.
  - A connector's secret goes only to the origin (OAuth: the endpoints) it was given
    for: a server's new origin or a client's new endpoints disconnect its connectors
    (`connectors/moving.py`; a shared one stays only when the change says so).
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
