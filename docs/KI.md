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

## Agenten (`/api/agents`, Recht `agent.manage`; persönliche: ihre Besitzer)

Agenten sind Principals wie Personen: Mitglied von Bereichen (`PUT
/api/spaces/{id}/members` mit `member_type: agent`), Teilnehmer einer Direktnachricht,
Urheber von Nachrichten (`kind: agent`).

- `GET/POST /api/agents`, `GET/PATCH/DELETE /api/agents/{id}` (`agent.manage`, für
  persönliche Agenten auch ihre Besitzer, siehe unten; sonst 404 `agent.not_found`;
  `GET /api/agents` nennt Personen mit `ai.use` ohne `agent.manage` nur ihre eigenen
  persönlichen Agenten): Name, Kurzvorstellung, Anweisungen (höchstens 20.000
  Zeichen), Verbindung und Modell (eine Chat-Verbindung, die das Modell anbietet; 422
  `ai.connection_not_chat`, `ai.model_unknown`), verantwortliche Person (aktiv, kein
  Gast; 422 `agent.responsible_invalid`), Status `draft|active|paused`, Grenzen
  `max_steps` (1–25) und `max_runtime_seconds` (10–600). Änderungen mit `version`
  (409 `agent.version_conflict`), Audit ohne den Text der Anweisungen. Wer schon
  gesprochen oder gelaufen ist, wird nicht gelöscht (409 `agent.in_use`), sondern
  pausiert.
- Antworten nennen auch `responsible_name`, den Namen der verantwortlichen Person, und
  `owner_user_id` (die Besitzerin eines persönlichen Agenten, sonst leer).
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
  nicht angeboten. Ein Werkzeug, das der Katalog nicht kennt, läuft nie. `max_level`
  nennt die höchste Stufe, die die fragende Person diesem Agenten geben darf; die
  Oberfläche bietet nur Stufen bis dahin an.
- `GET /api/agents/{id}/spaces` (`agent.manage`, seitenweise nach Name): die Bereiche,
  in denen der Agent Mitglied ist, mit seiner Rolle (offene Bereiche, die er nur liest,
  stehen nicht darin).
- `GET /api/agents/{id}/profile` (`ai.use`): Name, Kurzvorstellung, Status; Entwürfe
  sind für alle ohne `agent.manage` unsichtbar, auch beim Hinzufügen als Mitglied
  eines Bereichs (404 `agent.not_found`). Wer Agenten nicht sieht (weder `ai.use` noch
  `agent.manage`), entfernt auch keinen aus einem Bereich: 404
  `spaces.member_not_found` wie für ein unbekanntes Mitglied. Das Verzeichnis (`/api/directory`)
  nennt Agenten nur Personen mit `ai.use`.
- `POST /api/dms` mit `{"agent_id": …}` (ohne weitere Personen, sonst 422
  `dm.agent_pair_only`): die Direktnachricht der Person mit dem Agenten; ohne `ai.use`
  404 `agent.not_found`.

## Persönliche Agenten (M6)

Ein persönlicher Agent gehört einer Person (`owner_user_id`).

- **Recht** `agent.create_personal`: abgeleitet wie `ai.use`, nie gespeichert: wer
  `ai.use` hat, solange die Organisation persönliche Agenten erlaubt. `/api/auth/me`
  nennt es in `permissions`.
- **Schalter**: `PUT /api/ai/assignments/personal-agents` (`ai.manage`, Körper
  `{"enabled": false, "version": n}` mit der Version aus `GET /api/ai/assignments`, die
  auch Standard- und Gruppenzuordnung schützt; 409 bei veralteter Version; Audit
  `ai_assignment.personal_agents_set`). `GET /api/ai/assignments` nennt den Stand in
  `personal_agents` (Voreinstellung: an). Aus: niemand legt neue an, und bestehende
  persönliche Agenten antworten nicht mehr (`agent.personal_disabled`).
