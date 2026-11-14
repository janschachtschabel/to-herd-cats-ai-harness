# M5 KI-Grundlage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die zentrale KI-Anbindung: Admins richten Verbindungen ein und ordnen sie Personen und Gruppen zu; wer keine Zuordnung hat, sieht keine KI-Funktion. Dazu Verbrauchserfassung, die KI-Richtlinie je Bereich, ein erster Agent als Gesprächspartner in einer Direktnachricht (Stufe 1, nur lesen), lokale Embeddings mit Hybridsuche und die Umwandlung hochgeladener Dateien in Markdown.

**Architecture:** Neues Modul `app/modules/ai` (Verbindungen, Zuordnung, Verbrauch, Richtlinie) und `app/modules/agents` (Profil, Lauf). Die Agenten-Schleife liegt in `app/runtime/` und ist der einzige Ort, der Pydantic AI importiert. Ein Lauf entsteht in der Transaktion der auslösenden Nachricht (`run`, Zustand `queued`); die Worker-Rolle führt ihn in einer eigenen Schleife aus (`FOR NO KEY UPDATE SKIP LOCKED`, Zeitlimit), getrennt vom Outbox-Verteiler. Jeder Werkzeugaufruf geht durch die Service-Schicht mit dem `Actor` des Laufs. Embeddings berechnet der Worker lokal; die Suche verbindet Volltext und Vektor in einer Abfrage mit dem Rechtefilter.

**Tech Stack:** neu im Backend: `pydantic-ai-slim[openai]` (MIT; nur unter `app/runtime/`), `cryptography` (Apache-2.0/BSD) für `enc:`-Geheimnisse, `pgvector` (MIT, SQLAlchemy-Typ), für Embeddings je nach Entscheidung F4 `model2vec` (MIT) oder `onnxruntime` (MIT) mit `tokenizers` (Apache-2.0); kein Torch im Hauptimage. Docling (MIT) nur im Zusatz-Image der Rolle `convert` (Entscheidung 9). Vor der Arbeit mit Pydantic AI, pgvector, model2vec, onnxruntime und Docling die aktuelle Dokumentation lesen (Context7), nicht aus dem Gedächtnis arbeiten.

**Spec:** `docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md` (Abschnitte 5.1, 5.2, 5.4, 5.6, 6.3, 7, 8.1 bis 8.3 soweit Stufe 1, 11 Suche und Dateien, 12, 14/M5)

---

## Entscheidungen dieses Plans

