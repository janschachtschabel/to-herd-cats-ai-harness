# Tickets: Bedienung und Betrieb

Tickets gibt es seit Meilenstein 4. Diese Seite beschreibt Arten und Hierarchie, den
Status-Workflow je Bereich, wer was darf, Zuweisung, die Diskussion eines Tickets mit
ihren Systemmeldungen, Karten in Kanälen, Seitenverknüpfungen, Tags, Suche, Grenzen und
den Betrieb (Worker, Ereignisse, Kapazität). Die Regeln selbst stehen in der
Spezifikation (Abschnitte 5.3, 6.2, 10, 11) und im Plan M4
(`docs/superpowers/plans/2026-11-13-m4-tickets.md`, „Entscheidungen“).

## Bedienung

### Wo Tickets stehen

- **Seitenleiste, „Arbeit“ → „Tickets“** mit Zähler: wie viele unerledigte Tickets
  einem selbst zugewiesen sind (Status der Kategorien offen, in Arbeit, zur Prüfung;
  über 99 zeigt er „99+“).
- **Liste `/tickets`:** zuerst „Meine Tickets“ (mir zugewiesen, nicht erledigt), daneben
  „Alle Tickets“ aller Bereiche, die man sehen darf. Filter: Status (nicht erledigt oder
  alle), Bereich, Art, Priorität, Tag (sobald ein Bereich gewählt ist), Text (Titel und
  Beschreibung); Sortierung nach letzter Änderung, Fälligkeit, Priorität oder Nummer.
  Die Filter stehen in der Adresse, ein Link zeigt also dieselbe Auswahl.
- **Ein Ticket `/tickets/<Nummer>`:** Titel und Beschreibung (Markdown), rechts die
  Felder (Status, zugewiesen an, Priorität, Art, Fälligkeit, übergeordnetes Ticket, Tags,
  verknüpfte Seiten), darunter die untergeordneten Tickets mit Fortschritt und die
  Diskussion.
- **Je Bereich** neben „Wiki“ die Reiter **„Board“** (die Status des Bereichs als
  Spalten) und **„Epics“** (jedes Epic mit Fortschrittsbalken, aufklappbar mit seinen
  Kindern). Beide erscheinen nur, wer Tickets des Bereichs lesen darf.
- **„Neues Ticket“** in der Liste (öffnet danach das Ticket), auf dem Board (das Board
  bleibt offen) und in der Epic-Übersicht („Neues Epic“). Ein neues Ticket steht im
  ersten Status der Kategorie `open`. Ein Titel genügt; alles andere lässt sich später
  ergänzen.

Jedes Ticket hat einen Schlüssel aus dem festen Präfix `HC` und seiner Nummer
(`HC-42`). Nummern sind je Organisation fortlaufend, nicht je Bereich; Adressen nutzen
nur die Nummer (`/tickets/42`).

### Arten und Hierarchie

| Art | Oberfläche | darf untergeordnet sein unter |
|---|---|---|
| `epic` | Epic | nichts (immer oben) |
| `story` | Story | einem Epic |
| `task` | Aufgabe | einem Epic oder einer Story |
| `bug` | Fehler | einem Epic oder einer Story |

Damit ist die Tiefe höchstens drei (Epic → Story → Aufgabe) und ein Kreis unmöglich.
Übergeordnetes und untergeordnetes Ticket liegen immer im selben Bereich (das sichert
auch die Datenbank). Eine Art lässt sich nur ändern, wenn sie zu den über- und
untergeordneten Tickets passt (sonst „Diese Art passt nicht …“, 422 `ticket.kind_invalid`).
Ein Epic zeigt, wie viele seiner direkten Kinder in jeder Kategorie stehen.

### Status je Bereich

Jeder Bereich hat seinen eigenen Workflow: eine geordnete Liste von Status mit Name und
**Kategorie**. Neue Bereiche bekommen fünf Standardstatus:

| Status | Kategorie | zählt als |
|---|---|---|
| Neu | `open` | offen |
| In Arbeit | `active` | in Arbeit |
| Zur Prüfung | `review` | zur Prüfung |
| Erledigt | `done` | erledigt |
| Verworfen | `cancelled` | verworfen |

- Was das System mit einem Status anfängt („Meine Tickets“, Zähler, Fortschritt, Filter
  „nicht erledigt“), hängt **nur an der Kategorie**, nie am Namen. Umbenennen ist also
  folgenlos.
