# M7 Automatisierung — Umsetzungsplan

> **Für ausführende Agenten:** Arbeite nach den Superpowers-Skills (subagent-driven-development bzw. executing-plans, TDD, verification-before-completion). Jede Aufgabe: fehlschlagender Test zuerst → kleinste Umsetzung → Tests grün → ruff/mypy sauber → Doku, wenn sich Verhalten ändert → Commit. `CLAUDE.md` gilt ohne Ausnahme.

**Ziel:** Agenten arbeiten ohne Anstoß im Gespräch: zu einem Zeitpunkt, wiederkehrend, als Heartbeat mit Checkliste und auf Ereignisse hin. Budgets begrenzen den Verbrauch je Tag. Seiten, deren Prüffrist abgelaufen ist, melden sich.

**Abnahme (Spezifikation 14):** Ein Zeitplan läuft bei drei Worker-Replikas genau einmal; eine Agentenkette stoppt bei Tiefe 3.

**Tech Stack:** wie M6. Neu ein Cron-Parser mit erlaubter Lizenz (Vorschlag `cronsim`, BSD-3-Clause; Lizenzprüfung muss grün sein) und `zoneinfo` aus der Standardbibliothek (`tzdata` als Paket nur, wenn das Image keine Zonendaten hat). Kein DBOS. *Geändert in M7 [Claude, 14.11.2026]: `cronsim` und das Paket `tzdata` sind Laufzeitabhängigkeiten. Das Image hat die Zonendaten von Debian (geprüft am Basis-Digest); `tzdata` bleibt als Rückfall für Systeme ohne sie (Steckbrief).*

---

## Was M6 schon kann (Abgleich)

- Läufe mit Journal, Sperrfrist, Wiederaufnahme, Zustand `waiting`, Abbruch, „ein offener Lauf je Bahn“ (`run.lane_id`).
- Jeder Lauf hat eine auslösende Person (`run.user_id`, nicht leer) und einen Ort (`run.conversation_id`); Lese- und Schreibbereich folgen dem Ort (`agents/scope.py`), Entwürfe bleiben bei den Bearbeitenden.
- Auslöser Erwähnung, Direktnachricht, Ticketzuweisung, Übergabe (`run.chain_depth` ≤ 3, höchstens 5 Übergaben je Lauf).
- Freigaben und Rückfragen an die auslösende Person; `usage_record` je Modellaufruf mit Kosten, sofern ein Preis hinterlegt ist; Grenzen je Lauf (Schritte, Laufzeit).
- Outbox mit Zustellung mindestens einmal; Ereignisse `page.published`, `ticket.created`, `ticket.updated` u. a. tragen den Akteur (auch Agenten), aber keinen Lauf.

## Entscheidungen dieses Plans

