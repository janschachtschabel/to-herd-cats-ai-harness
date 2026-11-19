# Kalender: Bedienung und Betrieb

Der Kalender entsteht mit Meilenstein 10 (Plan
`docs/superpowers/plans/2026-11-18-m10-kalender.md`, Entscheidungen 2 und 3). Diese
Seite wächst mit jeder Aufgabe; vollständig wird sie mit Task 21 (Bedienung, Serien,
Einladungen, Feeds und Abos, Abgleich, Betrieb). Bisher beschreibt sie Kalender,
Standardkalender, Rechte und Termine (anlegen, lesen, sehen; Task 3a).

## Kalender und Bereiche

- **Jeder Kalender gehört zu einem Bereich**, und dessen Rechte sind seine Rechte:
  lesen ab der Rolle Leser, Termine schreiben ab Autor, Kalender anlegen, umbenennen,
  umfärben und archivieren ab Moderator. Gäste sehen Kalender nur in Bereichen, in denen
  sie Mitglied sind.
- **Höchstens 20 Kalender je Bereich**, archivierte nicht mitgezählt (darüber 409
  `calendar.limit`). Ein archivierter Kalender ist für alle weg (in keiner Liste, per ID
  404); zurückholen lässt er sich nicht.
- **Zeitzone je Kalender** (`time_zone`, IANA-Name, ohne Angabe `Europe/Berlin`): Sie
  gilt für neue Termine, die keine eigene Zone nennen; schon angelegte Termine behalten
  ihre. Ein unbekannter Name antwortet 422 `calendar.invalid_time_zone`.

## Standardkalender

- **„Mein Kalender“** im persönlichen Bereich jeder Person und **ein Kalender im
  allgemeinen Bereich** entstehen beim ersten Aufruf der Kalenderliste, je Bereich
  genau einmal.
- **Ohne gespeicherten Namen:** Die API liefert `name: null` mit `is_default: true`; die
  Oberfläche zeigt „Mein Kalender“ bzw. „Allgemein“ in der Sprache der Person (englisch
  „My calendar“, „General“). Wer ihn umbenennt, gibt ihm einen festen Namen.
- **Nicht archivierbar:** Archivieren eines Standardkalenders antwortet 409
  `calendar.default_kept`.
- **Er zählt zur Grenze von 20.** Hat ein offener Bereich schon 20 Kalender, wenn er
  zum allgemeinen Bereich wird, bekommt er keinen Standardkalender.
- **Der allgemeine Bereich wird an seinem Namen erkannt** (offener Bereich namens
  „Allgemein“, wie bei der Einrichtung): Jeder offene Bereich dieses Namens bekommt einen
  Standardkalender; ein umbenannter allgemeiner Bereich bekommt keinen neuen, behält
  aber den, den er schon hat.

## Termine

- **Anlegen** (`POST /api/calendars/<id>/events`) darf, wer im Bereich des Kalenders
  Autor ist. Wer anlegt, ist Organisatorin. Ein Termin mit Uhrzeit nennt Anfang und Ende
  als Zeitpunkte und seine Zone (sonst die des Kalenders); ein ganztägiger nennt ersten
  und letzten Tag und liegt „schwebend“ auf diesen Tagen. Ganztägige Termine sind im
  Standard „frei“, alle anderen „belegt“. Titel ≤ 300 Zeichen, Ort ≤ 500, Text ≤ 20.000
  (reiner Text, nie als HTML gezeigt). Zeitpunkte tragen immer ihren Versatz (ohne:
  422) und liegen in den Jahren 1900 bis 2399 (sonst 422 `event.time_out_of_range`).
  Ein Termin dauert höchstens 366 Tage (422 `event.too_long`).
- **Serien** nach RFC 5545: Regel ab `DAILY` (stündlich und feiner antwortet 422
  `event.rrule_unsupported`), dazu einzelne Zusatz- und Ausnahmetermine als Ortszeit der
  Zone. Entfaltet wird beim Lesen in der Ortszeit: 09:00 bleibt über die Zeitumstellung
  09:00. Kein Vorkommen dauert über den Anfang des nächsten hinaus (422
  `event.series_overlaps`; gemessen an der Uhr der Zone, so bleibt eine tägliche
  24-Stunden-Schicht über die Zeitumstellung erlaubt). Geprüft werden die ersten 1.000
  Vorkommen (eine gezählte Serie ganz) und die Umgebung jedes späteren Zusatztermins.
  Fehler antworten 422 mit Code (`event.invalid_time`, `event.invalid_time_zone`,
  `event.time_out_of_range`, `event.too_long`, `event.series_overlaps`,
  `event.rrule_invalid`).
- **Eine UID je Kalender:** Zwei Termine mit derselben UID in einem Kalender gibt es
  nicht (409 `event.uid_taken`); ein gelöschter Termin blockiert seine UID nicht.
