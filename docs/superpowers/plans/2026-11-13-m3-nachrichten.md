# M3 Nachrichten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kommunikation im Slack-Stil: Kanäle je Bereich, Direktnachrichten, Threads (auch an Wiki-Seiten), Erwähnungen, Reaktionen, Lesestand, die persönliche Ansicht „Aktivität“ und Live-Zustellung über mehrere API-Knoten. Dazu die Outbox und die Worker-Rolle, auf denen ab M4 Tickets und ab M6 Agenten aufbauen.

**Architecture:** Neues Modul `app/modules/messaging` nach dem Muster aus M1/M2 (`router → service → repository`, Rechte nur über `core/access.py`). Jede ändernde Service-Methode schreibt in derselben Transaktion einen Eintrag in `event_outbox`. Die neue Rolle `worker` verteilt die Einträge mit `FOR UPDATE SKIP LOCKED` an Handler (Benachrichtigungen, Systemmeldungen in Seiten-Threads, Live-Zustellung per `NOTIFY herd_live`). Jeder API-Knoten hält genau eine `LISTEN`-Verbindung und filtert je SSE-Verbindung nach Rechten; die Nutzlast enthält nur IDs.

**Tech Stack:** wie M2. Keine neuen Laufzeit-Abhängigkeiten im Backend (SSE über `StreamingResponse`, `LISTEN/NOTIFY` über asyncpg). Frontend: `EventSource` des Browsers, keine neue Bibliothek.