- **Anlegen**: `POST /api/agents` mit `{"name": …, "personal": true}`. Ohne `ai.use`
  404 `agent.not_found`; mit `ai.use`, aber abgeschaltet, 403
  `agent.personal_disabled`. Verbindung und Modell sind die der Person (ihre
  Zuordnung); gibt man sie an, müssen es diese sein (422 `ai.connection_not_found`,
  `ai.model_unknown`). Verantwortlich ist die Besitzerin selbst (eine andere Person:
  422 `agent.responsible_invalid`). Höchstens Stufe 2 (403 `agent.level_denied`, auch
  für Admins). Höchstens `HERD_AI_PERSONAL_AGENTS_MAX` (Standard 5, 0 bis 100) je
  Person (409 `agent.personal_limit`; gezählt unter einer Sperre je Person, zwei
  gleichzeitige Anlagen überschreiten die Grenze nicht).
- **Bereiche**: Der Agent ist ab der Anlage Mitglied (`editor`) im persönlichen
  Bereich seiner Besitzerin und nur dort. Jeder Versuch, ihn einem anderen Bereich
  hinzuzufügen, scheitert mit 422 `agent.personal_space_only`, auch für Admins und die
  Besitzerin; wer den Agenten nicht sehen darf, bekommt 404 `agent.not_found`.
- **Verwalten**: Die Besitzerin (mit `ai.use`) liest, ändert, pausiert und löscht ihre
  Agenten (Löschen nur ungenutzt, sonst 409 `agent.in_use`) und setzt ihre
  Werkzeugfreigaben, über dieselben Endpunkte wie `agent.manage`, mit `version` (409).
  Jede Änderung übernimmt Verbindung und Modell neu aus ihrer Zuordnung: Ändert ein
  Admin ihre Zuordnung, antwortet der Agent mit `agent.connection_unavailable`, bis er
  einmal gespeichert wird (`PATCH` nur mit `version` genügt).
- **Reden**: Nur die Besitzerin erreicht ihn: Direktnachricht, Profil, Verzeichnis und
  Erwähnungen verbergen ihn vor allen anderen, auch vor Admins (404
  `agent.not_found`). Läufe fragen daher immer als Besitzerin, ihre Rechte gelten, der
  Verbrauch wird ihr gebucht. Ein Lauf für jemand anderen (spätere Auslöser) startet
  nicht (`agent.not_found`) oder endet vor dem ersten Aufruf (`rights_revoked`).
- **Ende**: Verliert die Besitzerin `ai.use` (`ai.unavailable`), wird sie deaktiviert
  (`agent.responsible_inactive`) oder schaltet die Organisation persönliche Agenten ab
  (`agent.personal_disabled`), startet kein Lauf mehr, und ein laufender endet mit
  `rights_revoked`. Personen werden nicht gelöscht, nur deaktiviert; ein persönlicher
  Agent bleibt dann bestehen, aber unbenutzbar.