- **Das Fenster** (`GET /api/calendar/events?from&to`) liefert jedes Vorkommen im
  Zeitraum, nach Anfang sortiert und seitenweise (höchstens 100 je Seite, höchstens
  2.000 Vorkommen je Abfrage, sonst 422 `calendar.window_too_dense`, gezählt in
  `herd_calendar_window_too_dense_total`). Dieselbe Antwort gibt es, wenn die gezählte
  Arbeit des Entfaltens 500.000 Schritte übersteigt (je geladener Termin 40, je
  Kandidat einer Regel 1; etwa 12.500 Serien): Serien, die im Zeitraum nicht vorkommen,
  kosten nur ihren Schritt. Die Grenzen `from` und `to` liegen in den Jahren 1900 bis
  2399 (422 `calendar.window_out_of_range`). `tz` nennt die Zone der Betrachterin: Dort
  beginnen die Tage ganztägiger Termine (Standard UTC). `calendar_ids` filtert, `q`
  sucht im Titel.
- **Wer was sieht:** Wer den Bereich des Kalenders lesen darf, sieht seine Termine; die
  Organisatorin sieht ihren Termin auch ohne den Bereich (nur diesen Termin, nie den
  Kalender). Einen **privaten** Termin sehen andere Leser nur als Zeit und „Belegt“
  (`redacted: true`, ohne Titel, Ort, Text, UID und Organisatorin), in der Liste, im
  Einzelabruf und in der Suche (die Suche findet ihn nicht über seinen Titel). Einen
  Termin, den man nicht sehen darf, gibt es nicht: 404 `event.not_found` wie für eine
  unbekannte ID.
- **Live:** Jede Änderung meldet `calendar.changed` mit den IDs von Bereich und Kalender
  an die Mitglieder des Bereichs, nie an Admins außerhalb, nie mit Inhalt.

## Was Admins sehen und was im Audit steht

- **Listen gelten für alle gleich, auch für Admins:** `/api/calendars` enthält nur
  Kalender der Bereiche, in denen man Mitglied ist (offene Bereiche über die Rolle).
- **Fremde Bereiche nur auf dem benannten Weg:** `GET /api/spaces/<id>/calendars`, der
  Abruf, das Ändern oder Archivieren eines Kalenders per ID. Öffnet ein Admin so einen
  Team- oder persönlichen Bereich, in dem er nicht Mitglied ist, steht das im Audit
  (`admin.access`, einmal je Admin, Bereich und Tag). Legt ein Admin im persönlichen
  Bereich einer Person einen Kalender an, entsteht dabei auch ihr „Mein Kalender“.
- **Termine ebenso:** Das Fenster ohne `space_id`, die Suche und „Meine Termine“
  enthalten nur Termine von Bereichen, in denen man Mitglied ist, und eigene. Fremde
  Termine sieht ein Admin über das Fenster mit `space_id=<Bereich>` oder den Abruf
  eines Termins per ID; nur dort sieht er auch den Inhalt privater Termine (E4), und
  das Öffnen eines fremden Team- oder persönlichen Bereichs steht im Audit.
- **Private Termine kraft Admin-Recht stehen immer im Audit:** Zeigt der Einzelabruf
  oder das Fenster mit `space_id=` einem Admin den Inhalt eines privaten Termins, den er
  ohne Admin-Recht nur als „Belegt“ sähe, entsteht `calendar.private_read` (Ziel der
  Termin, dazu nur die IDs von Bereich und Kalender; einmal je Admin, Termin und Tag).
  Das gilt auch, wenn er Mitglied des Bereichs ist oder der Bereich offen ist. Eigene
  Rechte (Organisatorin, gewöhnliche Leser) schreiben nie einen Eintrag.
- **Bekannte Lücke:** Wird die Änderung eines Admins in einem fremden Bereich abgelehnt
  (409 wegen veralteter Version, der Grenze oder eines Standardkalenders), rollt die
  Anfrage samt ihrem `admin.access`-Eintrag zurück. Das gilt heute ebenso für Tickets und
  Sprints. Der Admin erfährt dabei nur, dass es den Kalender gibt, und seine Version;
  die ID kannte er schon. Termine (M10 Task 3b) schreiben den Eintrag vor jeder
  Ablehnung, weil eine Ablehnung dort mehr verrät.
- **Der Schalter für den Abgleich** (`PUT /api/admin/calendar-settings`, Recht
  `calendar.manage`) steht im Audit (`calendar.settings_set`), wenn er sich ändert.

## Schreibgrenze

Anlegen, Ändern und Archivieren eines Kalenders und das Anlegen eines Termins zählen zur Schreibgrenze je Person
(`HERD_WRITE_RATE_PER_MINUTE`, darüber 429 `rate.limited` mit `Retry-After`; siehe
[`SICHERHEIT.md`](SICHERHEIT.md)), wie Seiten und Nachrichten. Lesen zählt nicht, der
Schalter für den Abgleich als Einstellung der Verwaltung auch nicht.