1. **Läufe ohne DBOS.** Ein Lauf der Stufe 1 ist kurz, liest nur und wartet auf niemanden. Er läuft in einer Schleife des Workers mit Zeitlimit. Stirbt der Worker mitten im Lauf, nimmt ein anderer Worker den Lauf nach Ablauf der Sperrfrist wieder auf und beginnt ihn neu; weil Stufe 1 nichts schreibt außer der Antwort, ist das gefahrlos. Die Antwort entsteht genau einmal (`client_id` = Lauf-ID). DBOS kommt in M6 mit Freigaben und mehrstufigen, wartenden Läufen. *Geändert in M6 [Claude, 14.11.2026]: Auch M6 nutzt kein DBOS: Läufe setzen nach einem Absturz aus ihrem Journal fort, statt neu zu beginnen (Plan M6, Entscheidung 1; Spezifikation E10).*
2. **Agent in M5 = Gesprächspartner in einer Direktnachricht zu zweit.** Tabelle `agent` mit den Feldern, die M5 liest: Name, Kurzvorstellung, Anweisungen, Verbindung und Modell, verantwortliche Person, Status (`draft`, `active`, `paused`), Grenzen (Schritte, Laufzeit). Keine Autonomiestufe als Feld (alle Agenten sind Stufe 1), keine Werkzeugliste, keine Skills, kein Gedächtnis: das kommt mit M6. Erwähnungen in Kanälen, Gruppen-DMs mit Agenten, Ticketzuweisung, Laufansicht und Abbruchknopf kommen mit M6. *Geändert in M6 [Claude, 14.11.2026]: Gruppen-DMs mit Agenten kamen auch mit M6 nicht; ein Agent ist nur in Direktnachrichten mit genau einer Person (`dm.agent_pair_only`).*
3. **Agenten sind Principals.** `PrincipalType.AGENT` wird überall zugelassen, wo M5 es braucht: Bereichsmitgliedschaft, DM-Teilnahme, Urheberschaft von Nachrichten (`kind=agent`, mit `run_id`). Die Rechteprüfung behandelt Agenten nicht gesondert: Der `Actor` eines Laufs trägt die Schnittmenge aus den Bereichen des Agenten und denen der auslösenden Person (`read_scope`, Spezifikation 5.6), und `can()` sowie die sichtbaren Bereiche wenden sie an.
4. **Werkzeuge der Stufe 1:** `search` (Hybridsuche über Seiten, Tickets, Dateien im Lesebereich), `read_page`, `read_ticket`. Jede Werkzeugantwort wird als nicht vertrauenswürdige Daten gerahmt und für das Modell gekürzt. Nachrichten anderer Gespräche liest der Agent in M5 nicht.
5. **`ai.use` ist abgeleitet.** Es gibt eine Standardzuordnung der Organisation (kann leer sein: dann hat niemand KI, bis ein Admin zuordnet), Zuordnungen je Gruppe (geordnete Liste, die erste passende gewinnt) und je Person (Verbindung und Modell oder ausdrücklich „keine KI“). Vorrang: Person vor Gruppe vor Standard. `/auth/me` liefert `ai.use` in `permissions`; Gäste haben es nie.
6. **Geheimnisse.** `secret_ref` ist `env:NAME` oder `enc:<Chiffrat>` (Fernet mit `HERD_SECRET_KEY`; ohne Schlüssel sind nur `env:`-Verweise möglich). Der Klartext wird nur im Augenblick des Aufrufs gebildet, erscheint in keiner API-Antwort, keinem Log, keiner Fehlermeldung und keinem Audit-Eintrag. Die Antwort nennt nur „gesetzt“ und die Art des Verweises.
7. **Ausgehende Aufrufe.** Jede Basis-URL geht durch eine SSRF-Sperre (`core/egress.py`): nur `https` (für `local` auch `http`), Namensauflösung vor dem Aufruf und Bindung an die geprüfte Adresse, keine Weiterleitungen. Verbindungen der Art `local` dürfen private Adressen ansprechen, alle anderen nicht; Link-Local- und Metadaten-Adressen sind immer gesperrt.
8. **Embeddings nur für Seiten, Tickets und umgewandelte Dateien.** Nachrichten bleiben bei der Volltextsuche (Menge, und Direktnachrichten sollen in keinen Vektorindex). Das Modell ist nach F4 fest; Dimension und Modellname stehen in einer Zeile `embedding_index` und in der Migration. Ohne geladenes Modell arbeitet die Suche nur mit Volltext, ohne Fehler.
9. **Docling in einem Zusatz-Image.** Docling zieht Torch und mehrere Gigabyte nach. Das Hauptimage bleibt schlank; die Rolle `convert` läuft in einem zweiten Image (`to-herd-cats-ai-convert`, gleiche Codebasis, Extra `convert`), im Chart als abschaltbares Deployment (Standard aus), in Compose als Profil. Ohne diese Rolle bleiben PDF- und Office-Dateien normale Anhänge; HTML, Text und Markdown wandelt der gewöhnliche Worker selbst um. Das weicht von E13 („ein Image“) ab und wird in der Spezifikation vermerkt; Jan kann es umkehren.
10. **Kein Budget in M5.** Erfasst wird der Verbrauch je Aufruf; Grenzen je Lauf (Schritte, Laufzeit) gelten. Tagesbudgets kommen wie geplant mit M7.
11. **Preise sind optional.** Je Verbindung und Modell kann ein Preis je Million Tokens (ein, aus) hinterlegt werden; ohne Preis bleiben die Kosten leer und werden nicht geschätzt.

## Offen bis zur Antwort von Jan (F4)

Die Modellwahl für Embeddings fällt nach dem Vergleich in Task 8. Task 8 braucht Netzzugriff auf Hugging Face; ohne ihn bleiben Task 8 bis 11 liegen, Task 1 bis 7 und 12 hängen nicht daran. Kein Ersatzergebnis erfinden.

## Global Constraints