- **Admins** sehen in der Verwaltung (`GET /api/agents`, `GET /api/agents/{id}`,
  `GET /api/agents/{id}/runs`) jeden Agenten mit seinen Anweisungen („Admins dürfen
  alles sehen“); dass sie einen persönlichen Agenten einer anderen Person gezeigt
  bekamen, steht im Audit (`agent.admin_access`, einmal je Admin, Agent und UTC-Tag).

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
  - `ask_user`: stellt der fragenden Person eine Frage (Karte im Gespräch, siehe
    „Freigaben und Rückfragen“) und wartet auf die Antwort.

  Schreibende Werkzeuge (M6; `backend/app/modules/agents/toolbox/{wiki,ticket,message}_tools.py`)
  gehen durch dieselben Dienste wie Menschen, mit dem Akteur des Laufs (Rechte, Lese-
  und Schreibbereich, Rolle des Agenten, `no_ai`). Was sie schreiben, nennt den Agenten
  als Autor und den Lauf (`run_id`); Ereignisse und Zeitleisten nennen den Agenten
  (`actor.type = "agent"`, `run_id`). Nichts, was der Lauf in einem anderen Bereich
  gelesen hat, geht in einen Bereich, dessen Publikum es nicht sehen darf (Antwort
  „Not allowed: what you have read in this run …“, nichts geschrieben). Kein Werkzeug löscht, legt in den
  Papierkorb oder entscheidet Vorschläge.
  - Stufe 2: `propose_page_change`, `propose_new_page` (Vorschläge, nur mit
    `page.edit` für den Lauf), `comment_ticket` (Nachricht `kind: agent` im
    Ticket-Thread), `set_ticket_status` (höchstens Kategorie `review`; `done` und
    `cancelled` setzt nur eine Person, die Antwort nennt die erlaubten Status),
    `create_ticket` (meldend: der Agent), `link_ticket_page` (einmal je Seite).
  - Stufe 3: `update_page` in zwei Schritten: der erste Aufruf liefert den Diff zur
    aktuellen Version und ein `token` (gebunden an Lauf, Seite, Version und beide
    Inhalte), erst der zweite Aufruf mit diesem Token schreibt, als Version der Quelle
    `agent` mit neuer Generation (laufende Sitzungen enden). Nur in Bereichen mit
    `agent_write_policy = direct`, sonst die Antwort „propose instead“; eine Seite mit
    `no_ai` wird nie geschrieben (auch nicht, wenn sie zwischen Diff und Schreiben
    gesperrt wird). `assign_ticket` (an Person oder Agent, mit Grund als Kommentar im
    Ticket-Thread; Agenten nur als Mitglied mit mindestens Rolle `editor` des Bereichs).
    `post_message` nur in das Gespräch des Laufs oder in einen Kanal eines Bereichs, in
    dem der Agent Mitglied ist.
  - Jede Wirkung steht in derselben Transaktion wie ihr Journaleintrag; nach einer
    Wiederaufnahme wird der Aufruf aus dem Journal eingespielt, nicht wiederholt.
    Abgelehnte Schreibversuche nehmen alles zurück (Savepoint) und antworten mit dem
    Fehlercode (`Not allowed (…)`, `Refused (…)`, `Changed meanwhile (…)`).

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
  geantwortet), `approval_expired` (niemand hat rechtzeitig freigegeben). Die
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
  beendeter Lauf bleibt, wie er ist. Den Endpunkt beschreibt der nächste Abschnitt.

### Laufansicht und Abbruch (M6)

- `GET /api/runs` („meine Läufe“): die Läufe, die man selbst ausgelöst hat, neueste
  zuerst, seitenweise (`limit` ≤ 100, `cursor`). Filter: `agent_id`, `state`
  (`queued`, `running`, `waiting`, `done`), `stop_reason`, `since` (einschließlich) und
  `until` (ausschließlich), beide mit Zeitzone (sonst 422). Nur mit `ai.use` oder
  `agent.manage`, sonst 404 `ai.not_found`.
- `GET /api/agents/{id}/runs`: alle Läufe eines Agenten, für seine verantwortliche
  Person (mit `ai.use`) und `agent.manage`; sonst 404 `agent.not_found` wie für einen
  unbekannten Agenten. Dieselben Filter außer `agent_id`.
- `GET /api/runs/{id}`: wer den Lauf sehen darf (siehe oben), sonst 404
  `run.not_found`. Listen und Einzelansicht zeigen dieselbe Form: Agent (ID, Name),
  fragende Person (ID, Name; alle, die einen Lauf sehen, dürfen Personen nach Namen
  finden), Ort (`place`: Art des Gesprächs `dm`, `channel`, `thread_page`,
  `thread_ticket`, seine ID; Bereich, Seite und Ticketnummer nur, wenn die lesende
  Person den Bereich lesen darf, sonst leer), Zustand, Stopgrund, `attempt`,
  `recoveries`, `steps`, Start, Ende, `wait_until`, Verbrauch aus den
  Verbrauchseinträgen (`usage`: Aufrufe, Token ein/aus/gecacht, Kosten der Aufrufe mit
  Preis, sonst leer) und `cancel_requested`. Listen filtern in SQL und brauchen je
  Seite zwei Abfragen, gleich wie lang sie ist.
