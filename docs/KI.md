# KI-Grundlage (M5): Verbindungen, Zuordnung, Verbrauch, Richtlinie, Agenten

Betrieb und Verwaltung der KI-Anbindung. Stand: M5, Tasks 1 bis 7 mit den Korrekturen
aus Modul-Review 1 (Verbindungen, Zuordnung, Verbrauch, Richtlinie, Agenten,
Laufschleife, Oberfläche). Hybride Suche und Embeddings (Tasks 8 bis 11) folgen.

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

## Agenten (`/api/agents`, Recht `agent.manage`)

Agenten sind Principals wie Personen: Mitglied von Bereichen (`PUT
/api/spaces/{id}/members` mit `member_type: agent`), Teilnehmer einer Direktnachricht,
Urheber von Nachrichten (`kind: agent`).

- `GET/POST /api/agents`, `GET/PATCH/DELETE /api/agents/{id}` (nur `owner`/`admin`,
  sonst 404 `agent.not_found`): Name, Kurzvorstellung, Anweisungen (höchstens 20.000
  Zeichen), Verbindung und Modell (eine Chat-Verbindung, die das Modell anbietet; 422
  `ai.connection_not_chat`, `ai.model_unknown`), verantwortliche Person (aktiv, kein
  Gast; 422 `agent.responsible_invalid`), Status `draft|active|paused`, Grenzen
  `max_steps` (1–25) und `max_runtime_seconds` (10–600). Änderungen mit `version`
  (409 `agent.version_conflict`), Audit ohne den Text der Anweisungen. Wer schon
  gesprochen oder gelaufen ist, wird nicht gelöscht (409 `agent.in_use`), sondern
  pausiert.
- Antworten nennen auch `responsible_name`, den Namen der verantwortlichen Person.
- **Autonomiestufe** `level` (1 nur lesen, 2 vorschlagen, 3 intern schreiben; Stufe 4
  kommt mit M8): neue Agenten haben Stufe 2, Agenten aus M5 wurden bei der Migration
  Stufe 1 (sie waren nur lesend gebaut). Eine Stufe über 2 vergibt nur ein Admin oder
  wer jeden Bereich verwaltet, in dem der Agent Mitglied ist (sonst 403
  `agent.level_denied`; ohne Bereiche nur Admins). Da Organisations-Agenten ohnehin
  `agent.manage` brauchen, sind das heute immer Admins.
- **Werkzeugfreigaben** (`GET/PUT /api/agents/{id}/tools`, `agent.manage`): jedes
  Werkzeug des Katalogs mit seiner Mindeststufe und Wirkung (`read`, `propose`,
  `write`), der Voreinstellung aus der Stufe (`allow` ab der Mindeststufe, sonst
  `block`), dem Eintrag des Agenten (`allow`, `confirm`, `block` oder keiner) und der
  wirksamen Freigabe (die strengere von beiden: Einträge können nur verschärfen).
  `PUT` ersetzt alle Einträge mit der `version` des Agenten (409
  `agent.version_conflict`); unbekannte Werkzeuge 422 `agent.tool_unknown`; jede
  Änderung im Audit (`agent.tools_changed`). Ein Lauf bietet dem Modell nur Werkzeuge
  mit wirksamem `allow` an und prüft die Freigabe vor jedem Aufruf neu (entzogen:
  `rights_revoked`). `confirm` wartet auf die Freigaben (M6 Task 7) und wird bis dahin
  nicht angeboten. Ein Werkzeug, das der Katalog nicht kennt, läuft nie.
- `GET /api/agents/{id}/profile` (`ai.use`): Name, Kurzvorstellung, Status; Entwürfe
  sind für alle ohne `agent.manage` unsichtbar, auch beim Hinzufügen als Mitglied
  eines Bereichs (404 `agent.not_found`). Wer Agenten nicht sieht (weder `ai.use` noch
  `agent.manage`), entfernt auch keinen aus einem Bereich: 404
  `spaces.member_not_found` wie für ein unbekanntes Mitglied. Das Verzeichnis (`/api/directory`)
  nennt Agenten nur Personen mit `ai.use`.
- `POST /api/dms` mit `{"agent_id": …}` (ohne weitere Personen, sonst 422
  `dm.agent_pair_only`): die Direktnachricht der Person mit dem Agenten; ohne `ai.use`
  404 `agent.not_found`.

## Läufe

Jede neue Nachricht der Person in einer solchen Direktnachricht (nicht in einem Thread)
legt in derselben Transaktion einen Lauf an. Die Antwort auf das Senden nennt ihn in
`agent_run: {"id", "reason"}`; ohne Lauf steht der Grund in `reason`:
`ai.unavailable`, `agent.paused`, `agent.draft`, `agent.responsible_inactive`,
`agent.connection_unavailable`, `run.thread_reply`, `run.waiting` (der Lauf des
Gesprächs wartet auf eine Antwort, siehe unten). Je Gespräch läuft höchstens ein
Lauf; Nachrichten, die währenddessen kommen, beantwortet der nächste Lauf gemeinsam.