**Spec:** `docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (Abschnitte 4.3, 5.3, 5.5, 6, 12.3, 12.4, 14/M3)

---

## Entscheidungen dieses Plans

1. **Verteiler ohne DBOS.** Die Spezifikation nennt den Verteiler einen DBOS-Workflow. In M3 ist er eine einfache Schleife mit `FOR UPDATE SKIP LOCKED`, Zustellnachweis je Handler und Wiederholung mit Wartezeit. Das reicht für „mindestens einmal, Handler idempotent“ und kommt ohne neue Abhängigkeit aus. DBOS kommt mit seinem ersten echten Leser: dauerhafte, mehrstufige Agenten-Läufe (M6) und Zeitpläne (M7). Abschnitt 4.3 der Spezifikation wird in Task 12 entsprechend ergänzt.
2. **Nur Menschen als Teilnehmende.** Agenten gibt es ab M5/M6. `message.kind` kennt in M3 `human` und `system`; `agent`, `card` und `run_id` entstehen mit ihrem ersten Leser.
3. **Benachrichtigungsgründe in M3:** `mention` und `reply`. Die Aktivität hat in M3 nur den Reiter „Für mich“. Weitere Gründe und Reiter kommen mit Tickets (M4) und Agenten (M6).
4. **Erwähnungen sind strukturiert.** Der Client sendet `mentions: [user_id]`; im Text steht `@[Name](user:<id>)`. Der Server prüft, ob die Person das Gespräch sehen darf. Wer es nicht sehen darf, wird nicht benachrichtigt, und die Antwort nennt diese IDs in `not_notified`. Es wird nie geprüft oder verraten, ob jemand zu einem unsichtbaren Bereich gehört.
5. **Kein Nachspielen verpasster Ereignisse.** Nach einer Unterbrechung sendet der Server `resync`, und der Client lädt offene Ansichten neu. Das ist einfacher und kann nichts verraten.
6. **Einsicht in Direktnachrichten (F1):** nur lesend, mit Pflichtbegründung, auf 60 Minuten befristet, im Audit vermerkt (`dm.admin_access`), eigene Verwaltungsansicht. Die Teilnehmenden sehen im Gespräch den Hinweis „Von der Verwaltung eingesehen am …“.

## Global Constraints

- Alle Global Constraints aus M1 und M2 gelten unverändert, ebenso „Stand nach dem M1-Review“ im M2-Plan.
- Neue Rechte in `core/permissions.py`: `channel.post` (ab `viewer`: lesen, schreiben, reagieren), `channel.manage` (ab `moderator`: Kanäle anlegen, umbenennen, archivieren, fremde Nachrichten löschen), systemweit `dm.inspect` (nur `owner` und `admin`).
- Sichtbarkeit eines Gesprächs:
  - `channel`: wer `space.read` im Bereich des Kanals hat.
  - `dm`: nur Teilnehmende. Admins haben in DMs kein Sonderrecht außer der Einsicht.
  - `thread_page`: wer die Seite sehen darf (Entwürfe nur mit `page.edit`).
  Unsichtbare Gespräche antworten mit 404 `conversation.not_found`, nie mit 403.
- Listen und Suche filtern in SQL (`visible_space_ids`, Teilnehmer-Join), nie im Ergebnis.
- Nachrichteninhalte stehen nie im Log, nie in `NOTIFY`-Nutzlasten und nie in Metrik-Labels.
- Systemmeldungen (`kind=system`) entstehen ausschließlich in `thread_page` (ab M4 auch `thread_ticket`). Ein CHECK oder Trigger in der Datenbank verhindert sie in `channel` und `dm`.
- Grenzen: Nachricht höchstens 20.000 Zeichen; DM mit 2 bis 9 Teilnehmenden; höchstens 50 Erwähnungen je Nachricht; Kanalname 1 bis 80 Zeichen, eindeutig je Bereich (ohne Groß-/Kleinschreibung); höchstens 5 SSE-Verbindungen je Sitzung.
- Markdown wird mit demselben sicheren Renderer wie im Wiki angezeigt (kein rohes HTML, nur erlaubte Link-Schemata).
- Handler der Outbox sind idempotent. Kein Handler darf sich darauf verlassen, genau einmal zu laufen.
- `NOTIFY`-Nutzlasten bleiben unter 4.000 Bytes (Postgres erlaubt 8.000).

## Review Focus

1. **Live-Zustellung an Unberechtigte:** Einer Person wird die Mitgliedschaft entzogen, während ihre SSE-Verbindung offen ist. Erwartet wird: ab dem nächsten Ereignis keine Zustellung mehr. Dasselbe für Direktnachrichten Dritter und für eine beendete Sitzung (Verbindung wird geschlossen). Task 7.
2. **Outbox:** Ein Worker stirbt mitten in der Verteilung; zwei Worker laufen parallel. Erwartet wird: jedes Ereignis erreicht jeden Handler mindestens einmal, und die sichtbare Wirkung entsteht genau einmal (keine doppelte Benachrichtigung, keine doppelte Systemmeldung). Task 1, 6, 8.
3. **Knoten A nach Knoten B:** Eine Nachricht, die auf einem API-Prozess geschrieben wird, erscheint in einer SSE-Verbindung eines zweiten API-Prozesses. Test mit zwei echten Prozessen. Task 7, 11.
4. **Erwähnung verrät nichts:** Eine Erwähnung einer Person ohne Zugang erzeugt keine Benachrichtigung und keinen Unterschied in der Antwort, aus dem sich Bereichsmitgliedschaften ablesen lassen, außer `not_notified` für genau die angefragten IDs. Task 5, 6.
5. **Suche und Zähler:** Ungelesen-Zähler, Aktivität und Suche enthalten nie Nachrichten aus fremden DMs oder unsichtbaren Bereichen, auch nicht nach Entzug der Mitgliedschaft. Task 5, 6, 9.
6. **Einsicht ohne Spur:** Kein Weg führt an Begründung, Befristung und Audit-Eintrag vorbei; nach Ablauf antwortet die Einsicht mit 404. Task 4.
7. **Systemmeldungen im Kanal:** Kein API-Weg und kein Handler kann eine Systemmeldung in einen Kanal oder eine DM schreiben. Task 3, 8.

---

## Dateistruktur

```
backend/app/core/outbox.py                         # emit(), Modell event_outbox, event_delivery
backend/app/worker/                                # Rolle worker
  dispatcher.py handlers.py registry.py main.py
backend/app/modules/messaging/
  models.py schemas.py repository.py service.py router.py
  channels.py dms.py threads.py mentions.py reactions.py reads.py
  notifications.py activity.py inspect.py search.py
  live.py                                          # Hub: LISTEN, Filter, SSE
  handlers.py                                      # Outbox-Handler dieses Moduls