- `GET /api/runs/{id}/events`: das Journal wie oben (Schwärzung und Audit
  unverändert). Neu je Ereignis, wo der Schritt es festgehalten hat: `tokens_in`,
  `tokens_out`, `tokens_cached`, `cost` (Modellaufrufe mit Preis) und `duration_ms`
  (Modell- und Werkzeugaufrufe; ältere Werkzeugaufrufe ohne). Diese Zahlen sehen alle,
  denen der Lauf sichtbar ist, auch bei geschwärzten Ereignissen.
- `POST /api/runs/{id}/cancel`: abbrechen darf, wer den Lauf sehen darf (die fragende
  Person, die verantwortliche Person, `agent.manage`); sonst 404 `run.not_found`. Der
  Abbruch wird einmal gespeichert; ein Lauf in der Warteschlange oder ein wartender
  Lauf endet sofort in derselben Transaktion mit `cancelled` und seinem Hinweis im
  Gespräch, ein laufender vor seinem nächsten Schritt oder in der Transaktion seines
  Abschlusses (höchstens ein Modellaufruf, der schon unterwegs ist, wird noch bezahlt).
  Ein abgebrochener Lauf schreibt danach nichts mehr: keine Antwort und keinen neuen
  Lauf für Nachrichten, die währenddessen kamen. Ein zweiter Abbruch antwortet wie der
  erste (200); ein Lauf, der anders zu Ende ging, antwortet 409 `run.finished`. Einen
  Worker aufzuwecken ist nicht nötig: Was sofort endet, braucht keinen, und das
  Outbox-Ereignis des Hinweises weckt die Laufschleife ohnehin. Abbruch und Abschluss
  sperren beide die Zeile des Laufs: Entweder sieht der Abschluss den Abbruch
  (`cancelled`, keine Antwort), oder der Abbruch findet den Lauf beendet (409); ebenso
  gegen eine gleichzeitige Wiederaufnahme eines wartenden Laufs.

### Freigaben und Rückfragen (M6)

`backend/app/modules/agents/approvals/`. Ein Werkzeug, dessen wirksame Freigabe am
Agenten `confirm` ist, wird dem Modell angeboten wie jedes erlaubte; sein Aufruf läuft
erst nach der Freigabe einer Person:

- Der Aufruf legt eine **Freigabe** an (`approval`: Lauf, Schritt und Aufruf-ID,
  Werkzeug, kanonische Argumente, betroffene Objekte mit Version und Bereich,
  `fingerprint`), postet eine **Karte** im Gespräch des Laufs (Nachricht
  `kind: approval` des Agenten, `card: {"type", "id"}`, Text: Werkzeug und die
  genannten IDs, nie Inhalt) mit einem Aktivitätseintrag (Grund `approval`) für die
  fragende Person, und der Lauf wartet (`HERD_AI_APPROVAL_HOURS`, Standard 72).
  Ein Aufruf, der nichts ändert (die Vorschau von `update_page`), braucht keine
  Freigabe.
- **Fingerabdruck**: SHA-256 über Werkzeugname, Argumente als kanonisches JSON und
  Art, ID, Version und Bereich jedes betroffenen Objekts. Je Werkzeug: Seite
  (`propose_page_change`, `update_page` mit Token), Bereich und ggf. Elternseite
  (`propose_new_page`), Ticket (`comment_ticket`, `set_ticket_status`,
  `assign_ticket`), Bereich (`create_ticket`), Ticket und Seite (`link_ticket_page`),
  Gespräch (`post_message`); lesende Werkzeuge nur Name und Argumente.