- Alle Global Constraints aus M1 bis M4 gelten unverändert.
- Neue Rechte: systemweit `ai.manage` (nur `owner`, `admin`: Verbindungen, Zuordnung, Verbrauch), `agent.manage` (nur `owner`, `admin`: Agenten anlegen und ändern), abgeleitet `ai.use`. Bereichsbezogen gehört die KI-Richtlinie zu `space.manage`; die KI-Sperre einer Seite oder Datei (`no_ai`) setzt, wer `page.moderate` hat.
- **Personen ohne `ai.use` sehen keine KI-Funktion:** keine Agenten in der Personenauswahl für neue Direktnachrichten, kein Menüpunkt, keine Verwaltung; die API antwortet für sie auf KI-Endpunkte mit 404, nicht 403. Beiträge von Agenten in Gesprächen, die sie sehen dürfen, lesen sie normal.
- **Kein Inhalt an eine unzulässige Verbindung.** Vor jedem Modellaufruf wird geprüft: Die Verbindung des Agenten erfüllt die strengste Richtlinie aller Inhalte, die der Lauf bisher gelesen hat (einschließlich des Gesprächs selbst). Sonst endet der Lauf mit `policy_blocked`, bevor ein Byte gesendet wird. Bereiche mit `none` und Inhalte mit `no_ai` liefert kein Werkzeug aus; sie tauchen auch nicht als Treffer, Titel oder Zähler auf.
- Der Lesebereich eines Laufs ist nie größer als das, was die auslösende Person in diesem Augenblick sehen darf. Er wird vor jedem Werkzeugaufruf neu bestimmt; entzogene Rechte beenden den Lauf mit `rights_revoked`.
- Prompts, Modellantworten, Werkzeugargumente und -antworten stehen nie im Log und nie in Metrik-Labels. Sie stehen in `run_event` und sind dort nur für die auslösende Person, die verantwortliche Person und Admins lesbar (in M5 ohne Oberfläche außer der Fortschrittsanzeige; die Laufansicht kommt mit M6).
- Fehler des Anbieters (401, 402, 403, 429, Zeitüberschreitung) werden zu `provider_refused` oder `error` mit einem verständlichen, übersetzten Grund ohne Antworttext des Anbieters; 401/402/403 ohne Wiederholung.
- Grenzen: Anweisungen eines Agenten höchstens 20.000 Zeichen; Gesprächsverlauf für den Prompt nach Zeichen begrenzt (`history_window`, Standard 24.000); Werkzeugantwort im Prompt höchstens 8.000 Zeichen; je Lauf höchstens 25 Schritte und 10 Minuten (am Agenten einstellbar, nach oben begrenzt); je Gespräch höchstens ein Lauf zugleich (Advisory Lock), weitere Nachrichten warten. *Geändert in M6 [Claude, 14.11.2026]: Statt der Advisory-Sperre sichern eindeutige Teilindizes je Gespräch einen laufenden und einen aktiven Lauf; seit M6 gilt das je Bahn (in Kanälen je Thread, Plan M6, Entscheidung 6). Nur das Beanspruchen serialisiert sich auf einer Sperre je Transaktion.*
- Pydantic AI wird nur unter `backend/app/runtime/` importiert; ein Test prüft das.
- Tests brauchen keinen echten Anbieter: Die Schleife wird mit den Testmodellen von Pydantic AI geprüft, die Verbindungsschicht gegen einen lokalen Stub-Server, der das OpenAI-Protokoll spricht (auch Fehlerfälle und langsame Antworten).

## Review Focus