backend/app/modules/wiki/events.py                 # Ereignisse des Wikis
frontend/src/features/messaging/                   # Seitenleiste, Gespräch, Thread, Composer
frontend/src/features/activity/
frontend/src/lib/live.ts                           # EventSource-Hook mit resync
```

---

### Task 1: Outbox und Worker-Rolle

**Files:**
- Create: `backend/app/core/outbox.py`, `backend/app/worker/{main,dispatcher,registry}.py`, Migration `m3_outbox`, `backend/tests/test_outbox.py`, `backend/tests/test_dispatcher.py`
- Modify: `backend/app/launch.py` (Rolle `worker`; `all` startet sie mit), `backend/app/core/metrics.py`, `backend/app/web/internal.py` (`/ready` des Workers)

**Interfaces:**
- Produces:
  - Tabelle `event_outbox(id, org_id, type, actor_type, actor_id, space_id NULL, subject_type, subject_id, payload jsonb, created_at, dispatched_at NULL, attempts, next_attempt_at, failed_at NULL)`. `caused_by_run_id` und `depth` entstehen in M6 mit ihrem ersten Leser.
  - Tabelle `event_delivery(event_id, handler, delivered_at)` mit Primärschlüssel `(event_id, handler)`.
  - `outbox.emit(session, *, type, actor, space_id, subject_type, subject_id, payload)`: schreibt in der Transaktion des Aufrufers und ruft `NOTIFY herd_outbox` (wird beim Commit zugestellt).
  - `registry.handler(event_type_prefix, name)`: Dekorator; ein Handler bekommt `(session, event)`.
  - Verteiler: holt Stapel von 50 mit `FOR UPDATE SKIP LOCKED`, ruft je Ereignis jeden passenden Handler, dessen Zustellnachweis fehlt, **in einer eigenen Transaktion je Handler**, die auch den Nachweis schreibt. Fehler: `attempts + 1`, Wartezeit 2^n Sekunden bis höchstens 5 Minuten; nach 10 Versuchen `failed_at` und Log-Eintrag ohne Nutzlast. Wecken über `LISTEN herd_outbox`, sonst alle 2 s.
  - Aufräumen: zugestellte Ereignisse älter als 7 Tage werden stapelweise gelöscht.
  - Metriken: `herd_outbox_pending` (Gauge), `herd_outbox_dispatch_total{handler,result}`, `herd_outbox_oldest_pending_seconds`.
  - `HERD_ROLE=worker`: nur Verteiler und interner Port. Sauberes Beenden auf SIGTERM: laufenden Stapel abschließen.

- [ ] **Step 1: Write the failing tests**

```python
async def test_emit_is_part_of_the_callers_transaction(...): ...          # Rollback → kein Ereignis
async def test_each_handler_gets_each_event_once_when_all_succeed(...): ...
async def test_failed_handler_is_retried_and_others_are_not_repeated(...): ...
async def test_two_dispatchers_do_not_deliver_twice(real_commits): ...     # zwei Verbindungen
async def test_crash_between_handler_and_mark_redelivers_only_missing(...): ...
async def test_event_fails_after_ten_attempts_and_is_reported(...): ...
async def test_log_never_contains_payload(...): ...
async def test_worker_role_starts_and_stops_on_sigterm(...): ...
```

- [ ] **Step 2–5:** rot sehen, umsetzen, grün, Gates, Commit `outbox: add event outbox and worker role`

---

### Task 2: Gespräche und Kanäle

**Files:**
- Create: `backend/app/modules/messaging/{models,schemas,repository,service,router,channels}.py`, Migration `m3_conversations`, `backend/tests/test_channels.py`
- Modify: `core/permissions.py`, `core/access.py`, Einrichtung (`#allgemein` im Bereich „Allgemein“; für bestehende Installationen in der Migration)

**Interfaces:**
- Produces:
  - Tabelle `conversation(id, org_id, kind, space_id NULL, page_id NULL, name NULL, topic NULL, archived_at NULL, dm_key NULL, created_by, created_at, version)` mit CHECKs je Art (`channel` braucht `space_id` und `name`; `dm` braucht `dm_key`; `thread_page` braucht `page_id`, eindeutig).
  - `ChannelService.create(actor, space_id, name, topic)` (`channel.manage`), `.update` (Name, Thema; `version`, 409), `.archive`/`.unarchive`, `.list(actor, space_id=None, params)`: Kanäle aller sichtbaren Bereiche, paginiert, mit `space_id`, `my_role`-unabhängigen Feldern und `can_post`.
  - In `personal`-Bereichen gibt es keine Kanäle (409 `channel.not_allowed`).
  - In archivierten Kanälen kann niemand schreiben (409 `conversation.archived`); lesen bleibt möglich.
  - Routen: `GET/POST /api/spaces/{space_id}/channels`, `GET /api/channels`, `GET/PATCH /api/conversations/{conversation_id}`, `POST …/archive`, `POST …/unarchive`.
  - Ereignisse: `channel.created`, `channel.updated`, `channel.archived`.