1. **Kein DBOS, auch nicht für Zeitpläne.** Fällige Aufgaben holt eine Schleife im Worker mit `FOR UPDATE SKIP LOCKED`. In **einer** Transaktion entstehen der Lauf (bzw. der Vermerk „übersprungen“), der Eintrag im Protokoll der Aufgabe und der nächste Termin. Damit läuft ein Termin bei beliebig vielen Replikas genau einmal; ein eindeutiger Index `(automation_id, due_at)` im Protokoll sichert es zusätzlich. Spezifikation E10 und 12.4 werden entsprechend ergänzt.
2. **Jede Aufgabe gehört einer Person.** Der Lauf einer Aufgabe hat diese Person als auslösende Person (`run.user_id`); es gelten ihre Rechte ∩ die des Agenten ∩ das Publikum des Ortes, wie in M6. Läufe ohne Person gibt es weiterhin nicht. Freigaben und Rückfragen gehen an die Eigentümerin. Ist sie nicht mehr aktiv, hat sie `ai.use` verloren oder erreicht sie Agent oder Ort nicht mehr, wird die Aufgabe **angehalten** (`paused_reason`), und die verantwortliche Person des Agenten sowie die Verwaltenden des Bereichs bekommen eine Aktivität. Wer die Aufgabe selbst anlegen dürfte, kann sie **übernehmen** (wird Eigentümerin). Das ersetzt die in 5.4 angekündigte Weitergabe von Freigaben an die verantwortliche Person: Rechte wandern nie still, nur durch eine ausdrückliche Übernahme.
3. **Jede Aufgabe hat einen Ort**, an den das Ergebnis geht: die Direktnachricht der Eigentümerin mit dem Agenten, ein Kanal eines Bereichs (der Lauf eröffnet dort einen Thread je Termin) oder ein Ticket-Thread. Der Ort bestimmt Lese- und Schreibbereich nach den Regeln aus M6; neue Regeln entstehen nicht. Der Auftragstext der Aufgabe steht im Kontext als Wort der Eigentümerin; im Thread erscheint er als Systemeintrag „Aufgabe … gestartet“ (ohne den Auftragstext in Outbox, Logs oder NOTIFY). *Geändert in M7 [Claude, 14.11.2026]: Der Auftrag wird beim Feuern in den Termin kopiert (`automation_firing.instruction`); ein wartender oder wieder aufgenommener Lauf arbeitet mit dem Auftrag seines Termins, auch wenn die Eigentümerin ihn inzwischen ändert. Beim Heartbeat schreibt erst der Lauf den Systemeintrag, wenn er etwas zuzustellen hat.*
4. **Vier Arten in einer Tabelle `automation`:** `once` (Zeitpunkt), `recurring` (Cron mit IANA-Zeitzone), `heartbeat` (Abstand in Minuten, aktive Stunden als Wochentage und Von–Bis in einer Zeitzone, Checkliste), `event` (Ereignisart mit Filter). Ein Feld je Art nur, wo ein getesteter Leser es braucht.
5. **Termine:** Der nächste Termin wird beim Auslösen aus „jetzt“ berechnet, nicht aus dem verpassten. Nach einem Ausfall läuft eine Aufgabe einmal nach, nicht einmal je verpasstem Termin. Zeitumstellung: nicht vorhandene Ortszeiten fallen auf den nächsten gültigen Zeitpunkt, doppelte laufen einmal. Kleinster Abstand 15 Minuten (wiederkehrend und Heartbeat), geprüft beim Speichern an den nächsten fünf Terminen.
6. **Überspringen statt stauen:** Arbeitet der vorige Lauf der Aufgabe noch (Bahn `lane_id` = Aufgabe), wird der Termin übersprungen und im Protokoll vermerkt (`skipped_busy`). Ebenso `skipped_budget`, `skipped_paused_agent`, `skipped_policy`. *Geändert in M7 [Claude, 14.11.2026]: Dazu `skipped_off_hours` (Heartbeat nach einem Ausfall außerhalb der Stunden) und `skipped_depth` (Entscheidung 9). Damit die Bahn die Aufgabe sein kann, verliert `run.lane_id` seinen Fremdschlüssel auf `message`.*
7. **Heartbeat:** Antwortet der Agent genau mit `HEARTBEAT_OK` (nach Trimmen), wird das im Protokoll der Aufgabe vermerkt und nichts zugestellt; sonst geht die Antwort an den Ort. Außerhalb der aktiven Stunden entsteht kein Termin.
8. **Ereignis-Auslöser** hängen an einem Bereich und laufen über einen Outbox-Handler. Arten in M7: `page.published`, `ticket.created` (Filter: Tag, Art), `attachment.uploaded` (neu als Ereignis, nur IDs), `page.review_due` (Entscheidung 11). Der Inhalt des Ereignisses ist für den Lauf nicht vertrauenswürdig: Der Lauf bekommt nur die Art und die ID des Objekts als gerahmte Angabe und liest es mit seinen Werkzeugen im Rahmen seines Lesebereichs. Die Person, die das Ereignis verursacht, löst nichts mit ihren eigenen Rechten aus und gewinnt keine: Es gelten die Rechte der Eigentümerin der Regel, am Ort der Regel (Kanal oder Ticket des Bereichs), also mit der Sicht eines Betrachters und Schreiben nur in diesen Bereich. Ereignis-Regeln anlegen darf nur, wer den Bereich verwaltet. *Geändert in M7 [Claude, 14.11.2026]: Ort einer Ereignis-Regel ist immer ein Kanal oder Ticket ihres Bereichs. `attachment.uploaded` sendet nur ein Upload über die Route, kein Import. Die Filter von `ticket.created` werden am Ticket gelesen, wie es beim Zustellen ist. Ein Objekt, das der Lauf am Ort nicht lesen dürfte, wird gar nicht aufgenommen (kein Lauf, keine Zählung, kein Protokoll).*
9. **Ruhezeit und Tiefe:** Je Regel eine Ruhezeit (Standard 5 Minuten, mindestens 1 Minute): Innerhalb der Ruhezeit entsteht höchstens ein Lauf; weitere Ereignisse werden gezählt und dem nächsten Lauf als Anzahl mitgegeben, nicht einzeln nachgeholt. Ereignisse tragen neu `event_outbox.run_id`, wenn ein Lauf sie verursacht hat (gesetzt vom Schritt-Host). Ein Lauf aus einem solchen Ereignis erhält `chain_depth` = Tiefe des verursachenden Laufs + 1; bei Tiefe 3 entsteht kein weiterer Lauf (`skipped_depth` im Protokoll). Dasselbe Feld `chain_depth` zählt Übergaben und Ereignisse zusammen. Eine Regel reagiert nie auf ein Ereignis, das ihr eigener Lauf am selben Objekt verursacht hat. *Geändert in M7 [Claude, 14.11.2026]: „Am selben Objekt“ heißt: an einem Objekt, um das es im Termin dieses Laufs ging. Ein eigenes Feld `depth` am Ereignis gibt es nicht, die Tiefe liest der Handler am verursachenden Lauf. In der Ruhezeit wartende Ereignisse (`automation_event` ohne Termin) feuern an ihrem Ende als ein Termin mit der größten Tiefe; der Lauf erfährt Art, Anzahl und die IDs der neuesten 20 Objekte.*
10. **Budgets:** Tabelle `ai_budget` (Geltung: Organisation, Person oder Agent; Tageslimit in Tokens und/oder in Währung; `version`). Der Tag ist der UTC-Tag (wie die Tagesansicht aus M4b). Geprüft wird vor jedem Modellaufruf im Schritt-Host gegen die Summe aus `usage_record` (Index nach Geltung und Tag; im Steckbrief gemessen, eine Summentabelle nur, wenn die Messung sie verlangt). Ist ein Limit erreicht, endet der Lauf mit dem neuen Stopgrund `budget`, die auslösende Person sieht einen Hinweis am Ort, und fällige Aufgaben werden mit `skipped_budget` übersprungen. Ein Währungslimit greift nur für Aufrufe mit hinterlegtem Preis; ohne Preis zählt nur das Token-Limit (so in der Oberfläche gesagt). Ein laufender Modellaufruf wird nicht abgebrochen: Das Limit kann um einen Aufruf überschritten werden. *Geändert in M7 [Claude, 14.11.2026]: Eine Summentabelle ist nicht gebaut: Die Messung (Steckbrief, 100.000 Aufrufe des Tages) ergab P50 14 ms mit Budgets für Person und Agent und 63 bis 83 ms mit einem Budget der Organisation; erst deutlich mehr Aufrufe mit einem Budget der Organisation verlangen eine Tagessumme (Folgepunkt). Ein von einem Budget gestoppter Lauf reiht keinen Folgelauf ein. Metrik `herd_budget_stops_total{scope}`.*
11. **Veraltete Seiten:** `space.review_interval_days` (leer = aus) und `page.reviewed_at` (gesetzt beim Veröffentlichen und durch „Als geprüft markieren“ mit `page.edit`). Ein täglicher Durchlauf im Worker (als eingebaute Aufgabe über dieselbe Fälligkeits-Schleife, genau einmal) erzeugt je fälliger Seite einmal je Frist das Ereignis `page.review_due` (`page.review_notified_at`), daraus eine Aktivität bei den Moderierenden des Bereichs und, falls eine Regel besteht, einen Lauf. Entwürfe, Papierkorb und Gedächtnisseiten zählen nicht. *Geändert in M7 [Claude, 14.11.2026]: Der Durchlauf ist keine eingebaute Aufgabe (keine Zeile in `automation`): Die Fälligkeits-Schleife geht einmal je UTC-Tag durch jeden Bereich mit Frist, gesperrt auf der Zeile des Bereichs, in Schritten von höchstens 100 Seiten, und vermerkt den Tag in `space.review_checked_on`. Genau einmal gilt so ebenfalls; eine geänderte Frist löst den nächsten Durchlauf sofort aus.*
12. **Wer darf was:** Aufgaben anlegen darf, wer `ai.use` hat, den Agenten erreicht und am Ort schreiben darf; für Kanäle und Tickets eines Bereichs außerdem nur mit einem Agenten, der dort Mitglied ist. Ereignis-Regeln: nur Verwaltende des Bereichs. Anhalten, fortsetzen und löschen dürfen die Eigentümerin, die Verwaltenden des Bereichs und `agent.manage`; ändern nur die Eigentümerin (wer ändert, verantwortet den Auftrag). Persönliche Agenten: nur Aufgaben ihrer Eigentümerin mit Ort Direktnachricht oder persönlicher Bereich. Obergrenze `HERD_AI_AUTOMATIONS_MAX` je Person (Standard 20). Unsichtbares antwortet 404. *Geändert in M7 [Claude, 14.11.2026]: Wer sie sieht, aber die Aktion nicht darf, bekommt 403 `automation.not_allowed`; die Oberfläche bietet nur an, was `abilities` nennt. Wer eine Aufgabe sieht, regelt allein `automations/sight.py` (API, Live-Ereignisse, Aktivitäten).*
13. **Selbstschutz:** Nach drei Läufen in Folge, die nicht mit `completed` enden, hält die Aufgabe an (`paused_reason = failing`) mit Aktivität an die Eigentümerin. Ein pausierter oder gelöschter Agent, ein gelöschter Ort oder eine KI-Sperre des Bereichs halten sie ebenfalls an bzw. überspringen den Termin. *Geändert in M7 [Claude, 14.11.2026]: Ein abgebrochener oder von einem Budget gestoppter Lauf zählt nicht als Fehlschlag und setzt den Zähler auch nicht zurück; Fortsetzen und Übernehmen setzen ihn zurück.*
14. **Aufgabenverwaltung:** je Aufgabe nächster Termin, letzter Lauf mit Ergebnis, Protokoll der letzten Termine (paginiert), Anhalten und Fortsetzen, „Jetzt ausführen“ (ein Termin außer der Reihe, gleiche Regeln). Sichten: „Meine Aufgaben“, je Agent (Verwaltung), je Bereich. *Geändert in M7 [Claude, 14.11.2026]: „Jetzt ausführen“ darf nur die Eigentümerin (wie Ändern), und nicht für Ereignis-Regeln. Löschen setzt den Zustand `deleted` (die Läufe bleiben einsehbar, die Zeile wird nicht entfernt). Das SSE-Ereignis heißt `automation.changed`, aus dem Outbox-Ereignis `automation.updated`.*
15. **Nachtrag aus M6:** Der Abbrechen-Knopf der Laufansicht bekommt dieselbe kurze Sperrgrenze wie die Neuzuweisung (409 `conflict.retry`). `propose_new_page` nach gelesenem Entwurf bleibt gesperrt.

