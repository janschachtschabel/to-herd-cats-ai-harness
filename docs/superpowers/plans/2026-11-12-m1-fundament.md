# M1 Fundament Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein lauffähiges, clusterfähiges Grundsystem: Anmeldung, Personen, Gruppen, Bereiche (`open`/`team`/`personal`) mit Rollen und der einen Rechteprüfung, Audit, Verwaltungsoberfläche, ein Image mit zwei Ports, JSON-Logs mit Tracing, Compose und Helm-Grundgerüst, CI.

**Architecture:** Modularer Monolith in Python/FastAPI mit `router → service → repository`. Eine öffentliche App (Port 8080) und eine interne App (Port 9090) laufen im selben Prozess. Die React-SPA wird als statische Dateien von der öffentlichen App ausgeliefert. Ein Startprogramm (`app.launch`) wählt die Rolle über `HERD_ROLE`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, argon2-cffi, prometheus-client, OpenTelemetry; PostgreSQL 17 + pgvector; React 19, TypeScript strict, Vite, Tailwind 4, shadcn/ui, TanStack Router/Query, i18next, openapi-fetch; Docker, Helm 3.

**Spec:** `docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (Abschnitte 2, 4, 5, 12, 13, 14/M1)

## Global Constraints

- Nur PostgreSQL; keine SQLite-Codepfade. Testdatenbank ist ein echtes Postgres (`herd_test`).
- `org_id` auf jeder fachlichen Tabelle; jede Abfrage filtert nach der `org_id` des Actors.
- Schichten: Router validieren und übersetzen, Services halten Regeln, Repositories halten SQL. Kein SQL in Services, keine Regeln in Routern, keine Fachlogik in React-Komponenten.
- Dateien höchstens ~300 Zeilen.
- Jedes persistierte Feld wird von getestetem Code gelesen. Keine Felder „für später“.
- Jede Liste ist paginiert (`limit` ≤ 100, `cursor`). Jeder konkurrierende Schreibzugriff nutzt `version` und antwortet mit 409.
- Fehlerform: `{"error": {"code": "<bereich.grund>", "message": "...", "trace_id": "<32 hex>"}}`.
- Dienst-ID `to-herd-cats-ai` in Log-Feld `service`, `OTEL_SERVICE_NAME`, Image-Name und Chart-Name.
- Umgebungsvariablen mit Präfix `HERD_`; Ports: öffentlich `HERD_PUBLIC_PORT=8080`, intern `HERD_INTERNAL_PORT=9090`.
- In Logs stehen nie Header-Werte, Cookies, Passwörter oder Request-Bodies.
- Bezeichner, Kommentare, Commit-Nachrichten in Englisch; Oberflächentexte über i18n (`de` Standard, `en` vollständig), semantische Schlüssel (`spaces.create.title`).
- Commit-Format: `<area>: <imperative summary>`. Übernommener Code: Zusatzzeile `Ported-from: to-herd-cats-ai@<sha>:<path>`.
- Nur Abhängigkeiten mit MIT-, BSD-, Apache-2.0-, ISC- oder PostgreSQL-Lizenz.

## Review Focus

1. **Existenz verborgener Bereiche:** Ein Nicht-Admin ruft `GET /api/spaces/{id}` für einen fremden `team`- oder `personal`-Bereich auf. Erwartet wird 404 `space.not_found`, gleich wie bei einer unbekannten ID, nie 403. Abgedeckt in Task 7.
2. **Deaktivierte Person:** Wird eine Person deaktiviert, wird schon ihre nächste Anfrage mit 401 abgelehnt, weil alle Sitzungen gelöscht sind. Abgedeckt in Task 4.
3. **Rolle über Gruppe:** Wer aus einer Gruppe entfernt wird, verliert sofort die darüber erhaltene Bereichsrolle. Gibt es auch eine direkte Rolle, gilt die höhere. Abgedeckt in Task 7.
4. **Lecks im Log:** Eine Anfrage mit `Cookie`, `Authorization` und einem Passwort im Body, die mit einer Ausnahme (500) endet, schreibt keinen dieser Werte in eine Logzeile. Abgedeckt in Task 2.
5. **Letzte Inhaberin:** Die letzte Person mit `owner` kann weder herabgestuft noch deaktiviert werden. Erwartet wird 409 `users.last_owner`. Abgedeckt in Task 4.

---

## Dateistruktur

```
backend/
  pyproject.toml  uv.lock  alembic.ini  alembic/env.py  alembic/versions/
  app/
    launch.py                    # Rollenwahl: api | migrate | all  (worker folgt in M3)
    core/
      config.py  db.py  errors.py  models_base.py  repository.py  pagination.py
      logging.py  telemetry.py  metrics.py  request_log.py
      principal.py  permissions.py  access.py  security.py  ratelimit.py
    web/
      public.py  internal.py  spa.py
    modules/
      orgs/  users/  auth/  groups/  spaces/  audit/   (je models, schemas, repository, service, router)
  tests/
    conftest.py  factories.py  test_*.py
frontend/
  package.json  vite.config.ts  tsconfig*.json  index.html
  scripts/check-i18n.mjs
  src/app/ (router, shell)  src/features/{auth,spaces,admin}/  src/components/ui/  src/lib/  src/locales/{de,en}/
deploy/
  compose/compose.yml  compose/smoke.sh
  helm/to-herd-cats-ai/ (Chart.yaml, values.yaml, templates/, tests/)
