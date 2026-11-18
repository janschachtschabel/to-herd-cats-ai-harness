# Kalender: Bedienung und Betrieb

Der Kalender entsteht mit Meilenstein 10 (Plan
`docs/superpowers/plans/2026-11-18-m10-kalender.md`, Entscheidungen 2 und 3). Diese
Seite wächst mit jeder Aufgabe; vollständig wird sie mit Task 21 (Bedienung, Serien,
Einladungen, Feeds und Abos, Abgleich, Betrieb). Bisher beschreibt sie Kalender,
Standardkalender und Rechte.

## Kalender und Bereiche

- **Jeder Kalender gehört zu einem Bereich**, und dessen Rechte sind seine Rechte:
  lesen ab der Rolle Leser, Termine schreiben ab Autor, Kalender anlegen, umbenennen,
  umfärben und archivieren ab Moderator. Gäste sehen Kalender nur in Bereichen, in denen
  sie Mitglied sind.
- **Höchstens 20 Kalender je Bereich**, archivierte nicht mitgezählt (darüber 409
  `calendar.limit`). Ein archivierter Kalender ist für alle weg (in keiner Liste, per ID
  404); zurückholen lässt er sich nicht.

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

## Was Admins sehen und was im Audit steht

- **Listen gelten für alle gleich, auch für Admins:** `/api/calendars` enthält nur
  Kalender der Bereiche, in denen man Mitglied ist (offene Bereiche über die Rolle).
- **Fremde Bereiche nur auf dem benannten Weg:** `GET /api/spaces/<id>/calendars`, der
  Abruf, das Ändern oder Archivieren eines Kalenders per ID. Öffnet ein Admin so einen
  Team- oder persönlichen Bereich, in dem er nicht Mitglied ist, steht das im Audit
  (`admin.access`, einmal je Admin, Bereich und Tag). Legt ein Admin im persönlichen
  Bereich einer Person einen Kalender an, entsteht dabei auch ihr „Mein Kalender“.
- **Bekannte Lücke:** Wird die Änderung eines Admins in einem fremden Bereich abgelehnt
  (409 wegen veralteter Version, der Grenze oder eines Standardkalenders), rollt die
  Anfrage samt ihrem `admin.access`-Eintrag zurück. Das gilt heute ebenso für Tickets und
  Sprints. Der Admin erfährt dabei nur, dass es den Kalender gibt, und seine Version;
  die ID kannte er schon. Termine (M10 Task 3b) schreiben den Eintrag vor jeder
  Ablehnung, weil eine Ablehnung dort mehr verrät.
- **Der Schalter für den Abgleich** (`PUT /api/admin/calendar-settings`, Recht
  `calendar.manage`) steht im Audit (`calendar.settings_set`), wenn er sich ändert.