Ein Lauf arbeitet im Worker (`backend/app/worker/runs.py`,
`backend/app/modules/agents/executor.py`, Schleife `backend/app/runtime/loop.py`):

- Er liest mit den Rechten der Person, begrenzt auf die Bereiche des Agenten
  (`read_scope`): seine Mitgliedschaften und die offenen Bereiche, und darin auf das,
  was das Publikum des Orts sehen darf, an dem er antwortet (Spec 5.6, M6;
  `backend/app/modules/agents/scope.py`):

  | Ort                                         | liest (∩ Agent)              | schreibt (`write_scope`) |
  |---------------------------------------------|------------------------------|--------------------------|
  | Direktnachricht der Person allein mit Agent | alles                        | ohne Grenze              |
  | Direktnachricht mit mehreren Personen       | Bereiche, die alle lesen     | genau diese Bereiche     |
  | Kanal, Seiten- oder Ticket-Thread in S      | S und die offenen Bereiche   | nur S                    |

  Hat S einen Gast als Mitglied (direkt oder über eine Gruppe), zählen die offenen
  Bereiche nicht (Gäste lesen keine offenen Bereiche; strenger als Spec 5.6).
  Deaktivierte Teilnehmende zählen nicht; bleibt nur die fragende Person, gilt
  „allein“. Außerhalb von `write_scope` darf der Lauf lesen, was Rechte und
  `read_scope` erlauben, aber nichts schreiben (auch kein Posten, auch für Admins);
  die eine Rechteprüfung (`core/access.py`) wendet beides auf jeden Akteur an, ohne
  Agenten zu kennen. Vor jedem
  Modell- und Werkzeugaufruf wird das neu bestimmt; wer `ai.use` oder den Zugang zu
  einem schon gelesenen Bereich verliert, beendet den Lauf (`rights_revoked`), ebenso
  ein Agent, der währenddessen pausiert oder dessen verantwortliche Person deaktiviert
  wird.
- Werkzeuge: `search` (Volltext über Seiten und Tickets, nur in Bereichen, deren
  Richtlinie die Verbindung zulässt, ohne gesperrte Seiten), `read_page`,
  `read_ticket`. Ergebnisse gehen gerahmt (`<untrusted>`) und auf 8.000 Zeichen gekürzt
  an das Modell und vollständig in `run_event`. Seit M6 außerdem (alle Stufe 1, lesend):
  - `list_tree`: ohne `space_id` die lesbaren Bereiche (Name, Art, ID), mit `space_id`
    die Seiten des Bereichs nach Pfad (ID, Pfad, Titel; kein Inhalt; Entwürfe nur mit
    Bearbeitungsrecht), seitenweise mit `cursor`.
  - `list_versions`: die Versionen einer Seite (Nummer, Zeit, Autor, Quelle, Name,
    Änderungstext; kein Inhalt), nur mit `page.edit` wie für Menschen.
  - `search_tickets`: Text und Filter (Statuskategorien, mir oder niemandem
    zugewiesen, Art, Priorität, Bereich), zuletzt geänderte zuerst.
  - `read_conversation`: nur das Gespräch, in dem der Lauf antwortet (kein Argument
    nennt ein Gespräch): neueste Nachrichten, ältere mit `before`, Antworten auf eine
    Nachricht mit `replies_to`; ohne Zeitleisten-Einträge.
  - `search_past_runs`: frühere Läufe dieses Agenten für dieselbe fragende Person
    (nie der laufende): ein Werkzeugergebnis nur, solange jeder Bereich, aus dem es
    stammt, jetzt lesbar ist und seine Richtlinie die Verbindung zulässt (dieselbe
    Regel wie bei der Schwärzung in `GET /api/runs/{id}/events`); die eigenen Worte des
    Modells nur, solange jeder Bereich lesbar ist, den ihr Lauf gelesen hat. Außerhalb
    einer Direktnachricht allein mit dem Agenten nur Läufe desselben Gesprächs.
  - `submit_result`: gibt das Ergebnis ab; sein Text ist die Antwort, der Lauf endet
    `completed` ohne weiteren Modellaufruf (auch nach einer Wiederaufnahme genau einmal).

  Listen lassen wie `search` schon in der Abfrage weg, was die Verbindung nicht
  empfangen darf (Richtlinie, `no_ai`); was nicht lesbar ist, antwortet wie nicht
  vorhanden. Jedes Ergebnis nennt die Bereiche, aus denen es stammt (`spaces`).
