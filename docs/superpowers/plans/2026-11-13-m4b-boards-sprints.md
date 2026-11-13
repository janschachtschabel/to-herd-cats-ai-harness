# M4b Boards und Sprints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ergänzung zu M4 nach Jans Wunsch vom 13.11.2026: persönliche und teambezogene Boards, mit denen ein Team im Daily durchgeht, wer was zu tun hat und wie der Stand ist; Sprints je Bereich; die Hierarchie aus Epics, Storys und Aufgaben bleibt, wie M4 sie gebaut hat, und wird in den neuen Ansichten sichtbar.

**Architecture:** Erweiterung des Moduls `app/modules/tickets`: Tabelle `sprint`, Feld `work_item.sprint_id`, neue Ansichts-Endpunkte. Keine neue Art von Ereignis außer `sprint.*`; Systemmeldungen im Ticket-Thread für den Wechsel des Sprints. Im Frontend neue Ansichten in `features/tickets`.

**Tech Stack:** wie M4, keine neue Abhängigkeit.

**Spec:** Abschnitt 10 der Spezifikation wird in Task 4 um Sprints und die neuen Ansichten ergänzt („Ergänzt in M4b [Jan, 13.11.2026]“).

---

## Was M4 schon kann (Abgleich)

| Wunsch | Stand nach M4 |
|---|---|
| Epics und Aufgaben hierarchisch | vorhanden: Epic → Story → Aufgabe/Fehler (drei Ebenen), Epic-Übersicht mit Fortschritt, Kinder am Ticket |
| Board je Team | vorhanden als Board je Bereich (ein Team-Bereich ist das Team), filterbar nach Person, Art, Tag, Epic |
| Board je Person, über Bereiche hinweg | fehlt (es gibt nur die Liste „Meine Tickets“) |
| Daily: wer hat was zu tun, Stand je Person | fehlt (kein Gruppieren nach Person) |
| Sprints | fehlt |

## Entscheidungen dieses Plans

1. **Team = Bereich.** Ein Sprint gehört zu genau einem Bereich. Je Bereich ist höchstens ein Sprint aktiv. Ein Ticket ist in höchstens einem Sprint seines Bereichs; Tickets ohne Sprint bilden den Vorrat (Backlog).
2. **Sprint:** Name, Ziel (kurzer Text), Beginn und Ende als Datum, Zustand `planned`, `active`, `closed`, `version`. Anlegen, Starten und Abschließen darf, wer `ticket.assign` hat (ab `moderator`); Tickets in einen Sprint legen darf, wer `ticket.edit` hat.
3. **Abschließen eines Sprints:** Unerledigte Tickets (Kategorie nicht `done` oder `cancelled`) gehen nach Wahl in den nächsten geplanten Sprint oder zurück in den Vorrat. Der abgeschlossene Sprint behält seine Bilanz: geplant, erledigt, übertragen (als Zahlen, beim Abschluss festgehalten).
4. **Persönliches Board („Mein Board“):** alle mir zugewiesenen Tickets aus allen sichtbaren Bereichen. Weil jeder Bereich eigene Status hat, sind die Spalten hier die **Kategorien** (Offen, In Arbeit, Zur Prüfung, Erledigt); Ziehen in eine andere Spalte setzt den ersten Status dieser Kategorie im Bereich des Tickets. Erledigtes erscheint nur, wenn es in den letzten 14 Tagen erledigt wurde.
5. **Team-Board für das Daily:** das Board des Bereichs mit dem Schalter „nach Person gruppieren“: eine Zeile je zugewiesener Person (dazu „Nicht zugewiesen“), Spalten wie gehabt die Status. Voreinstellung im Daily-Modus: aktiver Sprint, falls vorhanden. Jede Zeile zeigt die Zahl je Spalte und hebt hervor, was sich seit dem letzten Arbeitstag geändert hat (Statuswechsel seit gestern 0 Uhr, montags seit Freitag).
6. **Person in einem Team ansehen:** Ein Klick auf eine Person im Team-Board filtert auf sie; für Admins und Mitglieder desselben Bereichs. Ein bereichsübergreifendes Board **einer anderen Person** gibt es nicht: man sähe sonst, in welchen Bereichen jemand arbeitet. Wer mehrere Teams überblicken will, nutzt die Liste mit Filter „Zugewiesen an“, die schon nur sichtbare Bereiche zeigt.
7. **Reihenfolge im Vorrat:** weiterhin Priorität, Fälligkeit, Nummer (M4, Entscheidung 8). Eine Handsortierung kommt erst, wenn die Sprintplanung sie wirklich braucht.
8. **Kein Schätzen, keine Burndown-Kurve in diesem Schritt.** Die Sprint-Bilanz zählt Tickets. Aufwandspunkte wären ein neues Feld ohne zweiten Leser; sie kommen, wenn Jan sie will.
9. **Kalender** ist nicht Teil dieses Plans; siehe die Empfehlung an Jan (Kalenderansicht über vorhandene Daten und iCal-Abo). Fälligkeiten und Sprint-Zeiträume liefern dafür die Daten.

## Global Constraints