- `POST /api/approvals/{id}/decide` (`decision: approve|reject`, `reason`, `version`):
  nur die fragende Person, und nur, wenn sie die Wirkung jetzt selbst ausführen dürfte
  (die Aktion des Werkzeugs in jedem betroffenen Bereich, mit ihren eigenen Rechten;
  403 `approval.not_permitted`; andere, die die Freigabe sehen: 403
  `approval.not_addressed`). 409: `approval.decided` (schon entschieden),
  `approval.expired`, `approval.run_ended` (Lauf beendet oder Abbruch angefordert),
  `approval.version_conflict`. Die Entscheidung setzt den Lauf in ihrer Transaktion
  wieder auf `queued` (zuerst wird der Lauf gesperrt, dann die Freigabe; der Ablauf
  sperrt in derselben Reihenfolge).
- Beim Fortsetzen: Fingerabdruck neu berechnet; weicht er ab, läuft nichts und das
  Werkzeugergebnis ist `approval_stale` (das Modell kann neu anfragen). Dann die Rechte
  des Laufs erneut (Freigabe am Agenten, Person, Agent, Aktion je Objekt): entzogen →
  `rights_revoked`. Abgelehnt → Werkzeugergebnis `approval_rejected` mit dem Grund
  (gerahmt wie jedes Ergebnis). Abgelaufen → Stopgrund `approval_expired`. Endet ein
  Lauf anders (Abbruch), sind seine offenen Freigaben und Fragen `expired`.
- `GET /api/approvals?state=pending` (seitenweise): meine. `GET /api/approvals/{id}`:
  wer den Lauf sehen darf (wie `GET /api/runs/{id}`), sonst 404
  `approval.not_found`; die Argumente (`args`) und `diff_url` nur für die fragende
  Person. `GET /api/approvals/{id}/diff`: die Seite jetzt gegen den Inhalt des Aufrufs
  (nur für die fragende Person, bei Seitenwerkzeugen).
- **Rückfragen**: `ask_user` legt `run_question` an, postet die Frage als Karte
  (`kind: question`, Aktivität `question`), der Lauf wartet. `POST
  /api/questions/{id}/answer` (`text` bis 4.000 Zeichen, `version`) nur durch die
  fragende Person (403 `question.not_addressed`; 409 `question.answered`,
  `question.expired`, `question.run_ended`, `question.version_conflict`); die Antwort
  geht als gerahmtes Werkzeugergebnis an das Modell. Ohne Antwort endet der Lauf mit
  `waiting_timeout`. `GET /api/questions/{id}` wie Freigaben (die Antwort nur für die
  fragende Person).
- Outbox und Live-Ereignisse tragen nur IDs (`approval.decided`,
  `question.answered`, `message.created` der Karte, `notification.created`).
- Die verantwortliche Person springt für die fragende nicht ein: Ein Lauf, dessen
  Person nicht mehr aktiv ist, endet vor jedem Werkzeugaufruf mit `rights_revoked`,
  fragt also nie (Läufe ohne fragende Person kommen erst mit M7).

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

## Skills (`/api/skills`, M6)

Ein Skill ist eine Anleitung im Format SKILL.md (agentskills.io): YAML-Kopf zwischen
zwei `---`-Zeilen mit `name` (1 bis 64 Zeichen: Kleinbuchstaben, Ziffern, einzelne
Bindestriche, nicht am Rand) und `description` (1 bis 1.024 Zeichen), danach die
Anweisungen in Markdown (höchstens 50.000 Zeichen). **Ein Skill ist Text: nichts darin
wird je ausgeführt**, auch keine Skripte (es gibt in v1 kein Werkzeug, das Code
ausführt). Ein Agent sieht im Kontext nur Name und Beschreibung seiner Skills; den Text
holt er mit `load_skill`.

- **Geltungsbereich:** organisationsweit oder einem Bereich zugeordnet; der Name ist
  je Organisation und Geltungsbereich eindeutig (409 `skill.name_taken`, archivierte
  eingeschlossen).