- Vor jedem Modellaufruf: die strengste Richtlinie aller gelesenen Bereiche (das
  Gespräch selbst zählt als `any`) muss den `data_location` der Verbindung erlauben,
  sonst endet der Lauf mit `policy_blocked`, bevor etwas gesendet wird. Gezählt wird
  der Bereich, in dem gelesen wurde, und der, in dem die gelesene Seite oder das
  Ticket jetzt liegt: wird eine Seite während des Laufs verschoben, gilt auch der neue
  Bereich (für Richtlinie und Zugang); eine seither gesperrte, gelöschte oder in den
  Papierkorb gelegte Seite und ein gelöschtes Ticket beenden den Lauf ebenfalls mit
  `policy_blocked`. Das gilt auch für Treffer der Suche.
- Der Verlauf: Gesendet werden die eigenen Nachrichten des Gesprächs (Person und
  Agent, ohne Threads). Hat eine frühere Antwort des Agenten Inhalt aus einem Bereich
  zitiert, gehört dieser Text nun zum Gespräch und geht mit dem Verlauf an das Modell,
  auch wenn der Bereich seither strenger eingestellt ist oder der Agent eine andere
  Verbindung nutzt (bewusst so entschieden: das Gespräch ist der Inhalt der Person
  und zählt als `any`). Wer das nicht will, löscht die betreffende Antwort.
- Ist die Nachricht, die einen Lauf ausgelöst hat, gelöscht, bevor er beginnt (keine
  Nachricht der Person nach der letzten Antwort), endet er mit `completed` ohne
  Aufruf, Antwort oder Hinweis.
- Stopgründe: `completed`, `max_steps`, `deadline`, `no_progress` (dritter gleicher
  Werkzeugaufruf), `rights_revoked`, `policy_blocked`, `provider_refused` (401, 402,
  403, 429; ohne Wiederholung), `error` (auch sofort, wenn ein Schritt nicht
  gespeichert werden kann oder ein Werkzeug scheitert; kein blindes Wiederholen),
  `cancelled` (Abbruch angefordert), `waiting_timeout` (niemand hat rechtzeitig
  geantwortet). Die
  Antwort ist eine Nachricht `kind: agent`
  mit `client_id` = Lauf-ID (genau einmal); bei jedem anderen Stopp steht im Gespräch
  ein Zeitleisten-Eintrag `system.key = "run.stopped"` mit dem Grund in
  `system.new.value`.
- Live: `run.progress` (`conversation_id`, `run_id`, `step`) nach jedem Modellaufruf,
  an die Person im Gespräch.
- `GET /api/runs/{id}` und `GET /api/runs/{id}/events` (seitenweise): für die Person,
  die gefragt hat, und die verantwortliche Person (je mit `ai.use`) und für
  `agent.manage`; sonst 404 `run.not_found`. Die Person, die gefragt hat, sieht ihre
  Läufe vollständig. Alle anderen sehen ein Werkzeugergebnis nur, solange sie jeden
  Bereich lesen dürfen, aus dem es stammt (jedes Ergebnis nennt seine Bereiche in
  `spaces`); sonst kommt das Ereignis mit `redacted: true` und nur Schritt,
  Werkzeugname und Quelle. Wer als Admin einen Team- oder persönlichen Bereich nur
  kraft Admin-Rechts liest, bekommt den Inhalt und einen Audit-Eintrag
  `space.admin_access` (einmal je Admin, Bereich und Tag), wie beim direkten Lesen
  einer Seite. Die eigenen Worte des Modells (Text und Argumente) gehören zum Gespräch
  und bleiben der Person vorbehalten; Admins lesen sie nur über die begründete,
  protokollierte Einsicht in Direktnachrichten, die Agenten-Nachrichten mit der
  KI-Kennzeichnung und Stopps als Hinweis zeigt. Verbrauch, Modell und Stopp sehen alle,
  denen der Lauf sichtbar ist.
- Verbrauch wird je Modellaufruf einmal gebucht, in derselben Transaktion wie der
  Schritt (`run_event`, eindeutig je Lauf, Versuch und Schritt); Ausnahmen siehe
  „Bekannte Untererfassung“.

### Journal, Wiederaufnahme, Warten, Abbruch (M6)

- **Journal**: `run_event` ist das Laufprotokoll. `seq` zählt über alle Aufnahmen eines
  Laufs fort (der Stopp hat `seq` 0), `attempt` nennt die Aufnahme, die den Schritt
  geschrieben hat. Jede Modellantwort (Text, Werkzeugaufrufe mit Argumenten, Verbrauch)
  und jedes Werkzeugergebnis (vollständig, mit den Bereichen und den gelesenen Seiten
  und Tickets) steht dort.
