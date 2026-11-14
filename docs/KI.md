# KI-Grundlage (M5): Verbindungen, Zuordnung, Verbrauch, Richtlinie, Agenten

Betrieb und Verwaltung der KI-Anbindung. Stand: M5, Tasks 1 bis 4 (Agenten, Laufschleife
und Oberfläche folgen).

## Verbindungen (`/api/ai/connections`, Recht `ai.manage`)

Eine Verbindung beschreibt einen Anbieter, der das OpenAI-Protokoll spricht:

| Feld | Bedeutung |
|---|---|
| `kind` | `openai`, `openai_compatible`, `b_api` (Modellname ist ein Routenname, nie Streaming), `local` (darf http und private Adressen); nicht änderbar |
| `base_url` | z. B. `https://api.openai.com/v1`; ohne Benutzerdaten, Query oder Fragment |
| `secret` | `{"value": "sk-…"}` (verschlüsselt gespeichert) oder `{"env": "HERD_AI_…"}`; `null` entfernt ihn. Antworten zeigen nur `{"set": true, "kind": "enc"}` |
| `models` | angebotene Modelle; das erste ist das Standardmodell der Verbindung |
| `param_family` | `max_completion_tokens` (GPT-5/6) oder `max_tokens` (ältere und offene Modelle) |
| `extra_body` | zusätzliche Felder je Aufruf (z. B. `reasoning_effort`); keine reservierten oder geheimnisähnlichen Schlüssel |
| `data_location` | `local`, `eu`, `external`; entscheidet mit der KI-Richtlinie des Bereichs |
| `purpose` | `chat`, `embedding`, `both` |
| `prices` | je Modell `{"input": "2.50", "output": "10"}` in Währung je Million Token; ohne Preis bleibt `cost` leer |
| `max_concurrency`, `requests_per_minute` | Grenzen für die Laufschleife (ab Task 6) |

- `POST /api/ai/connections/{id}/test` prüft mit einem kleinen Aufruf (Chat mit 16 Token
  oder ein Embedding) und antwortet mit einem Zustand: `ok`, `unauthorized`,
  `payment_required`, `forbidden`, `not_found`, `rate_limited`, `provider_error`,
  `redirect`, `timeout`, `unreachable`, `blocked`, `invalid_response`,
  `secret_unavailable`, `no_model`. Kein Wiederholen, kein Text des Anbieters.
- `POST /api/ai/connections/{id}/models` liest die Modellliste des Anbieters
  (`version` nötig); das Standardmodell bleibt vorn.
- Löschen (`DELETE …?version=`) scheitert mit 409 `ai.connection_in_use`, solange eine
  Zuordnung oder ein Agent die Verbindung nutzt.
- Abschalten (`enabled: false`), eine Änderung von `models` oder `purpose`, der
  Standardzuordnung oder der Gruppen-Zuordnungen meldet den Betroffenen
  `access.changed`: ihre Oberfläche lädt `ai.use` neu.
- Während des Anbieteraufrufs hält der Server keine Datenbankverbindung.

## Schlüssel

- `HERD_SECRET_KEY` (mindestens 32 Zeichen, `openssl rand -hex 32`): aus ihm wird per
  HKDF der Schlüssel für `enc:`-Werte abgeleitet. Ohne ihn sind nur `env:`-Verweise
  möglich (422 `secrets.key_missing`).
- `HERD_SECRET_KEY_PREVIOUS`: nur während eines Schlüsselwechsels. Ablauf: neuen Wert
  in `HERD_SECRET_KEY`, alten in `HERD_SECRET_KEY_PREVIOUS`, ausrollen,
  `cd backend && uv run python -m scripts.rotate_secrets`, danach
  `HERD_SECRET_KEY_PREVIOUS` entfernen.
- `env:`-Verweise dürfen nur Variablen mit dem Präfix `HERD_AI_` nennen, damit kein
  Datenbank-Passwort und nicht der Server-Schlüssel an einen Anbieter gehen; die
  eigenen Einstellungen `HERD_AI_EGRESS_PROXY` und `HERD_AI_CHECK_TIMEOUT_SECONDS` sind
  ausgenommen.
- Schlüssel erscheinen nie in Antworten, Protokollen, Audit-Einträgen oder
  Fehlermeldungen; Fehlerkörper der Anbieter werden verworfen.
- `HERD_AI_CHECK_TIMEOUT_SECONDS` (Standard 20): Zeitlimit für Test und Modellliste.

## Ausgehende Aufrufe (SSRF-Sperre)

`backend/app/core/egress.py` löst den Namen beim Verbindungsaufbau auf, prüft jede
Adresse und wählt nur geprüfte Adressen an (TLS weiterhin auf den Namen):

- nur `https`; die Art `local` darf auch `http` und private Adressen (RFC 1918,
  Loopback, ULA);
- nie: Link-Local, Metadaten-Adressen (169.254.169.254, 100.100.100.200,
  168.63.129.16, fd00:ec2::254), Multicast, `0.0.0.0/8`; eingebettete IPv4-Adressen
  (IPv4-mapped, 6to4, NAT64) zählen wie die eingebettete Adresse;
