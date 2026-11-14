# M6 Agenten als Mitarbeiter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agenten arbeiten wie Kolleginnen: Sie lassen sich in Kanälen und Threads erwähnen, bekommen Tickets zugewiesen, schlagen Änderungen an Seiten vor oder schreiben sie (je nach Stufe), fragen bei kritischen Schritten nach einer Freigabe, führen ein Gedächtnis je Bereich und nutzen Skills. Jeder Lauf ist Schritt für Schritt einsehbar und lässt sich abbrechen. Abnahme (Spezifikation 14): Ein Agent bearbeitet ein Ticket bis „Zur Prüfung“; eine Freigabe für einen geänderten Inhalt wird abgelehnt; ein Lauf übersteht den Neustart des Workers.

**Architecture:** Aufbau auf M5 (`modules/agents`, `app/runtime/`, `worker/runs.py`). Neu: Werkzeugkatalog mit Freigaben und Stufen (`agents/toolbox/`), Freigaben (`agents/approvals`), Auslöser (`agents/triggers`), Laufprotokoll als Journal mit Wiedergabe, Module `modules/proposals` und `modules/skills`, Gedächtnisseiten im Wiki. Schreibende Werkzeuge gehen durch dieselben Services wie Menschen (`router → service → repository`), mit dem Lauf-Actor.

**Tech Stack:** wie M5. Neu höchstens eine Diff-Bibliothek für den Drei-Wege-Abgleich (Lizenz prüfen; sonst `difflib`). Kein DBOS (Entscheidung 1).

**Spec:** Abschnitte 5.4, 5.6, 6.3, 8 (ohne 8.4 Zeitpläne, Heartbeat, Ereignisse: M7), 9 (Vorschläge), 11 (Skills). Task 14 trägt die Änderungen dieses Plans in die Spezifikation ein.

---

## Was M5 schon kann (Abgleich)

| Baustein | Stand nach M5 |
|---|---|
| Agent als Principal, Mitglied in Bereichen, Status, Grenzen | vorhanden |
| Lauf mit Sperrfrist, Wiederaufnahme von vorn, `run_event`, Stopgründe, Verbrauch | vorhanden (Stufe 1, nur lesen) |
| Lesebereich (`read_scope`) am Lauf-Actor, Prüfung vor jedem Schritt | vorhanden für die Direktnachricht zu zweit |
| Werkzeuge `search`, `read_page`, `read_ticket` | vorhanden |
| Direktnachricht mit einem Agenten, Fortschrittskarte | vorhanden |
| Stufen, Werkzeugfreigaben, Freigaben, Schreiben, Erwähnung, Ticketzuweisung, Laufansicht, Abbruch, Gedächtnis, Skills, Vorschläge, persönliche Agenten | fehlt |

## Entscheidungen dieses Plans

1. **Kein DBOS; das Laufprotokoll ist das Journal.** [Claude, ändert E10] M5 hat Läufe als Zeilen mit Sperrfrist gebaut. M6 macht daraus eine dauerhafte Ausführung ohne zweite Zustandsmaschine:
   - Jeder Schritt (Modellantwort, Werkzeugaufruf mit Ergebnis) wird als `run_event` festgeschrieben. Ein **schreibendes Werkzeug schreibt seine Wirkung und sein `run_event` in derselben Transaktion**. Damit ist jede Wirkung innerhalb der Datenbank genau einmal, was DBOS mit getrennter Zustandsdatenbank nicht zusichert.
   - Wiederaufnahme nach einem Absturz **spielt das Journal wieder ein** (Modellantworten und Werkzeugergebnisse aus `run_event`) und setzt nach dem letzten festgeschriebenen Schritt fort, statt von vorn zu beginnen. Verloren geht höchstens ein Modellaufruf (Kosten, keine Wirkung).
   - **Warten** (Freigabe, Rückfrage) ist ein Zustand `waiting` der Zeile; kein Prozess hält etwas. Die Antwort setzt den Lauf auf `queued`. Zeitlimit 72 h über eine Spalte `wait_until`, die die Laufschleife prüft.
   - Zeitpläne und „genau einmal bei drei Replikas“ (M7) entscheidet der M7-Plan neu; mit `SKIP LOCKED` ist das ohne DBOS lösbar (Spezifikation 12.4 nennt beides).
