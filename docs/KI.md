# KI-Grundlage: Verbindungen, Zuordnung, Verbrauch, Richtlinie

Betrieb und Verwaltung der KI-Anbindung. Stand: M5 Tasks 1 bis 7 (mit den Korrekturen
aus Modul-Review 1) und M6. Hybride Suche und Embeddings (M5 Tasks 8 bis 11) folgen.

Agenten, Läufe, Werkzeuge, Freigaben, Skills, Gedächtnis und ihr Betrieb (Worker,
Metriken, Alarme) stehen in [`AGENTEN.md`](AGENTEN.md).

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
| `max_concurrency`, `requests_per_minute` | Grenzen für Läufe über alle Worker ([`AGENTEN.md`](AGENTEN.md#wie-ein-lauf-arbeitet)) |

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
  `HERD_SECRET_KEY_PREVIOUS` entfernen. Das Skript schlüsselt alle `enc:`-Werte in einer
  Transaktion neu um (alles oder nichts) und nennt nur ihre Zahl. Das Image enthält
  `backend/scripts/` nicht: den Wechsel aus einem Quellstand desselben Release starten,
  mit derselben Datenbank und beiden Schlüsseln in der Umgebung.
- `env:`-Verweise dürfen nur Variablen mit dem Präfix `HERD_AI_` nennen, damit kein
  Datenbank-Passwort und nicht der Server-Schlüssel an einen Anbieter gehen; die
  eigenen Einstellungen mit diesem Präfix (`HERD_AI_EGRESS_PROXY`,
  `HERD_AI_CHECK_TIMEOUT_SECONDS`, `HERD_AI_APPROVAL_HOURS`,
  `HERD_AI_PERSONAL_AGENTS_MAX`, künftig jede weitere) sind ausgenommen.
- Wo die Schlüssel herkommen: Compose aus der optionalen Datei `deploy/compose/ai.env`,
  Helm aus dem Secret `ai.existingSecret` (an API und Worker); Einzelheiten in
  [`AGENTEN.md`](AGENTEN.md#umgebungsvariablen).
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
  `local` gehen dann per `CONNECT` durch ihn. Namen löst dann der Proxy auf, nicht der
  Server: hier geprüft werden nur noch das Schema und Ziele, die als Adresse geschrieben
  sind (Adressliterale); was ein Name dahinter erreicht, verantwortet der Proxy. TLS
  bleibt Ende zu Ende auf den Namen des Anbieters. `local`-Verbindungen gehen nie über
  den Proxy und werden immer hier geprüft.

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

- `GET /api/ai/usage?from=&to=&by=user|agent|space|connection&run_id=` (`ai.manage`):
  Summen je UTC-Tag, ohne `by` nur je Tag, mit `by` zusätzlich je Person, Agent,
  Bereich oder Verbindung (mit Namen, soweit bekannt); seitenweise. Standard: die
  letzten 30 Tage; höchstens 365 Tage (422 `ai.usage_period_invalid`). `cost` ist leer,
  wenn kein Aufruf einen Preis hatte; `unpriced_calls` zählt die Aufrufe ohne Preis.
  Gebucht wird auf das Modell, an das der Aufruf ging (das des Agenten beim Start des
  Laufs).
- `GET /api/ai/usage/me` (`ai.use`): die eigenen Summen, ohne Verbindungsnamen.

Bekannte Untererfassung (beides selten, beides nur zu wenig gezählt, nie doppelt):

- Stirbt ein Worker während eines Anbieteraufrufs oder verliert er seine Sperrfrist,
  ist dieser Aufruf bezahlt, aber nicht gebucht; der nächste Versuch bucht nur seine
  eigenen Aufrufe.
- Kann ein Schritt nicht gespeichert werden (etwa ein Datenbankfehler beim Schreiben von
  `run_event`), endet der Lauf sofort mit `error`; der Verbrauch des Aufrufs wird in
  einer eigenen Transaktion nachgebucht. Scheitert auch das, fehlt dieser eine Aufruf.
  Zeichen, die die Datenbank nicht speichern kann (NUL, einzelne Surrogate), entfernt
  der Server vorher aus Text und Argumenten des Modells, damit es dazu nicht kommt.

## KI-Richtlinie je Bereich und KI-Sperre

Beides ist Verwaltung, nicht Nutzung: wer den Bereich verwaltet oder moderiert, setzt
Richtlinie und Sperre auch ohne eigenes `ai.use` (die Oberfläche bietet sie dann
ebenso an). Leser ohne KI sehen von beidem nichts.

- `PATCH /api/spaces/{id}` (`space.manage`, mit `version`): `ai_policy` ist `any`
  (Standard), `restricted` (nur Verbindungen mit `data_location` in
  `allowed_locations`, mindestens ein Ort) oder `none` (KI sieht den Bereich nicht, keine
  Embeddings). `allowed_locations` nur zusammen mit `ai_policy`, und nur bei
  `restricted`.
- `PUT /api/pages/{id}/ai-lock` und `PUT /api/attachments/{id}/ai-lock`
  (`page.moderate`, Körper `{"no_ai": true, "version": n}`): sperrt eine Seite oder
  Datei für KI. Eine Datei auf einer gesperrten Seite gilt ebenfalls als gesperrt.
- Für einen Lauf, der Inhalte aus mehreren Bereichen liest, gilt die strengste ihrer
  Richtlinien (`app/modules/ai/policy.py`); was KI lesen darf, filtern
  `ai_space_ids` und `ai_readable` (`app/modules/ai/policy_filters.py`) in SQL, in
  derselben Abfrage wie die Rechte.

## Agenten

Agenten nutzen diese Verbindungen: Ein Agent hat eine Chat-Verbindung und ein Modell,
handelt im Auftrag einer Person mit `ai.use`, und sein Verbrauch wird ihr gebucht. Vor
jedem Modellaufruf gilt die strengste KI-Richtlinie der Bereiche, die der Lauf gelesen
hat (`policy_blocked`); Seiten mit `no_ai` liest und schreibt er nie. Alles Weitere
(Agenten anlegen, Stufen und Werkzeuge, die Publikumsregel, Läufe, Freigaben, Skills,
Gedächtnis, persönliche Agenten, Worker-Betrieb, Metriken und Alarme) steht in
[`AGENTEN.md`](AGENTEN.md).

## Testen ohne Anbieter

`backend/tests/support/openai_stub.py` ist ein lokaler Anbieter für Tests und e2e:
`cd backend && uv run python -m tests.support.openai_stub --port 8099`, gesteuert über
`/_stub/script`, `/_stub/log`, `/_stub/reset`.

- Er bietet die Modelle `gpt-6-luna`, `gpt-6-luna-mini` und `text-embedding-3-small`
  an und antwortet ohne Skript mit „stub reply“. In der KI-Verwaltung eine Verbindung
  der Art `local` mit `base_url` `http://127.0.0.1:8099/v1` (ohne Schlüssel) anlegen,
  testen und als Standardzuordnung wählen; danach einen Agenten anlegen und ihm eine
  Direktnachricht schreiben (ein Worker muss laufen, z. B. `HERD_ROLE=all`).
- `POST /_stub/script` mit `{"replies": [{"content": "…"}, {"tool_calls": [{"name":
  "search", "arguments": {"query": "…"}}]}]}` legt die nächsten Antworten fest (eine je
  Modellaufruf, über alle Läufe hinweg), `{"delay": 1}` verzögert jede Antwort,
  `{"failures": [429]}` lässt den nächsten Aufruf scheitern. `GET /_stub/log` zeigt, was
  ein Anbieter bekommen hätte (mit Kopfzeilen: nur zum Testen).
- Der Stub ist Testcode, nicht Teil des Images.