- keine Weiterleitungen (Zustand `redirect`), Antworten höchstens 2 MiB;
- Proxy-Variablen der Umgebung (`HTTPS_PROXY`) werden nicht beachtet. Wer Anbieter nur
  über einen Proxy erreicht, setzt `HERD_AI_EGRESS_PROXY` (`http://[user:pass@]host:port`
  oder `https://…`, vom Betrieb gesetzt und vertraut): Aufrufe an Verbindungen außer
  `local` gehen dann per `CONNECT` durch ihn; die Adressprüfung gilt weiter für das Ziel
  (Adressliterale werden auch über den Proxy geprüft), TLS bleibt Ende zu Ende auf den
  Namen des Anbieters. `local`-Verbindungen gehen nie über den Proxy.

## Wer nutzt welches Modell (`/api/ai/assignments`, `ai.manage`)

Reihenfolge: Zuordnung der Person, sonst die der ersten ihrer Gruppen (nach Position),
sonst die Standardzuordnung der Organisation. Eine Person kann ausdrücklich `no_ai`
bekommen. Gäste und deaktivierte Personen haben nie KI.

Daraus folgt das Recht **`ai.use`**: Es wird nie gespeichert, sondern bei jeder Prüfung
abgeleitet. Eine abgeschaltete Verbindung, eine reine Embedding-Verbindung oder ein
Modell, das die Verbindung nicht mehr anbietet, gibt kein `ai.use` (und es wird nicht
auf die nächste Zuordnung ausgewichen). `/api/auth/me` nennt dann `ai.use` in
`permissions` und den Modellnamen in `ai_model`; mehr über Verbindungen erfahren
Personen ohne `ai.manage` nicht. Alle KI-Endpunkte antworten Personen ohne das nötige
Recht mit 404 `ai.not_found`.

## Verbrauch (`/api/ai/usage`)

Jeder Modellaufruf und jeder Embedding-Stapel wird als `usage_record` gespeichert
(Person, Agent, Lauf, Bereich, Verbindung, Modell, Token ein/aus/gecacht, Dauer,
Kosten, wenn ein Preis hinterlegt ist; gecachte Token zählen als Eingabe).

- `GET /api/ai/usage?from=&to=&by=day|user|space|connection&run_id=` (`ai.manage`):
  Summen je Tag und Schlüssel, seitenweise. Standard: die letzten 30 Tage; höchstens
  365 Tage (422 `ai.usage_period_invalid`). `cost` ist leer, wenn kein Aufruf einen Preis
  hatte; `unpriced_calls` zählt die Aufrufe ohne Preis.
- `GET /api/ai/usage/me` (`ai.use`): die eigenen Summen, ohne Verbindungsnamen.

## KI-Richtlinie je Bereich und KI-Sperre

- `PATCH /api/spaces/{id}` (`space.manage`, mit `version`): `ai_policy` ist `any`
  (Standard), `restricted` (nur Verbindungen mit `data_location` in
  `allowed_locations`, mindestens ein Ort) oder `none` (KI sieht den Bereich nicht, keine
  Embeddings). `allowed_locations` nur zusammen mit `ai_policy`, und nur bei
  `restricted`.
- `PUT /api/pages/{id}/ai-lock` und `PUT /api/attachments/{id}/ai-lock`
  (`page.moderate`, Körper `{"no_ai": true, "version": n}`): sperrt eine Seite oder
  Datei für KI. Eine Datei auf einer gesperrten Seite gilt ebenfalls als gesperrt.
- Ein Lauf, der Inhalte aus mehreren Bereichen liest, gilt die strengste ihrer
  Richtlinien (`app/modules/ai/policy.py`); was KI lesen darf, filtern
  `ai_space_ids` und `ai_readable` (`app/modules/ai/policy_filters.py`) in SQL, in
  derselben Abfrage wie die Rechte.

## Agenten (`/api/agents`, Recht `agent.manage`)

Agenten sind Principals wie Personen: Mitglied von Bereichen (`PUT
/api/spaces/{id}/members` mit `member_type: agent`), Teilnehmer einer Direktnachricht,
Urheber von Nachrichten (`kind: agent`). In M5 ist jeder Agent Stufe 1: er liest nur.

- `GET/POST /api/agents`, `GET/PATCH/DELETE /api/agents/{id}` (nur `owner`/`admin`,
  sonst 404 `agent.not_found`): Name, Kurzvorstellung, Anweisungen (höchstens 20.000
  Zeichen), Verbindung und Modell (eine Chat-Verbindung, die das Modell anbietet; 422
  `ai.connection_not_chat`, `ai.model_unknown`), verantwortliche Person (aktiv, kein
  Gast; 422 `agent.responsible_invalid`), Status `draft|active|paused`, Grenzen
  `max_steps` (1–25) und `max_runtime_seconds` (10–600). Änderungen mit `version`
  (409 `agent.version_conflict`), Audit ohne den Text der Anweisungen. Wer schon
  gesprochen oder gelaufen ist, wird nicht gelöscht (409 `agent.in_use`), sondern
  pausiert.
