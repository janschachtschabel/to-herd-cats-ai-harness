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
  als Zeitpunkte und seine Zone `time_zone` (sonst die des Kalenders); ein ganztägiger nennt ersten
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
  Diese Antwort verrät einer Autorin, dass es die UID im Kalender gibt, auch die eines
  privaten Termins, dessen UID sie sonst nicht sieht. Für erzeugte UIDs ist das ohne
  Belang, importierte können erratbar sein; die Antwort nennt nichts weiter, und kein
  späterer Schreibweg (Ändern, Import) fügt ihr etwas hinzu.
- **Das Fenster** (`GET /api/calendar/events?from&to`) liefert jedes Vorkommen im
  Zeitraum, nach Anfang sortiert und seitenweise (höchstens 100 je Seite, höchstens
  2.000 Vorkommen je Abfrage, sonst 422 `calendar.window_too_dense`, gezählt in
  `herd_calendar_window_too_dense_total`). Dieselbe Antwort gibt es, wenn die gezählte
  Arbeit des Entfaltens 500.000 Schritte übersteigt (je geladener Termin 40, je
  Kandidat einer Regel 1; etwa 12.500 Serien): Serien, die im Zeitraum nicht vorkommen,
  kosten nur ihren Schritt. Die Grenzen `from` und `to` liegen in den Jahren 1900 bis
  2399 (422 `calendar.window_out_of_range`). `time_zone` nennt die Zone der
  Betrachterin: Dort beginnen die Tage ganztägiger Termine (Standard UTC; die
  Oberfläche schickt immer die Zone des Browsers, sonst zeigt sie den Nachbartag).
  Ein Cursor gilt nur mit der Zone, mit der er entstand (sonst 422
  `calendar.cursor_time_zone`). `calendar_ids` filtert, `q` sucht im Titel.
- **Ein Name für Zonen:** Die API heißt jede Zone `time_zone`: die des Kalenders, die
  eines Termins (seine Serie läuft in ihrer Ortszeit; die Spalte heißt wie in
  iCalendar `tzid`) und die der Betrachterin im Fenster.
- **Serien und Ausnahmen:** Ein einzeln geändertes Vorkommen (Ausnahme) steht im
  Fenster als eigener Termin und nennt seine Serie in `series_id` (der Einzelabruf
  dazu in `recurrence_id` das Vorkommen, an dessen Stelle es steht).
- **Ändern** (`PATCH /api/events/<id>`) und **Löschen** (`DELETE /api/events/<id>`)
  nennen die gelesene Version (`version` im Körper bzw. als Parameter; sonst 409
  `event.version_conflict` mit `current_version`). Sie verlangen Autorin im Bereich
  des Kalenders **und** volle Sicht: Wer einen privaten Termin nur als „Belegt“ sieht,
  bekommt auf jeden Schreibversuch 403 `event.private` (ohne Inhalt, ohne Version);
  ohne Autorenrecht 403 `auth.permission_denied`. Die Sichtbarkeit (`visibility`)
  ändern nur die Organisatorin und Admins (403 `event.visibility_organiser_only`). Die
  Organisatorin bleibt, wer den Termin angelegt hat. Eine Änderung wird geprüft wie ein
  neuer Termin (dieselben 422-Codes); nur gesendete Felder ändern sich, Zeiten gehen vom
  gespeicherten Stand aus (`all_day` wechselt die Art und braucht dann deren Grenzen).