- **Wiederaufnahme**: Stirbt ein Worker, nimmt ein anderer den Lauf nach Ablauf der
  Sperrfrist wieder auf. Er spielt das Journal ein, ohne den Anbieter erneut zu fragen
  und ohne ein Werkzeug erneut auszuführen, und setzt nach dem letzten gespeicherten
  Schritt fort; was der Lauf gelesen hatte, zählt für Richtlinie und Rechte wie zuvor.
  Ein gespeicherter Werkzeugaufruf ohne Ergebnis (der Worker starb dazwischen) wird
  jetzt ausgeführt. Verloren geht höchstens ein Modellaufruf, dessen Antwort noch nicht
  gespeichert war (er wird wiederholt; Kosten, keine Wirkung). Der Lauf beantwortet das
  Gespräch bis zu seinem ersten Start (`started_at`), gleich in welcher Aufnahme.
- **Schreibende Werkzeuge** schreiben ihre Wirkung und ihren Journaleintrag in
  derselben Transaktion: entweder beides oder nichts. Eine Wirkung entsteht daher
  innerhalb der Datenbank genau einmal, auch wenn der Worker vor, während oder nach
  dem Schreiben stirbt.
- `attempt` zählt jede Aufnahme (auch nach dem Warten), `recoveries` nur die nach
  einem verlorenen Worker; nach der dritten solchen (`recoveries` > 2) endet der Lauf
  mit `error` (Detail `attempts`).
- **Warten**: Braucht ein Lauf eine Antwort (Freigabe, Rückfrage; ab M6 Task 7), steht
  er auf `waiting` bis `wait_until` (Freigaben: 72 Stunden). Dabei hält er nichts: keine
  Sperrfrist, keinen Worker. Das Gespräch bleibt belegt: Eine neue Nachricht startet
  keinen Lauf (`run.waiting`); wenn der wartende Lauf endet, legt er für die
  Nachrichten, die seit seinem Start gekommen sind, einen neuen Lauf an. Die Antwort
  setzt den Lauf in ihrer Transaktion wieder auf `queued`; er spielt sein Journal ein
  und führt den Werkzeugaufruf, auf den er wartete, erneut aus. Läuft `wait_until` ab,
  beendet die Laufschleife ihn mit `waiting_timeout` und einem Hinweis im Gespräch.
  `GET /api/runs/{id}` nennt `wait_until`.
- **Abbruch**: ein eigener Datensatz `run_cancel_request` (einmal je Lauf, mit der
  anfragenden Person). Geprüft wird vor jedem Schritt und in der Transaktion des
  Abschlusses; er gewinnt dort auch gegen eine fertige Antwort (`cancelled`, keine
  Antwort, ein Hinweis). Ein wartender Lauf endet bei der nächsten Runde der
  Laufschleife, ein Lauf in der Warteschlange, sobald er aufgenommen wird. Ein schon
  beendeter Lauf bleibt, wie er ist. Der Endpunkt dafür kommt mit der Laufansicht.

Betrieb:

- Protokolle: Die HTTP-Clients (`httpx`, `httpcore`, `httpx2`, `httpcore2`, `openai`)
  bleiben auch bei `HERD_LOG_LEVEL=DEBUG` auf WARNING, weil sie sonst Kopfzeilen der
  Anbieter protokollieren.
- `HERD_RUN_CONCURRENCY` (Standard 4): Läufe je Worker zugleich; dazu begrenzt
  `max_concurrency` der Verbindung über alle Worker, `requests_per_minute` die Aufrufe
  je Minute (Fenster in der Datenbank). Der Worker braucht dafür bis zu
  `HERD_RUN_CONCURRENCY` + 3 Datenbankverbindungen; während eines Anbieteraufrufs hält
  ein Lauf keine.
- `HERD_RUN_LEASE_SECONDS` (Standard 30): Sperrfrist eines Laufs, alle 10 s erneuert.
  Stirbt ein Worker, nimmt ein anderer den Lauf nach Ablauf wieder auf und setzt ihn
  aus dem Journal fort (nach der dritten Wiederaufnahme dieser Art `error`).
- Die Läufe zählen nicht zur Bereitschaft (`/ready`) des Workers. Metriken:
  `herd_runs_total{reason}`, `herd_run_duration_seconds`, `herd_runs_queued`,
  `herd_runs_oldest_queued_seconds`, `herd_runs_stuck`, `herd_runs_waiting` (Läufe, die
  auf eine Antwort warten); Alarme `HerdRunsStuck` und `HerdRunsQueued`.

## Testen ohne Anbieter

`backend/tests/support/openai_stub.py` ist ein lokaler Anbieter für Tests und e2e:
`cd backend && uv run python -m tests.support.openai_stub --port 8099`, gesteuert über
`/_stub/script`, `/_stub/log`, `/_stub/reset`.
