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
  Die Grenze gilt **je Abfrage, nicht je Zeitraum:** Eine Folgeseite entfaltet nur ab
  ihrem Cursor. Ein Zeitraum über der Grenze antwortet schon auf der ersten Seite 422,
  aber eine Seite mit einem späteren Cursor kann 200 antworten (ein Cursor ist ein
  beliebiger Zeitpunkt mit ID). Ein 200 auf einer Folgeseite heißt also nicht, dass
  der ganze Zeitraum passt; wer das wissen will, liest ihn von der ersten Seite an.
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
  Organisatorin und jede Eingeladene sehen den Termin auch ohne den Bereich (nur diesen
  Termin, nie den Kalender, seine anderen Termine oder den Bereich), und zwar ganz, auch
  einen privaten. Einen **privaten** Termin sehen andere Leser nur als Zeit und „Belegt“
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

## Einladungen und Antworten

- **Eingeladene** (`PUT /api/events/<id>/attendees`, die ganze Liste mit der gelesenen
  `version`; 409 `event.version_conflict`) setzt, wer den Termin ändern darf (Autorin im
  Bereich und volle Sicht, wie beim Ändern). Eingeladen werden Personen und Agenten des
  Systems (`type` `user`/`agent` mit `id`) und Adressen (`type` `email` mit
  `email` und optional `name`), jede `required` oder `optional`, höchstens 100
  Einträge (422 `validation_failed`; `event.too_many_attendees`, wenn ein Neuer der
  Serie eine Ausnahme über 100 brächte), niemand doppelt (422 `event.attendee_duplicate`,
  Adressen ohne Rücksicht auf Groß- und Kleinschreibung). Wer `directory.read` hat (alle
  außer Gästen), lädt jede aktive Person der Organisation ein; ein Gast nur, wer den
  Bereich des Kalenders liest. Agenten nur mit `ai.use`, keine Entwürfe, ein
  persönlicher Agent nur von seiner Besitzerin (ein Gast: nur Agenten des Bereichs).
  Wen man nicht einladen kann, antwortet 422 `event.attendee_unknown`. Die Liste zu
  setzen erhöht die Version des Termins.
- **Lesen** (`GET /api/events/<id>/attendees`, seitenweise) darf, wer den Termin ganz
  sieht (bei „Belegt“ 403 `event.private`). Personen und Agenten erscheinen mit
  `principal_id` und Namen, nie mit ihrer Adresse; Adressen mit `email` und dem
  angegebenen Namen. `delivery` sagt, wie die Einladung ankommt: `internal` (in der
  Aktivität), `not_sent` (eine Adresse: nichts wird verschickt; die `.ics`-Datei des
  Termins gibt man selbst weiter).
- **Antworten** (`POST /api/events/<id>/response` mit `accepted`, `tentative` oder
  `declined` und der gelesenen `version`) darf nur, wer eingeladen ist (403
  `event.not_invited`, auch für die Organisatorin, die nicht eingeladen ist). Hat sich
  der Termin seit dem Lesen geändert, 409; die Antwort selbst ändert die Version nicht.
  Ein Agent gilt sofort als zugesagt; eine Einladung startet keinen Lauf. Wird ein
  eingeladener Agent gelöscht, verschwinden seine Einladungen mit ihm (wie seine
  Mitgliedschaften).
- **Serien:** Die Eingeladenen und ihre Antworten gelten für die ganze Serie. Eine
  Ausnahme (ein einzeln geändertes Vorkommen) und der abgeteilte Teil einer Serie
  (`scope=following`) übernehmen sie; danach hat die Ausnahme ihre eigene Liste. Wer
  nur zu einer Ausnahme eingeladen ist, sieht nur dieses Vorkommen; wer daraus
  entfernt ist, sieht es nicht. Wer bei der Serie dazukommt oder geht, kommt dazu oder
  geht auch bei ihren Ausnahmen; eine Antwort auf die Serie erreicht die Ausnahmen, auf
  denen noch dieselbe Antwort stand.
- **Zeit geändert:** Rücken Anfang oder Ende (einer Serie, eines Vorkommens), stehen
  die Antworten der anderen Eingeladenen wieder auf offen (`needs_action`), und sie
  werden benachrichtigt; wer geändert hat, behält ihre. Titel, Ort und Text ändern
  keine Antwort.