Dockerfile  .dockerignore  .github/workflows/ci.yml
CLAUDE.md  README.md  docs/STECKBRIEF.md
```

---

### Task 1: Backend-Gerüst, Konfiguration, Fehler, Datenbank, Testgerüst

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/core/{config,db,errors,models_base,repository,pagination}.py`, `backend/app/web/public.py`, `backend/tests/conftest.py`, `backend/tests/test_errors.py`, `backend/tests/test_pagination.py`, `CLAUDE.md`
- Port: `config.py`, `db.py`, `errors.py`, `models_base.py`, `repository.py`, `conftest.py` aus ai-1 `backend/`

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings, Präfix `HERD_`): `environment`, `database_url`, `test_database_url`, `public_port: int = 8080`, `internal_port: int = 9090`, `internal_token: str`, `session_cookie_name = "herd_session"`, `session_ttl_hours = 168`, `cookie_secure`, `login_rate_limit_per_minute = 5`, `bootstrap_admin_email`, `bootstrap_admin_password`, `bootstrap_org_name = "Meine Organisation"`, `log_format: Literal["json","text"] = "json"`, `log_level = "INFO"`, `role: Literal["api","migrate","all"] = "all"`, `static_dir: Path | None`.
  - `get_settings() -> Settings` (gecacht).
  - `AppError(message=None, *, code=None)` und Unterklassen `NotFound` 404, `Conflict` 409, `Unauthorized` 401, `Forbidden` 403, `ValidationFailed` 422, `RateLimited` 429.
  - `install_error_handlers(app)`.
  - `Base`, Mixins `UuidPk` (UUIDv7), `Timestamps`, `OrgScoped`, `utcnow()`.
  - `get_session()` als FastAPI-Dependency.
  - `Page[T]` (`items: list[T]`, `next_cursor: str | None`), `PageParams` (`limit: int = 50` mit 1–100, `cursor: str | None`), `encode_cursor(created_at, id) -> str`, `decode_cursor(str) -> tuple[datetime, UUID]`.
  - `create_public_app() -> FastAPI`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_errors.py
async def test_app_error_has_code_message_and_trace_id(client):
    r = await client.get("/api/_test/not-found")          # Testroute, nur bei environment=test registriert
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "test.not_found"
    assert len(body["trace_id"]) == 32