- Verwalten im Bereich unter **Einstellungen → Ticket-Status** (Verwalter des Bereichs,
  `space.manage`): anlegen, umbenennen, Kategorie ändern, nach oben und unten
  verschieben, löschen. Die Reihenfolge ist die der Board-Spalten.
- Höchstens 20 Status je Bereich; Name 1 bis 40 Zeichen, je Bereich eindeutig ohne
  Rücksicht auf Groß- und Kleinschreibung.
- Es gibt immer mindestens einen Status der Kategorie `open` und einen der Kategorie
  `done`; was das verletzen würde, lehnt die API ab (`ticket_status.category_required`).
- Ein Status mit Tickets wird nur mit Ersatz gelöscht: Seine Tickets wechseln in den
  gewählten Status, jedes mit einer Systemmeldung in seiner Diskussion.
- Die Standardnamen sind Deutsch (Organisationen haben noch keine Sprache) und danach
  gewöhnliche Daten. Jeder Statuswechsel ist frei: Es gibt keine erlaubten oder
  verbotenen Übergänge.

### Wer was darf

Rechte im Bereich (Rollen aus Spezifikation 5.3; die Oberfläche bietet nur an, was die
eigene Rolle im Bereich erlaubt):

| Was | Recht | ab Rolle |
|---|---|---|
| Tickets, ihre Diskussion, Status, Board und Epics sehen | `ticket.read` | Leser |
| in der Diskussion schreiben, antworten, reagieren | `channel.post` | Leser |
| Tickets anlegen | `ticket.create` | Autor |
| Titel, Beschreibung, Status, Priorität, Art, Fälligkeit, übergeordnetes Ticket, Tags, Seitenverknüpfungen ändern | `ticket.edit` | Autor |
| ein nicht zugewiesenes Ticket übernehmen, die eigene Zuweisung abgeben | `ticket.edit` | Autor |
| jemand anderem zuweisen, eine fremde Zuweisung lösen oder ändern | `ticket.assign` | Moderator |
| Status des Bereichs verwalten | `space.manage` | Verwalter |

Wer ein Ticket nicht sehen darf, für den gibt es es nicht: Die API antwortet auf die
Nummer, die Diskussion, die verknüpften Seiten und jede Änderung mit 404
`ticket.not_found`, genau wie bei einer Nummer, die nie vergeben wurde (gleiche Antwort,
gleiche Laufzeitklasse; gemessen in `docs/demo/m4.md`). Listen, Board, Epics, Zähler,
Suche, Aktivität und Live-Ereignisse nennen es nicht. Wer aus einem Bereich entfernt
wird, verliert seine Tickets sofort, auch Benachrichtigungen und Live-Ereignisse dazu;
eine bestehende Zuweisung an diese Person bleibt als Name stehen, gibt ihr aber keinen
Zugang. Ein Ticket kann nicht gelöscht werden: Man setzt es auf einen Status der
Kategorie `cancelled` („Verworfen“). Zwischen Bereichen verschieben lässt es sich nicht.

### Zuweisung

- Zugewiesen werden in M4 nur Personen (Agenten kommen mit M6), und nur wer die
  Tickets des Bereichs lesen darf. Alles andere beantwortet die API gleich mit 422
  `ticket.assignee_invalid`, ob es die Person gibt oder nicht.
- **„Übernehmen“** weist ein nicht zugewiesenes Ticket sich selbst zu, **„Abgeben“**
  löst die eigene Zuweisung (beides mit `ticket.edit`). **„Jemandem zuweisen“** (mit
  `ticket.assign`) öffnet eine Personenauswahl mit genau den Personen, die den Bereich
  lesen dürfen (`GET /api/directory?space_id=…`).
- Wer von jemand anderem ein Ticket zugewiesen bekommt, findet es in der **Aktivität**
  („anna hat dir HC-42 zugewiesen“, Grund `assignment`); wer es sich selbst nimmt, nicht.
  Zuweisen und Lösen stehen im Audit (`ticket.assigned`).

### Diskussion und Systemmeldungen

Jedes Ticket hat genau eine Diskussion, angelegt mit dem Ticket. Sie sieht, wer das
Ticket sieht; schreiben darf, wer im Bereich schreiben darf. Kommentare sind gewöhnliche
Nachrichten (Markdown, Threads, Erwähnungen, Reaktionen, Bearbeiten, Löschen; siehe
[`docs/NACHRICHTEN.md`](NACHRICHTEN.md)).