- [ ] **Step 1: Write the failing tests** (Rechte je Rolle und Bereichsart, 404 für Unsichtbares, Namenskonflikt 409, Gast ohne Mitgliedschaft, anderer Org, Paginierung, `#allgemein` existiert nach Einrichtung)
- [ ] **Step 2–5:** Commit `messaging: add conversations and channels`

---

### Task 3: Nachrichten und Threads

**Files:**
- Create: `backend/app/modules/messaging/threads.py`, Migration `m3_messages`, `backend/tests/test_messages.py`, `backend/tests/test_message_races.py`
- Modify: `service.py`, `repository.py`, `router.py`, `schemas.py`

**Interfaces:**
- Produces:
  - Tabelle `message(id, org_id, conversation_id, parent_id NULL, author_type, author_id NULL, kind, body_md, client_id NULL, created_at, edited_at NULL, deleted_at NULL, reply_count, last_reply_at NULL)`. Eindeutig `(author_id, client_id)`, damit ein wiederholtes Senden dieselbe Nachricht liefert (200 statt zweiter Nachricht). Trigger oder CHECK: `kind=system` nur in `thread_page`.
  - `MessageService.post(actor, conversation_id, body_md, parent_id=None, client_id=None, mentions=())`: verlangt Sichtbarkeit und `channel.post` (Kanal, Seiten-Thread) bzw. Teilnahme (DM). `parent_id` muss eine Nachricht der obersten Ebene desselben Gesprächs sein (eine Ebene; sonst 422 `message.bad_parent`).
  - `.edit(actor, message_id, body_md)`: nur die eigene, setzt `edited_at`. `.delete(actor, message_id)`: eigene oder mit `channel.manage`; weiches Löschen, der Text wird geleert, Antworten bleiben.
  - `.list(actor, conversation_id, params, before=None, after=None)`: oberste Ebene, neueste zuerst, mit `reply_count`. `.replies(actor, message_id, params)`.
  - `reply_count` und `last_reply_at` werden in derselben Transaktion gepflegt (Zeilensperre auf der Elternnachricht).
  - Routen: `GET/POST /api/conversations/{conversation_id}/messages`, `GET /api/messages/{message_id}/replies`, `PATCH/DELETE /api/messages/{message_id}`.
  - Ereignisse: `message.created`, `message.updated`, `message.deleted` mit `payload = {conversation_id, message_id, parent_id}` (kein Text).

- [ ] **Step 1: Write the failing tests** (Schreiben je Rolle; Viewer darf schreiben; Gast nur mit Mitgliedschaft; fremde Nachricht bearbeiten 403 oder 404 je Sichtbarkeit; `client_id` doppelt; Antwort auf Antwort 422; archiviert 409; gelöschte Nachricht zeigt keinen Text; 20.000 Zeichen; parallele Antworten zählen richtig (echte Commits); Systemmeldung im Kanal scheitert auch per direktem Repository-Aufruf)
- [ ] **Step 2–5:** Commit `messaging: add messages and threads`

---

### Task 4: Direktnachrichten und Einsicht

**Files:**
- Create: `backend/app/modules/messaging/{dms,inspect}.py`, Migration `m3_dm`, `backend/tests/test_dms.py`, `backend/tests/test_dm_inspect.py`

**Interfaces:**
- Produces:
  - Tabelle `conversation_participant(conversation_id, principal_type, principal_id, joined_at)`; `principal_type` in M3 nur `user` (CHECK, wird in M5 erweitert).
  - `DmService.open(actor, user_ids)`: 2 bis 9 Teilnehmende einschließlich der eigenen Person; `dm_key` ist der Hash der sortierten IDs, eindeutig je Org, sodass dieselbe Gruppe immer dasselbe Gespräch bekommt (auch bei gleichzeitigem Öffnen: ein Gespräch). Nur aktive Personen; Gäste können keine DM eröffnen (403 `dm.guest_cannot_open`), aber in bestehenden antworten. Teilnehmende ändern sich nie; eine andere Gruppe ist ein anderes Gespräch.
  - `.list(actor, params)`: eigene DMs nach letzter Aktivität.
  - Deaktivierte Personen bleiben als Teilnehmende sichtbar, können aber nicht mehr lesen (Sitzung endet ohnehin).
  - **Einsicht:** Tabelle `dm_inspection(id, org_id, conversation_id, admin_id, reason, granted_at, expires_at)`.
    - `InspectService.find(actor, user_id, params)`: DMs einer Person, nur Teilnehmernamen und Zeitpunkt, keine Inhalte (`dm.inspect`).
    - `.grant(actor, conversation_id, reason)`: `reason` mindestens 10 Zeichen; schreibt Audit `dm.admin_access` mit Gespräch und Begründung; gilt 60 Minuten.
    - `.messages(actor, inspection_id, params)`: nur lesen; nach Ablauf 404.
    - Das DM-Gespräch liefert den Teilnehmenden `inspections: [{at, admin_name}]`; Transparenz gegenüber den Teilnehmenden geht vor.
  - Routen: `POST /api/dms`, `GET /api/dms`, `GET /api/admin/dm-inspect?user_id=`, `POST /api/admin/dm-inspect`, `GET /api/admin/dm-inspect/{inspection_id}/messages`.