2. **Autonomiestufe = Voreinstellung, wirksam = Minimum.** Tabelle `agent_tool` (Agent, Werkzeug, `allow|confirm|block`). Die Stufe (1 bis 4) legt die Voreinstellung je Werkzeug fest; Einträge können nur verschärfen. Stufe 4 und externe Werkzeuge kommen mit M8; in M6 sind Stufen 1 bis 3 wählbar. Eine Stufe über 2 vergibt nur, wer jeden Bereich des Agenten verwaltet, oder ein Admin.
3. **Werkzeuge in M6** (alle über die Services, alle mit Rechteprüfung vor dem Aufruf):
   - Stufe 1: `search`, `read_page`, `list_tree`, `list_versions`, `search_tickets`, `read_ticket`, `read_conversation` (nur das auslösende Gespräch), `load_skill`, `search_past_runs` (nur eigene Läufe, die der Lesebereich erlaubt), `ask_user`, `submit_result`.
   - Stufe 2: dazu `propose_page_change`, `propose_new_page`, `comment_ticket`, `set_ticket_status` (höchstens Kategorie `review`), `create_ticket`, `link_ticket_page`, `update_memory`, `propose_skill`.
   - Stufe 3: dazu `update_page` (zweistufig mit Diff, nur in Bereichen mit `agent_write_policy=direct`), `assign_ticket` (Übergabe mit Begründung), `post_message` (nur in Gespräche, in denen der Agent Mitglied ist).
   - Agenten löschen nie und legen nichts in den Papierkorb.
4. **Freigabe mit Fingerabdruck.** `approval` (Lauf, Werkzeug, Argumente, `fingerprint` = Hash aus Werkzeug, kanonischen Argumenten und Version des betroffenen Objekts, Zustand `pending|approved|rejected|expired`, entschieden von, Zeit). Beim Ausführen nach der Freigabe wird der Fingerabdruck **neu berechnet**; weicht er ab (Objekt geändert), gilt die Freigabe nicht, der Lauf erfährt das als Werkzeugergebnis `approval_stale` und kann neu anfragen. Freigaben gehen an die auslösende Person, sonst an die verantwortliche (5.4); sie erscheinen als Karte im Gespräch und in der Aktivität. Entscheiden darf nur, wer die Wirkung selbst ausführen dürfte.
5. **Publikumsregel (5.6) vollständig.** `read_scope` wird für jeden Ausgabeort berechnet: Kanal, Ticket- oder Seiten-Thread in Bereich S (S und `open`; ist S `open`, nur `open`), Direktnachricht (Schnittmenge aller Teilnehmenden), allein mit dem Agenten (volle Rechte der Person ∩ Agent). **Schreiben** wird zusätzlich auf den Bereich des Auftrags begrenzt: Ein Lauf aus einem Ticket oder Kanal in S schreibt nur in S; ein Lauf aus der Direktnachricht zu zweit schreibt, wo Person und Agent es beide dürfen.
6. **Auslöser in M6:** Direktnachricht (M5), **Erwähnung** `@agent` in Kanal oder Thread (Antwort als Thread-Antwort auf die erwähnende Nachricht), **Ticketzuweisung** (Antwort als Kommentar im Ticket-Thread; Auslöser ist die zuweisende Person; bei Übergabe von Agent zu Agent die ursprüngliche Person, `run.origin_user_id`; Kettentiefe höchstens 3, das Tiefenlimit für Ereignisse folgt in M7). Ein Gespräch hat weiter höchstens einen laufenden Lauf; ein Ticket ebenso.
7. **Agent als Ticket-Bearbeiter:** `work_item.assignee` nimmt Agenten (M4 hat es vorbereitet). Ein Agent setzt den Status höchstens auf eine Kategorie `review`; „erledigt“ setzt ein Mensch. Scheitert der Lauf, bleibt das Ticket zugewiesen und der Thread nennt den Grund; die verantwortliche Person erhält eine Aktivität.
8. **Vorschläge** (`modules/proposals`): `page_proposal` (Seite oder neue Seite, Basisversion, vorgeschlagener Inhalt, Begründung, Urheber als Principal, `run_id`, Zustand). Annehmen oder Ablehnen mit `page.moderate`; beim Annehmen mit veralteter Basis ein Drei-Wege-Abgleich im Dialog, bei Konflikt keine stille Übernahme. Angenommene Vorschläge erzeugen eine Version mit Quelle `agent`, KI-Kennzeichen und `run_id`. `human_review` (Vorschläge von Menschen) bleibt aus M6 heraus, bis Jan es will. `agent_write_policy` je Bereich: `propose` (Voreinstellung) oder `direct`.
9. **Schreiben in Seiten** (`update_page`, Annahme eines Vorschlags): vorher eine Version, danach neue Generation (schließt Live-Sitzungen, wie M2 es für Agenten vorgesehen hat); nie in eine Seite mit `no_ai`; `version` mit 409 wie bei Menschen.
10. **Gedächtnis:** je Agent und Bereich eine normale Seite unter `/_agenten/<agent>/gedaechtnis` (angelegt beim ersten `update_memory`), Rechte des Bereichs, höchstens 4.000 Zeichen im Kontext, nur Bereiche des Lesebereichs. `update_memory` ist auf Stufe 2 direkt erlaubt; Menschen korrigieren die Seite wie jede andere. Im Seitenbaum steht der Ordner `_agenten` am Ende.
11. **Skills** (`modules/skills`): SKILL.md (Frontmatter `name`, `description`, Text), versioniert, einem Bereich zugeordnet oder organisationsweit (`skill.manage`), Agenten zugeordnet. Im Kontext stehen nur Name und Beschreibung; den Text holt `load_skill` (Rechte des Bereichs, KI-Richtlinie). Import und Export als Datei oder Zip. `propose_skill` nutzt die Vorschlags-Moderation. Skripte in Skills werden **nicht ausgeführt** (kein Code-Werkzeug in v1); Anhänge eines Skills sind Text.
12. **Laufansicht und Abbruch:** Liste der Läufe je Agent und „meine Läufe“; Ansicht mit Schritten, Werkzeugaufrufen (Argumente und Ergebnis), Freigaben, Kosten und Dauer; lesbar für die auslösende Person, die verantwortliche Person und `agent.manage` (bei Admins mit Audit-Vermerk, wenn Inhalte fremder privater Bereiche sichtbar werden). Abbruch als eigener Datensatz `run_cancel_request`, geprüft vor jedem Schritt und in der Transaktion des Abschlusses; Stopgrund `cancelled`. Neu außerdem `budget` nicht (M7), aber `approval_expired` und `waiting_timeout`.
13. **Persönliche Agenten:** `agent.create_personal` (für `ai.use`, abschaltbar durch Admins): eigene Agenten, Mitglied nur im eigenen persönlichen Bereich, höchstens Stufe 2, zählen auf das Konto der Person.
14. **Ersatzmodell, Avatar, Persönlichkeit** aus 8.1: Persönlichkeit ist Teil der Anweisungen (kein eigenes Feld); Avatar und Ersatzmodell kommen nur, wenn ein Leser sie braucht, sonst nicht (harte Regel 5).