## Nicht in M7

Kalender (M10), externe Auslöser über Token oder Webhook (M8), Budgets je Bereich oder Monat, Benachrichtigung per E-Mail.

## Global Constraints

- Alles aus `CLAUDE.md`; insbesondere: keine Inhalte (Auftragstexte, Checklisten, Antworten) in Logs, Outbox, NOTIFY, Metrik-Labels oder Audit; nur IDs, Arten, Zähler, Codes.
- Migrationen nur erweiternd, eine je Scheibe, ein Head; neue Enum-Werte (`budget`, Protokoll-Ergebnisse) so, dass der vorige Stand weiterläuft.
- Jede neue Einstellung `HERD_AI_*` in Compose, Chart und `docs/AGENTEN.md`.
- Zeit in Tests über eine einstellbare Uhr, keine Schlafpausen; Wettläufe mit echten Commits und mehreren Verbindungen.
- Dateien ≤ ~300 Zeilen; neues Modul `modules/automations` (Modelle, Termine, Auslösen, Regeln, Verwaltung getrennt), Budgets in `modules/ai`, Seitenprüfung in `modules/wiki`.

## Review Focus

1. Genau einmal: drei Worker, Absturz zwischen Auslösen und Commit, Uhr springt, Zeitumstellung.
2. Rechte: Aufgabe einer Person, die Rechte verliert; Übernahme; Ereignis durch jemanden mit weniger Rechten als die Eigentümerin der Regel (kein Gewinn, kein Leck); persönlicher Agent.
3. Schleifen: Regel reagiert auf eigene Wirkung, zwei Regeln im Kreis, Tiefe 3, Ruhezeit unter Last.
4. Budgets: Wettlauf mehrerer Läufe am Limit, Limit geändert während des Laufs, fehlender Preis.
5. Heartbeat: `HEARTBEAT_OK` wird nirgends zugestellt; aktive Stunden über Mitternacht und Zeitzonen.
6. Veraltete Seiten: einmal je Frist, nichts über unsichtbare Seiten.

