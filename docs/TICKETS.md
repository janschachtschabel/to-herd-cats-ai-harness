# Tickets: Bedienung und Betrieb

Tickets gibt es seit Meilenstein 4, Sprints, Vorrat, „Mein Board“ und die Daily-Ansicht
seit M4b. Diese Seite beschreibt Arten und Hierarchie, den Status-Workflow je Bereich,
wer was darf, Zuweisung, die Diskussion eines Tickets mit ihren Systemmeldungen, Karten
in Kanälen, Seitenverknüpfungen, Tags, Board, Sprints und die neuen Boards, Suche,
Grenzen und den Betrieb (Worker, Ereignisse, Kapazität). Die Regeln selbst stehen in der
Spezifikation (Abschnitte 5.3, 6.2, 10, 11) und in den Plänen M4
(`docs/superpowers/plans/2026-11-13-m4-tickets.md`) und M4b
(`docs/superpowers/plans/2026-11-13-m4b-boards-sprints.md`), jeweils unter
„Entscheidungen“.

## Bedienung

### Wo Tickets stehen

- **Seitenleiste, „Arbeit“ → „Tickets“** mit Zähler: wie viele unerledigte Tickets
  einem selbst zugewiesen sind (Status der Kategorien offen, in Arbeit, zur Prüfung;
  über 99 zeigt er „99+“). Darunter **„Mein Board“** (`/my-board`, siehe unten).
- **Liste `/tickets`:** zuerst „Meine Tickets“ (mir zugewiesen, nicht erledigt), daneben
  „Alle Tickets“ aller Bereiche, die man sehen darf. Filter: Status (nicht erledigt oder
  alle), Bereich, Art, Priorität, Tag (sobald ein Bereich gewählt ist), Text (Titel und
  Beschreibung); Sortierung nach letzter Änderung, Fälligkeit, Priorität oder Nummer.
  Die Filter stehen in der Adresse, ein Link zeigt also dieselbe Auswahl.
- **Ein Ticket `/tickets/<Nummer>`:** Titel und Beschreibung (Markdown), rechts die
  Felder (Status, zugewiesen an, Priorität, Art, Fälligkeit, Sprint, übergeordnetes
  Ticket, Tags, verknüpfte Seiten), darunter die untergeordneten Tickets mit Fortschritt und die
  Diskussion.