1. **Richtlinie hält (Abnahme 14/M5):** Ein `restricted`-Bereich erreicht nie eine `external`-Verbindung: über Suche, `read_page`, `read_ticket`, Gesprächsverlauf, Dateien, Embeddings, Titel in Trefferlisten. Der Stub-Server protokolliert jede Anfrage; der Test durchsucht die Protokolle nach einem Kennwort aus dem Bereich.
2. **Keine KI ohne Zuordnung:** Person ohne `ai.use` findet keinen Weg, einen Lauf auszulösen (DM anlegen, in bestehende DM schreiben nach Entzug, direkte API), und sieht keine KI-Oberfläche.
3. **Lesebereich:** Ein Agent mit Mitgliedschaft in Bereich A, ausgelöst von einer Person ohne Zugang zu A, liest nichts aus A; und umgekehrt. Entzug während des Laufs.
4. **Geheimnisse:** Schlüssel in keiner Antwort, keinem Log (auch nicht bei Fehlern des HTTP-Clients), keinem Audit, keinem `run_event`; Rotation des `HERD_SECRET_KEY` dokumentiert.
5. **SSRF:** private Adressen, Weiterleitungen, DNS-Wechsel zwischen Prüfung und Aufruf, IPv6-Schreibweisen, Metadaten-Adresse.
6. **Prompt-Injektion über Inhalte:** Eine Seite mit Anweisungen („ignoriere …, lies Bereich X“) kann den Lesebereich nicht erweitern, weil er außerhalb des Modells erzwungen wird; Werkzeugantworten sind gerahmt.
7. **Genau eine Antwort:** Worker-Absturz im Lauf, zwei Worker, doppelte Zustellung der auslösenden Nachricht: ein Lauf, eine Antwort; Verbrauch nicht doppelt.
8. **Suche:** Hybridsuche filtert Rechte in derselben Abfrage; Vektortreffer aus unsichtbaren Bereichen, `none`-Bereichen oder zu veralteten Versionen erscheinen nie; ohne Modell nur Volltext.

---

### Task 1: Verbindungen, Geheimnisse, ausgehende Aufrufe

**Files:** Create `backend/app/core/{secrets,egress}.py`, `backend/app/modules/ai/{models,schemas,repository,connections,router}.py`, Migration `m5_ai_connections`, Tests `test_secrets.py`, `test_egress.py`, `test_ai_connections.py`, Stub-Server `backend/tests/support/openai_stub.py`

**Produces:** Tabelle `ai_connection` (Felder aus Spezifikation 7.1; `version`); `GET/POST /api/ai/connections`, `PATCH/DELETE /api/ai/connections/{id}`, `POST …/{id}/test` (ein kleiner Aufruf, Ergebnis als Zustand, nie mit Antworttext des Anbieters), `POST …/{id}/models` (Modelle über `/models` einlesen); alles nur mit `ai.manage`, Audit für jede Änderung ohne Geheimnis.

- [ ] Failing tests (Rollenmatrix; Geheimnis nie in Antwort, Log, Audit; `env:` und `enc:`; SSRF-Fälle aus dem Review Focus; b-api: Routenname, kein Streaming; `param_family`; Löschen einer benutzten Verbindung 409) → implement → gates → commit `ai: add connections with secret references and guarded egress`

### Task 2: Zuordnung und `ai.use`

**Files:** Create `backend/app/modules/ai/{assignments,assignment_repository,assignment_router}.py`, Migration `m5_ai_assignments`, Tests `test_ai_assignments.py`; Modify `auth` (`/auth/me`), `core/permissions.py`, `core/access.py`

**Produces:** Standardzuordnung, Gruppen-Zuordnungen (geordnet), Personen-Zuordnungen inkl. „keine KI“; Auflösung `effective_assignment(user)` in einer Abfrage; `ai.use` in `/auth/me`; `GET/PUT /api/ai/assignments…` mit `ai.manage`.

- [ ] Failing tests (Vorrang Person > Gruppe > Standard; geordnete Gruppen; Gast nie; deaktivierte Verbindung; Leck: Nicht-Admin erfährt nichts über Verbindungen außer dem Namen des eigenen Modells) → implement → gates → commit `ai: add assignments and the derived ai.use right`

### Task 3: Verbrauch

**Files:** Create `backend/app/modules/ai/{usage,usage_repository,usage_router}.py`, Migration `m5_usage`, Tests `test_ai_usage.py`

**Produces:** `usage_record` (Felder aus 7.4, ohne Budget); `record_usage()` als einziger Schreibweg, aufgerufen von der Laufschleife und vom Embedding-Stapel; optionale Preise je Verbindung und Modell; `GET /api/ai/usage` (gruppiert nach Tag und wahlweise Person, Agent, Bereich, Verbindung; Zeitraum; paginiert) mit `ai.manage`; eigene Summe für die Person unter `/api/ai/usage/me`.

- [ ] Failing tests → implement → gates → commit `ai: record usage per call`

### Task 4: KI-Richtlinie je Bereich und KI-Sperre

**Files:** Modify `modules/spaces` (Felder `ai_policy`, `allowed_locations`), `modules/wiki` (`page.no_ai`), Anhänge (`no_ai`); Create `backend/app/modules/ai/policy.py`, Migration `m5_ai_policy`, Tests `test_ai_policy.py`