- **Benachrichtigungen** stehen nur in der Aktivität, nie in einem Kanal oder einer
  Direktnachricht: `invitation` für jede neu eingeladene Person, nach einer
  Zeitänderung, einer Absage (`status=cancelled`) und dem Löschen, auch eines einzelnen
  Vorkommens oder „dieses und der folgenden“ (das wie die Absage dieses Vorkommens:
  hatte es eine Ausnahme, deren Eingeladene). Fallen dabei Ausnahmen einer Serie weg
  oder werden mit ihr abgesagt, hören auch die nur dort Eingeladenen davon; wer bei
  Serie und Ausnahme steht, einmal (über die Serie). `invite_reply` für
  die Organisatorin (eine Person, kein Agent), wenn jemand absagt oder „vielleicht“
  antwortet (nie für ihre eigene Antwort). Je Person, Termin und Grund gibt es eine
  Benachrichtigung; eine spätere Änderung frischt sie auf (wieder ungelesen, oben),
  dieselbe noch einmal zugestellt nicht (eine gelesene bleibt gelesen).
  Sie nennt Titel, Anfang und die eigene Antwort und bleibt sichtbar, solange die
  Person den Termin besucht (eingeladen oder Organisatorin; ein gelöschter Termin
  erscheint als abgesagt) und sein Kalender nicht archiviert ist; wer ausgeladen ist,
  sieht sie nicht mehr.
- **Meine Termine:** Das Fenster mit `mine=true` zeigt nur, was man organisiert oder
  wozu man eingeladen ist, über alle Bereiche; ohne `mine` zeigt es dazu die Termine
  der eigenen Bereiche.
- **Live und Outbox:** `calendar_event.invited` (je eingeladene Person, nur IDs) und
  `calendar_event.responded` (mit der Antwort); die Eingeladene bekommt live
  `event.invited` (nur die ID des Termins), die Mitglieder des Bereichs wie bei jeder
  Änderung `calendar.changed`.

## Überlagerungen

`GET /api/calendar/overlays?from&to&kinds=tickets,sprints,automations` zeigt neben den
Terminen, was andere Bereiche der App ohnehin wissen, ohne etwas zu speichern (keine
Tabelle, kein Audit, keine Kopie):

- **Tickets** (`tickets`): Fälligkeiten (`due_on`) im Zeitraum, nur Tickets, die nicht
  erledigt oder abgebrochen sind (nach der Kategorie ihres Status). Ein erledigtes oder
  abgebrochenes Ticket verschwindet damit auch aus vergangenen Wochen: Die Überlagerung
  zeigt, was noch fällig ist, keinen Verlauf. `ref` ist der Schlüssel (`HC-12`),
  `title` der Titel.
- **Sprints** (`sprints`): jeder Sprint jeden Zustands, der einen Tag des Zeitraums
  enthält, vom ersten bis zum letzten Tag (`starts_on`, `ends_on`); `title` ist sein
  Name.
- **Aufgaben** (`automations`): nur der **nächste** Termin aktiver Aufgaben (pausierte,
  erledigte und Ereignisregeln haben keinen), keine späteren: Eine tägliche Aufgabe
  steht also einmal im Kalender, an ihrem nächsten Tag, nicht an jedem Tag der Woche.
  Der Termin steht an seinem Tag in der Zone der Betrachterin (`time_zone`, Standard
  UTC), der Zeitpunkt in `at`; wo die Uhr über Mitternacht zurückgestellt wurde (in
  America/St_Johns bis 2010), gehört die wiederholte Zeit vor Mitternacht zum neuen
  Tag. `title` ist der Name des Agenten, `space_id` bei einer Aufgabe in einer
  Direktnachricht leer.