- **Rechte:** Skills gibt es nur für Personen mit `ai.use` oder `skill.manage`; für
  alle anderen antwortet jeder Skill-Pfad 404 `skill.not_found` wie für eine
  unbekannte ID. Organisationsweite Skills lesen alle mit `ai.use`, Skills eines
  Bereichs alle, die den Bereich lesen. Organisationsweite Skills verwaltet, wer
  `skill.manage` hat (Admins), Skills eines Bereichs die Moderatoren des Bereichs
  (`page.moderate`) oder `skill.manage`; wer einen Skill sieht, aber nicht verwalten
  darf, bekommt 403 `auth.permission_denied`.
- `GET /api/skills` (nach Name, Filter `space_id`, `org_wide`, `state`, `q` für einen
  Teil des Namens; seitenweise), `POST /api/skills`, `GET/PATCH /api/skills/{id}`,
  `POST /api/skills/{id}/archive` und `/unarchive` (kein Löschen; 409
  `skill.state_conflict`). Schreiben mit `version` (409 `skill.version_conflict`);
  Eingaben 422 `skill.name_invalid`, `skill.description_invalid`,
  `skill.content_invalid`.
- **Versionen:** jede Änderung von Beschreibung oder Text ist eine Version (die erste
  beim Anlegen; Umbenennen nicht). `GET /api/skills/{id}/versions`,
  `GET …/versions/{n}`, `POST …/versions/{n}/restore` (eine neue Version mit dem alten
  Stand; 404 `skill.version_not_found`).
- **Export und Import:** `GET /api/skills/{id}/export` liefert die SKILL.md.
  `POST /api/skills/import` (optional `?space_id=`) nimmt eine SKILL.md oder ein ZIP
  mit einem oder mehreren Skill-Ordnern (je Ordner eine `SKILL.md`, deren `name` dem
  Ordnernamen gleicht; höchstens vier Pfadteile tief, 100 Skills, 10 MB). Der Kopf
  wird streng geprüft (nur die Felder des Formats; `license`, `compatibility`,
  `metadata` und `allowed-tools` werden angenommen, aber nicht übernommen und als
  `ignored_fields` gemeldet). Das ZIP wird wie beim Wiki-Import gelesen (Grenzen für
  Einträge, entpackte Größe, keine Pfadtricks, kein zip64). Andere Dateien eines
  Ordners werden nicht übernommen (`file_unsupported`): ein Skill besteht hier nur aus
  seiner SKILL.md. Die Antwort nennt je Skill, was angelegt wurde und warum nicht
  (`exists`, `duplicate`, `name_mismatch`, `frontmatter_invalid`, `too_large`, …).
- **Agenten:** `GET/PUT /api/agents/{id}/skills` (`agent.manage`) zeigt und ersetzt die
  Skills eines Agenten (höchstens 50, mit der `version` des Agenten). Zuweisbar sind
  organisationsweite Skills und Skills eines Bereichs, den der Agent liest (422
  `agent.skill_not_assignable`); zwei Skills gleichen Namens 422
  `agent.skill_names_clash`. Ob ein Lauf einen Skill nutzen darf, entscheidet sich
  beim Nutzen: zugewiesen, aktiv, organisationsweit oder in einem Bereich, den der
  Lauf liest (Rechte der Person, des Agenten und Publikum des Ortes), und die
  KI-Richtlinie dieses Bereichs lässt die Verbindung des Laufs zu. Verlässt ein Agent
  einen Bereich, bleibt die Zuweisung stehen, wirkt aber nicht (`available: false`).
- Audit: `skill.created`, `skill.updated`, `skill.restored`, `skill.archived`,
  `skill.unarchived`, `skill.imported`, `agent.skills_changed`, mit Namen, Längen und
  Nummern, nie mit Beschreibung oder Text.

## Testen ohne Anbieter

`backend/tests/support/openai_stub.py` ist ein lokaler Anbieter für Tests und e2e:
`cd backend && uv run python -m tests.support.openai_stub --port 8099`, gesteuert über
`/_stub/script`, `/_stub/log`, `/_stub/reset`.