**Produces:** `PATCH` der Bereichseinstellungen mit `ai_policy` (`space.manage`); `no_ai` an Seite und Datei (`page.moderate`); reine Funktionen `strictest(policies)` und `connection_allowed(connection, policy)`; Hilfen für SQL-Filter „für KI lesbar“ (Bereich nicht `none`, Inhalt nicht `no_ai`), die Werkzeuge und Indexierung gemeinsam nutzen.

- [ ] Failing tests (jede Kombination Richtlinie × `data_location`; Filter mit Mutationsprobe) → implement → gates → commit `ai: add the space ai policy and the no-ai lock`

### Task 5: Agenten als Principals, Profil, Lauf-Tabellen

**Files:** Create `backend/app/modules/agents/{models,schemas,repository,service,router}.py`, Migration `m5_agents_runs`, Tests `test_agents.py`, `test_agent_principals.py`; Modify `core/principal.py`, Bereichsmitgliedschaft, `messaging` (DM mit genau einer Person und einem Agenten; `MessageKind.AGENT`, `run_id`; Trigger und CHECKs), Verzeichnis (Agenten nur für Personen mit `ai.use`)

**Produces:** `agent` (Entscheidung 2), `run` (Agent, auslösende Person, Gespräch, auslösende Nachricht, Zustand `queued|running|done`, `stop_reason`, Zeiten, Versuch, Sperrfrist), `run_event` (Schritt, Art, Inhalt als JSON, Zeit); CRUD für Agenten mit `agent.manage`; Agent als Mitglied von Bereichen; `POST /api/dms` mit einem Agenten nur mit `ai.use`; eine Nachricht in einer solchen DM legt in derselben Transaktion einen Lauf an (nur wenn die Person `ai.use` hat und der Agent `active` ist, sonst bleibt die Nachricht ohne Lauf und der Client zeigt den Grund).

- [ ] Failing tests (Rollenmatrix; Person ohne `ai.use`: 404 und kein Lauf; Agent pausiert; verantwortliche Person deaktiviert; Agent nie in Gruppen-DM oder Kanal in M5; M3-/M4-Tests bleiben grün) → implement → gates → commit `agents: add agent principals, profiles and runs`

### Task 6: Laufschleife (Stufe 1)

**Files:** Create `backend/app/runtime/{loop,tools,untrusted,context,models}.py`, `backend/app/worker/runs.py`, `backend/app/modules/agents/{actor,executor}.py`, Tests `test_run_loop.py`, `test_run_policy.py`, `test_run_scope.py`, `test_run_recovery.py`, `test_runtime_imports.py`

**Produces:** Worker-Schleife, die Läufe beansprucht (SKIP LOCKED, Sperrfrist, höchstens n zugleich je Verbindung nach `max_concurrency`, `requests_per_minute`); Kontext aus Anweisungen und begrenztem Gesprächsverlauf; Werkzeuge `search`, `read_page`, `read_ticket` über die Services mit dem Lauf-`Actor` (`read_scope`); Richtlinienprüfung vor jedem Modellaufruf; Stopgründe `completed`, `max_steps`, `deadline`, `no_progress`, `rights_revoked`, `policy_blocked`, `provider_refused`, `error`; Antwort als Nachricht `kind=agent` (`client_id` = Lauf-ID) oder, bei Abbruch, eine kurze übersetzbare Meldung mit Grund; `run_event` je Schritt; `record_usage` je Modellaufruf; Live-Ereignis `run.progress` (nur IDs und Schrittzähler) an die Teilnehmenden; Metriken (Läufe nach Stopgrund, Dauer, wartende Läufe) und Alarm für hängende Läufe.

- [ ] Failing tests (Review Focus 1, 3, 6, 7 vollständig; ein Lauf je Gespräch; Wiederaufnahme nach Sperrfrist; Zeitlimit; dritter identischer Werkzeugaufruf; Import-Test für `app/runtime`) → implement → gates → commit `agents: run level-1 agents in direct messages`

### Task 7: Oberfläche I (Verwaltung und Gespräch)