---

## Aufgaben

### Task 1: Budgets (Backend)
`ai_budget`, Summen aus `usage_record` mit Index, Prüfung vor jedem Modellaufruf, Stopgrund `budget`, Hinweis am Ort, API für Admins (`ai.manage`: lesen, setzen, löschen; paginiert), Verbrauch je Person, Agent, Bereich und Tag ergänzen, wo er fehlt.
- [ ] Tests zuerst (Limit Tokens und Währung je Geltung; engstes Limit gewinnt; Wettlauf; Aufruf ohne Preis; Limit geändert) → Umsetzung → Gates → Commit `ai: add daily budgets`

### Task 2: Aufgaben und Fälligkeits-Schleife
`automation`, `automation_firing` (Protokoll; eindeutig je Termin), Termine für `once` und `recurring` (Cron, Zeitzone, Mindestabstand), Schleife im Worker (`SKIP LOCKED`, eine Transaktion je Termin), Überspringen, Nachlauf nach Ausfall, einstellbare Uhr.
- [ ] Tests zuerst (drei Schleifen auf einer Datenbank: ein Lauf; Absturz vor dem Commit: kein doppelter, kein verlorener Termin; Zeitumstellung; `skipped_busy`) → Umsetzung → Gates → Commit `automations: fire due automations exactly once`