## Global Constraints

- Alle Global Constraints aus M1 bis M5 gelten, ebenso die Ergebnisse der Reviews (insbesondere: nur `app/runtime/` importiert Pydantic AI; Inhalte nie in Logs, Outbox, NOTIFY, Metriken; Geheimnisse nie im Prompt).
- **Jedes Werkzeug prüft vor dem Aufruf und beim Fortsetzen nach einer Freigabe erneut** die Schnittmenge aus 5.4 (Rolle des Agenten, Rechte des Auslösers, Werkzeugfreigabe, Stufe, `no_ai`, KI-Richtlinie) und den Lese- und Schreibbereich. Entzug endet mit `rights_revoked`.
- Werkzeugergebnisse sind nicht vertrauenswürdige Daten: gerahmt, im Prompt gekürzt, im Protokoll vollständig. Kein Werkzeugergebnis kann eine Freigabe erteilen, eine Stufe ändern oder ein Werkzeug freischalten.
- Schreibende Werkzeuge: Wirkung und `run_event` in einer Transaktion; Wiedergabe führt nichts zweimal aus (Test mit getötetem Worker zwischen Wirkung und nächstem Schritt).
- Alles, was ein Agent schreibt, trägt Urheber `agent:<id>`, KI-Kennzeichen und `run_id` und ist in der Oberfläche als KI erkennbar (Nachricht, Kommentar, Version, Vorschlag, Ticketänderung).
- Systemmeldungen nur in Threads; nichts über ein Ticket in einem Kanal (M4). Die Antwort auf eine Erwähnung ist eine Thread-Antwort.
- Migrationen: nur erweitern, eine Kette, ein Head.

## Review Focus