- [ ] **Step 1: Write the failing tests** (gleiche Gruppe → gleiches Gespräch, auch parallel; Dritte 404; Admin ohne Einsicht 404 auf DM-Routen; Einsicht ohne Begründung 422; Audit-Eintrag vorhanden; abgelaufen 404; Einsicht kann nicht schreiben, reagieren oder als gelesen markieren; Routen-Wächtertest)
- [ ] **Step 2–5:** Commit `messaging: add direct messages and audited admin inspection`

---

### Task 5: Erwähnungen, Reaktionen, Lesestand

**Files:**
- Create: `backend/app/modules/messaging/{mentions,reactions,reads}.py`, Migration `m3_mentions_reactions_reads`, `backend/tests/test_mentions.py`, `backend/tests/test_reactions.py`, `backend/tests/test_reads.py`

**Interfaces:**
- Produces:
  - `message_mention(message_id, user_id)`; `post` und `edit` nehmen `mentions`. Gespeichert werden nur Personen, die das Gespräch sehen dürfen; die übrigen IDs kommen als `not_notified` zurück. Unbekannte IDs und IDs ohne Zugang sind in der Antwort nicht unterscheidbar.
  - `reaction(message_id, user_id, emoji)`, eindeutig; `emoji` ist genau ein Emoji-Graphem (Prüfung über Unicode-Eigenschaften, keine freie Zeichenkette). `PUT/DELETE /api/messages/{message_id}/reactions/{emoji}`. Nachrichten liefern Reaktionen zusammengefasst `{emoji, count, mine}`.
  - `conversation_read(conversation_id, user_id, last_read_message_id, updated_at)`. `POST /api/conversations/{conversation_id}/read {message_id}` (nur vorwärts). `GET /api/conversations/unread` → je sichtbarem Gespräch `{conversation_id, unread, mentions}`; eine SQL-Abfrage, gefiltert nach Sichtbarkeit zum Zeitpunkt der Abfrage.
  - Ereignisse: `reaction.changed`, `conversation.read` (nur an die eigene Person zugestellt).

- [ ] **Step 1: Write the failing tests** (Review Focus 4 und 5 als Tests; Reaktion doppelt ist idempotent; ungültiges Emoji 422; Zähler nach Entzug der Mitgliedschaft null)
- [ ] **Step 2–5:** Commit `messaging: add mentions, reactions and read state`

---

### Task 6: Benachrichtigungen und Aktivität

**Files:**
- Create: `backend/app/modules/messaging/{notifications,activity,handlers}.py`, Migration `m3_notifications`, `backend/tests/test_notifications.py`

**Interfaces:**
- Consumes: Outbox-Handler aus Task 1, Ereignis `message.created`
- Produces:
  - Tabelle `notification(id, org_id, user_id, reason, conversation_id, message_id, created_at, read_at NULL, done_at NULL)`, eindeutig `(user_id, message_id, reason)` (das macht den Handler idempotent).
  - Handler `notify_on_message`: `mention` für jede gespeicherte Erwähnung; `reply` für die Autorin der Elternnachricht und alle, die im Thread schon geschrieben haben. Nie an die schreibende Person selbst. Die Sichtbarkeit wird **zum Zeitpunkt der Zustellung** erneut geprüft.
  - `ActivityService.list(actor, params, only_open=True)`: liefert Einträge mit Gesprächsname, Autorin und einem Ausschnitt von höchstens 140 Zeichen; Einträge, deren Gespräch nicht mehr sichtbar ist, werden in SQL ausgefiltert. `.mark_read`, `.mark_done`, `.count_open`.
  - Routen: `GET /api/activity`, `GET /api/activity/count`, `POST /api/activity/{notification_id}/read`, `POST …/done`, `POST /api/activity/read-all`.
  - Ereignis `notification.created` (nur an die empfangende Person).