Grau darin steht, was mit dem Ticket geschah; diese Systemmeldungen schreibt der Worker,
**eine je geänderte Eigenschaft**: angelegt, Status, zugewiesen oder gelöst, Priorität,
Art, übergeordnetes Ticket, Fälligkeit, Titel, Beschreibung, Seite verknüpft oder
gelöst. Status-, Personen-, Ticket- und Seitennamen löst die API beim Lesen auf (ein
gelöschter Status heißt „einem gelöschten Status“; eine Seite, die die lesende Person
nicht sehen darf, erscheint ohne Titel und ohne Kennung). Titel und Beschreibung werden
nur genannt („hat den Titel geändert“), nie wiedergegeben. Tags ändern keine
Systemmeldung. Auf eine Systemmeldung antwortet niemand (422 `message.bad_parent`).

**„Systemmeldungen ausblenden“** über der Diskussion blendet die grauen Zeilen aus; die
Kommentare bleiben (`GET /api/conversations/{id}/messages?include_system=false`).

Benachrichtigungen aus der Diskussion: Erwähnungen und Antworten wie überall; dazu
bekommen die zugewiesene und die meldende Person jeden neuen Kommentar anderer in ihre
Aktivität (Grund `ticket_comment`), nicht zusätzlich zu einer Erwähnung oder Antwort und
nie für eigene Kommentare. Systemmeldungen benachrichtigen niemanden, außer der
Zuweisung.

### Kanäle bleiben frei von Ticketmeldungen

Kein Ticket schreibt etwas in einen Kanal oder eine Direktnachricht, weder beim Anlegen
noch bei einer Änderung (Abnahme M4, ausgeführt in `docs/demo/m4.md` und im
Browser-Test `e2e/tests/tickets-quiet.spec.mjs`). Wer ein Ticket in einem Kanal zeigen
will, nennt es:

- Steht in einer Nachricht ein Schlüssel (`HC-42`) oder ein Link auf ein Ticket
  (`/tickets/42`, auch mit Adresse davor), zeigt der Browser darunter eine **Karte**
  mit Schlüssel, Titel, Status, Priorität und zugewiesener Person. Höchstens drei Karten
  je Nachricht; Text in Code (`` `HC-42` `` oder Codeblock) zählt nicht.
- Die Karte lädt jeder Browser selbst über die Ticket-API und hält sie über die
  Live-Ereignisse aktuell. Wer das Ticket nicht sehen darf, bekommt 404 und sieht nur den
  Text. Der Server schreibt dafür nichts in den Kanal; es gibt keine eigene Nachrichtenart.

### Seiten verknüpfen

- Am Ticket unter „Verknüpfte Seiten“ (+) sucht man eine Seite nach Titel oder Inhalt
  und verknüpft sie; an einer Wiki-Seite steht unten „Verknüpfte Tickets“ mit „Ticket
  verknüpfen“ (Suche nach Schlüssel oder Titel). Beide Richtungen nutzen dieselbe
  Verknüpfung, beide lösen sie wieder.
- Verknüpfen und Lösen brauchen `ticket.edit` am Ticket und Sicht auf die Seite. Seiten
  anderer Bereiche sind erlaubt.
- Eine Verknüpfung sieht nur, wer **beide Enden** sehen darf; gefiltert wird in der
  Datenbankabfrage. Eine Seite im Papierkorb behält ihre Verknüpfungen, zeigt sie aber
  nicht; wiederhergestellt sind sie zurück, endgültig gelöscht sind sie weg.
- Höchstens 50 Seiten je Ticket (422 `ticket.too_many_pages`); die Grenze zählt auch
  Verknüpfungen zu Seiten, die man selbst nicht sieht.
- Verknüpfen und Lösen schreiben eine Systemmeldung, kein Audit.

### Tags

Tickets tragen systemweite Tags und Tags ihres Bereichs (dieselben wie die Seiten,
Verwaltung wie in [`docs/WIKI.md`](WIKI.md)), höchstens 20 je Ticket, am Ticket unter
„Tags“ ändern (`ticket.edit`). Die Liste und das Board filtern danach (in der Liste
müssen alle gewählten Tags passen). Ein gelöschter Tag verschwindet von allen Tickets.
Tags ändern die Version des Tickets und stehen im Audit (`ticket.tags_set`).

