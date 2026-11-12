# CLAUDE.md — to-herd-cats-ai (project constitution)

Arbeite nach den Superpowers-Skills (https://github.com/obra/superpowers): brainstorming → writing-plans → subagent-driven-development/executing-plans, TDD, verification-before-completion.

Knowledge & agent cockpit for companies. The authority is the design spec
`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (German). M1
(`docs/superpowers/plans/2026-11-12-m1-fundament.md`) is built; the next plan is
`docs/superpowers/plans/2026-11-12-m2-wiki.md`. Parts named in the spec but not yet
built (wiki, tickets, agents) are planned, not present. Operations: `README.md`
(Betriebshinweise), `docs/STECKBRIEF.md` (update its measurements each milestone).

## Stack (present)

- Backend: Python 3.13, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2,
  PostgreSQL only. Tooling: `uv`, `ruff`, `mypy` (strict), `pytest`.
- Frontend (`frontend/`): React 19, TypeScript strict, Vite, Tailwind 4, shadcn/ui
  (Radix), TanStack Router (code-based routes in `src/app/router`) and Query, i18next,
  react-hook-form + zod (schemas derived from `openapi.json`), next-themes. Tooling:
  `npm`, `oxlint`, `prettier`, `vitest` + Testing Library.
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
  && uv run python scripts/check_licenses.py npm ../frontend/package-lock.json
```

```bash
cd frontend && npm ci
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && node scripts/check-i18n.mjs
cd frontend && npm run generate:api   # after API changes: openapi.json + src/lib/api-types.ts
cd frontend && npm run check:api      # fails if those files are stale
cd frontend && npm run dev            # proxies /api to http://localhost:8080
```

```bash
docker build -t to-herd-cats-ai:local .                 # the image (SPA + API, uid 10001)
bash deploy/compose/smoke.sh                            # compose reference: build, start, check, tear down
bash deploy/compose/load.sh                             # docker stats idle/warm/load + latency (Steckbrief)
```

```bash
bash deploy/helm/scripts/check-chart-version.sh         # chart version = appVersion = pyproject version
helm lint --strict deploy/helm/to-herd-cats-ai          # also with -f deploy/helm/to-herd-cats-ai/ci/*-values.yaml
helm template t deploy/helm/to-herd-cats-ai | kubeconform -strict -summary
promtool test rules deploy/helm/to-herd-cats-ai/tests/rules-test.yaml
```

CI (`.github/workflows/ci.yml`, every push) runs all of the above plus `pip-audit`,
`npm audit --audit-level=high`, the image build, `smoke.sh` and Trivy. A tag `vX.Y.Z`
(`release.yml`) publishes `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z`/`:X.Y` and the chart
as OCI under `ghcr.io/<owner>/charts`; tag, pyproject and chart versions must match.

The backend serves the built SPA when `HERD_STATIC_DIR` points at `frontend/dist`
(`backend/app/web/spa.py`: CSP, cache headers, index.html fallback outside `/api`).

Tests need Postgres; `HERD_TEST_DATABASE_URL` defaults to
`postgresql+asyncpg://herd:herd@localhost:5433/herd_test`. Backend tests create a
fresh schema per session and roll back per test.

## Conventions

- Identifiers, comments, docstrings, commit messages in English.
- Commit messages: `<area>: <imperative summary>`; ported code adds a trailer
  `Ported-from: to-herd-cats-ai@<sha>:<path>`.
- Alembic: one migration per slice, never edited after merge.
- Alembic: migrations must stay backward compatible with the previous release (expand
  first, contract in a later release). `/ready` stays ready when the database is at a
  revision this code does not know (a newer release migrated before its pods rolled
  out); it is not ready only with no revision or a known older one.

## Definition of done (per task)

Failing test first → minimal implementation → tests green → ruff/mypy clean →
docs updated if behaviour changed → commit.