- `GET /api/agents/{id}/profile` (`ai.use`): Name, Kurzvorstellung, Status; Entwürfe
  sind für alle ohne `agent.manage` unsichtbar. Das Verzeichnis (`/api/directory`)
  nennt Agenten nur Personen mit `ai.use`.
- `POST /api/dms` mit `{"agent_id": …}` (ohne weitere Personen, sonst 422
  `dm.agent_pair_only`): die Direktnachricht der Person mit dem Agenten; ohne `ai.use`
  404 `agent.not_found`.

## Läufe

Jede neue Nachricht der Person in einer solchen Direktnachricht (nicht in einem Thread)
legt in derselben Transaktion einen Lauf an. Die Antwort auf das Senden nennt ihn in
`agent_run: {"id", "reason"}`; ohne Lauf steht der Grund in `reason`:
`ai.unavailable`, `agent.paused`, `agent.draft`, `agent.responsible_inactive`,
`agent.connection_unavailable`, `run.thread_reply`. Je Gespräch läuft höchstens ein
Lauf; Nachrichten, die währenddessen kommen, beantwortet der nächste Lauf gemeinsam.

Ein Lauf arbeitet im Worker (`backend/app/worker/runs.py`,
`backend/app/modules/agents/executor.py`, Schleife `backend/app/runtime/loop.py`):

- Er liest mit den Rechten der Person, begrenzt auf die Bereiche des Agenten
  (`read_scope`): seine Mitgliedschaften und die offenen Bereiche. Vor jedem
  Modell- und Werkzeugaufruf wird das neu bestimmt; wer `ai.use` oder den Zugang zu
  einem schon gelesenen Bereich verliert, beendet den Lauf (`rights_revoked`).
- Werkzeuge: `search` (Volltext über Seiten und Tickets, nur in Bereichen, deren
  Richtlinie die Verbindung zulässt, ohne gesperrte Seiten), `read_page`,
  `read_ticket`. Ergebnisse gehen gerahmt (`<untrusted>`) und auf 8.000 Zeichen gekürzt
  an das Modell und vollständig in `run_event`.
- Vor jedem Modellaufruf: die strengste Richtlinie aller gelesenen Bereiche (das
  Gespräch selbst zählt als `any`) muss den `data_location` der Verbindung erlauben,
  sonst endet der Lauf mit `policy_blocked`, bevor etwas gesendet wird.
- Stopgründe: `completed`, `max_steps`, `deadline`, `no_progress` (dritter gleicher
  Werkzeugaufruf), `rights_revoked`, `policy_blocked`, `provider_refused` (401, 402,
  403, 429; ohne Wiederholung), `error`. Die Antwort ist eine Nachricht `kind: agent`
  mit `client_id` = Lauf-ID (genau einmal); bei jedem anderen Stopp steht im Gespräch
  ein Zeitleisten-Eintrag `system.key = "run.stopped"` mit dem Grund in
  `system.new.value`.
- Live: `run.progress` (`conversation_id`, `run_id`, `step`) nach jedem Modellaufruf,
  an die Person im Gespräch.
- `GET /api/runs/{id}` und `GET /api/runs/{id}/events` (seitenweise): für die Person,
  die gefragt hat, und die verantwortliche Person (je mit `ai.use`) und für
  `agent.manage`; sonst 404 `run.not_found`.
- Verbrauch wird je Modellaufruf einmal gebucht, in derselben Transaktion wie der
  Schritt (`run_event`, eindeutig je Lauf, Versuch und Schritt).

Betrieb:

- `HERD_RUN_CONCURRENCY` (Standard 4): Läufe je Worker zugleich; dazu begrenzt
  `max_concurrency` der Verbindung über alle Worker, `requests_per_minute` die Aufrufe
  je Minute (Fenster in der Datenbank). Der Worker braucht dafür bis zu
  `HERD_RUN_CONCURRENCY` + 3 Datenbankverbindungen; während eines Anbieteraufrufs hält
  ein Lauf keine.
- `HERD_RUN_LEASE_SECONDS` (Standard 30): Sperrfrist eines Laufs, alle 10 s erneuert.
  Stirbt ein Worker, nimmt ein anderer den Lauf nach Ablauf neu auf (Versuch + 1;
  nach drei Versuchen `error`).
- Die Läufe zählen nicht zur Bereitschaft (`/ready`) des Workers. Metriken:
  `herd_runs_total{reason}`, `herd_run_duration_seconds`, `herd_runs_queued`,
  `herd_runs_oldest_queued_seconds`, `herd_runs_stuck`; Alarme `HerdRunsStuck` und
  `HerdRunsQueued`.

## Testen ohne Anbieter

`backend/tests/support/openai_stub.py` ist ein lokaler Anbieter für Tests und e2e:
`cd backend && uv run python -m tests.support.openai_stub --port 8099`, gesteuert über
`/_stub/script`, `/_stub/log`, `/_stub/reset`.