### Board

- Die Spalten sind die Status des Bereichs in ihrer Reihenfolge, je mit Anzahl. Jede
  Spalte lädt zuerst 50 Karten, „Mehr laden“ den Rest.
- In einer Spalte gilt eine **feste Reihenfolge**: Priorität (dringend zuerst),
  Fälligkeit (früheste zuerst, ohne Datum zuletzt), Nummer. Von Hand sortieren lässt sich
  nicht.
- Filter: nur meine, Art, Tag, Epic (das Epic mit Kindern und Enkeln).
- Eine Karte wechselt die Spalte auf drei gleichwertigen Wegen: mit der Maus ziehen; per
  Tastatur am Griff „HC-42 verschieben“ (Leertaste hebt an, Pfeil links/rechts wählt die
  Spalte, Leertaste legt ab, Escape bricht ab; ein Bildschirmleser hört jeden Schritt);
  oder über das Menü „Status von HC-42 ändern“. Der Fokus bleibt danach an der Karte.
- Die Karte springt sofort; lehnt der Server ab, springt sie zurück, und das Board sagt
  warum. Hat jemand das Ticket inzwischen geändert (409), lädt das Board neu: „Das
  Ticket wurde inzwischen geändert und ist wieder an seinem Platz …“.
- Änderungen anderer erscheinen live auf dem Board, in Listen, am Ticket und an Karten
  in Kanälen.

### Gleichzeitig ändern

Jede Änderung nennt die Version, die man gelesen hat; hat jemand anderes inzwischen
gespeichert, antwortet die API mit 409 `ticket.version_conflict`. Am Ticket heißt das
„Jemand hat diesen Eintrag inzwischen geändert …“ mit „Aktuelle Fassung laden“; der
eigene Text im Titel- oder Beschreibungsfeld bleibt dabei stehen und lässt sich danach
speichern. Verknüpfungen von Seiten tragen keine Version (sie sind eine Menge: zweimal
verknüpfen ist einmal verknüpft).

### Suche

Strg+K findet Seiten, Nachrichten und Tickets zusammen (`GET /api/search`, Typ
`ticket`: Treffer mit Schlüssel, Titel, Status, Bereich und Ausschnitt aus der
Beschreibung). Eine Eingabe wie `HC-42`, `hc-42` oder `42` stellt das sichtbare Ticket
mit dieser Nummer an den Anfang. Gesucht wird in Titel und Beschreibung (Deutsch und
ohne Sprachregeln), nur in Bereichen, deren Tickets man lesen darf, im selben
SQL-Ausdruck. Die Ticket-Liste hat dazu ihr eigenes Textfeld.

### Grenzen

| Was | Grenze |
|---|---|
| Titel | 1 bis 200 Zeichen |
| Beschreibung | höchstens 100.000 Zeichen Markdown (derselbe sichere Renderer wie bei Nachrichten) |
| Status je Bereich | höchstens 20, Name 1 bis 40 Zeichen |
| Tags je Ticket | höchstens 20 |
| verknüpfte Seiten je Ticket | höchstens 50 |
| Listen | `limit` höchstens 100, weiter mit `cursor`; Board je Spalte ebenso |
| Hierarchie | höchstens drei Ebenen (Epic, Story, Aufgabe oder Fehler) |
| Karten je Nachricht | höchstens drei |

### Was es noch nicht gibt

- Agenten als Zugewiesene, Abnahmekriterien als Pflichtabschnitt, die Sperre von
  `done`/`cancelled` für Agenten und den Verbrauch je Ticket (M6); Tags als Auslöser
  (M7); die Abholung von Tickets durch externe Agenten (M8).
- Ein einstellbares Präfix (fest `HC`), Nummern je Bereich, Verschieben zwischen
  Bereichen, endgültiges Löschen, Handsortierung, erlaubte Statusübergänge,
  Beobachterlisten, Anhänge an Tickets, Vorlagen, Massenbearbeitung, Benachrichtigung
  per E-Mail.
- Eine eigene Ticket-Ansicht je Bereich in der Seitenleiste gibt es nicht; Board und
  Epics sind Reiter des Bereichs, die Liste filtert nach Bereich.