### Task 3: Lauf einer Aufgabe
Ort und Auftrag im Kontext (Entscheidung 3), Thread je Termin im Kanal, Systemeintrag, Bahn je Aufgabe, Anhalten bei verlorenen Rechten und nach drei Fehlschlägen, Übernahme, Budget- und Richtlinien-Überspringen, Abbruch.
- [ ] Tests zuerst (Rechte der Eigentümerin ∩ Agent ∩ Ort; Eigentümerin deaktiviert → angehalten, Aktivität; Übernahme; Freigabe geht an die Eigentümerin; Entwurfsregel gilt) → Umsetzung → Gates → Commit `automations: run an automation as its owner`

### Task 4: Heartbeat
Abstand, aktive Stunden, Checkliste, `HEARTBEAT_OK` nur protokolliert.
- [ ] Tests zuerst (über Mitternacht, Zeitzone, nichts zugestellt und nichts in Aktivität bei OK) → Umsetzung → Gates → Commit `automations: add heartbeats`

### Task 5: Ereignis-Auslöser
`event_outbox.run_id`, Ereignis `attachment.uploaded`, Handler mit Filter, Ruhezeit, Tiefe, Selbstauslösung ausgeschlossen; idempotent bei doppelter Zustellung.
- [ ] Tests zuerst (Kette stoppt bei Tiefe 3; zwei Regeln im Kreis; doppelte Zustellung: ein Lauf; Ereignis einer Betrachterin: Lauf sieht nur, was ein Betrachter sieht; Ruhezeit zählt zusammen) → Umsetzung → Gates → Commit `automations: trigger on events with a quiet time and a depth limit`

### Task 6: Veraltete Seiten (Backend)
Felder, täglicher Durchlauf über die Fälligkeits-Schleife, Ereignis, Aktivität, „Als geprüft markieren“, Filter „Prüfung fällig“ in der Seitenliste.
- [ ] Tests zuerst (einmal je Frist; Sichtbarkeit; Entwürfe und Gedächtnisseiten ausgenommen) → Umsetzung → Gates → Commit `wiki: flag pages whose review is due`