Wer was sieht: Tickets und Sprints aus den Bereichen, in denen man Mitglied ist (offene
über die Rolle), **auch für Admins nur diese**; fremde Bereiche kommen hier nie vor.
Aufgaben nach ihrer eigenen Sichtregel (Besitzerin, verantwortliche Person des Agenten,
wer den Bereich ihres Orts verwaltet, Admins mit `agent.manage`; ohne `ai.use` keine),
und auch davon nur die, deren Ort in einem eigenen Bereich liegt, oder die eigenen
(die Aufgabe in der eigenen Direktnachricht mit einem Agenten). Die verantwortliche
Person eines Agenten sieht hier also nur dessen Aufgaben in ihren Bereichen und ihre
eigenen, nicht die in Direktnachrichten anderer oder in fremden Bereichen, auch wenn
die Aufgabenliste des Agenten sie ihr zeigt. Gefiltert wird in der Datenbank, je Art
eine Abfrage.

`from` und `to` sind Tage, `to` gehört nicht mehr dazu (wie beim Fenster), beide
zwischen 1900-01-01 und 2400-01-01 (422 `calendar.window_out_of_range`, `from` vor `to`
sonst `calendar.invalid_window`). Ohne `kinds` kommen alle drei Arten; eine unbekannte
Art ist 422 `calendar.overlay_kind_unknown` (so schaltet die Oberfläche Überlagerungen
ab). Die Liste ist seitenweise nach (Tag, Art, ID) sortiert, Aufgaben eines Tages nach
ihrem Zeitpunkt; ein Cursor gilt nur mit der Zone, mit der er entstand (422
`calendar.cursor_time_zone`).

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

## Zugänge zu externen Kalendern (Grundlage)

Ein verbundener externer Kalender (ab Task 13c) nutzt die Konnektoren und OAuth-Apps
aus M8 mit dem Zweck `calendar` (`connectors/purposes.py`): Der Zugang gehört der
Person (persönlich, nie geteilt, nie an einem MCP-Server), verbinden darf, wer
`calendar.sync` hat (kein `ai.use` nötig: der Kalender geht ohne KI), die Google-App
verwaltet, wer `calendar.manage` hat. Die Rückleitungsadresse beim Anbieter ist die der
App (`/api/ai/oauth/<id>/callback`); danach geht der Browser auf
`/calendar/accounts?status=…`. Die Anfrage an Google trägt `access_type=offline` und
`prompt=consent` aus dem Zweck. Ein Zugang wird nur für seinen Zweck benutzt; ändert
sich der Endpunkt einer Kalender-App, werden ihre Zugänge getrennt wie in M8. Die
Verwaltung der KI zeigt Kalender-Zugänge und -Apps nie.

- **Ursprung:** Ein Zugang mit Passwort (CalDAV) wird für einen Ursprung angelegt,
  `https://host[:port]` in genau einer Schreibweise (`connectors/origins.py`, dieselbe,
  mit der M8 einen umgezogenen Server erkennt): nur https, Host klein geschrieben und
  geprüft (internationale Namen IDNA-kodiert, keine Leer- oder Sonderzeichen, IPv4 nur
  in Punktschreibweise, IPv6 in eckigen Klammern), Port 443 entfällt. Alles andere ist
  422 `connector.origin_invalid`; ein leeres oder nur aus Leerzeichen bestehendes
  Passwort 422 `connector.secret_invalid`.
- **Rückkehr ohne Sitzung:** Endet die Sitzung während der Zustimmung beim Anbieter,
  landet der Browser trotzdem auf `/calendar/accounts?status=invalid` (der Zweck der
  App, deren Rückleitungsadresse getroffen wurde), nicht auf der Seite der KI. Dass die
  Rückleitungsadresse einer Kalender-App so anders antwortet als eine unbekannte ID,
  ist gewollt (siehe [`MCP.md`](MCP.md), OAuth).
- **Namen:** Der Name der Kalender-App teilt sich den Namensraum mit den MCP-Apps der
  Organisation (409 `oauth_client.name_taken`, siehe [`MCP.md`](MCP.md)). Eine
  Kalender-App sollte also nicht wie ein Katalogeintrag heißen („GitHub“, „GitLab“).
- **Zurückgehen unter die Migration** `d5f8a1c3e7b9` löscht alle Kalender-Zugänge und
  Kalender-Apps (sonst zählten sie als MCP-Zugänge); nach dem erneuten Hochgehen
  verbinden die Personen neu.