- **Je Bereich** neben „Wiki“ die Reiter **„Board“** (die Status des Bereichs als
  Spalten; mit „Nach Person gruppieren“ die Daily-Ansicht), **„Epics“** (jedes Epic mit
  Fortschrittsbalken, aufklappbar mit seinen Kindern), **„Sprints“** und **„Vorrat“**.
  Sie erscheinen nur, wer Tickets des Bereichs lesen darf.
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
Übergeordnetes und untergeordnetes Ticket liegen immer im selben Bereich. Eine Art lässt
sich nur ändern, wenn sie zu den über- und untergeordneten Tickets passt (sonst „Diese
Art passt nicht …“, 422 `ticket.kind_invalid`). Diese Regeln hält auch die Datenbank
(Trigger `work_item_hierarchy`, Review M4 P7), gleich wer schreibt: kein Ticket unter
sich selbst, das übergeordnete im selben Bereich und von einer Art, die darüber stehen
darf, und keine Änderung von Art oder Bereich, nach der die Kinder nicht mehr passen.
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
  Diese Regel hält nur der Dienst, nicht die Datenbank (sie gilt für die Menge der
  Status eines Bereichs, nicht für eine Zeile; Review M4 P7): Wer an der API vorbei in
  die Datenbank schreibt, kann den letzten `done`-Status löschen, solange kein Ticket ihn
  nutzt. Bis ein Verwalter wieder einen anlegt, lässt sich dann kein Ticket erledigen.
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
| Sprints, Vorrat und die Daily-Ansicht sehen | `ticket.read` | Leser |
| ein Ticket in einen Sprint oder in den Vorrat legen | `ticket.edit` | Autor |
| Sprints anlegen, ändern, starten, abschließen | `ticket.assign` | Moderator |
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
Art, übergeordnetes Ticket, Fälligkeit, Sprint („hat das Ticket von Sprint 46 nach
Sprint 47 verschoben“, auch beim Abschluss eines Sprints), Titel, Beschreibung, Seite
verknüpft oder gelöst. Status-, Personen-, Ticket-, Sprint- und Seitennamen löst die API beim Lesen auf (ein
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
  in Kanälen. Ein Ticket-Ereignis lädt nur die Ansichten seines Bereichs, das Ticket
  selbst und Listen über alle Bereiche neu, gesammelt über 250 ms.
- Oben wählt **„Sprint“**, welche Tickets das Board zeigt: alle, den Vorrat (ohne
  Sprint) oder einen Sprint.

### Sprints (M4b)

Ein Bereich ist ein Team; ein Sprint gehört zu genau einem Bereich und bündelt dessen
Tickets für einen Zeitraum. Reiter **„Sprints“**: der laufende Sprint zuerst, dann die
geplanten (frühester Beginn zuerst), dann die abgeschlossenen (zuletzt beendete zuerst).
Jeder Sprint zeigt Name, Zustand, Zeitraum und Ziel; aufgeklappt seine Tickets.

- **Anlegen** („Neuer Sprint“): Name (1 bis 80 Zeichen), Ziel (ein Satz, höchstens 500
  Zeichen), Beginn und Ende als Datum (das Ende nicht vor dem Beginn, sonst 422
  `sprint.dates_invalid`). Ein neuer Sprint ist **geplant**. Name, Ziel und Zeitraum
  ändert `PATCH /api/sprints/{id}`; die Oberfläche bietet das noch nicht an.
- **Starten:** Je Bereich läuft **höchstens ein Sprint**. Läuft schon einer, steht am
  geplanten „Starten geht, sobald … abgeschlossen ist“; die API antwortet 409
  `sprint.active_exists`. Das hält ein eindeutiger Teilindex der Datenbank, auch wenn
  zwei Personen im selben Augenblick starten.
- **Abschließen** (nur ein laufender Sprint): Der Dialog fragt, wohin die
  **unerledigten** Tickets gehen (Kategorie nicht `done` oder `cancelled`): in den
  nächsten geplanten Sprint (der mit dem frühesten Beginn; ohne geplanten Sprint geht
  das nicht, 422 `sprint.next_missing`) oder zurück in den Vorrat. Erledigte und
  verworfene bleiben im abgeschlossenen Sprint. Der Abschluss ist eine Transaktion.
- **Bilanz:** Beim Abschluss hält der Sprint drei Zahlen fest und zeigt sie danach:
  *geplant* (alle Tickets, die er beim Abschluss hielt), *erledigt* (Kategorie `done`)
  und *übertragen* (die verschobenen). Verworfene zählen nur unter „geplant“. Die
  Bilanz ändert sich später nicht mehr.
- Ein abgeschlossener Sprint ändert sich nicht mehr (409 `sprint.state_invalid`) und
  nimmt keine Tickets mehr auf. Seine Tickets lassen sich aber herausnehmen.
- **Wieder geöffnet:** Wird ein erledigtes Ticket eines abgeschlossenen Sprints später
  wieder geöffnet, **bleibt es in diesem Sprint**, bis jemand es in einen anderen Sprint
  oder in den Vorrat legt. Die Sprint-Liste markiert es („Wieder offen nach dem
  Abschluss“, mit „… in den Vorrat legen“), das Ticket sagt es am Feld „Sprint“.
- Am Ticket wählt das Feld **„Sprint“** einen laufenden oder geplanten Sprint des
  eigenen Bereichs oder „Kein Sprint (Vorrat)“. Ein Sprint eines anderen Bereichs, ein
  abgeschlossener oder ein unbekannter ergeben dieselbe Antwort, 422
  `ticket.sprint_invalid`; die Datenbank hält per Fremdschlüssel, dass der Sprint eines
  Tickets zu dessen Bereich gehört.
- Löschen lässt sich ein Sprint nicht. Wer die Sprints eines Bereichs nicht sehen darf,
  bekommt für den Bereich 404 `space.not_found` und für einen Sprint 404
  `sprint.not_found`, wie für einen, den es nicht gibt.

### Vorrat (M4b)

Reiter **„Vorrat“**: die unerledigten Tickets des Bereichs ohne Sprint, sortiert nach
Priorität, Fälligkeit, Nummer (wie das Board; eine Handsortierung gibt es nicht).
Ankreuzen (einzeln oder „Alle auswählen“, mit der Tastatur wie mit der Maus), oben den
**Ziel-Sprint** wählen (der laufende zuerst, dann die geplanten) und **„In Sprint legen
(n)“**. Jedes Ticket wird mit der Version gelegt, die der Vorrat gelesen hat; wer es
inzwischen geändert hat, dessen Ticket bleibt im Vorrat, und der Vorrat sagt es und lädt
neu. Gibt es weder einen laufenden noch einen geplanten Sprint, bietet der Vorrat an,
einen anzulegen.

### Mein Board (M4b)

`/my-board`: alle mir zugewiesenen Tickets aus allen Bereichen, die ich sehen darf. Weil
jeder Bereich eigene Status hat, sind die Spalten hier die **Kategorien**: Offen, In
Arbeit, Zur Prüfung, Erledigt. „Erledigt“ zeigt nur, was in den letzten 14 Tagen in
einen `done`-Status kam; Verworfenes erscheint nicht. Jede Karte nennt Bereich und
Status; jede Spalte lädt 50 Karten, „Mehr laden“ den Rest.

- Eine Karte wechselt die Spalte wie auf dem Board auf drei Wegen (ziehen, Tastatur am
  Griff, Menü „Spalte von HC-42 ändern“). Gesetzt wird der **erste Status dieser
  Kategorie im Bereich des Tickets** (in der Reihenfolge des Bereichs), nie ein Status
  eines anderen Bereichs. Hat der Bereich keinen Status der Kategorie, bleibt das Ticket
  stehen, und das Board sagt es („Team Birne hat keinen Status der Kategorie Zur
  Prüfung …“, 422 `ticket.category_empty`). Die Änderung braucht `ticket.edit` im
  Bereich des Tickets und nennt seine Version (409 wie überall).
- Ein Board **einer anderen Person** über ihre Bereiche hinweg gibt es nicht: Es verriete,
  in welchen Bereichen sie arbeitet. Wer mehrere Teams überblickt, nutzt die Liste mit
  dem Filter „Zugewiesen an“ oder die Daily-Ansicht je Bereich.
- Verliert man den Zugang zu einem Bereich, verschwinden dessen Tickets sofort von
  „Mein Board“ (gefiltert in der Datenbankabfrage, wie alle Zähler).

### Daily-Ansicht (M4b)

Auf dem Board des Bereichs schaltet **„Nach Person gruppieren“** auf die Ansicht für das
Daily: eine **Zeile je zugewiesener Person** (nach Name), am Ende „Nicht zugewiesen“;
die Spalten bleiben die Status des Bereichs. Voreingestellt ist der **laufende Sprint**,
falls es einen gibt; die Sprint-Auswahl, Art, Tags, Epic und „Nur meine“ gelten weiter.

- Jede Zeile nennt, wie viele Tickets die Person hier hat und wie viele davon sich seit
  dem letzten Arbeitstag geändert haben; jede Zelle ihre Anzahl, die Zahl der geänderten
  und die ersten 20 Karten („Mehr laden“ für den Rest der Zelle).
- **Hervorgehoben** („Geändert“, farbiger Rand) ist jedes Ticket, dessen Status seit
  **0 Uhr UTC des letzten Arbeitstags** gewechselt hat oder das seitdem neu ist.
  Arbeitstage sind **Montag bis Freitag**, ohne Feiertage: dienstags bis freitags gilt
  „seit gestern 0 Uhr“, samstags, sonntags und montags „seit Freitag 0 Uhr“. Die Zeit
  kommt aus der Spalte `status_changed_at`, die ein Trigger bei jedem Statuswechsel setzt
  (gleich, wer schreibt); sie stimmt mit den Systemmeldungen „hat den Status … gesetzt“
  überein. Organisationen haben noch keine Zeitzone; über der Ansicht steht deshalb, ab
  wann gezählt wird („seit Freitag, 13.11. (0 Uhr UTC)“).
- Ein **Klick auf eine Person** filtert auf sie („Gefiltert auf Ben.“, „Alle Personen
  zeigen“ hebt es auf); ebenso „Nicht zugewiesen“.
- Den Status einer Karte ändert hier das Menü an der Karte (Ziehen gibt es nur im
  ungruppierten Board).
- **Höchstens 100 Personenzeilen** je Aufruf. Haben mehr Personen Tickets in der
  Auswahl, zeigt die Ansicht die ersten 100 nach Namen und sagt, dass Sprint, Art oder
  Tag die Auswahl eingrenzen. Personen und Tickets, die man nicht sehen darf, zählen
  nirgends mit.

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
| Sprint | Name 1 bis 80 Zeichen, Ziel höchstens 500; je Bereich höchstens ein laufender |
| Daily-Ansicht | höchstens 100 Personenzeilen, je Zelle zuerst 20 Karten (`limit` höchstens 100) |
| Mein Board | je Spalte zuerst 50 Karten; „Erledigt“ nur die letzten 14 Tage |

### Bekannte Grenzen

- **Verknüpfte Seiten zählen auch unsichtbare** (Review M4 P6): Die Grenze von 50
  Seiten je Ticket gilt für alle Verknüpfungen. Wer nur einen Teil der Seiten sehen
  darf, bekommt beim Verknüpfen 422 `ticket.too_many_pages`, obwohl die Liste weniger
  zeigt, und erfährt so, wie viele Verknüpfungen er nicht sieht. Das verrät keine Seite
  (Titel und IDs unsichtbarer Seiten erscheinen nirgends, auch nicht in den
  Systemmeldungen), nur ihre Anzahl; die Diskussion zeigt die unbenannten Einträge
  „Seite verknüpft“ ohnehin.
- **Liste und Board lesen alle sichtbaren Tickets des Bereichs** (Review M4 P8): Die
  Standardsortierung der Liste (`updated`), `due` und `priority` sowie die Zähler und
  die Spalten des Boards gehen je Aufruf über alle Tickets der sichtbaren Bereiche und
  sortieren dann (gemessen bei 12.006 Tickets in einem Bereich: Liste 23–46 ms, Board
  51–64 ms im Median, 3 bis 7 Abfragen je Aufruf). Nur `sort=number`, `parent`, die
  Suche nach dem Schlüssel und die Volltextsuche nutzen einen Index für Reihenfolge oder
  Treffer. Der Aufwand wächst linear; bei etwa zehnmal so vielen Tickets je Bereich
  braucht die Liste einen Index je Sortierung und das Board eine günstigere erste Seite.

- **Ein wieder geöffnetes Ticket bleibt im abgeschlossenen Sprint** (Plan M4b): Es
  wandert nicht von selbst in den laufenden Sprint oder den Vorrat; die Sprint-Liste und
  das Ticket markieren es, bis es jemand verschiebt. Die Bilanz des Sprints bleibt, wie
  sie beim Abschluss war.
- **Die Daily-Ansicht ist groß:** Sie liefert je Zelle die ersten 20 Karten aller
  Personen auf einmal. Bei 21 Personen und 3.000 Tickets im Sprint sind das 1,4 MB und
  rund 0,2 s je Aufruf, unter zehn gleichzeitigen Aufrufen gut 2 s
  ([Steckbrief](STECKBRIEF.md#sprints-und-boards-m4b)). Jedes Ticket-Ereignis des
  Bereichs lädt sie bei allen neu, die sie offen haben.
- **„Seit dem letzten Arbeitstag“ in UTC, Montag bis Freitag:** Ohne Zeitzone der
  Organisation beginnt der Tag um 0 Uhr UTC (in Deutschland 1 oder 2 Uhr), Feiertage
  kennt die Regel nicht.

### Was es noch nicht gibt

- Agenten als Zugewiesene, Abnahmekriterien als Pflichtabschnitt, die Sperre von
  `done`/`cancelled` für Agenten und den Verbrauch je Ticket (M6); Tags als Auslöser
  (M7); die Abholung von Tickets durch externe Agenten (M8).
- Zu Sprints (M4b): Schätzung oder Aufwandspunkte, eine Burndown-Kurve, ein Kalender,
  Sprints über mehrere Bereiche, Löschen eines Sprints, Ändern von Name und Zeitraum in
  der Oberfläche (die API kann es), ein bereichsübergreifendes Board einer anderen Person.
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

**Sprints (M4b):** Anlegen, Ändern, Starten und Abschließen schreiben je ein Ereignis
`sprint.created`, `sprint.updated`, `sprint.started` oder `sprint.closed` (nur Kennungen
und Feldnamen); `publish_live` sendet daraus `sprint.changed` mit `space_id` und
`sprint_id` an alle Verbindungen, deren Person Tickets des Bereichs sehen darf. Der
Wechsel des Sprints eines Tickets ist ein gewöhnliches `ticket.updated` mit dem Feld
`sprint` (alte und neue Sprint-ID). **Das Abschließen** verschiebt alle unerledigten
Tickets in einer Transaktion und schreibt dabei **ein `ticket.updated` je verschobenem
Ticket** (und daraus je eine Systemmeldung, also ein `message.created`). Die Handler
arbeiten in eigenen Bahnen: Die Systemmeldungen eines großen Abschlusses halten
Erwähnungen, Benachrichtigungen und Live-Ereignisse anderer Handler nicht auf. Gemessen
(siehe [`docs/STECKBRIEF.md`](STECKBRIEF.md#sprints-und-boards-m4b)): Ein Abschluss mit
1.782 verschobenen Tickets dauerte 2,9 s; ein Worker hatte die rund 3.570 Ereignisse
8,5 s danach verteilt. Eine Erwähnung kam in dieser Zeit nach 0,2 s an, die erste
Systemmeldung eines gleichzeitig angelegten Tickets erst nach knapp 8 s (dieselbe Bahn).
Ohne laufenden Worker geht nichts verloren, aber Systemmeldungen, Zuweisungs-
Benachrichtigungen und Live-Aktualisierungen bleiben aus, bis er läuft. Die Metrik
`herd_outbox_dispatch_total{handler="ticket_timeline",result="ok"}` zeigt, dass er
Tickets verarbeitet; `smoke.sh` prüft genau das (Ticket anlegen, Status ändern, beide
Systemmeldungen in der Diskussion).

**Kapazität** (gemessen, siehe [`docs/STECKBRIEF.md`](STECKBRIEF.md#tickets-m4)):
Seit jeder Handler eine eigene Bahn hat (Review M4 P3), schafft ein eigener
Worker-Prozess hier gut 400 Ereignisse je Sekunde (vorher rund 90), zwei rund 700. Das ist mehr, als die API an Anlagen erzeugt (60 Tickets je Sekunde ergeben gut
130 Ereignisse). Hängt ein Handler (etwa an einer Sperre), arbeiten die anderen weiter.
In `HERD_ROLE=all` teilen sich API und Worker einen Prozess und dessen CPU; dort holt
der Worker unter Dauerlast langsamer auf (`herd_outbox_pending`, Alarm
`HerdOutboxBacklog`).

### Daten und Migrationen

- Tabellen: `work_item` (die Tickets, mit `search_tsv`), `ticket_status`,
  `ticket_counter` (eine Zeile je Organisation; zwei gleichzeitige Anlagen warten kurz
  aufeinander, Nummern werden nie doppelt vergeben), `ticket_page_link`; die
  Diskussion ist ein Gespräch der Art `thread_ticket`, Tags stehen in `tagging`.
- Die Migrationen von M4 erweitern nur (der Code von M3 läuft gegen das Schema von M4).
  Die fünf Standardstatus legt ein Trigger beim Anlegen eines Bereichs an, auch wenn der
  Bereich von einer älteren Version angelegt wird; die Migration hat sie für bestehende
  Bereiche nachgetragen.
- Ein Trigger hält übergeordnetes Ticket und Status im Bereich des Tickets, ein zweiter
  (`work_item_hierarchy`, Review M4 P7) die Hierarchie: kein Ticket unter sich selbst,
  nur erlaubte Arten übereinander, keine Änderung von Art oder Bereich, zu der die
  Kinder nicht passen (SQLSTATE `23514`, Meldungen `work_item_parent_self`,
  `work_item_parent_other_space`, `work_item_parent_kind`,
  `work_item_children_do_not_fit`). Er liest das übergeordnete Ticket `FOR SHARE`, wie
  der Dienst.
- Audit: `ticket.created`, `ticket.assigned`, `ticket.cancelled`, `ticket.tags_set`,
  `ticket_status.created`, `ticket_status.updated`, `ticket_status.deleted`. Andere
  Feldänderungen stehen in der Diskussion, nicht im Audit.
- Neue Einstellungen (`HERD_*`) bringt M4 nicht mit.
- **M4b** fügt zwei Migrationen hinzu, beide nur erweiternd (der Code von M4 läuft gegen
  das neue Schema): Tabelle `sprint` mit dem eindeutigen Teilindex
  `uq_sprint_space_id_active` (höchstens ein aktiver Sprint je Bereich) und der Bedingung,
  dass nur und immer ein abgeschlossener Sprint eine Bilanz hat; `work_item.sprint_id`
  mit dem Fremdschlüssel `(sprint_id, space_id)` auf den Sprint desselben Bereichs;
  `work_item.status_changed_at`, gesetzt vom Trigger `work_item_status_changed_at` bei
  jedem Wechsel von `status_id` (auch durch ältere Versionen und beim Löschen eines
  Status mit Ersatz), für bestehende Tickets aus der letzten Systemmeldung zum Status
  nachgetragen. Sperren: erst Sprints, dann Tickets. Audit: `sprint.created`,
  `sprint.started`, `sprint.closed` (mit Ziel der unerledigten Tickets und Bilanz).
  Keine neuen Einstellungen.

### Woran man Probleme erkennt

- Ein Ticket ohne Systemmeldungen in der Diskussion: Der Worker läuft nicht oder hängt
  zurück (`herd_outbox_pending`, `herd_outbox_oldest_pending_seconds`, `/ready` des
  Workers).
- 409 `ticket.version_conflict` häufen sich: mehrere Personen oder Skripte ändern
  dieselben Tickets; Skripte sollten vor jeder Änderung neu lesen.
- 422 `ticket.assignee_invalid` beim Zuweisen: Die Person darf den Bereich nicht lesen
  (oder es gibt sie nicht; die API unterscheidet das absichtlich nicht).