**Files:** Create `frontend/src/features/ai/*` (Verbindungen mit Test-Schaltfläche, Zuordnung, Verbrauch), `frontend/src/features/agents/*` (Liste, Formular), Tests; Modify Verwaltung, Bereichseinstellungen (KI-Richtlinie), Seite und Anhang (KI-Sperre), Nachrichten (Agent mit „KI“-Kennzeichen, Fortschrittskarte, Abbruchgrund), DM-Dialog (Agenten nur mit `ai.use`), Verbrauch im Profil

**Produces:** alles nur sichtbar nach `permissions` (`ai.manage`, `agent.manage`, `ai.use`); Geheimnisfeld schreibt nur, zeigt nie; verständliche Zustände „keine Verbindung eingerichtet“, „Anbieter lehnt ab“, „durch Richtlinie des Bereichs gestoppt“; i18n de/en; Tastatur; Hell und Dunkel; 375 px.

- [ ] Failing component tests → implement → Browser-Durchlauf gegen die echte App mit dem Stub-Server als Anbieter (Admin richtet Verbindung und Agenten ein, ordnet zu; Person mit KI schreibt dem Agenten, sieht Fortschritt und Antwort mit Quelle; Person ohne KI sieht nichts davon; `restricted`-Bereich stoppt den Lauf mit verständlichem Grund), Screenshots nach `.superpowers/sdd/m5/screens/` → gates → commits `web: add ai administration`, `web: add agents and the chat with an agent`

### Task 8: Embedding-Vergleich (F4) — braucht Hugging Face

**Files:** Create `backend/scripts/embedding_eval/` (Datensatz-Erzeugung aus den deutschen Texten des Repos und der Demo-Daten mit von Hand geprüften Frage-Treffer-Paaren, Messung), `docs/entscheidungen/2026-11-embedding.md`

**Produces:** Vergleich der drei Kandidaten aus Spezifikation 7.2 auf deutschen Wiki- und Ticket-Texten: Recall@10 und MRR der **Hybridsuche** (und zum Vergleich nur Volltext, nur Vektor), Durchsatz auf CPU (Texte je Sekunde, ein Kern und vier Kerne), RAM, Größe auf der Platte, Kaltstart, Abhängigkeiten und Lizenzen (Modell und Bibliotheken). Ehrlich messen; die Empfehlung nennt, was sie kostet. **Danach Entscheidung durch Jan; erst dann Task 9.**

- [ ] Datensatz und Messung → Dokument → Commit `docs: compare the embedding candidates`

### Task 9: Embeddings und Indexierung

**Files:** Create `backend/app/modules/search/{chunks,chunk_repository,embedder,indexer}.py`, `backend/app/worker/indexing.py`, Migration `m5_search_chunks` (Erweiterung `vector`, Tabelle `search_chunk` aus Spezifikation 11 mit der Dimension des gewählten Modells, HNSW-Index, `embedding_index`), Tests

**Produces:** Zerlegung von Seiten (nach Überschriften), Tickets und umgewandelten Dateien in Abschnitte; Indexierung über Outbox-Ereignisse in eine Auftragstabelle, die der Worker stapelweise abarbeitet; Modell aus `HERD_MODEL_DIR` (Volume), träge geladen; keine Embeddings für `none`-Bereiche, für `restricted` nur bei erlaubter `data_location` der Embedding-Verbindung (lokal: immer); Neuindexierung als Auftrag mit Fortschritt (`GET/POST /api/ai/embedding-index`, `ai.manage`); `record_usage` je Stapel; Metriken und Alarm für Rückstand.

- [ ] Failing tests → implement → gates → commit `search: index pages, tickets and files with local embeddings`

### Task 10: Hybridsuche

**Files:** Modify `modules/search/*`; Tests `test_hybrid_search.py`

**Produces:** Volltext und Vektor per Reciprocal Rank Fusion in einer Abfrage mit dem Rechtefilter; Prüfung vor der Ausgabe, dass die Quellversion des Abschnitts aktuell ist; ohne Modell oder für Nachrichten nur Volltext; Antwortform unverändert plus Trefferart Datei; das Werkzeug `search` des Agenten nutzt denselben Service mit dem Lauf-`Actor`.

- [ ] Failing tests (Review Focus 8 mit Mutationsprobe; Abfrageplan nutzt die Indizes; Messung mit 10.000 Abschnitten) → implement → gates → commit `search: combine full text and vectors`