- **Welche Vorkommen** (`scope`, mit `occurrence` = `recurrence_id` aus dem Fenster,
  also die Ortszeit des Vorkommens):
  - `scope=all` (Standard; für einzelne Termine und Ausnahmen der einzige) ändert die
    Serie selbst; ihre Zeiten sind die des ersten Vorkommens. Rückt der Anfang auf der
    Uhr der Zone (09:00 → 10:00, ein anderer Tag; dieselbe Uhrzeit in einer anderen
    Zone rückt nicht), rücken gelöschte Vorkommen, Zusatztermine und die Vorkommen der
    Ausnahmen mit: Gelöschtes bleibt gelöscht, Ausnahmen bleiben (zu ihrer eigenen
    Zeit). Was danach kein Vorkommen der neuen Serie mehr trifft (etwa nach einer neuen
    Regel), entfällt; die Antwort nennt es (`dropped_overrides`, `dropped_exdates`), und
    `dry_run=true` rechnet nur, ohne zu schreiben. Selbst gesendete Listen
    `rdates`/`exdates` gelten, wie sie sind; ein gesendetes `exdates`-Datum eines
    einzeln geänderten Vorkommens löscht auch dessen Ausnahme (sie zählt in
    `dropped_overrides`). Der Inhalt erreicht die Ausnahmen: Jedes Feld (Titel, Ort,
    Text, Status, Sichtbarkeit, `busy`), das eine Ausnahme noch mit dem alten Wert der
    Serie hält, bekommt den neuen; was eine Ausnahme selbst geändert hat, bleibt.
    `visibility=private` und `status=cancelled` erreichen jede Ausnahme.
  - `scope=this` legt eine Ausnahme an: eine eigene Zeile mit UID, Inhalt und
    Organisatorin der Serie, zur Zeit des Vorkommens, wenn die Änderung keine andere
    nennt; sie ist keine Serie (`rrule`, `rdates`, `exdates` antworten 422
    `event.scope_invalid`), und ein schon einzeln geändertes Vorkommen 409
    `event.occurrence_overridden` (auch mit `dry_run=true`). Eine neue Ausnahme ändert
    die Version der Serie nicht; wer die Serie vorher gelesen hat, schreibt mit ihrer
    Version weiter. Löschen mit `scope=this` (mit der Version der Serie) macht das
    Vorkommen zu einem gelöschten (höchstens 500, sonst 422 `event.too_many_dates`);
    eine Ausnahme zu löschen löscht ihr Vorkommen ebenso.
  - `scope=following` teilt die Serie. Die neue beginnt am ersten Vorkommen ab dem
    genannten, das die Regel selbst nennt und dessen Ortszeit es gibt (der
    **Ansatzpunkt**: kein bloßer Zusatztermin, keine Uhrzeit in der Lücke der
    Zeitumstellung), mit eigener UID, Inhalt und Organisatorin der alten und ihrer
    Regel ausgeschrieben (Wochentag, Monatstag und Monat, die eine Regel sonst vom
    Anfang nimmt: `FREQ=WEEKLY` wird `FREQ=WEEKLY;BYDAY=MO`), damit sich das Muster
    nicht ändert. Die alte endet eine Sekunde vor dem Ansatzpunkt (ganztägig: am Tag
    davor; `UNTIL` statt `COUNT`). Eine gezählte Serie behält ihre Summe (die neue
    zählt den Rest, gelöschte Vorkommen mitgezählt); spätere Ausnahmen, gelöschte
    Vorkommen und Zusatztermine wandern zur neuen. Vorkommen zwischen dem genannten und
    dem Ansatzpunkt (ein Zusatztermin, ein Vorkommen in der Lücke, etwa 02:30 am Tag
    der Umstellung) bleiben bei der alten Serie und bekommen die Änderung als
    Ausnahme, unter der Ortszeit, die die Regel ihnen gibt; die übrigen behalten ihre
    Uhrzeit. Die Zeiten der Änderung sind die des genannten Vorkommens; dieselbe
    Verschiebung auf der Uhr gilt am Ansatzpunkt und für jedes solche Vorkommen. Der
    Inhalt erreicht die mitgenommenen Ausnahmen wie bei `scope=all`. Nennt die
    Änderung eine eigene Regel, beginnt die neue Serie am genannten Vorkommen. Am
    ersten noch nicht gelöschten Vorkommen ist das `scope=all` (die Zeiten der Änderung
    gelten dann verschoben für den Anfang der Serie). Löschen mit `scope=following`
    beendet die Serie dort, am ersten noch nicht gelöschten Vorkommen löscht es sie.
  - **Ausnahmen, die man nicht voll sieht:** Jede Änderung einer Serie, die eine
    Ausnahme schreiben würde (löschen, entfallen lassen, verschieben, zur neuen Serie
    mitnehmen, ihren Inhalt ändern), braucht auch für diese Ausnahme volle Sicht. Sieht
    die Schreibende eine davon nur als „Belegt“ (eine private Ausnahme einer anderen),
    antwortet die ganze Änderung 403 `event.private`, ohne zu sagen, welche, auch mit
    `dry_run=true`, und nichts wird geschrieben.
  - Bleibt einer Serie kein Vorkommen (alle einzeln gelöscht, oder gesendete
    `exdates` treffen alle), wird sie samt Ausnahmen zum Grabstein.
  - Ein fehlendes Vorkommen ist 422 `event.occurrence_required`, eines, das es nicht
    (mehr) gibt, 422 `event.occurrence_unknown`; `this`/`following` für einen
    einzelnen Termin oder eine Ausnahme 422 `event.scope_invalid`.