- Alle Global Constraints aus M1 bis M4 gelten unverändert, ebenso die Ergebnisse der Befundbehebung nach dem gemeinsamen Review (Verteiler mit Bahnen, Trigger für Elternregeln).
- Sichtbarkeit: Sprints sieht, wer `ticket.read` im Bereich hat; unsichtbar ist 404. „Mein Board“ und alle Zähler filtern in SQL über die sichtbaren Bereiche.
- Jede Änderung an Sprint und Sprint-Zuordnung nennt die gelesene `version` (409). „Höchstens ein aktiver Sprint je Bereich“ sichert ein eindeutiger Teilindex, nicht nur der Service.
- Ereignisse tragen nur IDs; der Wechsel des Sprints erzeugt eine Systemmeldung im Ticket-Thread (`ticket.sprint_changed`), nie eine Nachricht in einem Kanal.
- Das Abschließen eines Sprints mit vielen Tickets ist eine Transaktion mit einem Ereignis je Ticket; der Verteiler muss das ohne Stau für andere Handler verarbeiten (Bahnen aus der Befundbehebung).

## Review Focus

1. Leck über „Mein Board“ und Sprint-Endpunkte: Tickets und Sprints fremder Bereiche, auch nach Entzug der Mitgliedschaft; Sprint-ID eines fremden Bereichs als Filter oder Ziel.
2. Wettläufe: zwei Sprints gleichzeitig starten; Sprint abschließen, während Tickets hinein- oder herausbewegt werden; Ziehen im Kategorien-Board, während der Zielstatus gelöscht wird.
3. Kategorien-Board: der gesetzte Status gehört immer zum Bereich des Tickets; kein Bereich ohne Status der Zielkategorie führt zu einem Fehler 500 (dann 422 mit verständlichem Grund).
4. Daily-Hervorhebung stimmt mit den Systemmeldungen überein und verrät nichts über Tickets, die man nicht sieht.

---

### Task 1: Sprints (Backend)

**Files:** Create `backend/app/modules/tickets/{sprints,sprint_repository,sprint_router}.py`, Migration `m4b_sprints`, Tests `test_sprints.py`, `test_sprint_races.py`; Modify Ticket-Schemas und -Service (`sprint_id`), Handler `ticket_timeline`

**Produces:** `GET/POST /api/spaces/{id}/sprints`, `PATCH /api/sprints/{id}`, `POST /api/sprints/{id}/start`, `POST /api/sprints/{id}/close` (mit `move_open_to: next|backlog`); `sprint_id` am Ticket (PATCH, Filter in Liste und Board, `sprint=none` für den Vorrat); Bilanz am abgeschlossenen Sprint; Ereignisse `sprint.created|updated|started|closed`, Systemmeldung `ticket.sprint_changed`; Live-Ereignisse.

- [ ] Failing tests (Rollenmatrix; ein aktiver Sprint; Sprint eines fremden Bereichs 404/422 ohne Unterschied zu „gibt es nicht“; Abschluss mit beiden Varianten; Wettläufe mit echten Commits; genau eine Systemmeldung) → implement → gates → commit `tickets: add sprints per space`

### Task 2: Ansichten (Backend)

**Files:** Create `backend/app/modules/tickets/{my_board,daily}.py` mit Repository-Teilen, Tests `test_my_board.py`, `test_daily_board.py`

**Produces:** `GET /api/tickets/my-board` (Spalten nach Kategorie, je Spalte Anzahl und erste Seite, Nachladen je Kategorie; Karte nennt Bereich und Status); `POST /api/tickets/{number}/move-category` (setzt den ersten Status der Kategorie im Bereich des Tickets, mit `version`); `GET /api/spaces/{id}/board?group_by=assignee[&sprint=…]` (Zeilen je Person mit Zahlen je Status und erster Seite je Zelle, begrenzt; „seit dem letzten Arbeitstag geändert“ je Karte aus den Statuswechseln); feste Zahl von Abfragen je Aufruf.

- [ ] Failing tests (Leck-Tests mit Mutationsprobe; Abfragezähler; Kategorie ohne Status im Bereich 422; Arbeitstag-Regel inkl. Montag) → implement → gates → commit `tickets: add the personal board and the daily view`

### Task 3: Oberfläche

**Files:** Create `frontend/src/features/tickets/{sprints,my-board,daily}/*`, Tests; Modify Bereichsansicht (Reiter „Sprints“, „Vorrat“), Board (Schalter „nach Person gruppieren“, Sprint-Auswahl), Seitenleiste („Mein Board“), Ticketansicht (Feld Sprint)

**Produces:** Sprint-Verwaltung (anlegen, starten, abschließen mit Wahl für Unerledigtes, Bilanz); Vorrat mit „in Sprint legen“ (Mehrfachauswahl, Tastatur); „Mein Board“ mit Ziehen zwischen Kategorien und gleichwertigem Tastatur- und Menüweg; Team-Board im Daily-Modus mit Zeilen je Person, Hervorhebung des seit gestern Geänderten und Klick auf eine Person als Filter; alles nur nach `my_role` und `permissions`; i18n de/en; 375 px; Hell und Dunkel.

- [ ] Failing component tests → implement → Browser-Durchlauf mit zwei Personen gegen die echte App (Sprint planen und starten, Daily-Board, Mein Board über zwei Bereiche, Sprint abschließen), Screenshots nach `.superpowers/sdd/m4b/screens/` → gates → commit `web: add sprints, my board and the daily view`

### Task 4: Browsertests, Demo-Daten, Dokumentation

**Files:** Create `e2e/tests/tickets-sprints.spec.mjs`; Modify `backend/scripts/demo_tickets.py` (+ Test), `docs/TICKETS.md`, `README.md`, `CLAUDE.md`, `docs/STECKBRIEF.md` (Messung der neuen Ansichten mit 10.000 Tickets), Spezifikation Abschnitt 10

- [ ] Tests zuerst → alle Gates → commits `e2e: add sprint and board scenarios`, `docs: describe sprints and the new boards`