- [ ] **Step 1: Write the failing tests** (Erwähnung erzeugt genau eine Aktivität, auch wenn der Handler zweimal läuft; keine für sich selbst; Antwort benachrichtigt Thread-Beteiligte; nach Entzug verschwindet der Eintrag; fremde Benachrichtigung 404)
- [ ] **Step 2–5:** Commit `messaging: add notifications and activity`

---

### Task 7: Live-Zustellung (SSE)

**Files:**
- Create: `backend/app/modules/messaging/live.py`, `backend/tests/test_live.py`, `backend/tests/test_live_two_nodes.py`
- Modify: `handlers.py` (Handler `publish_live`), `backend/app/web/public.py` (Lebenszyklus des Hubs), `core/metrics.py`

**Interfaces:**
- Produces:
  - Handler `publish_live`: `NOTIFY herd_live, '{"t": <type>, "o": <org_id>, "c": <conversation_id>, "m": <message_id>, "u": <user_id|null>}'` für `message.*`, `reaction.changed`, `notification.created`, `conversation.read`, `channel.*`.
  - Hub je API-Prozess: eine eigene asyncpg-Verbindung außerhalb des Pools mit `LISTEN herd_live`, Wiederverbindung mit Wartezeit; nach jeder Wiederverbindung bekommen alle Clients `resync`.
  - Filter je Ereignis und Verbindung: Org gleich; bei `u` nur diese Person; sonst Sichtbarkeit des Gesprächs für die Person, **bei jedem Ereignis frisch geprüft** (eine Abfrage je Ereignis für alle verbundenen Personen, nicht je Verbindung), ohne Zwischenspeicher über Ereignisse hinweg.
  - `GET /api/stream`: `text/event-stream`, Ereignisse `message.created|updated|deleted`, `reaction.changed`, `notification.created`, `conversation.read`, `channel.changed`, `resync`; Daten sind nur IDs. Kommentarzeile als Herzschlag alle 15 s. Die Sitzung wird alle 30 s geprüft; ist sie beendet, schließt der Server. Langsame Clients: Warteschlange von 100 Ereignissen, bei Überlauf `resync` und Leeren. Sechste Verbindung derselben Sitzung: 429.
  - Die SSE-Route hält keine Datenbankverbindung aus dem Pool (Review M1, S1).
  - Header: `Cache-Control: no-store`, `X-Accel-Buffering: no`.
  - Metriken: `herd_sse_connections` (Gauge), `herd_live_events_total{type}`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_member_receives_message_event_with_ids_only(...): ...