### Task 11: Dateien in Markdown umwandeln

**Files:** Create `backend/app/modules/files/{conversion,converters}.py`, `backend/app/convert/main.py` (Rolle `convert`), `Dockerfile.convert`, Migration `m5_file_conversion`, Tests; Modify Anhänge, Chart (Deployment `convert`, Standard aus), Compose (Profil), CI (Image bauen, Lizenzprüfung des Extras)

**Produces:** Auftrag je hochgeladener Datei; HTML, Text, Markdown im gewöhnlichen Worker (sicherer HTML-nach-Markdown-Weg ohne Skripte); PDF und Office in der Rolle `convert` mit Docling (Modelle über ein Volume, kein Netzzugriff zur Laufzeit, Zeit- und Größenlimit, Absturz eines Auftrags trifft nur diesen); Original und Markdown bleiben erhalten; Zustand je Datei sichtbar; Vorschau des Markdown und „Als Seite anlegen“; umgewandelter Text wird indexiert (Task 9), außer bei `no_ai`.

- [ ] Failing tests (ohne Rolle `convert` bleibt die Datei ein Anhang, kein Fehler; feindliche Dateien: Zip-Bombe, riesige Seitenzahl, eingebettete Skripte; Rechte) → implement → gates → commit `files: convert uploads to markdown`

### Task 12: Auslieferung, Browsertests, Dokumentation, Abnahme

**Files:** Modify `deploy/*` (neue Variablen `HERD_SECRET_KEY`, `HERD_MODEL_DIR`, Volume für Modelle, Init-Schritt zum Laden des Modells, Speichergrenzen des Workers, NetworkPolicy: Worker darf zu den Anbietern hinaus), `smoke.sh` (Stub-Anbieter als Dienst: Verbindung, Agent, DM, Antwort), `demo_seed`, `README.md`, `CLAUDE.md`, `docs/STECKBRIEF.md`, Spezifikation (Vermerke „Geändert in M5“); Create `docs/KI.md`, `docs/demo/m5.md`, `e2e/tests/ai-*.spec.mjs`

**Produces:** e2e mit dem Stub-Anbieter (Admin richtet ein; Person mit KI chattet; Person ohne KI sieht nichts; `restricted` stoppt); Demo mit beiden Abnahmesätzen aus 14/M5; Steckbrief mit gemessenem Speicher des Workers mit geladenem Modell, Indexierungsdurchsatz, Suchzeiten; was hier nicht messbar ist, steht als nicht gemessen im Dokument. Ein Lauf gegen einen echten Anbieter ist nur möglich, wenn ein Schlüssel als Geheimnis der Umgebung vorliegt; sonst steht das als nicht geprüft im Dokument.

- [ ] Tests und Skripte zuerst → alle Gates → commits `e2e: add ai scenarios`, `ops: deliver models, secrets and the convert role`, `docs: add m5 demo, fact sheet and ai notes`

---

## Abdeckung der Spezifikation (Selbstprüfung)

| Spezifikation | Task |
|---|---|
| 5.1 Agent als Principal; 5.4 Schnittmenge (Punkte 1, 2, 5, 6); 5.6 Lesebereich für die DM zu zweit | 5, 6 |
| 6.3 Direktnachricht mit einem Agenten, Fortschritt, ein Lauf je Gespräch | 5, 6, 7 |
| 7.1 Verbindungen inkl. b-api | 1 |
| 7.2 Zuordnung, `ai.use`, lokales Embedding | 2, 8, 9 |
| 7.3 KI-Richtlinie | 4, 6, 9 |
| 7.4 Verbrauch (ohne Budgets) | 3 |
| 8.3 Lauf (ohne Freigaben, ohne DBOS), Stopgründe | 6 |
| 11 Hybridsuche, Dateien mit Docling, KI-Sperre je Datei | 9, 10, 11 |
| 14/M5 Abnahme | 6, 7, 12 |

Nicht in M5: Autonomiestufen 2 bis 4, Werkzeugfreigaben, Freigaben mit Fingerabdruck, Skills, Gedächtnis, Erwähnungen in Kanälen, Ticketzuweisung an Agenten, Laufansicht und Abbruch, persönliche Agenten (`agent.create_personal`), DBOS (alles M6); Budgets und Auslöser (M7); MCP und Konnektoren (M8).