1. Durchsickern über das Schreiben: Ein Agent schreibt Inhalte aus Bereich A in ein Gespräch, Ticket oder eine Seite, deren Publikum A nicht sieht (Publikumsregel bei jedem Ausgabeort, Gedächtnis, `search_past_runs`, Skills).
2. Rechteausweitung: Admin als Auslöser, Übergabeketten (`origin_user_id`), Entzug während des Wartens auf eine Freigabe, Stufe und Freigaben nur verschärfbar, persönliche Agenten außerhalb des eigenen Bereichs.
3. Freigaben: Fingerabdruck bei geändertem Objekt, doppelte Entscheidung, Entscheidung durch Unbefugte, abgelaufene Freigabe, Freigabe eines Laufs, der schon beendet ist.
4. Dauerhaftigkeit: Worker stirbt vor, in und nach einer schreibenden Wirkung; zwei Worker; Wiedergabe mit geändertem Werkzeugkatalog; Abbruch gegen Abschluss.
5. Prompt-Injektion mit Schreibwirkung: Seiten- oder Ticketinhalt, der den Agenten zu Änderungen, Zuweisungen oder Nachrichten verleitet; Grenzen (Schritte, Laufzeit, Kettentiefe, dritter identischer Aufruf).
6. Seiten: Version vor jedem Agenten-Schreibzugriff, Generation, `no_ai`, Live-Sitzungen verlieren nichts.

---

### Task 1: Journal und Wiedergabe, Zustand `waiting`

**Files:** Modify `agents/{models,executor,executor_repository,step_host}.py`, `runtime/loop.py`, `worker/runs.py`; Migration; Tests `test_run_replay.py`, `test_run_waiting.py`

**Produces:** Wiederaufnahme setzt nach dem letzten festgeschriebenen `run_event` fort; Zustand `waiting` mit `wait_until`; Stopgründe `cancelled`, `waiting_timeout`; Metrik `herd_runs_waiting`.

- [ ] Failing tests (Worker als echter Prozess, getötet nach Schritt n: kein Schritt doppelt, Antwort genau einmal; Wiedergabe ohne Modellaufruf für festgeschriebene Schritte) → implement → gates → commit `ai: resume runs from their journal`

### Task 2: Werkzeugkatalog, Stufen, Freigaben am Agenten

**Files:** Create `agents/toolbox/{catalog,policy}.py`, Tabelle `agent_tool`, Feld `agent.level`; Modify Agent-Service, -Schemas, -Router; Tests

**Produces:** Katalog mit Stufe und Wirkung (`read|propose|write`) je Werkzeug; wirksame Freigabe = Minimum aus Stufe und Eintrag; Regel für Stufe > 2; `GET /api/agents/{id}/tools`, `PUT …/tools`.

- [ ] Failing tests (Matrix Stufe × Werkzeug × Eintrag; nur verschärfen; wer darf Stufe 3 vergeben) → implement → gates → commit `ai: add tool grants and autonomy levels`

### Task 3: Lese- und Schreibbereich für alle Ausgabeorte

**Files:** Modify `agents/actor.py`, `core/actor.py` (`ReadScope`, neu `WriteScope`), Tests `test_run_scope_places.py`

- [ ] Failing tests (Leck-Tests je Ausgabeort mit Mutationsprobe; Schreibversuch außerhalb des Auftragsbereichs) → implement → gates → commit `ai: scope runs by the audience of their place`

### Task 4: Lesende Werkzeuge der Stufe 1

`list_tree`, `list_versions`, `search_tickets`, `read_conversation`, `search_past_runs`, `submit_result`.

- [ ] Failing tests → implement → gates → commit `ai: add the reading tools`

### Task 5: Vorschläge (Backend)

**Files:** Create `modules/proposals/*`, Migration (`page_proposal`, `space.agent_write_policy`), Tests

**Produces:** `GET /api/spaces/{id}/proposals`, `GET /api/proposals/{id}` (mit Diff), `POST …/accept` (mit `base_version`, Drei-Wege-Abgleich, 409 bei Konflikt mit Konfliktstellen), `POST …/reject`; Ereignisse `proposal.*`, Aktivität für Moderatoren, Systemmeldung im Seiten-Thread.

- [ ] Failing tests → implement → gates → commit `wiki: add page proposals`

### Task 6: Schreibende Werkzeuge für Wiki und Tickets

`propose_page_change`, `propose_new_page`, `update_page`, `comment_ticket`, `set_ticket_status`, `create_ticket`, `link_ticket_page`, `assign_ticket`, `post_message`; KI-Kennzeichen und `run_id` an Version, Nachricht und Ticketereignis.