async def test_non_member_and_other_org_receive_nothing(...): ...
async def test_revoked_member_stops_receiving_without_reconnect(...): ...
async def test_dm_event_reaches_only_participants_not_admins(...): ...
async def test_stream_closes_after_logout(...): ...
async def test_sixth_connection_is_429(...): ...
async def test_slow_client_gets_resync_instead_of_growing_queue(...): ...
async def test_stream_holds_no_pool_connection(...): ...                    # Pool der Größe 1
async def test_message_on_node_a_arrives_on_node_b(two_app_processes): ...  # zwei echte Prozesse
```

- [ ] **Step 2–5:** Commit `messaging: add live delivery over sse and listen/notify`

---

### Task 8: Seiten-Threads und Systemmeldungen

**Files:**
- Create: `backend/app/modules/wiki/events.py`, `backend/tests/test_page_threads.py`
- Modify: `wiki/service.py`, `wiki/moves.py`, `wiki/trash.py`, `wiki/versions.py` (Ereignisse schreiben), `messaging/threads.py`, `messaging/handlers.py`

**Interfaces:**
- Produces:
  - Wiki-Ereignisse in derselben Transaktion wie die Änderung: `page.created`, `page.published`, `page.moved`, `page.trashed`, `page.restored`, `page.version_restored`. Inhaltsänderungen erzeugen kein Ereignis (zu laut; Versionen zeigen sie).
  - `ThreadService.for_page(actor, page_id)`: liefert das Gespräch `thread_page` der Seite und legt es beim ersten Zugriff an (eindeutig je Seite, auch bei gleichzeitigem Zugriff).
  - Handler `page_timeline`: schreibt je Ereignis eine Systemmeldung in den Seiten-Thread, mit `body_md` als Schlüssel plus Parametern für die Übersetzung im Client (`{"key": "page.published", "actor": <id>}`), nie fertiger Text. Idempotent über einen eindeutigen Bezug auf die Ereignis-ID.
  - `GET /api/pages/{page_id}/thread` → Gespräch; Nachrichten über die Routen aus Task 3, mit `?include_system=false` zum Ausblenden.
  - Endgültiges Löschen einer Seite löscht ihren Thread samt Nachrichten, Erwähnungen, Reaktionen und Benachrichtigungen.

- [ ] **Step 1: Write the failing tests** (Thread nur für Sichtberechtigte; Entwurf nur mit `page.edit`; Veröffentlichen erzeugt genau eine Systemmeldung, auch bei doppelter Zustellung; Systemmeldung löst keine Benachrichtigung aus; Seite im Papierkorb: Thread 404; Purge räumt auf)
- [ ] **Step 2–5:** Commit `wiki: add page threads with system timeline`

---

### Task 9: Suche in Nachrichten

**Files:**
- Create: `backend/app/modules/messaging/search.py`, Migration `m3_message_search`, `backend/tests/test_message_search.py`
- Modify: `backend/app/modules/search/{service,router,schemas}.py`

**Interfaces:**
- Produces:
  - Generierte `tsvector`-Spalte und GIN-Index auf `message` (Konfiguration wie bei Seiten); gelöschte und Systemnachrichten sind ausgeschlossen.
  - `GET /api/search` bekommt `types=page,message` (Standard beide); Treffer vom Typ `message` tragen Gespräch, Autorin, Zeit und Ausschnitt. Der Filter liegt im selben SQL: Kanäle über sichtbare Bereiche, DMs über Teilnahme, Seiten-Threads über Seitensichtbarkeit. Die Einsicht gibt keinen Zugang zur Suche.

- [ ] **Step 1: Write the failing tests** (wie die Leck-Tests aus M2 Task 5, je Gesprächsart; Mutationsprobe: Filter entfernen lässt Tests scheitern)
- [ ] **Step 2–5:** Commit `search: include messages`

---

### Task 10: Oberfläche

**Files:**
- Create: `frontend/src/features/messaging/*`, `frontend/src/features/activity/*`, `frontend/src/lib/live.ts`, Tests daneben
- Modify: Seitenleiste (Abschnitte „Aktivität“, „Kanäle“, „Direkt“ vor „Bereiche“, wie in der Skizze 6.2), Wiki-Seitenansicht (Thread-Leiste), Suche (Treffer vom Typ Nachricht), Verwaltung (Einsicht)

**Interfaces:**
- Produces:
  - Gesprächsansicht: Nachrichtenliste mit Nachladen nach oben, Tagestrenner, „Neu“-Markierung ab Lesestand, Composer (Markdown, Enter sendet, Umschalt+Enter Zeile, Erwähnungen mit Auswahl aus `/api/directory`, Entwurf je Gespräch im Speicher des Tabs), Bearbeiten und Löschen eigener Nachrichten, Reaktionen, Thread-Leiste rechts.
  - Senden ist optimistisch mit `client_id`; ein Fehler markiert die Nachricht mit „Erneut senden“.
  - Seitenleiste: Kanäle der sichtbaren Bereiche und DMs mit Ungelesen-Zähler, Erwähnungen hervorgehoben; Dialoge „Kanal anlegen“ (nur mit `my_role` ≥ moderator) und „Direktnachricht“ (Personenauswahl, höchstens 8 weitere).
  - Aktivität: Liste „Für mich“ mit Sprung ins Gespräch, „Erledigt“, „Alle gelesen“; Zähler in der Seitenleiste und im Fenstertitel.
  - Wiki: Leiste „Diskussion“ an der Seite mit Schalter „Systemmeldungen ausblenden“; Systemmeldungen als graue Zeitleisten-Einträge, übersetzt aus Schlüssel und Parametern.
  - Verwaltung: „Einsicht in Direktnachrichten“ mit Personensuche, Begründungsfeld, Ablaufanzeige, nur lesender Ansicht; nur mit `dm.inspect` aus `/auth/me`.
  - `useLive()`: eine `EventSource` je Tab, Wiederverbindung mit Wartezeit; Ereignisse invalidieren gezielt TanStack-Query-Schlüssel; `resync` invalidiert alle Gesprächs-, Zähler- und Aktivitätsabfragen. Kein Inhalt aus Ereignissen wird angezeigt, es wird immer nachgeladen.
  - Alle Texte über i18n (de, en); Lade-, Leer- und Fehlerzustände; Tastaturbedienung; `aria-live` für neue Nachrichten.

- [ ] **Step 1: Write the failing component tests** (Sichtbarkeit von Aktionen nur aus `permissions` und `my_role`; optimistisches Senden und Fehlerfall; `resync` invalidiert; Systemmeldungen ausblenden; Einsicht nur mit Recht)
- [ ] **Step 2: Implement; Step 3: Browser-Durchlauf** mit Playwright gegen die echte App (Rolle `all`, Wegwerf-Datenbank): zwei Personen in zwei Kontexten schreiben im Kanal und sehen einander live; Erwähnung erscheint in der Aktivität; DM; Thread; Seiten-Diskussion mit Systemmeldung; Einsicht. Screenshots nach `.superpowers/sdd/m3/screens/`. Konsole ohne CSP-Verstöße.
- [ ] **Step 4–5:** Gates; Commits `web: add channels, direct messages and threads`, `web: add activity and live updates`

---

### Task 11: Auslieferung

**Files:**
- Modify: `deploy/compose/*`, `deploy/helm/to-herd-cats-ai/*`, `deploy/compose/smoke.sh`, `Dockerfile` nur falls nötig, `.github/workflows/ci.yml`

**Interfaces:**
- Produces:
  - Compose: `HERD_ROLE=all` enthält den Worker. Für den Abnahmetest ein zweites Profil mit zwei API-Diensten und einem Worker.
  - Helm: eigenes Deployment `worker` (Replikas einstellbar, Standard 1; mehrere sind sicher), Proben auf 9090; PrometheusRule `HerdOutboxBacklog` (ältestes offenes Ereignis > 5 min) und `HerdOutboxFailed`; NetworkPolicy für den Worker (nur Datenbank); Hinweise und Annotationen für SSE am Ingress (Pufferung aus, Lese-Timeout ≥ 1 h) in `values.yaml` und README.
  - `smoke.sh`: Nachricht senden und über `/api/stream` empfangen; im Zwei-Knoten-Profil: senden an Knoten A, empfangen an Knoten B.
  - Regeltests (`promtool`) für die neuen Alarme; `check-chart-rules.sh` erweitert.

- [ ] **Steps:** Tests und Skripte zuerst; `helm lint --strict` mit allen Wertedateien; Commit `ops: add worker deployment, sse hints and outbox alerts`

---

### Task 12: Dokumentation und Abnahme M3

**Files:**
- Modify: `README.md`, `docs/STECKBRIEF.md`, `CLAUDE.md`, Spezifikation (4.3 Verteiler ohne DBOS bis M6; 6 und 14/M3, wo anders entschieden)
- Create: `docs/demo/m3.md`

**Interfaces:**
- Produces:
  - Demo: Die beiden Abnahmesätze aus 14/M3 werden wirklich ausgeführt und protokolliert („Eine Nachricht auf Knoten A erscheint live auf Knoten B; eine Erwähnung erzeugt eine Aktivität“), dazu Entzug der Mitgliedschaft bei offener Verbindung und die Einsicht mit Audit-Eintrag.
  - Steckbrief: neue Rolle, Metriken, Alarme; Messung mit 200 offenen SSE-Verbindungen und 20 Nachrichten je Sekunde über 60 s (Speicher und CPU von API und Worker, Verzögerung bis zur Zustellung). Ehrlich messen; was hier nicht messbar ist, steht als nicht gemessen im Dokument.

- [ ] **Steps:** Demo ausführen und protokollieren; alle Gates; Commit `docs: add m3 demo, fact sheet and operations notes`

---

## Abdeckung der Spezifikation (Selbstprüfung)

| Spezifikation | Task |
|---|---|
| 4.3 Outbox, Verteiler, Schleifenschutz (Tiefe erst M6) | 1 |
| 5.3 `channel.post`, `channel.manage`; `#allgemein` | 2 |
| 5.5 Einsicht in Direktnachrichten | 4 |
| 6.1 Modell (ohne `card`, `run_id`, Agenten) | 2–6 |
| 6.2 Trennung von System und Gespräch; Aktivität „Für mich“ | 3, 6, 8, 10 |
| 6.4 Live-Zustellung, nur IDs, Filter je Verbindung | 7 |
| 12.3 Metriken Outbox und SSE | 1, 7 |
| 12.4 mehrere API-Knoten | 7, 11 |
| 14/M3 Abnahme | 7, 11, 12 |

Nicht in M3: Ticket-Threads und verlinkte Ticket-Karten (M4), Agenten in Gesprächen und Fortschrittskarten (M5/M6), Reiter „Freigaben“ und „Abläufe“ (M6/M7), `presence` über den Lesestand hinaus.