async def test_unhandled_exception_is_500_with_generic_message(client):
    r = await client.get("/api/_test/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal"
    assert "boom" not in r.text

async def test_validation_error_uses_error_shape(client):
    r = await client.get("/api/_test/needs-int?n=abc")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"

# tests/test_pagination.py
def test_cursor_round_trip():
    ts, id_ = datetime(2026, 11, 12, tzinfo=UTC), uuid7()
    assert decode_cursor(encode_cursor(ts, id_)) == (ts, id_)

def test_invalid_cursor_is_422():
    with pytest.raises(ValidationFailed):
        decode_cursor("not-a-cursor")
```

`trace_id` kommt bis Task 2 aus einer zufällig erzeugten 32-Hex-ID je Anfrage (`request.state.trace_id`). Task 2 ersetzt die Quelle durch OpenTelemetry.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_errors.py tests/test_pagination.py -v`
Expected: FAIL (Module fehlen)

- [ ] **Step 3: Implement**

ai-1-Dateien übernehmen. Danach:

- `ai-1`-Felder entfernen, die M1 nicht liest: DBOS, SMTP, Attachments, Chat, LLM.
- Den Fehler-Handler um `trace_id` sowie um Handler für `RequestValidationError` (→ 422 `validation_failed`) und `Exception` (→ 500 `internal`) ergänzen.
- Testrouten unter `/api/_test/*` nur bei `environment == "test"` registrieren.

`CLAUDE.md` übernimmt die Hard Rules aus ai-1 (angepasst an diese Spezifikation) und den Hinweis: „Arbeite nach den Superpowers-Skills (https://github.com/obra/superpowers): brainstorming → writing-plans → subagent-driven-development/executing-plans, TDD, verification-before-completion.“

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -v && uv run ruff check . && uv run mypy app`
Expected: PASS, keine Befunde

- [ ] **Step 5: Commit**

```bash
git add backend CLAUDE.md
git commit -m "core: add backend skeleton with settings, errors, db and pagination"
```

---

### Task 2: JSON-Logging, Anfragezeile, Tracing

**Files:**
- Create: `backend/app/core/{logging,telemetry,request_log}.py`, `backend/tests/test_logging.py`
- Modify: `backend/app/web/public.py` (Middleware einhängen), `backend/app/core/errors.py` (`trace_id` aus aktivem Span)

**Interfaces:**
- Consumes: `Settings.log_format`, `Settings.log_level`
- Produces:
  - `configure_logging(settings) -> None`
  - `configure_tracing(app: FastAPI, settings) -> None`
  - `current_trace_ids() -> tuple[str, str]` (`trace_id`, `span_id` als Hex; ohne aktiven Span neu erzeugt)
  - `RequestLogMiddleware`
  - `log_context(**fields)` als Contextvar-Kontextmanager für `org_id` und `actor`

- [ ] **Step 1: Write the failing tests**

```python
async def test_request_line_is_json_with_required_fields(client, capsys):
    await client.get("/api/_test/ok")
    line = json.loads(last_line(capsys, "http.request"))
    assert line["service"] == "to-herd-cats-ai"
    assert {"timestamp", "level", "trace_id", "span_id", "message"} <= line.keys()
    assert line["path"] == "/api/_test/ok" and line["status"] == 200 and "duration_ms" in line

async def test_incoming_traceparent_is_continued(client, capsys):
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    r = await client.get("/api/_test/not-found", headers={"traceparent": tp})
    assert r.json()["error"]["trace_id"] == "0af7651916cd43dd8448eb211c80319c"

async def test_client_trace_id_is_logged(client, capsys):
    await client.get("/api/_test/ok", headers={"x-client-trace-id": "abc-123"})
    assert json.loads(last_line(capsys, "http.request"))["client_trace_id"] == "abc-123"

async def test_secrets_never_reach_logs(client, capsys):
    await client.post("/api/_test/boom-post", json={"password": "hunter2-secret"},
                      headers={"Cookie": "herd_session=sess-secret", "Authorization": "Bearer tok-secret"})
    out = capsys.readouterr().out + capsys.readouterr().err
    for secret in ("hunter2-secret", "sess-secret", "tok-secret"):
        assert secret not in out
```

`last_line(capsys, message)` ist eine Hilfsfunktion in `tests/conftest.py`. Sie gibt die letzte JSON-Zeile mit `message == <message>` zurück.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_logging.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

- **Logging:** stdlib-`logging` mit eigenem JSON-Formatter (oder `python-json-logger`). Die Felder kommen aus Contextvars und `current_trace_ids()`. Bei `log_format=text` wird lesbarer Text ausgegeben.
- **Tracing:** `opentelemetry-sdk` mit FastAPI-Instrumentierung. Den Propagator aus `OTEL_PROPAGATORS` wählen (Standard `tracecontext,baggage`, `b3` über `opentelemetry-propagator-b3`). Der OTLP-Exporter wird nur aktiviert, wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist.
- **Access-Log:** Uvicorn startet mit `access_log=False`. Die eigene Middleware schreibt genau eine Zeile `http.request` mit `method`, `path` (Route-Template, sonst roher Pfad), `status`, `duration_ms`, `client_trace_id`.
- **Ausnahmen:** Der Exception-Handler loggt `exc_info` ohne Request-Body und ohne Header.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "core: add json logging, request line and otel tracing"
```

---

### Task 3: Interner Port, Proben, Metriken, Startprogramm, Migrationen

**Files:**
- Create: `backend/app/web/internal.py`, `backend/app/core/metrics.py`, `backend/app/launch.py`, `backend/alembic/env.py`, `backend/alembic.ini`, `backend/tests/test_internal.py`, `backend/tests/test_migrations.py`
- Port: `test_migrations.py` aus ai-1 (Rollback-Prüfung offline)

**Interfaces:**
- Consumes: `create_public_app()`, `Settings`
- Produces:
  - `create_internal_app() -> FastAPI` mit `GET /health` (immer 200 `{"status":"ok"}`), `GET /ready` (200 oder 503 `{"status":"not_ready","reason": "database"|"migrations"}`) und `GET /metrics`.
  - `schema_is_current(engine) -> bool` (vergleicht die Alembic-Revision in der Datenbank mit dem Head).
  - Metriken `herd_http_requests_total{method,route,status}` und `herd_http_request_duration_seconds{route}`.
  - `python -m app.launch` startet je nach `HERD_ROLE`:
    - `api`: beide Apps über `uvicorn.Server` in einer Event-Loop.
    - `migrate`: `alembic upgrade head`, danach Ende.
    - `all`: erst migrieren, dann wie `api`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_health_is_always_ok(internal_client):
    assert (await internal_client.get("/health")).json() == {"status": "ok"}

async def test_ready_is_503_when_schema_behind(internal_client, monkeypatch):
    monkeypatch.setattr("app.web.internal.schema_is_current", AsyncMock(return_value=False))
    r = await internal_client.get("/ready")
    assert r.status_code == 503 and r.json()["reason"] == "migrations"

async def test_metrics_count_public_requests(client, internal_client):
    await client.get("/api/_test/ok")
    assert 'herd_http_requests_total{method="GET",route="/api/_test/ok",status="200"}' in (await internal_client.get("/metrics")).text

async def test_probes_are_not_on_public_port_or_in_openapi(client):
    assert (await client.get("/health")).status_code == 404
    paths = (await client.get("/api/openapi.json")).json()["paths"]
    assert not any(p.startswith(("/health", "/ready", "/metrics", "/internal")) for p in paths)

def test_every_migration_can_be_rolled_back(): ...   # aus ai-1, Assertion auf "DROP TABLE organization"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_internal.py tests/test_migrations.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`prometheus-client` mit eigener Registry. Bei gesetztem `PROMETHEUS_MULTIPROC_DIR` den Multiprozess-Collector nutzen. `launch.py` fängt SIGTERM ab und beendet beide Server geordnet. `env.py` rendert ohne `fileConfig` (Lehre aus ai-1).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "ops: add internal port with probes and metrics, launcher and alembic"
```

---

### Task 4: Organisation, Personen, Anmeldung, Sitzungen

**Files:**
- Create: `backend/app/modules/{orgs,users,auth}/{models,schemas,repository,service,router}.py`, `backend/app/core/{security,ratelimit,principal}.py`, Migration `m1_identity`, `backend/tests/{test_auth,test_users}.py`, `backend/tests/factories.py`
- Port: ai-1 `core/security.py`, `core/ratelimit.py`, `core/principal.py`, `modules/{orgs,users,auth}` und die Tests `test_auth.py`, `test_users.py`

**Interfaces:**
- Produces:
  - Tabellen:
    - `organization(id, name, slug)`,
    - `app_user(id, org_id, email, name, password_hash, system_role, is_active, locale, last_login_at, version)`,
    - `user_session(id, org_id, user_id, token_hash, expires_at, ip, user_agent)`,
    - `rate_limit_hit`.
  - `SystemRole(StrEnum)`: `owner`, `admin`, `member`, `guest`.
  - `PrincipalType`: `user`, `agent`, `group`. `Principal(type, id)` mit `.user()` und `.group()`. `agent` wird erst in M6 benutzt, gehört aber zum Enum.
  - `AuthService.login(email, password, ip, user_agent) -> tuple[User, str]`, `.logout(token)`, `.resolve(token) -> AuthContext | None`.
  - `UserService.create(actor, data) -> User`, `.update(actor, user_id, data, version) -> User`, `.deactivate(actor, user_id) -> None` (löscht alle Sitzungen), `.list(actor, PageParams) -> Page[User]`.
  - `ensure_bootstrap(session, settings) -> None`: legt Organisation und `owner` an, wenn keine Person existiert.
  - Routen:
    - `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
    - `GET|POST /api/admin/users`, `PATCH /api/admin/users/{id}`, `POST /api/admin/users/{id}/deactivate`.
  - CSRF: Unsichere Methoden verlangen `X-Requested-With: herd` (ai-1).

- [ ] **Step 1: Write the failing tests**

Die ai-1-Tests werden übernommen und angepasst: `org_role` heißt jetzt `system_role`, und es gibt die Rolle `guest`. Neu hinzu kommen:

```python
async def test_deactivated_user_is_logged_out_immediately(client, owner, member_client, member):
    await owner.post(f"/api/admin/users/{member.id}/deactivate")
    assert (await member_client.get("/api/auth/me")).status_code == 401

async def test_last_owner_cannot_be_demoted_or_deactivated(owner, owner_user):
    r = await owner.patch(f"/api/admin/users/{owner_user.id}", json={"system_role": "admin", "version": owner_user.version})
    assert r.status_code == 409 and r.json()["error"]["code"] == "users.last_owner"
    r = await owner.post(f"/api/admin/users/{owner_user.id}/deactivate")
    assert r.json()["error"]["code"] == "users.last_owner"

async def test_member_cannot_manage_users(member_client):
    assert (await member_client.get("/api/admin/users")).status_code == 403

async def test_login_is_rate_limited(client):
    for _ in range(5): await client.post("/api/auth/login", json=bad_creds, headers=CSRF)
    assert (await client.post("/api/auth/login", json=bad_creds, headers=CSRF)).status_code == 429

async def test_stale_version_is_409(owner, member):
    r = await owner.patch(f"/api/admin/users/{member.id}", json={"name": "X", "version": member.version - 1})
    assert r.status_code == 409
```

`factories.py` liefert die Fixtures `owner`, `member`, `guest` (jeweils als `httpx`-Client) sowie `make_user(role=...)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py tests/test_users.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

ai-1-Code übernehmen. Darüber hinaus:

- Umbenennung zu `system_role` und Rolle `guest`.
- Regel „letzte Inhaberin“.
- `deactivate` löscht Sitzungen.
- `version` an `app_user`.
- Paginierte Liste.
- Eine Migration `m1_identity` (autogenerate, Fremdschlüssel benannt).
- Bootstrap beim Start der Rolle `api`/`all`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "auth: add organisation, users, sessions and login"
```

---

### Task 5: Gruppen

**Files:**
- Create: `backend/app/modules/groups/*`, Migration `m1_groups`, `backend/tests/test_groups.py`

**Interfaces:**
- Consumes: `Principal`, `UserService`, `Page`
- Produces:
  - Tabellen `user_group(id, org_id, name, description, version)` und `group_member(group_id, member_type, member_id)`. `member_type` ist in M1 nur `user`; ein CHECK-Constraint wird in M6 erweitert.
  - `GroupService.create`, `.update`, `.delete`, `.add_member`, `.remove_member`, `.list`.
  - `GroupRepository.group_ids_for(principal) -> frozenset[UUID]`.
  - Routen `/api/admin/groups[...]` (Recht `group.manage`).

- [ ] **Step 1: Write the failing tests**

```python
async def test_admin_creates_group_and_adds_member(owner, member): ...
async def test_member_cannot_create_group(member_client): ...   # 403
async def test_group_ids_for_user(session, group_with_member, member):
    assert await GroupRepository(session).group_ids_for(Principal.user(member.id)) == {group_with_member.id}
async def test_deleting_group_removes_memberships(owner, group_with_member, session): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_groups.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Gruppen anlegen und verwalten nach der Interface-Liste oben. Das Löschen einer Gruppe entfernt per `ON DELETE CASCADE` alle `group_member`-Zeilen und alle Bereichsmitgliedschaften der Gruppe.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "groups: add groups and memberships"
```

---

### Task 6: Bereiche und Mitgliedschaften

**Files:**
- Create: `backend/app/modules/spaces/*`, Migration `m1_spaces`, `backend/tests/test_spaces.py`
- Port: ai-1 `modules/spaces` (Modell, Repository, Service) mit neuer Bereichsart

**Interfaces:**
- Consumes: `GroupRepository.group_ids_for`, `UserService.create`
- Produces:
  - Tabellen:
    - `space(id, org_id, kind, name, slug, description, icon, owner_user_id NULL, version)`; `kind ∈ {open, team, personal}`; `owner_user_id` nur bei `personal`, mit Unique-Constraint `(org_id, owner_user_id)`.
    - `space_member(space_id, member_type ∈ {user, group}, member_id, role ∈ {viewer, editor, moderator, admin})`.
  - `SpaceRole` mit Ordnung `viewer < editor < moderator < admin`.
  - `SpaceService.create(actor, kind, name, ...) -> Space`. `personal` ist nur intern erlaubt; über die API gibt es 422 `spaces.kind_not_allowed`.
  - `SpaceService.update`, `.set_member(actor, space_id, member_type, member_id, role)`, `.remove_member`, `.get(actor, space_id)`, `.list_visible(actor, PageParams)`.
  - Hook: `UserService.create` ruft `SpaceService.create_personal(user)` in derselben Transaktion auf.
  - Erweiterung von `ensure_bootstrap` (Task 4): Es legt zusätzlich den offenen Bereich „Allgemein“ (`slug=allgemein`) an, falls er fehlt. Test: `test_bootstrap_creates_allgemein_once`.
  - Routen `/api/spaces`, `/api/spaces/{id}`, `/api/spaces/{id}/members`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_new_user_gets_personal_space(owner, session):
    u = await create_user(owner, "lea@example.com")
    spaces = await list_spaces_as(u)
    assert [s["kind"] for s in spaces] == ["personal"]

async def test_personal_space_members_are_fixed(owner, member):
    r = await owner.put(f"/api/spaces/{member.personal_space_id}/members", json={"member_type": "user", "member_id": str(other.id), "role": "viewer"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "spaces.personal_members_fixed"

async def test_cannot_create_personal_via_api(member_client):
    assert (await member_client.post("/api/spaces", json={"kind": "personal", "name": "x"})).status_code == 422

async def test_guest_cannot_create_space(guest_client):
    assert (await guest_client.post("/api/spaces", json={"kind": "team", "name": "x"})).status_code == 403

async def test_space_admin_manages_members_but_viewer_cannot(...): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spaces.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Die Sichtbarkeitsprüfung kommt in Task 7. Bis dahin ruft der Service `access.can()` auf, das hier als Stub für `admin` alles und sonst nur Mitgliedschaften erlaubt. Task 7 ersetzt den Stub, und die Tests aus Task 6 müssen dann weiter grün bleiben.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "spaces: add open, team and personal spaces with members"
```

---

### Task 7: Die eine Rechteprüfung

**Files:**
- Create: `backend/app/core/permissions.py`, `backend/app/core/access.py`, `backend/tests/test_access.py`
- Modify: `backend/app/modules/spaces/service.py` (Stub ersetzen), alle Router (`require_action` statt eigener Prüfungen)
- Port: Struktur von ai-1 `core/permissions.py`

**Interfaces:**
- Produces:
  - `Action(StrEnum)` mit genau diesen Werten in M1:
    - `space.read`, `space.manage`, `space.create`,
    - `user.manage`, `group.manage`, `audit.read`.

    Weitere Werte kommen mit ihren Meilensteinen.
  - `Actor` (frozen dataclass): `org_id`, `principal`, `system_role`, `group_ids: frozenset[UUID]`, Property `is_admin`.
  - `async def actor_for(session, auth: AuthContext) -> Actor`.
  - `async def space_role(session, actor, space_id) -> SpaceRole | None`: Maximum aus direkter Rolle und Gruppenrollen. In `open`-Bereichen ist die Untergrenze für `member` die Rolle `viewer`; für `guest` gibt es keine Untergrenze.
  - `async def can(session, actor, action, space_id: UUID | None = None) -> bool`.
  - `async def require(session, actor, action, space_id=None) -> None`:
    - Ist der Bereich unsichtbar, gibt es `NotFound("space.not_found")`.
    - Ist er sichtbar, aber das Recht fehlt, gibt es `Forbidden("auth.permission_denied")`.
  - `def visible_space_ids(actor) -> Select[tuple[UUID]]`:
    - Admin: alle Bereiche der Organisation.
    - `member`: `open` ∪ Mitgliedschaften (direkt oder über Gruppe).
    - `guest`: nur Mitgliedschaften.
  - Zuordnung der Rollen zu Rechten:
    - `viewer` → `space.read`,
    - `admin` (Bereich) → zusätzlich `space.manage`,
    - Systemrolle `member` → `space.create`,
    - `admin`/`owner` → alle Rechte.

- [ ] **Step 1: Write the failing tests**

Die Tests stellen eine Matrix aus Systemrolle, Bereichsart und Mitgliedschaft auf.

```python
@pytest.mark.parametrize("kind", ["team", "personal"])
async def test_non_member_sees_neither_content_nor_existence(kind, member_client, other_space_of_kind):
    s = other_space_of_kind(kind)
    assert (await member_client.get(f"/api/spaces/{s.id}")).status_code == 404
    assert (await member_client.get(f"/api/spaces/{uuid7()}")).json()["error"]["code"] == "space.not_found"
    ids = [x["id"] for x in (await member_client.get("/api/spaces")).json()["items"]]
    assert str(s.id) not in ids

async def test_admin_sees_every_space(owner, team_space, other_personal_space): ...
async def test_open_space_readable_by_member_not_by_guest(member_client, guest_client, open_space): ...
async def test_group_role_counts_and_is_revoked_on_removal(session, member, team_space, group):
    await add_group_member(group, member); await set_space_member(team_space, group, "editor")
    assert await space_role(session, await actor_of(member), team_space.id) == SpaceRole.EDITOR
    await remove_group_member(group, member)
    assert await space_role(session, await actor_of(member), team_space.id) is None

async def test_direct_role_and_group_role_take_the_higher(...): ...   # viewer direkt + editor über Gruppe → editor
async def test_visible_space_ids_matches_can(session, actors_and_spaces):
    for actor in actors:  # SQL-Filter und Einzelprüfung dürfen nie auseinanderlaufen
        visible = set((await session.scalars(visible_space_ids(actor))).all())
        for s in spaces:
            assert (s.id in visible) == await can(session, actor, Action.SPACE_READ, s.id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_access.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`can()` lädt Systemrolle, Bereichsart und Rolle mit **einer** SQL-Abfrage. Danach ersetzt `require` in allen bisherigen Routern und Services die Ad-hoc-Prüfungen. Es gibt keine weitere Prüfstelle.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS, auch alle Tests aus Task 4–6

- [ ] **Step 5: Commit**

```bash
git commit -am "access: add single permission check and visible spaces filter"
```

---

### Task 8: Audit-Protokoll

**Files:**
- Create: `backend/app/modules/audit/*`, Migration `m1_audit`, `backend/tests/test_audit.py`
- Modify: Services aus Task 4–7 (Audit-Aufrufe)

**Interfaces:**
- Consumes: `Actor`, `require`
- Produces:
  - Tabelle `audit_log(id, org_id, actor_type, actor_id, action, target_type, target_id, details jsonb, ip, created_at)`. Sie ist nur anhängend: Das Repository bietet kein Update und kein Delete.
  - `async def record(session, actor, action: str, target_type: str, target_id: UUID, details: dict | None = None) -> None`. Der Aufruf erfolgt in der Transaktion der Änderung.
  - Protokollierte Aktionen in M1:
    - `user.created|updated|deactivated`,
    - `group.created|updated|deleted|member_added|member_removed`,
    - `space.created|updated|member_set|member_removed`,
    - `space.admin_access`: Ein Admin öffnet einen `team`/`personal`-Bereich ohne eigene Mitgliedschaft; höchstens ein Eintrag je Admin, Bereich und UTC-Tag.
  - `GET /api/admin/audit?actor_id=&action=&cursor=&limit=` mit Recht `audit.read`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_space_member_change_is_audited(owner, team_space, member): ...
async def test_admin_access_to_foreign_personal_space_is_audited_once_per_day(owner, member, session):
    for _ in range(3): await owner.get(f"/api/spaces/{member.personal_space_id}")
    rows = await audit_rows(session, action="space.admin_access")
    assert len(rows) == 1
async def test_audit_is_not_written_when_change_fails(owner, ...): ...   # Rollback-Fall
async def test_member_cannot_read_audit(member_client): ...               # 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audit.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`record` in die Services aus Task 4–7 einhängen, jeweils in der Transaktion der Änderung. Die Tagesgrenze für `space.admin_access` sichert ein Partial Unique Index auf `(actor_id, target_id, (created_at AT TIME ZONE 'UTC')::date)`, gefiltert auf diese Aktion, mit `ON CONFLICT DO NOTHING`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "audit: add append-only audit log"
```

---

### Task 9: Frontend-Gerüst, Anmeldung, Navigation, i18n

**Files:**
- Create: `frontend/*` (Vite-Projekt), `frontend/scripts/check-i18n.mjs`, `frontend/src/app/{router,shell}/*`, `frontend/src/features/auth/*`, `frontend/src/lib/{api,api-types}.ts`, `frontend/src/locales/{de,en}/common.json`
- Port: ai-1 `frontend/src/components/ui/*`, `components.json`, Vite- und TS-Konfiguration ohne assistant-ui und ai-sdk; ai-2 `scripts/check-i18n.mjs`

**Interfaces:**
- Consumes: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`, `/api/openapi.json`
- Produces:
  - `api` (openapi-fetch-Client mit `X-Requested-With: herd`, `credentials: "include"`; bei 401 Weiterleitung auf `/login`).
  - `useMe()`.
  - `<AppShell>` mit Seitenleiste nach Spezifikation 6.2. In M1 sind nur die Abschnitte „Bereiche“ und (für Admins) „Verwaltung“ sichtbar. Weitere Abschnitte werden mit ihren Meilensteinen freigeschaltet, über eine statische Liste `NAV_SECTIONS` mit Feld `milestone`.
  - Routen `/login`, `/spaces`, `/spaces/$spaceId`, `/admin/*`.

- [ ] **Step 1: Write the failing tests** (Vitest + Testing Library)

```ts
test("login posts credentials and redirects to /spaces", ...)
test("shell shows admin section only for admin/owner", ...)
test("shell hides sections of later milestones", ...)
test("every user-facing string resolves in de and en", ...)   // rendert Shell in beiden Sprachen, kein Key sichtbar
```

Zusätzlich prüft `node scripts/check-i18n.mjs`, dass `de` und `en` dieselben Schlüssel, dieselben Platzhalter und dieselben Pluralformen haben.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL

- [ ] **Step 3: Implement**

`npm run generate:api` erzeugt die Typen aus dem laufenden Backend. Die erzeugte Datei wird eingecheckt; ein CI-Schritt prüft, ob sie aktuell ist. Schriften und Icons sind selbst gehostet, es gibt keine Anfragen an Dritte. Hell- und Dunkelmodus über `next-themes`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run lint && npm run typecheck && npm test && npm run build && node scripts/check-i18n.mjs`
Expected: alles grün

- [ ] **Step 5: Commit**

```bash
git commit -am "web: add frontend shell, login and i18n"
```

---

### Task 10: Verwaltungs- und Bereichsseiten

**Files:**
- Create: `frontend/src/features/admin/{users,groups,audit}/*`, `frontend/src/features/spaces/*`, Locale-Schlüssel

**Interfaces:**
- Consumes: alle Routen aus Task 4–8
- Produces:
  - Seiten:
    - Personen (Liste, anlegen, Rolle ändern, deaktivieren),
    - Gruppen (Liste, Mitglieder),
    - Audit (Liste mit Filter),
    - Bereiche (Liste nach Art gruppiert, anlegen als `open`/`team`, Mitglieder mit Rollen, Einstellungen).
  - Jede Seite hat Lade-, Leer- und Fehlerzustand, ist mit der Tastatur bedienbar und hat Kontraste nach WCAG 2.2 AA.

- [ ] **Step 1: Write the failing tests**

```ts
test("admin creates a team space and adds a group as editor", ...)
test("409 on stale version shows reload hint and keeps the form", ...)
test("member sees no admin routes; direct navigation shows not-found", ...)
test("personal space shows no member editor", ...)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL

- [ ] **Step 3: Implement**

Formulare mit `react-hook-form` und `zod`. Das zod-Schema wird aus den erzeugten Typen abgeleitet und nicht von Hand dupliziert. Bei 409 zeigt die Seite einen Hinweis zum Neuladen und behält den Formularinhalt.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run lint && npm run typecheck && npm test && npm run build`
Expected: grün

- [ ] **Step 5: Commit**

```bash
git commit -am "web: add admin and space management pages"
```

---

### Task 11: SPA-Auslieferung, Image, Compose

**Files:**
- Create: `backend/app/web/spa.py`, `backend/tests/test_spa.py`, `Dockerfile`, `.dockerignore`, `deploy/compose/compose.yml`, `deploy/compose/.env.example`, `deploy/compose/smoke.sh`

**Interfaces:**
- Consumes: `Settings.static_dir`, `create_public_app()`
- Produces:
  - Die SPA wird unter `/` ausgeliefert. Jeder unbekannte Pfad außerhalb von `/api` liefert `index.html` aus.
  - Header für die SPA: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.
  - Image `to-herd-cats-ai`:
    - Stufen: Frontend-Build mit `node:22-slim`, Python-Abhängigkeiten mit `uv`, Laufzeit mit `python:3.13-slim` (Digest festgelegt).
    - Läuft als Benutzer `10001`, Einstiegspunkt `tini -- python -m app.launch`, `EXPOSE 8080 9090`, `HEALTHCHECK` auf `:9090/health`.
    - Funktioniert mit nur lesbarem Dateisystem plus `/tmp`.
  - Compose-Dienste:
    - `db` (`pgvector/pgvector:pg17`, Healthcheck),
    - `app` (`HERD_ROLE=all`, `read_only: true`, `tmpfs: /tmp`, `cap_drop: [ALL]`, nur Port 8080 veröffentlicht).

- [ ] **Step 1: Write the failing tests**

```python
async def test_unknown_path_serves_index(client_with_static): ...
async def test_api_404_is_json_not_index(client_with_static): ...
async def test_spa_security_headers(client_with_static): ...
```

`smoke.sh` startet die Dienste mit `docker compose up -d --wait` und meldet sich per `curl` mit dem Bootstrap-Admin an. Danach prüft es:

- `GET /api/auth/me` liefert 200,
- `:9090/ready` liefert 200 (über `docker compose exec`),
- `docker compose exec app id -u` liefert `10001`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spa.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`spa.py`, `Dockerfile`, `.dockerignore` und `deploy/compose/*` nach der Interface-Liste oben anlegen. `.env.example` enthält nur Variablennamen mit Platzhaltern, keine echten Werte.

- [ ] **Step 4: Run tests and smoke to verify they pass**

Run: `uv run pytest -v && bash deploy/compose/smoke.sh`
Expected: PASS, Smoke endet mit `SMOKE OK`

- [ ] **Step 5: Commit**

```bash
git commit -am "ops: add image, spa serving and compose reference"
```

---

### Task 12: Helm-Grundgerüst

**Files:**
- Create:
  - `deploy/helm/to-herd-cats-ai/{Chart.yaml,values.yaml,values.schema.json}`,
  - `templates/{deployment-api,job-migrate,service,service-internal,ingress,networkpolicy,servicemonitor,prometheusrule,secret-ref,_helpers.tpl}.yaml`,
  - `tests/rules-test.yaml`,
  - `scripts/check-chart-version.sh`.

**Interfaces:**
- Consumes: Image aus Task 11
- Produces:
  - `version` = `appVersion` = Version aus `backend/pyproject.toml`; `check-chart-version.sh` bricht bei Abweichung ab.
  - Jeder Wert in `values.yaml` ist mit `## @param` kommentiert. Abgedeckt werden:
    - `image.{repository,tag,digest}`, `imagePullSecrets`,
    - `api.{replicas,resources,env}`,
    - `secrets.existingSecret` (nur Name),
    - `database.{url,existingSecret}`,
    - `postgresql.enabled` (minimales pgvector-StatefulSet, nur für Test und Staging),
    - `ingress.*`,
    - `networkPolicy.{publicFrom,internalFrom,egress}`,
    - `metrics.serviceMonitor.enabled`, `metrics.prometheusRule.enabled`,
    - `tracing.otlpEndpoint`.
  - Der Migrations-Job läuft als Helm-Hook `pre-install,pre-upgrade` mit `HERD_ROLE=migrate`. Das API-Deployment läuft mit `HERD_ROLE=api`.
  - Pod Security „restricted“: `runAsNonRoot`, `readOnlyRootFilesystem`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`.
  - PrometheusRule mit `HerdNotReady` (Ready-Probe ≥ 5 min fehlerhaft) und `HerdHigh5xx` (Anteil 5xx > 5 % über 10 min). Für beide gibt es einen `promtool test rules`-Fall.

- [ ] **Step 1: Write the failing checks**

`tests/rules-test.yaml` mit einem feuernden und einem nicht feuernden Fall je Regel. `check-chart-version.sh` vergleicht `Chart.yaml` mit `backend/pyproject.toml`.

- [ ] **Step 2: Run checks to verify they fail**

Run: `bash deploy/helm/scripts/check-chart-version.sh`
Expected: FAIL (Chart fehlt)

- [ ] **Step 3: Implement**

Chart, Templates und `values.schema.json` nach der Interface-Liste oben anlegen. `values.schema.json` beschreibt jeden Wert aus `values.yaml`.

- [ ] **Step 4: Run checks to verify they pass**

Run:

```
helm lint --strict deploy/helm/to-herd-cats-ai \
  && helm template t deploy/helm/to-herd-cats-ai | kubeconform -strict -summary \
  && promtool test rules deploy/helm/to-herd-cats-ai/tests/rules-test.yaml \
  && bash deploy/helm/scripts/check-chart-version.sh
```

Expected: alles grün

- [ ] **Step 5: Commit**

```bash
git commit -am "ops: add helm chart skeleton with network policy and alerts"
```

---

### Task 13: CI, Abhängigkeitsprüfung, Veröffentlichung

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `renovate.json`

**Interfaces:**
- Produces:
  - **CI-Jobs bei jedem Push:**
    - `backend`: ruff, mypy, pytest gegen den Dienst `pgvector/pgvector:pg17`, `pip-audit`.
    - `frontend`: lint, typecheck, test, build, `check-i18n`, Aktualität von `api-types`, `npm audit --audit-level=high`.
    - `chart`: Befehle aus Task 12.
    - `image`: Docker-Build, `deploy/compose/smoke.sh`, Trivy-Scan (HIGH/CRITICAL brechen ab).
    - `licenses`: Prüft alle Laufzeitabhängigkeiten gegen die Liste erlaubter Lizenzen aus den Global Constraints.
  - **Release bei Tag `vX.Y.Z`:** Prüft Tag = `pyproject`-Version = Chart-Version. Veröffentlicht danach das Image `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y` sowie das Chart als OCI unter `ghcr.io/<owner>/charts/to-herd-cats-ai`. Anschließend wird geprüft, ob beides ohne Anmeldung abrufbar ist; wenn nicht, gibt es nur eine Warnung.

- [ ] **Step 1: Push the branch and observe CI**

Run: `git push`, dann den Workflow-Lauf ansehen.
Expected: alle Jobs grün. Ein roter Job wird an der Ursache behoben, nie durch Abschalten.

- [ ] **Step 2: Commit**

```bash
git commit -am "ci: add checks, audits and release workflow"
```

---

### Task 14: Dokumentation und Abnahme M1

**Files:**
- Create: `README.md`, `docs/STECKBRIEF.md`, `docs/demo/m1.md`
- Modify: `docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` nur, falls sich in M1 eine Entscheidung geändert hat (mit Begründung)

**Interfaces:**
- Produces:
  - **README:** Schnellstart (Compose), Entwicklung, Prüfbefehle.
  - **Steckbrief:** alle Zeilen aus Spezifikation 12.7. Ressourcen werden gemessen: `docker stats` im Leerlauf, warm, und unter Last mit 20 parallelen Logins und Bereichslisten über 60 s (Skript `deploy/compose/load.sh` mit `hey` oder `oha`). Daraus Request und Limit mit 20–30 % Puffer.
  - **Demo-Skript M1:** Admin legt zwei Team-Bereiche und zwei Personen an. Jede Person sieht nur ihren Bereich, auch per direkter URL. Der Admin sieht beide, und der Zugriff steht im Audit.

- [ ] **Step 1: Run the demo script manually against compose and record the result in `docs/demo/m1.md`**

Expected: jeder Schritt wie beschrieben

- [ ] **Step 2: Run full verification**

Run:

```
cd backend && uv run pytest && uv run ruff check . && uv run mypy app \
  && cd ../frontend && npm run lint && npm run typecheck && npm test && npm run build \
  && cd .. && bash deploy/compose/smoke.sh
```

Expected: alles grün

- [ ] **Step 3: Commit**

```bash
git commit -am "docs: add readme, fact sheet and m1 demo"
```

---

## Abdeckung der Spezifikation (Selbstprüfung)

| Spezifikation | Task |
|---|---|
| 2 E8, E9, E13, E14 | 1, 3, 11, 12 |
| 4.1 Rollen und Migrationen | 3, 11, 12 |
| 4.2 eine Rechteprüfung | 7 |
| 5.1–5.3 Principals, Systemrollen, Bereiche | 4–7 |
| 5.5 Admin-Einsicht in Bereiche | 8 |
| 12.1 OpenAPI, Fehlerform | 1, 3 |
| 12.2 Logging und Tracing | 2 |
| 12.3 Ports, Proben, Metriken | 3 |
| 12.5 Image, Helm, CI | 11–13 |
| 12.7 Steckbrief | 14 |
| 13 Übernahmen für M1 | 1, 4, 6, 7, 9 |

Bewusst **nicht** in M1, weil es in M1 keinen Leser gäbe (Regel „kein Feld für später“):

- Outbox und Worker-Rolle: in M3 mit Systemmeldungen und Benachrichtigungen,
- Tags: in M2 mit Seiten,
- SecretRef: in M5 mit KI-Verbindungen,
- SSRF-Sperre und Speicher: in M2 mit Anhängen bzw. M5,
- DBOS: in M3,
- Agent als Principal-Typ in Tabellen: in M6.