- [ ] Failing tests (je Werkzeug: Rechte, Stufe, `no_ai`, Richtlinie, Version vor Schreibzugriff, Generation, genau einmal bei Wiedergabe) → implement → gates → commit `ai: add the writing tools`

### Task 7: Freigaben und Rückfragen

**Files:** Create `agents/approvals/*`, Migration (`approval`, `run_question`), Tests `test_approvals.py`, `test_approval_races.py`

**Produces:** `confirm` erzeugt eine Freigabe und setzt den Lauf auf `waiting`; `POST /api/approvals/{id}/decide`; `ask_user` als Karte; Fingerabdruck neu geprüft; Ablauf nach 72 h; Karten als Nachricht `kind=approval|question` im Gespräch (Thread), Aktivität.

- [ ] Failing tests (geänderter Inhalt → abgelehnt; doppelte und unbefugte Entscheidung; Entzug während des Wartens; Wettläufe mit echten Commits) → implement → gates → commit `ai: add approvals bound to a fingerprint`

### Task 8: Auslöser Erwähnung und Ticketzuweisung

**Files:** Create `agents/triggers.py`, Handler; Modify Messaging-Hooks, Ticket-Zuweisung (Agent als Bearbeiter), Tests

- [ ] Failing tests (Erwähnung ohne `ai.use` startet nichts und verrät nichts; Antwort im Thread; Zuweisung → Lauf → Kommentar → Status `review`; Übergabekette mit `origin_user_id`, Tiefe 3; nichts im Kanal) → implement → gates → commit `ai: start runs from mentions and ticket assignment`

### Task 9: Gedächtnis und Skills (Backend)

**Files:** Create `modules/skills/*`, `agents/memory.py`, Migration, Tests

- [ ] Failing tests (Gedächtnis nur aus Bereichen des Lesebereichs, 4.000 Zeichen; Skill-Text nur über `load_skill`; Import/Export; Vorschlag eines Skills) → implement → gates → commit `ai: add agent memory and skills`

### Task 10: Laufansicht, Abbruch, persönliche Agenten (Backend)

- [ ] Failing tests (wer sieht welche Läufe; Abbruch gegen Abschluss; persönlicher Agent bleibt im eigenen Bereich und höchstens Stufe 2) → implement → gates → commit `ai: add the run view, cancelling and personal agents`

### Task 11: Oberfläche Agentenverwaltung

Profil mit Stufe und Werkzeugfreigaben, Bereiche, Skills, persönliche Agenten; Skills-Verwaltung; Vorschläge im Wiki (Liste, Diff, Annehmen mit Konfliktdialog, Ablehnen); `agent_write_policy` in den Bereichseinstellungen.

- [ ] Failing component tests → implement → Browser-Durchlauf, Screenshots → gates → commit `web: add agent levels, skills and proposals`

### Task 12: Oberfläche Zusammenarbeit

Erwähnung von Agenten im Editor (nur mit `ai.use`), Agent als Bearbeiter am Ticket und im Board, Freigabe- und Rückfragekarten, Laufansicht mit Abbruch, KI-Kennzeichen an Versionen, Kommentaren und Ticketänderungen, Gedächtnisseiten im Baum.

- [ ] Failing component tests → implement → Browser-Durchlauf (Abnahme-Szenario), Screenshots → gates → commit `web: add agents to tickets, threads and the run view`

### Task 13: Browsertests und Demo-Daten

`e2e/tests/agents-work.spec.mjs` mit dem Stub: Ticket bis „Zur Prüfung“; Freigabe für geänderten Inhalt abgelehnt; Worker-Neustart mitten im Lauf; Erwähnung im Kanal; Vorschlag annehmen. `backend/scripts/demo_ai.py` (+ Test), `docs/demo/m6.md` ausgeführt.

- [ ] Tests zuerst → gates → commits `e2e: add agent work scenarios`, `demo: add agents at work`

### Task 14: Betrieb und Dokumentation

`docs/AGENTEN.md` (Nutzung und Betrieb), `docs/KI.md`, `README.md`, `CLAUDE.md`, `docs/STECKBRIEF.md` (Messung: Läufe je Minute mit einem Worker, Wartende, Wiederaufnahme), Helm/Compose (neue Variablen, Alarme `HerdRunsWaitingExpired`), Spezifikation: E10 und 8.3 (Journal statt DBOS, Entscheidung 1), 6.3 (eindeutiger Index statt Advisory Lock), 8.1 (Entscheidung 14), 14 (M6 erfüllt).

- [ ] Gates → commit `docs: describe agents as colleagues`