## Betrieb

### Ereignisse und Worker

Jede Änderung an einem Ticket schreibt in ihrer Transaktion genau ein Ereignis in die
Outbox: `ticket.created` oder `ticket.updated`. Es trägt nur Kennungen: das Ticket, seine
Diskussion, die Namen der geänderten Felder und für Status, Zuweisung, Priorität, Art,
übergeordnetes Ticket, Fälligkeit und Seite den alten und neuen Wert als ID,
Aufzählungswert oder Datum; nie Titel oder Beschreibung. Der Worker verteilt es an drei
Handler:

| Handler | tut |
|---|---|
| `ticket_timeline` | schreibt die Systemmeldungen in die Diskussion (je Feld eine, idempotent über eine aus Ereignis und Feld abgeleitete `client_id`) |
| `notify_on_ticket` | schreibt die Benachrichtigung `assignment` |
| `publish_live` | sendet `ticket.created`/`ticket.updated` (nur IDs) an alle Verbindungen, deren Person Tickets des Bereichs sehen darf |

Jede Systemmeldung ist ihrerseits ein `message.created`-Ereignis (Live-Zustellung,
`notify_on_message`). Ein angelegtes Ticket mit Zuweisung ergibt also drei Ereignisse.
Ohne laufenden Worker geht nichts verloren, aber Systemmeldungen, Zuweisungs-
Benachrichtigungen und Live-Aktualisierungen bleiben aus, bis er läuft. Die Metrik
`herd_outbox_dispatch_total{handler="ticket_timeline",result="ok"}` zeigt, dass er
Tickets verarbeitet; `smoke.sh` prüft genau das (Ticket anlegen, Status ändern, beide
Systemmeldungen in der Diskussion).

**Kapazität** (gemessen, siehe [`docs/STECKBRIEF.md`](STECKBRIEF.md#tickets-m4)):
Ein Worker schafft hier rund 90 Ereignisse je Sekunde. Wer dauerhaft mehr als etwa 40
Tickets je Sekunde anlegt (zum Beispiel ein Import über die API), erzeugt mehr, als ein
Worker abarbeitet: Die Outbox wächst, und Systemmeldungen und Live-Ereignisse kommen
entsprechend später (`herd_outbox_pending`, Alarm `HerdOutboxBacklog`). Mehrere Worker
sind sicher. In `HERD_ROLE=all` teilen sich API und Worker einen Prozess; dort holte
der Worker unter Dauerlast erst nach dem Ende der Anlagen auf.

### Daten und Migrationen

- Tabellen: `work_item` (die Tickets, mit `search_tsv`), `ticket_status`,
  `ticket_counter` (eine Zeile je Organisation; zwei gleichzeitige Anlagen warten kurz
  aufeinander, Nummern werden nie doppelt vergeben), `ticket_page_link`; die
  Diskussion ist ein Gespräch der Art `thread_ticket`, Tags stehen in `tagging`.
- Die Migrationen von M4 erweitern nur (der Code von M3 läuft gegen das Schema von M4).
  Die fünf Standardstatus legt ein Trigger beim Anlegen eines Bereichs an, auch wenn der
  Bereich von einer älteren Version angelegt wird; die Migration hat sie für bestehende
  Bereiche nachgetragen.
- Ein Trigger hält übergeordnetes Ticket und Status im Bereich des Tickets.
- Audit: `ticket.created`, `ticket.assigned`, `ticket.cancelled`, `ticket.tags_set`,
  `ticket_status.created`, `ticket_status.updated`, `ticket_status.deleted`. Andere
  Feldänderungen stehen in der Diskussion, nicht im Audit.
- Neue Einstellungen (`HERD_*`) bringt M4 nicht mit.

### Woran man Probleme erkennt

- Ein Ticket ohne Systemmeldungen in der Diskussion: Der Worker läuft nicht oder hängt
  zurück (`herd_outbox_pending`, `herd_outbox_oldest_pending_seconds`, `/ready` des
  Workers).
- 409 `ticket.version_conflict` häufen sich: mehrere Personen oder Skripte ändern
  dieselben Tickets; Skripte sollten vor jeder Änderung neu lesen.
- 422 `ticket.assignee_invalid` beim Zuweisen: Die Person darf den Bereich nicht lesen
  (oder es gibt sie nicht; die API unterscheidet das absichtlich nicht).