- **Gelöschte Termine** bleiben 30 Tage als Grabstein (unsichtbar, ohne UID-Sperre;
  eine Serie nimmt ihre Ausnahmen mit), dann entfernt sie die Fälligkeits-Schleife.
- **Wer was sieht:** Wer den Bereich des Kalenders lesen darf, sieht seine Termine; die
  Organisatorin sieht ihren Termin auch ohne den Bereich (nur diesen Termin, nie den
  Kalender). Einen **privaten** Termin sehen andere Leser nur als Zeit und „Belegt“
  (`redacted: true`, ohne Titel, Ort, Text, UID und Organisatorin), in der Liste, im
  Einzelabruf und in der Suche (die Suche findet ihn nicht über seinen Titel). Einen
  Termin, den man nicht sehen darf, gibt es nicht: 404 `event.not_found` wie für eine
  unbekannte ID.
- **Live:** Jede Änderung meldet `calendar.changed` mit den IDs von Bereich und Kalender
  an die Mitglieder des Bereichs, nie an Admins außerhalb, nie mit Inhalt. Die Outbox
  trägt `calendar_event.created`, `.updated` (mit den Namen der geänderten Spalten,
  etwa `tzid`) und `.deleted`, nur mit IDs; schreibt eine Änderung der Serie auch
  Ausnahmen (verschoben, mitgenommen, geändert, gelöscht), nennt ihr Ereignis deren IDs
  in `overrides`. Eine neue Ausnahme meldet sich mit ihrem eigenen `.created`.

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
- **Abgelehnte Änderungen behalten das Audit:** Wird die Änderung eines Admins in einem
  fremden Bereich abgelehnt (403, 409, 422, auch bei Kalendern, Tickets und Sprints)
  oder scheitert die Anfrage sonst, rollt sie zurück; ihr `admin.access`-Eintrag (und
  ein `calendar.private_read`) wird danach in einer eigenen kurzen Transaktion noch
  einmal geschrieben, denn der Blick in den Bereich hat stattgefunden. Die Dienste
  selbst schreiben nie fest; ein Aufrufer außerhalb einer Anfrage (Import,
  Agentenschritt) ruft dafür nach seinem Zurückrollen `audit.kept.write` auf.
- **Schreiben kraft Admin-Recht steht immer im Audit:** Ändert oder löscht ein Admin
  einen Termin, den er ohne Admin-Recht nicht schreiben dürfte (einen privaten Termin
  eines anderen, oder ohne Autorenrecht im Bereich), entsteht je Schreibvorgang
  `calendar.admin_write` (Ziel der Termin; dazu die IDs von Bereich und Kalender, die
  Art `update`/`delete`, `scope` und die Namen der geänderten Spalten, nie ihre Werte).
  Das gilt auch, wenn erst eine Ausnahme, die die Änderung der Serie mitschreibt, nur
  kraft Admin-Recht sichtbar ist. Eine Änderung, die nichts ändert, schreibt keinen
  Eintrag.
- **Der Schalter für den Abgleich** (`PUT /api/admin/calendar-settings`, Recht
  `calendar.manage`) steht im Audit (`calendar.settings_set`), wenn er sich ändert.

## Schreibgrenze

Anlegen, Ändern und Archivieren eines Kalenders und das Anlegen, Ändern (auch mit
`dry_run`) und Löschen eines Termins zählen zur Schreibgrenze je Person
(`HERD_WRITE_RATE_PER_MINUTE`, darüber 429 `rate.limited` mit `Retry-After`; siehe
[`SICHERHEIT.md`](SICHERHEIT.md)), wie Seiten und Nachrichten. Lesen zählt nicht, der
Schalter für den Abgleich als Einstellung der Verwaltung auch nicht.