### Task 7: Verwaltung der Aufgaben (API)
Anlegen, ändern (`version` → 409), anhalten, fortsetzen, löschen, „Jetzt ausführen“, Protokoll; Sichten „meine“, je Agent, je Bereich; Rechte nach Entscheidung 12; Obergrenze; Vorschau der nächsten fünf Termine; `openapi.json` neu.
- [ ] Tests zuerst (jede Rolle gegen jede Aktion; 404 für Unsichtbares; Obergrenze; persönlicher Agent) → Umsetzung → Gates → Commit `automations: add the management API`

### Task 8: Oberfläche Aufgaben
`features/automations`: Listen, Formular je Art (Vorlagen für häufige Zeitpläne statt rohem Cron, Cron als Expertenfeld mit Vorschau der Termine in der Zeitzone), Protokoll, Zustände angehalten mit Grund, Übernehmen, Live-Aktualisierung über ein SSE-Ereignis `automation.changed` (nur IDs). i18n de/en, 375 px, hell und dunkel, Tastatur.
- [ ] vitest zuerst → Umsetzung → lint, typecheck, build, check-i18n → Commit `web: add the automations views`

### Task 9: Oberfläche Budgets, Ereignis-Regeln, veraltete Seiten
Budgets in der KI-Verwaltung mit Verbrauch des Tages; Hinweis `budget` in Laufansicht und am Ort; Ereignis-Regeln im Bereich; Prüffrist in den Bereichseinstellungen, Kennzeichen und „Als geprüft markieren“ an der Seite, Filter im Seitenbaum.
- [ ] vitest zuerst → Umsetzung → Gates → Commit `web: add budgets, event rules and review marks`

### Task 10: Browsertests, Demo-Daten, Demo
`e2e/tests/automations.spec.mjs` mit dem Stub und einer einstellbaren Uhr (nur im e2e-Geschirr): Zeitplan läuft einmal, Heartbeat OK bleibt still, Ereignis-Kette stoppt, Budget stoppt einen Lauf, Seite wird fällig. `backend/scripts/demo_automations.py` (+ Test), `docs/demo/m7.md` ausgeführt und protokolliert, darin die Abnahme mit **drei Worker-Prozessen** auf einer Datenbank; `SMOKE_NODES=1` um einen Zeitplan ergänzen, wenn es ohne lange Wartezeit geht.

### Task 11: Betrieb und Dokumentation
Metriken (`herd_automations_due`, Verzug des ältesten fälligen Termins, Auslösungen nach Ergebnis, Budget-Stopps) und Alarme (`HerdAutomationsLagging`, promtool-Tests), Compose und Chart (neue Variablen), `docs/AGENTEN.md` (Aufgaben, Ereignisse, Budgets, Grenzen), `docs/WIKI.md` (Prüffrist), `docs/KI.md` (Budgets), README, `CLAUDE.md`, Steckbrief (Messung: Verzug bei 1.000 fälligen Aufgaben, Kosten der Budgetprüfung je Aufruf), Spezifikation (E10, 4.3, 5.4, 7.4, 8.4, 9, 12.4, 14) mit Vermerken „Geändert in M7“. *Geändert in M7 [Claude, 14.11.2026]: Gebaut wie geplant, dazu die Gauges `herd_automations_paused{reason}`, `herd_wiki_review_reminders_total`, `herd_wiki_review_spaces_unchecked`, der Alarm `HerdAutomationsFailing` (Anstieg der wegen Fehlschlägen angehaltenen Aufgaben) und die Aufbewahrung im Worker (Termine 90 Tage, aufgenommene Ereignisse 7 Tage, als Konstanten, nicht einstellbar; Migration nur für einen Index). Neue Variablen gibt es außer `HERD_AI_AUTOMATIONS_MAX` (Task 7) keine. Vermerke auch in 5.6 und 8.3. Gemessen zusätzlich der Prüfdurchlauf über 10.000 Seiten.*

## Reihenfolge und Parallelität

Task 1 und Task 2 parallel (nur Task 2 legt die Migration für `automation` an; Migrationen nacheinander verketten). Dann 3 → 4 und 5 parallel → 6 und 7 parallel → 8 und 9 parallel → 10 und 11 parallel. Danach Modul-Review mit Behebung.
