# Agenten: Bedienung und Betrieb

Agenten arbeiten wie Kolleginnen und Kollegen: Sie sind Mitglied in Bereichen, lassen
sich ansprechen und erwähnen, bekommen Tickets, schlagen Änderungen vor oder schreiben
sie selbst (je nach Stufe), fragen bei kritischen Schritten nach einer Freigabe und
führen je Bereich ein Gedächtnis. Jeder Lauf ist Schritt für Schritt einsehbar und
lässt sich abbrechen. Seit M7 arbeiten sie auch ohne Anstoß im Gespräch: als Aufgabe
einer Person zu einem Zeitpunkt, wiederkehrend, als Heartbeat oder auf Ereignisse im
Bereich hin, begrenzt durch Tagesbudgets. Stand: M7 (Spezifikation 5.4, 5.6, 6.3, 7.4,
8, 9 und 11, soweit gebaut); aus M8 externe Werkzeuge und externe Agenten.

Die KI-Anbindung selbst (Verbindungen, Schlüssel, ausgehende Aufrufe, wer welches
Modell nutzt, Verbrauch, KI-Richtlinie je Bereich und KI-Sperre) steht in
[`KI.md`](KI.md). Vorschläge im Wiki: [`WIKI.md`](WIKI.md#vorschläge-seit-m6),
Agenten an Tickets: [`TICKETS.md`](TICKETS.md#zuweisung), Erwähnungen in Kanälen:
[`NACHRICHTEN.md`](NACHRICHTEN.md).

## Bedienung

Alles in diesem Teil sieht nur, wer KI nutzen darf (`ai.use`: eine Zuordnung zu einem
Modell, siehe [`KI.md`](KI.md#wer-nutzt-welches-modell-apiaiassignments-aimanage)).
Wer keine hat, sieht keine Agenten zur Auswahl, keine Läufe und keine KI-Menüs; was
Agenten in Gesprächen geschrieben haben, liest jede und jeder normal, mit dem
KI-Kennzeichen.

### Was ein Agent ist

Ein Agent hat einen Namen, eine Kurzvorstellung, Anweisungen (darin auch seine
„Persönlichkeit“), ein Modell, eine verantwortliche Person und eine **Stufe**:

| Stufe | kann von sich aus |
|---|---|
| 1: nur lesen | Seiten, Tickets, Versionslisten, das eigene Gespräch und frühere eigene Läufe lesen, Skills laden, zurückfragen, antworten |
| 2: vorschlagen | dazu Änderungen an Seiten und neue Seiten **vorschlagen**, Skills vorschlagen, Tickets kommentieren, anlegen, mit Seiten verknüpfen und bis „Zur Prüfung“ setzen, sein Gedächtnis pflegen |
| 3: intern schreiben | dazu Seiten direkt schreiben (nur in Bereichen, die das erlauben), Tickets übergeben, in Gespräche schreiben, in denen er Mitglied ist |

Ein Agent liest nie mehr, als die Person darf, die ihn gerade fragt, und nie mehr, als
er selbst als Mitglied darf, und davon nur, was alle sehen dürfen, die die Antwort
lesen werden (siehe [Die Publikumsregel](#die-publikumsregel-wer-liest-mit)). Er
handelt immer im Auftrag einer Person: Ihre Rechte gelten, ihr wird der Verbrauch
gebucht.

### Mit einem Agenten sprechen

**Neue Direktnachricht** → einen Agenten wählen. Jede Nachricht startet einen Lauf;
eine Karte im Gespräch zeigt, dass er arbeitet („Hilda arbeitet …“, mit dem Schritt),
dann kommt die Antwort mit Quellen. Was währenddessen geschrieben wird, beantwortet der
nächste Lauf gemeinsam. Kann kein Lauf starten, sagt das Eingabefeld warum (keine KI
zugeordnet, Agent pausiert oder Entwurf, verantwortliche Person deaktiviert, Verbindung
abgeschaltet, Lauf wartet noch auf eine Antwort, Antwort in einem Thread).

### Erwähnen in Kanal und Thread

`@` im Eingabefeld eines Kanals, einer Seiten- oder Ticket-Diskussion bietet neben
Personen die Agenten an, die Mitglied des Bereichs sind (mit KI-Kennzeichen). Der
erwähnte Agent antwortet **im Thread** der Nachricht, nie als neue Nachricht im Kanal;
er liest diesen Thread (bis zu seinem Start), nicht den ganzen Kanal. Als Auftrag gilt
nur, was die erwähnende Person geschrieben hat: Nachrichten anderer Personen und anderer
Agenten im Thread bekommt er mit Namen als Kontext, ausdrücklich als Daten und nie als
Anweisung, und nur seine eigenen früheren Antworten gelten als seine. Je Thread ist
höchstens ein Lauf offen; eine weitere Erwähnung im selben Thread wartet, bis er fertig
ist („Lauf wartet“). In anderen Threads desselben Kanals laufen andere Läufe zugleich.
Eine nachträgliche Bearbeitung, die einen Agenten erwähnt, startet nichts. Wer keine KI
hat, kann Agenten nicht erwähnen; eine Erwähnung von Hand verrät nichts und startet
nichts.

### Tickets zuweisen und übergeben

Ein Agent kann Bearbeiter eines Tickets sein (Auswahl „Zugewiesen“, Agenten mit
KI-Kennzeichen; nur aktive Agenten, die mindestens als `editor` Mitglied des Bereichs
sind; persönliche nur durch ihre Eigentümerin). Die Zuweisung startet seinen Lauf: Er
liest das Ticket, arbeitet, kommentiert in der Ticket-Diskussion und setzt den Status
höchstens auf eine Kategorie „Zur Prüfung“; **erledigt oder verworfen setzt immer ein
Mensch**. Kann der Lauf nicht starten oder endet er ohne Antwort, bleibt das Ticket
zugewiesen, die Diskussion nennt den Grund, und die verantwortliche Person des Agenten
bekommt einen Eintrag in ihrer Aktivität. Auf Stufe 3 kann ein Agent das Ticket mit
Begründung an eine Person oder einen anderen Agenten **übergeben**; der nächste Agent
arbeitet dann für dieselbe Person weiter. Nach drei Übergaben ist Schluss
(„Übergabegrenze“). Nichts über ein Ticket erscheint in einem Kanal.

### Freigaben und Rückfragen

Ein Werkzeug kann für einen Agenten auf **„Nach Freigabe“** stehen. Will der Agent es
nutzen, erscheint im Gespräch (oder Thread) eine **Freigabekarte**: was er tun will (mit
Diff bei Seiten), wer entscheidet, bis wann. Entscheiden darf nur die Person, die den
Lauf ausgelöst hat, und nur, wenn sie die Änderung auch selbst vornehmen dürfte. Andere
sehen die Karte ohne Knöpfe. **Freigeben** setzt den Lauf fort; **Ablehnen** (mit
optionalem Grund) teilt das dem Agenten mit, er arbeitet ohne diese Änderung weiter.
Hat sich das Objekt zwischen Anfrage und Ausführung geändert (z. B. hat jemand die Seite
bearbeitet), wird nichts ausgeführt; die Karte zeigt „Veraltet“, und der Agent kann neu
fragen. Schreibende **externe Werkzeuge** (Stufe 4) fragen immer: Die Karte nennt Server
und Werkzeug („Tracker · create_issue“), die entscheidende Person sieht die Argumente,
die nach der Freigabe an den Server gehen. Hat sich der Server oder das Werkzeug seit
der Anfrage geändert, ist die Freigabe veraltet, und es wird nichts gesendet. Ohne Entscheidung endet der Lauf nach `HERD_AI_APPROVAL_HOURS` (Standard 72
Stunden). Eine **Rückfrage** (`ask_user`) erscheint ebenso als Karte mit Antwortfeld
(bis 4.000 Zeichen) für die fragende Person. Offene Freigaben stehen unter
**Freigaben** in der Seitenleiste (mit Zähler) und in der Aktivität.

Solange ein Lauf wartet, hält er nichts fest außer seinem Thread (bzw. dem Gespräch
oder Ticket): Neue Nachrichten dort starten keinen weiteren Lauf; nach seinem Ende
beantwortet ein neuer Lauf, was inzwischen kam.

### Läufe ansehen und abbrechen

**Meine Läufe** (Seitenleiste) listet die Läufe, die man ausgelöst hat, mit Filtern
nach Zustand und Stopgrund; am Agenten (Verwaltung oder „Meine Agenten“) stehen alle
seine Läufe für die verantwortliche Person. Die **Laufansicht** zeigt Agent, fragende
Person, Ort, Zustand, Stopgrund in Worten, Versuche, Dauer, Token und Kosten,
Übergabetiefe und jeden Schritt: Modellantworten, Werkzeugaufrufe mit Argumenten und
Ergebnis, Freigaben und Rückfragen. **Lauf abbrechen** (mit Bestätigung) steht allen
offen, die den Lauf sehen dürfen; ein laufender Lauf hält vor seinem nächsten Schritt,
ein wartender oder noch nicht begonnener sofort, und er schreibt danach nichts mehr.
Links zu einem Lauf (an Antworten, Vorschlägen, Ticketmeldungen) erscheinen nur für
Personen, die ihn sehen dürfen.

### Vorschläge

Auf Stufe 2 schreibt ein Agent Seiten nicht selbst, sondern **schlägt** Änderungen oder
neue Seiten **vor**. Sie stehen im Reiter **Vorschläge** des Bereichs (für alle, die
dort Seiten bearbeiten dürfen; mit Zähler), mit Diff, Begründung und Lauf. Moderatoren
nehmen an oder lehnen ab; hat sich die Seite inzwischen geändert, zeigt ein
Zusammenführen-Dialog die Stellen, und nichts wird still übernommen. Einzelheiten in
[`WIKI.md`](WIKI.md#vorschläge-seit-m6). Ebenso schlägt ein Agent Änderungen an Skills
oder neue Skills vor; darüber entscheidet, wer die Skills dort verwaltet.

### Skills

Ein Skill ist eine Anleitung (eine SKILL.md: Name, Beschreibung, Text), organisationsweit
oder in einem Bereich, und einem Agenten zugewiesen. Der Agent kennt Name und
Beschreibung seiner Skills und holt den Text, wenn er ihn braucht. **Nichts in einem
Skill wird ausgeführt**: Ein Skill ist Text, auch wenn er Code enthält. Skills stehen
unter **Skills** im Bereich (für alle mit KI, die den Bereich lesen) und in der
Verwaltung; Moderatoren eines Bereichs pflegen dessen Skills, organisationsweite die
Admins. Versionen, Wiederherstellen, Import (SKILL.md oder ZIP) und Export gibt es dort.

### Gedächtnis

Ein Agent kann sich je Bereich Notizen machen (Stufe 2). Sie stehen auf einer ganz
normalen Wiki-Seite unter **Agenten › <Name des Agenten> › Gedächtnis** (Ordner
`_agenten`, im Seitenbaum am Ende), mit den Rechten, Versionen und dem KI-Kennzeichen
jeder Seite. Wer die Seite bearbeiten darf, korrigiert sie im Editor; wer sie für KI
sperrt, verbietet dem Agenten das Schreiben. Aus einer Direktnachricht allein mit dem
Agenten merkt er sich nur etwas in einem Bereich, den sonst niemand liest; für einen
gemeinsamen Bereich erwähnt man ihn in dessen Kanal oder einer Diskussion dort. Bei jedem Lauf liest der Agent die
Gedächtnisseiten der Bereiche, die er in diesem Lauf lesen darf (zusammen höchstens
4.000 Zeichen).

### Persönliche Agenten

Unter **Meine Agenten** legt man eigene Agenten an (wenn die Organisation es erlaubt,
höchstens `HERD_AI_PERSONAL_AGENTS_MAX`, Standard 5). Ein persönlicher Agent nutzt das
eigene Modell, arbeitet höchstens auf Stufe 2, ist nur Mitglied im eigenen persönlichen
Bereich und nur für seine Eigentümerin erreichbar (Direktnachricht, Erwähnung,
Zuweisung); alle anderen sehen ihn nicht. Admins sehen ihn in der Verwaltung, mit
Vermerk im Audit.

### Externe Agenten (seit M8)

Ein **externer Agent** (etwa Claude Code oder Codex, das ein Team auf einem eigenen
Rechner oder in einer Pipeline betreibt) ist ein Teammitglied wie jeder Agent: mit
Namen, Kurzvorstellung, verantwortlicher Person und Mitgliedschaften in Bereichen. Er
hat aber **kein Modell, keine Läufe, keine Aufgaben und kein Budget im System**: Er
arbeitet von außen über den Endpunkt `/mcp` mit einem **Agenten-Token** (siehe
[`MCP.md`](MCP.md#externe-agenten)).

- Erwähnungen, Direktnachrichten und Aufgaben starten bei ihm nichts; die Antwort auf
  eine Nachricht nennt den Grund `agent.external`.
- Ein Ticket, das man ihm zuweist, startet keinen Lauf und bekommt keinen Hinweis in der
  Diskussion: Es **wartet auf Abholung** (`awaiting_pickup: true`, solange es offen
  ist). Der Agent holt es ab (`claim_ticket`), kommentiert, setzt den Status höchstens
  auf „Zur Prüfung“; **erledigt setzt ein Mensch**. Er kann auch ein nicht
  zugewiesenes Ticket eines Bereichs, in dem er Mitglied mit Bearbeitungsrecht ist,
  selbst übernehmen.
- Was er schreibt, steht unter seinem Namen, mit KI-Kennzeichen und dem Namen des
  Tokens (`via_token`), auch in den Systemeinträgen der Ticket-Zeitleiste.
- Er darf nie mehr als seine verantwortliche Person, nie mehr als er selbst als
  Mitglied und nie mehr als der Umfang seines Tokens; höchstens Stufe 2. Ist seine
  verantwortliche Person nicht mehr aktiv (oder hat sie kein `mcp.use` mehr), oder
  ist der Agent pausiert, **ruht** er: seine Token antworten 401.

### Aufgaben: Agenten arbeiten ohne Anstoß (seit M7)

Eine **Aufgabe** lässt einen Agenten arbeiten, ohne dass ihn jemand im Gespräch
anspricht. Es gibt vier Arten:

| Art | wann der Agent arbeitet |
|---|---|
| Einmalig | einmal zu einem Zeitpunkt |
| Wiederkehrend | nach einem Zeitplan (Cron) in einer Zeitzone, etwa werktags um 9 Uhr; höchstens alle 15 Minuten |
| Heartbeat | alle 15 bis 1.440 Minuten innerhalb aktiver Stunden (Wochentage, von–bis, Zeitzone) geht er eine Checkliste durch |
| Ereignis-Regel | wenn im Bereich etwas geschieht: eine Seite veröffentlicht, ein Ticket angelegt (wahlweise nur mit einem Tag oder einer Art), ein Anhang hochgeladen, die Prüffrist einer Seite abgelaufen |

**Meine Aufgaben** (Seitenleiste) listet die eigenen mit nächstem Termin und letztem
Lauf; der Reiter **Aufgaben** eines Bereichs zeigt die an seinen Kanälen und Tickets,
soweit man sie sieht; die Verwaltung zeigt sie je Agent. Die Ansicht einer Aufgabe nennt
die nächsten Termine (in ihrer Zeitzone) und das **Protokoll** jedes Termins: gestartet
(mit Link zum Lauf), still (`HEARTBEAT_OK`) oder übersprungen mit Grund.

- **Jede Aufgabe gehört einer Person**, der Eigentümerin. Ihr Lauf läuft in ihrem
  Auftrag: Es gelten ihre Rechte ∩ die des Agenten ∩ das Publikum des Ortes (wie bei
  jedem Lauf, siehe [Die Publikumsregel](#die-publikumsregel-wer-liest-mit)); ihr wird
  der Verbrauch gebucht, an sie gehen Freigaben und Rückfragen.
- **Jede Aufgabe hat einen Ort**, an den das Ergebnis geht: die Direktnachricht der
  Eigentümerin mit dem Agenten, ein Kanal eines Bereichs (jeder Termin eröffnet dort
  einen eigenen Thread mit dem Eintrag „Aufgabe … gestartet“, in dem man auch antworten
  kann) oder ein Ticket. Im Kanal liest der Agent wie ein Betrachter des Bereichs,
  Entwürfe nur in der Direktnachricht. Der Auftrag selbst erscheint am Ort nicht.
- **Heartbeat:** Ist nichts zu tun, antwortet der Agent genau `HEARTBEAT_OK`; dann
  erscheint nirgends etwas (keine Nachricht, keine Aktivität), nur das Protokoll
  vermerkt „nichts zu melden“. Alles andere kommt an den Ort. Solange ein Heartbeat
  noch nichts zugestellt hat, zeigt der Ort auch kein „arbeitet …“: Sein Fortschritt
  geht live nur an die Eigentümerin (ihre Laufansicht folgt ihm).
- **Ereignis-Regeln** legen nur die Verwaltenden eines Bereichs an, an einem Kanal oder
  Ticket dieses Bereichs. Der Agent erfährt nur Art und Kennung des Objekts und liest es
  selbst, mit den Rechten der Eigentümerin am Ort: Wer das Ereignis ausgelöst hat,
  gewinnt nichts, und über ein Objekt, das der Lauf nicht lesen dürfte (ein Entwurf,
  eine für KI gesperrte Seite), erfährt er nichts. **Ruhezeit** (Standard 5 Minuten,
  mindestens 1): Nach einem Lauf startet die Regel frühestens nach der Ruhezeit
  wieder; was dazwischen geschieht, bekommt der nächste Lauf als Anzahl, nicht einzeln.
  **Tiefe:** Lösen Agenten mit ihren Läufen weitere Regeln aus, endet die Kette bei
  Tiefe 3 (Übergaben zählen mit); eine Regel reagiert nie auf das, was ihr eigener Lauf
  an seinem Objekt getan hat. **Freigabe:** Was ein anderer ins Objekt schreibt (der Titel
  eines Tickets, eine Seite), liest das Modell im Lauf der Eigentümerin. Deshalb fragt
  dort jedes direkt schreibende Werkzeug der Stufe 3 (`update_page`, `assign_ticket`,
  `post_message`), das sonst ohne Rückfrage liefe (`allow`), die Eigentümerin um
  Freigabe (wie `confirm`, eine Karte am Ort und eine Aktivität). Werkzeuge der Stufe 2
  (Tickets anlegen, kommentieren, Status, Vorschläge, Gedächtnis) bleiben, wie sie dem
  Agenten erlaubt sind, damit Ketten von Regeln ohne Freigabe weiterlaufen; die Antwort
  des Laufs in seinem Thread braucht keine. Ein **externes Werkzeug** fragt dort immer,
  auch ein lesendes der Stufe 2: Seine Argumente verlassen das System, und der Text der
  auslösenden Person kann sie bestimmen (Review M8 1, Befund 5). **Budget:** Läufe einer Ereignis-Regel gehen
  auf das Budget der Eigentümerin (und des Agenten), nicht auf das der Person, die das
  Ereignis ausgelöst hat.
- **Angehalten:** von Hand, oder vom System: wenn die Eigentümerin die Aufgabe nicht mehr
  ausführen darf (nicht mehr aktiv, keine KI mehr, erreicht Agent oder Ort nicht mehr;
  bei einer Ereignis-Regel auch, wenn sie den Bereich nicht mehr verwaltet) oder wenn drei Läufe in Folge nicht zu Ende kamen. Wer betroffen ist, bekommt eine
  Aktivität (die verantwortliche Person des Agenten und die Verwaltenden des Bereichs
  bzw. bei Fehlschlägen die Eigentümerin). Rechte wandern nie still: Wer die Aufgabe
  selbst anlegen dürfte, kann sie **übernehmen** und wird Eigentümerin. Ein noch offener
  Lauf der bisherigen Eigentümerin wird dabei abgebrochen (er hielte sonst die Bahn der
  Aufgabe, womöglich bis eine Freigabe verfällt, die niemand mehr gibt).
- **Fortsetzen** holt einen verpassten Termin einmal nach. **Jetzt ausführen** (nur die
  Eigentümerin, nicht für Ereignis-Regeln) löst einen Termin außer der Reihe aus, mit
  denselben Prüfungen. **Löschen** entfernt die Aufgabe; ihre Läufe bleiben einsehbar.
  Die Zeile bleibt als Verlauf mit ihrem Auftrag gespeichert (der Lauf und sein
  Protokoll verweisen darauf; jeder gestartete Termin hält eine Kopie 90 Tage), nur
  angezeigt und ausgeführt wird sie nicht mehr.
- **Übersprungen** wird ein Termin, wenn der vorige Lauf noch arbeitet, der Agent
  angehalten ist, der Ort archiviert oder für diese KI gesperrt ist, ein Tagesbudget
  erreicht ist, ein Heartbeat nach einem Ausfall außerhalb seiner Stunden käme oder eine
  Kette zu tief wäre. Nach einem Ausfall läuft eine Aufgabe einmal nach, nicht einmal je
  verpasstem Termin.

**Tagesbudgets** (seit M7) setzen Admins für die Organisation, eine Person oder einen
Agenten ([`KI.md`](KI.md#budgets-apiaibudgets-aimanage)). Ist eines erreicht, endet ein
Lauf vor seinem nächsten Modellaufruf mit dem Hinweis „Tagesbudget erreicht“ (der Lauf
nennt, wessen Limit), und fällige Termine werden übersprungen, bis der nächste UTC-Tag
beginnt.

### Das KI-Kennzeichen

Alles, was ein Agent schreibt, trägt das Kennzeichen **KI** und nennt den Agenten (und,
für wer es sehen darf, den Lauf): Antworten und Kommentare, Systemmeldungen über seine
Ticketänderungen, Seitenversionen und Vorschläge, Skill-Versionen, Freigabe- und
Rückfragekarten, Einträge in Aktivität und Suche, die Einsicht in Direktnachrichten.

### Was Agenten nie tun

- nichts löschen und nichts in den Papierkorb legen;
- keine Vorschläge annehmen oder ablehnen und keine Freigaben erteilen, auch nicht für
  sich selbst;
- kein Ticket auf erledigt oder verworfen setzen;
- keine Seite schreiben, die für KI gesperrt ist, und in Bereichen mit „Agenten schlagen
  vor“ keine Seite direkt;
- nichts lesen, was die fragende Person nicht lesen darf, und nichts aus einem Bereich
  an einen Ort tragen, dessen Publikum es nicht sehen darf;
- keinen Inhalt an eine Verbindung oder einen externen MCP-Server schicken, deren
  Datenort die KI-Richtlinie eines gelesenen Bereichs nicht zulässt (ein externes
  Werkzeug antwortet dann `policy_blocked` und wird nicht aufgerufen), ohne Freigabe
  der fragenden Person nach außen handeln (schreibende externe Werkzeuge), und nichts in einen Bereich mit der KI-Richtlinie `none`
  schreiben (keine Nachricht, kein Gedächtnis, kein Ticket, kein Vorschlag: jedes
  Werkzeug antwortet dort „nicht gefunden“);
- Code ausführen (es gibt kein solches Werkzeug), andere Agenten erwähnen oder sich
  selbst eine Stufe, ein Werkzeug oder eine Freigabe geben: Was in Seiten, Tickets,
  Skills, Beschreibungen und Ergebnissen externer Werkzeuge steht, sind für den Agenten
  Daten, keine Anweisungen.

## Verwaltung

### Agenten anlegen (`agent.manage`)

Verwaltung → **Agenten** (Owner und Admins). `GET/POST /api/agents`,
`GET/PATCH/DELETE /api/agents/{id}` (sonst 404 `agent.not_found`): Name,
Kurzvorstellung, Anweisungen (höchstens 20.000 Zeichen), Verbindung und Modell (eine
Chat-Verbindung, die das Modell anbietet; 422 `ai.connection_not_chat`,
`ai.model_unknown`, `agent.connection_and_model`), verantwortliche Person (aktiv, kein
Gast; 422 `agent.responsible_invalid`), Status `draft|active|paused`, Grenzen
`max_steps` (1–25) und `max_runtime_seconds` (10–600), Stufe. Änderungen mit `version`
(409 `agent.version_conflict`), Audit ohne den Text der Anweisungen. Wer schon
gesprochen hat oder gelaufen ist, wird nicht gelöscht (409 `agent.in_use`), sondern
pausiert. Antworten nennen `responsible_name` und `owner_user_id` (bei persönlichen
Agenten). Einen Agenten nimmt man wie eine Person in einen Bereich auf (`PUT
/api/spaces/{id}/members` mit `member_type: agent`); `GET /api/agents/{id}/spaces`
listet seine Bereiche mit Rolle. Entwürfe sehen nur Personen mit `agent.manage`.
Persönlichkeit, Avatar und Ersatzmodell der Spezifikation (8.1): Die Persönlichkeit
gehört in die Anweisungen; Avatar und Ersatzmodell gibt es nicht.

- Agenten sind Principals wie Personen: Mitglied von Bereichen, Teilnehmer einer
  Direktnachricht, Urheber von Nachrichten (`kind: agent`).
- `GET /api/agents` nennt Personen mit `ai.use` ohne `agent.manage` nur ihre eigenen
  persönlichen Agenten. `GET /api/agents/{id}/spaces` (seitenweise nach Name) nennt
  nur Mitgliedschaften; offene Bereiche, die der Agent nur liest, stehen nicht darin.
- `GET /api/agents/{id}/profile` (`ai.use`): Name, Kurzvorstellung, Status. Entwürfe
  sind für alle ohne `agent.manage` unsichtbar, auch beim Hinzufügen als Mitglied
  eines Bereichs (404 `agent.not_found`). Wer Agenten nicht sieht (weder `ai.use` noch
  `agent.manage`), entfernt auch keinen aus einem Bereich: 404
  `spaces.member_not_found` wie für ein unbekanntes Mitglied. Das Verzeichnis
  (`/api/directory`) nennt Agenten nur Personen mit `ai.use`.
- `POST /api/dms` mit `{"agent_id": …}` (ohne weitere Personen, sonst 422
  `dm.agent_pair_only`): die Direktnachricht der Person mit dem Agenten; ohne `ai.use`
  404 `agent.not_found`.

### Externe Agenten anlegen (seit M8)

Mit `agent.manage`: `POST /api/agents` mit `"kind": "external"`, Name, Kurzvorstellung,
verantwortlicher Person (Pflicht; 422 `agent.responsible_invalid`), Status und Stufe
(1 oder 2). Eine Verbindung oder ein Modell, `personal: true` oder eine Stufe über 2
sind 422 `agent.external_invalid`, auch bei einer späteren Änderung; die Art ändert sich
nie. Antworten nennen `kind` (`internal|external`); bei externen Agenten sind
`connection_id` und `model` `null`. Das Profil (`/profile`) nennt `kind` ebenfalls,
damit die Oberfläche keine Direktnachricht anbietet. Mitgliedschaften wie bei jedem
Agenten (`PUT /api/spaces/{id}/members`, `member_type: agent`). Wer Token bekommen
hat, wird nicht gelöscht, sondern pausiert (409 `agent.in_use`). Aufgaben lassen sich
für externe Agenten nicht anlegen (403 `automation.not_allowed`). Seine Token:
[`MCP.md`](MCP.md#externe-agenten). Werkzeugfreigaben (`agent_tool`) wirken auch für
ihn, nur verschärfend: Was nicht `allow` ist, bietet `/mcp` ihm nicht an (Freigaben
mit `confirm` gibt es dort nicht). `GET /api/agents/{id}/tools` nennt dafür je Werkzeug
`via_mcp` (das Werkzeug des Katalogs kann sein Token über `/mcp` erreichen: dort
angeboten und höchstens Stufe 2; bei allen anderen Agenten `false`) und `max_level` 2.
Das Verzeichnis (`GET /api/directory`) nennt bei Agenten `kind`, damit Auswahllisten
(Erwähnung, Zuweisung) einen externen Agenten kennzeichnen.

### Stufen und Werkzeugfreigaben

Neue Agenten haben Stufe 2; Agenten aus M5 wurden bei der Migration Stufe 1. Eine Stufe
über 2 vergibt nur ein Admin (sonst 403 `agent.level_denied`): Agenten der Organisation
ändert ohnehin nur, wer `agent.manage` hat, und persönliche Agenten bleiben bei 2;
`max_level` in `GET /api/agents/{id}/tools` nennt die höchste Stufe, die man selbst
geben darf. Stufe 4 (extern handeln, seit M8) öffnet die schreibenden Werkzeuge externer
MCP-Server, immer nur mit Freigabe (siehe „Externe Werkzeuge“).

Die Stufe ist eine **Voreinstellung**: Jedes Werkzeug ab seiner Mindeststufe steht auf
`allow`, darunter auf `block`. Je Werkzeug kann ein Eintrag (`allow`, `confirm`,
`block`) nur **verschärfen**; wirksam ist das Strengere (`GET/PUT
/api/agents/{id}/tools` mit der `version` des Agenten, unbekannte Werkzeuge 422
`agent.tool_unknown`, Audit `agent.tools_changed`). In der Oberfläche: „Wie die Stufe“,
„Nur nach Freigabe“, „Gesperrt“. Ein Lauf bietet dem Modell nur Werkzeuge mit `allow`
oder `confirm` an und prüft die Freigabe vor jedem Aufruf neu (entzogen:
`rights_revoked`). Ein Werkzeug, das der Katalog nicht kennt, läuft nie.

| Werkzeug | Stufe | Wirkung | Was es tut |
|---|---|---|---|
| `search` | 1 | lesen | Volltext über Seiten und Tickets |
| `read_page`, `read_ticket` | 1 | lesen | eine Seite, ein Ticket |
| `list_tree` | 1 | lesen | lesbare Bereiche; Seiten eines Bereichs nach Pfad (ohne Inhalt) |
| `list_versions` | 1 | lesen | Versionen einer Seite (ohne Inhalt; nur mit `page.edit`) |
| `search_tickets` | 1 | lesen | Tickets nach Text und Filtern |
| `read_conversation` | 1 | lesen | nur das Gespräch bzw. den Thread des Laufs |
| `search_past_runs` | 1 | lesen | frühere Läufe dieses Agenten für dieselbe Person |
| `load_skill` | 1 | lesen | Text eines Skills, in Teilen zu höchstens 7.000 Zeichen |
| `ask_user` | 1 | lesen | Rückfrage an die fragende Person (wartet) |
| `submit_result` | 1 | lesen | gibt das Ergebnis ab und beendet den Lauf |
| `propose_page_change`, `propose_new_page` | 2 | vorschlagen | Seitenvorschlag (`page.edit` nötig) |
| `propose_skill` | 2 | vorschlagen | Skill-Vorschlag |
| `update_memory` | 2 | schreiben | Gedächtnisseite des Bereichs ersetzen (höchstens 8.000 Zeichen) |
| `comment_ticket` | 2 | schreiben | Kommentar in der Ticket-Diskussion |
| `set_ticket_status` | 2 | schreiben | Status, höchstens Kategorie `review` |
| `create_ticket` | 2 | schreiben | Ticket anlegen (meldend: der Agent) |
| `link_ticket_page` | 2 | schreiben | Ticket mit Seite verknüpfen |
| `update_page` | 3 | schreiben | Seite schreiben, in zwei Schritten (Diff, dann Schreiben); nur bei `agent_write_policy = direct` |
| `assign_ticket` | 3 | schreiben | Ticket übergeben, mit Begründung als Kommentar |
| `post_message` | 3 | schreiben | Nachricht in das Gespräch des Laufs oder einen Kanal eines Bereichs, in dem der Agent Mitglied ist |
| `ext_…` (externes Werkzeug, `read`) | 2 | lesen | Aufruf eines externen MCP-Werkzeugs; nur mit Eintrag |
| `ext_…` (externes Werkzeug, `write`) | 4 | schreiben | Aufruf eines externen MCP-Werkzeugs; nur mit Eintrag, immer mit Freigabe |

#### Externe Werkzeuge (seit M8)

Freigegebene Werkzeuge externer MCP-Server ([`MCP.md`](MCP.md#externe-mcp-server))
erscheinen in derselben Liste, nach dem Katalog, mit `external` (Server-ID und -Name,
Werkzeug-ID und -Name, `usable`, `left_out`). Die Liste hat keine Seiten, sondern eine feste
Obergrenze: sie ist ein Dokument mit der Version des Agenten, das `PUT` als Ganzes
ersetzt, und Seiten würden das teilen. Gezeigt werden die 22 Werkzeuge des Katalogs, die
freigegebenen externen Werkzeuge (höchstens 200 je Organisation, siehe
[`MCP.md`](MCP.md#externe-mcp-server)) und Werkzeuge mit Eintrag (höchstens 100 je
`PUT`); gelesen werden in SQL nur diese. Ihr Name im Lauf und in den Einträgen ist
`ext_<Werkzeug-ID, alle 32 Hexzeichen>_<Name>` (höchstens 64 Zeichen, die ID wird nie
gekürzt; Zeichen, die ein Modell nicht nutzen darf, werden `_`). So steht jeder Name für
genau ein Werkzeug, gleich wie ein Server seine Werkzeuge nennt (Review M8 1, Befund 1:
bis dahin waren es nur die ersten 12 Hexzeichen, bei einer UUIDv7 die Millisekunde, in
der ein Abruf alle Werkzeuge eines Servers anlegt). Beim Update bekommt jeder Eintrag
unter einem alten Namen, der für genau ein Werkzeug stand, einen Zwilling unter dem
neuen; ein alter Name, der für zwei Werkzeuge stand, gibt keinem mehr etwas (beide
erscheinen ohne Eintrag). Ein Lauf, dessen Journal noch alte Namen trägt, wird mit den
neuen fortgesetzt; eine offene Freigabe unter altem Namen wird beim Fortsetzen
`approval_stale`, und das Modell kann neu fragen.

- **Nur mit Eintrag.** Ein externes Werkzeug hat die Voreinstellung `block`: Ein Agent
  bekommt es erst mit einem Eintrag (`allow` oder `confirm`), und auch dann höchstens,
  was seine Stufe erlaubt. Ein als `read` eingestuftes Werkzeug ist Stufe 2, ein als
  `write` eingestuftes Stufe 4 und **nie lockerer als `confirm`**: Auch mit `allow`
  wartet jeder Aufruf auf die Freigabe der fragenden Person.
- **Nur brauchbare.** Gelistet und angeboten werden nur Werkzeuge, die freigegeben,
  unverändert (Fingerabdruck wie freigegeben), noch gelistet und auf einem
  eingeschalteten Server sind. Ein Eintrag für ein Werkzeug, das das nicht mehr ist
  (gesperrt, geändert, Server aus), bleibt gelistet mit `usable: false` und wirksam
  `block`. Ein `ext_…`-Name, der kein Werkzeug der Organisation ist, ist 422
  `agent.tool_unknown`. Jeder Aufruf beurteilt das Werkzeug, wie es jetzt ist: Stuft
  der Admin es während eines Laufs auf `write` um, braucht schon der nächste Aufruf
  Stufe 4 und die Freigabe (sonst endet der Lauf mit `rights_revoked`; Review M8 1,
  Befund 6).
- **Höchstens 100.000 Zeichen zusammen** (Review M8 2, Befund G5;
  `toolbox/external_bound.py`): Name, Beschreibung und Argumentschema aller externen
  Werkzeuge, die ein Lauf des Agenten bekäme, gehen mit jedem Modellaufruf mit. Sind
  es zusammen mehr, nimmt der Lauf sie in Namensreihenfolge (`ext_<Werkzeug-ID>`, eine
  UUIDv7: in der Reihenfolge, in der sie zuerst gelistet wurden), jedes, solange die
  Summe in der Grenze bleibt; eines, das nicht mehr passt, bleibt weg, kleinere danach
  können noch passen. Dieselben Werkzeuge und Einträge ergeben bei jedem Schritt, nach
  jeder Fortsetzung und beim Wiederholen aus dem Journal dieselbe Auswahl. Die
  Werkzeugliste des Agenten zeigt ein weggelassenes Werkzeug mit
  `external.left_out: true` („Nicht im Modellaufruf“ mit Erklärung); die Metrik
  `herd_external_tool_definitions_left_out_total` zählt sie ohne Namen.
- **Beschreibung** für das Modell: Werkzeug, Server, ob es liest oder nach außen
  handelt; die Beschreibung des Servers folgt gerahmt als nicht vertrauenswürdig und
  auf 1.000 Zeichen gekürzt, ebenso gerahmt und gekürzt, was er über die Argumente
  sagt (`mcp_tool_arguments`). Argumente: nur die Struktur des gespeicherten
  Eingabeschemas, nie ein Wort des Servers; geprüft werden sie vom Server. Ein Werkzeug,
  dessen Schema sich so nicht anbieten lässt (`schema_problem`), ist nicht brauchbar
  ([`MCP.md`](MCP.md#externe-mcp-server); Review M8 1, Befund 2).
- **Höchstens `HERD_MCP_MAX_CALLS_PER_RUN` Aufrufe je Lauf** (Standard 20, seit Task 13
  von M8). Gezählt werden die gesendeten Aufrufe (ihr erster Eintrag im Journal, an
  seinem Feld `sent`, nie am Text: ein Server, der genau den Platzhalter antwortet,
  zählt nicht doppelt; Einträge von vor diesem Feld zählen am Platzhalter); was
  die Richtlinie, eine Freigabe oder ein fehlender Zugang zurückhielt, zählt nicht. Der
  nächste Aufruf wird nicht gesendet, das Modell liest `external_tool_limit: …` und kann
  ohne das Werkzeug weitermachen. Externe Aufrufe kosten keine Modell-Tokens; kein
  Tagesbudget zählt sie, diese Grenze begrenzt sie.

Ob Agenten in einem Bereich Seiten direkt schreiben dürfen, stellt, wer den Bereich
verwaltet: Einstellungen → „Schreiben durch Agenten“ (`agent_write_policy`: `propose`,
Voreinstellung, oder `direct`).

Jedes Werkzeug geht durch dieselben Dienste wie ein Mensch (`router → service →
repository`), mit dem Akteur des Laufs: den Rechten der fragenden Person, begrenzt auf
die Rolle des Agenten und den Lese- und Schreibbereich des Ortes, mit Richtlinie und
`no_ai`. Was ein Agent schreibt, nennt ihn als Urheber (`agent:<id>`) und den Lauf
(`run_id`). Ein abgelehnter Schreibversuch nimmt alles zurück und meldet dem Modell nur
den Code.

### Die Publikumsregel: wer liest mit

Ein Lauf liest höchstens, was die fragende Person darf, und davon nur Bereiche, in denen
der Agent Mitglied ist, und offene Bereiche. Dazu kommt das **Publikum des Ortes**, an
dem er antwortet: Er liest nur, was alle lesen dürfen, die seine Antwort sehen werden,
und er schreibt nur dorthin, wo sein Auftrag liegt.

| Ort | liest (∩ Person ∩ Agent) | schreibt |
|---|---|---|
| Direktnachricht der Person allein mit dem Agenten | alles | wo Person und Agent beide schreiben dürfen |
| Direktnachricht mit mehreren Personen (*) | Bereiche, die alle Teilnehmenden lesen | genau diese Bereiche |
| Kanal, Seiten- oder Ticket-Diskussion in Bereich S | S und die offenen Bereiche (keine offenen, wenn S einen Gast hat) | nur S |

(*) Gebaut, aber heute ohne Weg dorthin: Ein Agent ist nur in Direktnachrichten mit
genau einer Person (sonst 422 `dm.agent_pair_only`), und Teilnehmende einer
Direktnachricht ändern sich nie.

**Entwürfe** liest ein Lauf nur in der Direktnachricht allein mit dem Agenten. An jedem
anderen Ort sieht er Seiten wie ein Betrachter des Bereichs: nur veröffentlichte, auch
wenn die fragende Person und der Agent dort Seiten bearbeiten dürfen. Denn den Kanal
oder Thread lesen alle Mitglieder des Bereichs, Entwürfe aber nur, wer `page.edit` hat.
Das gilt für `read_page`, `search`, `list_tree`, `list_versions` und den Diff von
`update_page` (Inhalt, Titel und Ausschnitte): Ein Entwurf antwortet dort wie eine
unbekannte Seite. Technisch ist das `ReadScope.drafts` am Akteur des Laufs, das
`core/access.sees_drafts` und `draft_space_ids` auswerten.

**Ein gelesener Entwurf bleibt bei den Bearbeitenden.** Hat ein Lauf einen Entwurf aus
Bereich X gelesen (allein mit der Person: `read_page`, ein Treffer von `search`, ein
Titel in `list_tree`, ein Treffer von `search_past_runs`, eine Gedächtnisseite im
Entwurf), merkt er sich das (`Reads.drafts`; im Journal unter `read.drafts`, sodass ein
fortgesetzter Lauf es wieder weiß; auch wenn der Entwurf inzwischen veröffentlicht
ist). Ein Lauf im Thread einer Entwurfsseite beginnt mit dieser Marke. Solange sie
steht, antwortet jedes Werkzeug, dessen Wirkung andere als die Bearbeitenden von X
lesen könnten, mit einem Werkzeugfehler („Not allowed: you have read a draft …“), den
das Modell sieht:

| Werkzeug | nach einem Entwurf aus X |
|---|---|
| `search`, `read_page`, `read_ticket`, `list_tree`, `list_versions`, `search_tickets`, `read_conversation`, `search_past_runs`, `load_skill` | lesen, keine Prüfung |
| `ask_user`, `submit_result`, die Antwort | erlaubt (eigenes Gespräch) |
| `post_message` | ins eigene Gespräch erlaubt, in einen Kanal abgelehnt |
| `propose_page_change` | zu einer Seite von X erlaubt, sonst abgelehnt |
| `propose_new_page` | eine neue Seite in X erlaubt (seit M9; einen Vorschlag lesen nur die Bearbeitenden von X), sonst abgelehnt |
| `update_page` | an einem Entwurf von X erlaubt, sonst abgelehnt |
| `comment_ticket`, `set_ticket_status`, `create_ticket`, `link_ticket_page`, `assign_ticket` | abgelehnt |
| `propose_skill`, `update_memory` | abgelehnt |

Das eigene Gespräch des Laufs ist ausgenommen, weil dessen Publikum die Antwort
ohnehin liest: die Person allein (sie durfte den Entwurf lesen) oder der Thread eines
Entwurfs in X (den nur die Bearbeitenden von X lesen). In der Laufansicht sieht das
Ergebnis eines Werkzeugaufrufs, der einen Entwurf las, außer der fragenden Person nur,
wer in dessen Bereich Seiten bearbeiten darf.

**Was über den eigenen Konnektor kam, bleibt bei der Person** (seit M8). Liefert ein
externes Werkzeug ein Ergebnis über den persönlichen Konnektor der fragenden Person
(Server mit `connector_scope` `personal`), trägt der Lauf die persönliche Marke
(`Reads.personal`, im Journal unter `read.personal`). Seit Review M8 2 (Befund G2) wird
ein Schreiben, das andere als die Person lesen könnten, nicht mehr abgelehnt: Jedes
schreibende Werkzeug der Tabelle (ein Kanal, ein Ticket, eine Seite, ein Vorschlag,
eine Gedächtnisseite, ein Skill, auch `post_message` ins eigene Gespräch, wo andere
mitlesen) wartet auf die **Freigabe der fragenden Person**, die genau den Inhalt zeigt,
der geschrieben würde (die Freigabekarte trägt `personal: true`, ihre Angaben stehen
offen; im Lauf einer Automatisierung oder Ereignisregel gibt die Eigentümerin frei).
Gibt sie frei, läuft genau dieser Aufruf, und was so geschrieben wird, ist nicht
markiert: Sie hat entschieden, es zu veröffentlichen. Lehnt sie ab, sieht das Modell
die Ablehnung. Ins eigene Gespräch allein mit dem Agenten braucht es keine Freigabe;
was dort steht, ist markiert. Ebenso wenig in einen Bereich, den außer ihr niemand
liest (ihr persönlicher Bereich oder ein Bereich, in dem sie allein Mitglied ist; ein
Admin, der kraft Adminrecht hineinsieht, wird auditiert): Ein Gedächtnis, ein Ticket
oder eine Seite dort schreibt der Lauf ohne Freigabe (Review M8 3, Befund H7). Wer
später weitere Personen in einen solchen Bereich holt, entscheidet selbst darüber,
was sie dort lesen. Zurückgehalten bleiben die eigene Antwort des Laufs und
`ask_user`, wo andere mitlesen (Kanal, Thread einer Seite oder eines Tickets,
Direktnachricht mit mehreren): Der Lauf endet dann statt mit seiner Antwort mit
`policy_blocked` (`personal_connector`, im Halt-Ereignis und im Hinweis des Gesprächs,
`system.stop_detail`: die Person liest dort, dass er ihr in ihrer Direktnachricht allein
mit dem Agenten antwortet und ihr vorlegt, was er von dort anderswo schreiben will).
Externe Aufrufe folgen der Regel unten (Freigabe je Aufruf, an einen anderen Server
ebenso). Die Entwurfsmarke lehnt weiter ab, auch unter der persönlichen Marke.
Gefragt wird erst, wenn nichts anderes den Aufruf ablehnt (Review M8 3, Befund H3):
Entwurfsmarke, Leck in einen anderen Bereich, ein für KI geschlossener Bereich und die
eigenen Ablehnungen des Werkzeugs (etwa ein unbekanntes Eltern-Ticket oder Gedächtnis
aus der Direktnachricht in einen geteilten Bereich) kommen zuerst; die Freigabe wird
unmittelbar vor dem Schreiben verlangt (`writing.effect`). So wird sie nie um etwas
gebeten, das ohnehin abgelehnt würde.

Die Marke folgt dem Inhalt und ist gespeichert, nie nur im Gedächtnis eines Workers
(Review M8 2, Befund G1; `agents/personal_mark.py`):

- **Persönliche Inhalte** sind ein Ergebnis des eigenen Konnektors und jede Nachricht,
  die ein markierter Lauf schreibt (Antwort, `post_message` ins eigene Gespräch,
  Rückfrage): Sie trägt `message.personal` (in der API `personal: true`). Solche
  Nachrichten gibt es nur in der Direktnachricht allein mit dem Agenten.
- **Markiert wird ein Lauf**, sobald persönlicher Inhalt in seinen Kontext kommt, und
  dieser Moment steht sofort im Journal: das Ergebnis des eigenen Konnektors
  (`read.personal`), eine markierte Nachricht im Verlaufsfenster, das er zu Beginn
  bekommt (ein eigenes Journalereignis `mark` vor dem ersten Modellaufruf; das Modell
  erfährt in seinen Anweisungen, dass der Verlauf Persönliches enthält, das es in
  diesem Lauf nicht selbst gelesen hat), ein Treffer von `search_past_runs` aus einem
  markierten Lauf (Worte wie Werkzeugergebnisse; nur allein mit dem Agenten zu finden,
  im Kanal oder Thread nie) und eine markierte Nachricht, die `read_conversation`
  zurückgibt (beide mit `read.personal` am Aufruf, die Zeile beginnt mit
  `(personal)`). Fortsetzung nach Verlust des Workers, nach einer Rückfrage oder einer
  Freigabe liest die Marke aus dem Journal.
- **Was das Modell erfährt**: Ein Lauf, den sein Verlauf markiert, bekommt in seinen
  Anweisungen, dass frühere Nachrichten persönlich sind und dass er selbst in diesem
  Lauf nichts dergleichen gelesen hat, außer ein Werkzeugergebnis sagt es; was er
  anderswo schreiben will, wartet auf ihre Freigabe genau dieses Textes. Wer
  `read_conversation` oder `search_past_runs` aufrufen darf, erfährt in seinen
  Anweisungen außerdem, was eine Zeile mit `(personal)` am Anfang bedeutet: Gelesenes
  über den eigenen Zugang der Person, nur für sie, und was er danach anderswo schreibt,
  wartet auf ihre Freigabe (Review M8 3, Befund H4). Ein
  abgelehnter Rückfrage- oder Antwortversuch nennt den Grund („others read along
  here“).
- **Was die Person sieht**: In ihrer Direktnachricht trägt eine markierte Nachricht das
  Abzeichen „Persönlich“; ein Klick erklärt, was es heißt und wann der Agent vorher
  fragt. Die Freigabekarte unter der Marke sagt, dass genau der gezeigte Inhalt
  geschrieben wird und danach nicht mehr markiert ist, und zeigt ihn vollständig und
  aufgeklappt: alle Angaben des Aufrufs und bei einer Seitenänderung den ganzen
  Vergleich, ohne Knopf zum Öffnen (Review M8 3, Befund H5). Was sich so nicht
  vollständig zeigen lässt (ein Vergleich über `HERD_DIFF_MAX_LINES`), kann sie nicht
  freigeben: Der Aufruf wird abgelehnt, bevor eine Karte entsteht (das Modell liest
  `Refused (personal_release.too_large)`, die Laufansicht sagt es ihr in Worten), und
  eine schon gestellte Freigabe, die inzwischen zu groß ist (die Grenze wurde
  gesenkt), lässt sich nur noch ablehnen (409 `approval.not_shown_in_full`).
- **Sie endet**, wenn kein persönlicher Inhalt im Kontext ist: Ein Lauf, dessen
  Verlaufsfenster und Werkzeugergebnisse nichts Markiertes enthalten, beginnt und
  bleibt ohne Marke. Weil jede Antwort eines markierten Laufs selbst markiert ist,
  hält sich die Marke in einer laufenden Direktnachricht, solange markierte Antworten
  im Verlaufsfenster stehen (24.000 Zeichen, die neuesten zuerst).
  Das ist so gewollt: Nichts nimmt die Marke von selbst wieder ab (keine Heuristik).
  Der Ausweg ist ihre ausdrückliche Entscheidung (Review M8 3, Befund H2).
- **„Neu beginnen“**: In ihrer Direktnachricht allein mit dem Agenten (eine Person, ein
  Agent) steht oben im Gespräch „Neu beginnen“. Nach einer Rückfrage, die sagt, was es
  bewirkt, setzt es einen Schnitt (`conversation.fresh_start_at`): Läufe danach bekommen
  keinen Verlauf von vor dem Schnitt, weder im Verlaufsfenster noch über
  `read_conversation`; ohne Markiertes im Kontext beginnen sie ohne Marke. Offene Läufe
  des Gesprächs (wartend, laufend, auf Freigabe oder Antwort wartend; nicht die einer
  Automation) werden vorher abgebrochen, damit keiner, der mit dem alten Verlauf
  begonnen hat, nach dem Schnitt antwortet. Die Nachrichten davor bleiben, wie sie sind,
  markierte auch, und sie sieht sie weiter; im Gespräch zeigt eine Linie „Neu begonnen am
  …“, wo der Schnitt liegt. Das Abzeichen „Persönlich“ und die Freigabekarte unter der
  Marke nennen diesen Weg. Frühere markierte Läufe bleiben markiert: Ein Treffer von
  `search_past_runs` aus einem von ihnen markiert auch nach dem Schnitt.
  API: `POST /api/conversations/{id}/fresh-start` mit `{"version": n}` (die gelesene
  Version des Gesprächs) → das Gespräch mit `fresh_start_at` und neuer Version. Wer das
  Gespräch nicht sieht, bekommt 404 `conversation.not_found`; in jedem anderen Gespräch
  (Kanal, Thread, Direktnachricht mit mehreren oder mit einer Person) 403
  `conversation.not_alone_with_agent`; eine veraltete Version 409
  `conversation.version_conflict`. Audit `conversation.fresh_start` mit der Zahl der
  abgebrochenen Läufe (`cancelled_runs`), nie Inhalt. Ein Live-Ereignis gibt es dafür
  nicht: Andere Tabs derselben Person zeigen die Linie nach dem nächsten Laden.
- **Ein markierter Lauf gehört der fragenden Person** (Review M8 3, Befund H1): In der
  Laufansicht (`/api/runs/{id}/events`) sieht jede andere Person (die verantwortliche,
  wer `agent.manage` hat, ein Admin) **jedes** Ereignis eines Laufs, der die Marke trägt,
  geschwärzt, vom ersten an, nicht erst ab der Marke, gleich aus welchen Bereichen es
  kam: Werkzeugname, Quelle und Dauer bleiben, Text und Angaben nicht. Ebenso ist ein
  Ergebnis von `search_past_runs` mit einem Treffer aus einem markierten Lauf nur ihres
  (`asker_only`), und der suchende Lauf ist dadurch selbst markiert. Eine Vorschau, die
  nichts ändert (`update_page` ohne Token), läuft unter der Marke ohne Freigabe, aber nie
  als freigegebener Aufruf: Sie schreibt nichts (ein Schreiben ohne Freigabe lehnt
  `effect` mit „Not without the person's release“ ab), und ihre Ausgabe sieht nur sie.
- **Wer markierte Nachrichten liest**: wer die Direktnachricht liest, also die Person.
  Die Nachrichtensuche findet ohnehin nur Nachrichten von Personen, die Laufansicht
  zeigt anderen weder die Worte des Modells noch Ergebnisse ohne Bereich, `/mcp` hat
  kein Werkzeug, das Nachrichten oder Läufe liest, und die Einsicht eines Admins in
  die Direktnachricht zeigt eine markierte Nachricht mit Platz, Verfasser und Marke,
  aber ohne Text.

Ergebnisse über einen geteilten Konnektor, Fehler und ein Aufruf mit unbekanntem
Ausgang setzen keine Marke. Schreibende externe Werkzeuge prüft weder diese
noch die Entwurfsmarke: Sie warten immer auf die Freigabe der fragenden Person über
genau diese Argumente. Mit der Marke gilt das auch für jedes **lesende** externe
Werkzeug eines Servers, den der Lauf nicht über den eigenen Konnektor dieser Person
nutzt (geteilter Konnektor oder keiner): Seine Argumente verlassen das System und
können tragen, was nur sie lesen darf; sie gibt genau diese Argumente frei (in Läufen
von Automationen und Ereignisregeln die Eigentümerin). Review M8 1, Befund 3.

Beispiele:

- Anna fragt Hilda in einer Direktnachricht zu zweit. Hilda liest Annas Team-Bereich
  „Vertrieb“, wenn sie dort Mitglied ist, und kann in „Vertrieb“ vorschlagen.
- Anna erwähnt Hilda im Kanal von „Marketing“. Hilda liest nur „Marketing“ und die
  offenen Bereiche, nicht „Vertrieb“, auch wenn Anna und Hilda beide dort sind: Im
  Kanal lesen Leute mit, die „Vertrieb“ nicht sehen.
- Ist in „Marketing“ ein Gast Mitglied, liest Hilda dort auch keine offenen Bereiche
  (Gäste lesen keine offenen Bereiche).
- Hat Hilda in einem Lauf „Vertrieb“ gelesen (auch über ihr Gedächtnis dort), schreibt
  sie in diesem Lauf nichts in einen Bereich, dessen Publikum „Vertrieb“ nicht sieht:
  kein Vorschlag, kein Kommentar, kein Gedächtnis dort (Antwort „Not allowed: what you
  have read in this run …“).

Das wird vor jedem Modell- und Werkzeugaufruf neu bestimmt; wer Rechte oder `ai.use`
verliert, beendet den Lauf (`rights_revoked`), ebenso ein pausierter Agent oder eine
deaktivierte verantwortliche Person. Admins sind nicht ausgenommen: Fragt ein Admin
einen Agenten, liest der Lauf mit den Rollen des Agenten, nicht mit dem Admin-Recht.
Die eine Rechteprüfung (`core/access.py`) wendet Lese- und Schreibbereich auf jeden
Akteur an, ohne Agenten zu kennen (`agents/scope.py` berechnet sie).

### Ein offener Lauf je Thread

Höchstens ein Lauf ist je „Bahn“ offen (in der Warteschlange, laufend oder wartend). Die
Bahn ist in einem Kanal der Thread der erwähnenden Nachricht (eine Erwähnung auf
oberster Ebene beginnt ihren eigenen Thread), in einer Direktnachricht das Gespräch, in
einer Seiten-Diskussion die Seite, in einer Ticket-Diskussion das Ticket (Zuweisung,
Übergabe und Erwähnungen dort teilen sich die Bahn). Ein Lauf, der in einem Kanal-Thread
auf eine Freigabe wartet, hält also nur diesen Thread. Die Datenbank sichert das mit
eindeutigen Teilindizes über `COALESCE(lane_id, conversation_id)` (je Bahn ein laufender
und ein aktiver Lauf, einer in der Warteschlange je Bahn und Agent: der Lauf nach einer
Übergabe steht hinter dem übergebenden; wird dieser nach einer Freigabe wieder
eingereiht, bleibt der übergebene Lauf erhalten und folgt ihm). In einem Kanal ist
`run.lane_id` die Wurzel des Threads; Erwähnungen in anderen Threads desselben Kanals
laufen zugleich (jeweils bis zur `max_concurrency` der Verbindung). Eine Advisory-Sperre ist dafür nicht nötig
(die Indizes halten über Worker und Abstürze hinweg); nur das Beanspruchen von Läufen
serialisiert sich auf einer Sperre je Transaktion.

### Persönliche Agenten (Verwaltung)

Ein persönlicher Agent gehört einer Person (`owner_user_id`).

- **Recht** `agent.create_personal`: abgeleitet wie `ai.use`, nie gespeichert: wer
  `ai.use` hat, solange die Organisation persönliche Agenten erlaubt. `/api/auth/me`
  nennt es in `permissions`.
- **Schalter**: `PUT /api/ai/assignments/personal-agents` (`ai.manage`, Körper
  `{"enabled": false, "version": n}` mit der Version aus `GET /api/ai/assignments`, die
  auch Standard- und Gruppenzuordnung schützt; 409 bei veralteter Version; Audit
  `ai_assignment.personal_agents_set`). `GET /api/ai/assignments` nennt den Stand in
  `personal_agents` (Voreinstellung: an). Aus: niemand legt neue an, und bestehende
  persönliche Agenten antworten nicht mehr (`agent.personal_disabled`).
- **Anlegen**: `POST /api/agents` mit `{"name": …, "personal": true}`. Ohne `ai.use`
  404 `agent.not_found`; mit `ai.use`, aber abgeschaltet, 403
  `agent.personal_disabled`. Verbindung und Modell sind die der Person (ihre
  Zuordnung); gibt man sie an, müssen es diese sein (422 `ai.connection_not_found`,
  `ai.model_unknown`). Verantwortlich ist die Besitzerin selbst (eine andere Person:
  422 `agent.responsible_invalid`). Höchstens Stufe 2 (403 `agent.level_denied`, auch
  für Admins). Höchstens `HERD_AI_PERSONAL_AGENTS_MAX` (Standard 5, 0 bis 100) je
  Person (409 `agent.personal_limit`; gezählt unter einer Sperre je Person, zwei
  gleichzeitige Anlagen überschreiten die Grenze nicht).
- **Bereiche**: Der Agent ist ab der Anlage Mitglied (`editor`) im persönlichen
  Bereich seiner Besitzerin und nur dort. Jeder Versuch, ihn einem anderen Bereich
  hinzuzufügen, scheitert mit 422 `agent.personal_space_only`, auch für Admins und die
  Besitzerin; wer den Agenten nicht sehen darf, bekommt 404 `agent.not_found`.
- **Verwalten**: Die Besitzerin (mit `ai.use`) liest, ändert, pausiert und löscht ihre
  Agenten (Löschen nur ungenutzt, sonst 409 `agent.in_use`) und setzt ihre
  Werkzeugfreigaben, über dieselben Endpunkte wie `agent.manage`, mit `version` (409).
  Jede Änderung übernimmt Verbindung und Modell neu aus ihrer Zuordnung. Ein Lauf nimmt
  Verbindung und Modell der Besitzerin so, wie ihre Zuordnung beim Start des Laufs ist:
  Ändert ein Admin ihre Zuordnung (persönlich, über eine Gruppe oder den Standard),
  schreibt dieselbe Transaktion ihre neue Verbindung und ihr neues Modell an ihre
  persönlichen Agenten; schon der nächste Lauf arbeitet damit (ein laufender Lauf
  bleibt bei seiner). So zählt `max_concurrency` bei der Verbindung, die der Agent
  wirklich nutzt, und die alte Verbindung lässt sich löschen, sobald sie sonst niemand
  nutzt. Hat sie keine KI mehr, bleibt gespeichert, was war, und es startet kein Lauf
  (`ai.unavailable`).
- **Reden**: Nur die Besitzerin erreicht ihn: Direktnachricht, Profil, Verzeichnis und
  Erwähnungen verbergen ihn vor allen anderen, auch vor Admins (404
  `agent.not_found`). Läufe fragen daher immer als Besitzerin, ihre Rechte gelten, der
  Verbrauch wird ihr gebucht. Ein Lauf für jemand anderen (spätere Auslöser) startet
  nicht (`agent.not_found`) oder endet vor dem ersten Aufruf (`rights_revoked`).
- **Ende**: Verliert die Besitzerin `ai.use` (`ai.unavailable`), wird sie deaktiviert
  (`agent.responsible_inactive`) oder schaltet die Organisation persönliche Agenten ab
  (`agent.personal_disabled`), startet kein Lauf mehr, und ein laufender endet mit
  `rights_revoked`. Personen werden nicht gelöscht, nur deaktiviert; ein persönlicher
  Agent bleibt dann bestehen, aber unbenutzbar.
- **Admins** sehen in der Verwaltung (`GET /api/agents`, `GET /api/agents/{id}`,
  `GET /api/agents/{id}/runs`) jeden Agenten mit seinen Anweisungen („Admins dürfen
  alles sehen“); dass sie einen persönlichen Agenten einer anderen Person gezeigt
  bekamen, steht im Audit (`agent.admin_access`, einmal je Admin, Agent und UTC-Tag).

### Aufgaben verwalten (seit M7)

**Wer sieht eine Aufgabe:** wer `agent.manage` hat, alle der Organisation; sonst nur mit
`ai.use`, und dann die eigenen, die der Agenten, für die man verantwortlich ist, und die
mit einem Ort in einem Bereich, den man verwaltet (`space.manage`). Dieselbe Regel
(`automations/sight.py`) gilt für die API, die Live-Ereignisse und die Aktivitäten zu
einer Aufgabe. Was man nicht sieht, antwortet wie eine unbekannte ID (404).

**Was man von ihr liest:** den Auftrag, den Namen des Kanals und die Nummer des Tickets
nur, wem sie gehört, und wer ihren Ort jetzt lesen darf (Kanal oder Ticket nach den
Regeln der Unterhaltung; eine Direktnachricht nur ihre Person). Alle anderen, die sie
sehen (etwa die verantwortliche Person des Agenten außerhalb des Bereichs oder
`agent.manage`), bekommen diese Felder leer und `redacted: true`, in der Ansicht und in
den Listen; die Oberfläche sagt das in Worten. Wer den Ort nur mit Admin-Recht liest,
liest ihn ganz und wird vermerkt (`space.admin_access`, wie beim Lesen des Bereichs).

| Aktion | wer |
|---|---|
| anlegen | wer `ai.use` hat, den Agenten erreicht und am Ort schreiben darf; im Kanal und am Ticket muss der Agent Mitglied des Bereichs sein; Ereignis-Regeln nur, wer den Bereich verwaltet; persönliche Agenten nur ihre Eigentümerin, in ihrer Direktnachricht oder ihrem persönlichen Bereich |
| ändern, jetzt ausführen | nur die Eigentümerin (wer ändert, verantwortet den Auftrag), solange sie die Aufgabe selbst anlegen dürfte |
| anhalten, fortsetzen, löschen | die Eigentümerin, die Verwaltenden des Bereichs ihres Ortes, `agent.manage` |
| übernehmen | wer sie sieht und sie selbst anlegen dürfte (eine Ereignis-Regel also nur, wer den Bereich verwaltet) |
| ansehen, Protokoll | wer sie sieht |

Wer sie sieht, aber die Aktion nicht darf (etwa die verantwortliche Person des Agenten),
bekommt 403 `automation.not_allowed`; die Oberfläche bietet nur an, was die Antwort in
`abilities` nennt. Fortsetzen geht nur, solange die Eigentümerin die Aufgabe wieder
ausführen dürfte; sonst bleibt nur die Übernahme.

**Obergrenze:** höchstens `HERD_AI_AUTOMATIONS_MAX` (Standard 20, 0 bis 1.000) aktive
oder angehaltene Aufgaben je Eigentümerin; erledigte und gelöschte zählen nicht. Die
Grenze gilt auch, wenn eine erledigte einmalige Aufgabe einen neuen Zeitpunkt bekommt
(sie ist dann wieder aktiv) und bei der Übernahme (409 `automation.limit`). Wer im Bereich nur
liest, aber `ai.use` hat und den Agenten erreicht, kann bis zu dieser Grenze Aufgaben
in jeden Kanal legen, in dem der Agent Mitglied ist; die Verwaltenden des Bereichs
sehen, halten an und löschen sie.
**Budgets** begrenzen den Verbrauch je Tag für die Organisation, eine Person oder einen
Agenten ([`KI.md`](KI.md#budgets-apiaibudgets-aimanage)); Aufgaben haben kein eigenes
Budget, ihr Verbrauch zählt bei ihrer Eigentümerin und ihrem Agenten.

### Skills verwalten (`/api/skills`)

Ein Skill ist eine Anleitung im Format SKILL.md (agentskills.io): YAML-Kopf zwischen
zwei `---`-Zeilen mit `name` (1 bis 64 Zeichen: Kleinbuchstaben, Ziffern, einzelne
Bindestriche, nicht am Rand) und `description` (1 bis 1.024 Zeichen), danach die
Anweisungen in Markdown (höchstens 50.000 Zeichen). **Ein Skill ist Text: nichts darin
wird je ausgeführt**, auch keine Skripte (es gibt in v1 kein Werkzeug, das Code
ausführt). Ein Agent sieht im Kontext nur Name und Beschreibung seiner Skills; den Text
holt er mit `load_skill`.

- **Geltungsbereich:** organisationsweit oder einem Bereich zugeordnet; der Name ist
  je Organisation und Geltungsbereich eindeutig (409 `skill.name_taken`, archivierte
  eingeschlossen).
- **Rechte:** Skills gibt es nur für Personen mit `ai.use` oder `skill.manage`; für
  alle anderen antwortet jeder Skill-Pfad 404 `skill.not_found` wie für eine
  unbekannte ID. Organisationsweite Skills lesen alle mit `ai.use`, Skills eines
  Bereichs alle, die den Bereich lesen. Organisationsweite Skills verwaltet, wer
  `skill.manage` hat (Admins), Skills eines Bereichs die Moderatoren des Bereichs
  (`page.moderate`) oder `skill.manage`; wer einen Skill sieht, aber nicht verwalten
  darf, bekommt 403 `auth.permission_denied`.
- `GET /api/skills` (nach Name, Filter `space_id`, `org_wide`, `state`, `q` für einen
  Teil des Namens; seitenweise), `POST /api/skills`, `GET/PATCH /api/skills/{id}`,
  `POST /api/skills/{id}/archive` und `/unarchive` (kein Löschen; 409
  `skill.state_conflict`). Schreiben mit `version` (409 `skill.version_conflict`);
  Eingaben 422 `skill.name_invalid`, `skill.description_invalid`,
  `skill.content_invalid`.
- **Versionen:** jede Änderung von Beschreibung oder Text ist eine Version (die erste
  beim Anlegen; Umbenennen nicht). `GET /api/skills/{id}/versions`,
  `GET …/versions/{n}`, `POST …/versions/{n}/restore` (eine neue Version mit dem alten
  Stand; 404 `skill.version_not_found`).
- **Export und Import:** `GET /api/skills/{id}/export` liefert die SKILL.md.
  `POST /api/skills/import` (optional `?space_id=`) nimmt eine SKILL.md oder ein ZIP
  mit einem oder mehreren Skill-Ordnern (je Ordner eine `SKILL.md`, deren `name` dem
  Ordnernamen gleicht; höchstens vier Pfadteile tief, 100 Skills, 10 MB). Der Kopf
  wird streng geprüft (nur die Felder des Formats; `license`, `compatibility`,
  `metadata` und `allowed-tools` werden angenommen, aber nicht übernommen und als
  `ignored_fields` gemeldet). Das ZIP wird wie beim Wiki-Import gelesen (Grenzen für
  Einträge, entpackte Größe, keine Pfadtricks, kein zip64). Andere Dateien eines
  Ordners werden nicht übernommen (`file_unsupported`): ein Skill besteht hier nur aus
  seiner SKILL.md. Die Antwort nennt je Skill, was angelegt wurde und warum nicht
  (`exists`, `duplicate`, `name_mismatch`, `frontmatter_invalid`, `too_large`, …).
- **Agenten:** `GET/PUT /api/agents/{id}/skills` (`agent.manage`) zeigt und ersetzt die
  Skills eines Agenten (höchstens 50, mit der `version` des Agenten). Zuweisbar sind
  organisationsweite Skills und Skills eines Bereichs, den der Agent liest (422
  `agent.skill_not_assignable`); zwei Skills gleichen Namens 422
  `agent.skill_names_clash`. Ob ein Lauf einen Skill nutzen darf, entscheidet sich
  beim Nutzen: zugewiesen, aktiv, organisationsweit oder in einem Bereich, den der
  Lauf liest (Rechte der Person, des Agenten und Publikum des Ortes), und die
  KI-Richtlinie dieses Bereichs lässt die Verbindung des Laufs zu. Verlässt ein Agent
  einen Bereich, bleibt die Zuweisung stehen, wirkt aber nicht (`available: false`).
- Audit: `skill.created`, `skill.updated`, `skill.restored`, `skill.archived`,
  `skill.unarchived`, `skill.imported`, `agent.skills_changed`, mit Namen, Längen und
  Nummern, nie mit Beschreibung oder Text.

#### Skills im Lauf

`backend/app/modules/agents/toolbox/skill_tools.py`, `agents/briefing.py`.

- **Im Kontext** stehen nach den Anweisungen des Agenten Name und Beschreibung der
  Skills, die der Lauf nutzen darf (Regel oben), nach Name, höchstens 25, jede
  Beschreibung auf 300 Zeichen gekürzt, gerahmt wie ein Werkzeugergebnis; sind es mehr,
  sagt eine Zeile, wie viele fehlen. Der Text eines Skills steht nie im Kontext. Bei
  jeder Wiederaufnahme wird die Liste neu bestimmt.
- **`load_skill(name, part)`** (Stufe 1, lesend) liefert den Text, gerahmt wie jedes
  Werkzeugergebnis; der Bereich des Skills ist die Quelle des Ergebnisses (Richtlinie
  und Rechte vor jedem weiteren Modellaufruf, Laufansicht, `search_past_runs`),
  organisationsweite Skills haben keine. Was der Lauf nicht nutzen darf, ist „nicht
  gefunden“.
- **Teile statt längerem Schnitt**: Ein Ergebnis wird im Prompt bei 8.000 Zeichen
  gekürzt; ein Skill hat bis zu 50.000. Statt Skills einen größeren Schnitt zu geben
  (ein Skill nähme dann jedem weiteren Aufruf viel Platz), kommt der Text in Teilen zu
  höchstens 7.000 Zeichen, möglichst am Zeilenende geschnitten; jeder Teil außer dem
  letzten endet mit `[part n of m: call load_skill with part=n+1 for the rest]`, der
  Schnitt ist also sichtbar und der Rest einen Aufruf entfernt.
- Ein Skill ist Anleitung der Organisation, für den Lauf aber Daten: Er kann kein
  Werkzeug freischalten, keine Stufe ändern und nichts freigeben; das entscheidet der
  Host vor jedem Aufruf (getestet mit einem Skill, der genau das behauptet).

#### Skill-Vorschläge (`propose_skill`, `/api/skill-proposals`)

`backend/app/modules/skills/proposals.py` (Regeln), `proposal_decisions.py`
(Annehmen, Ablehnen), `sight.py` (wer was sieht), Werkzeug in
`agents/toolbox/skill_tools.py`.

- **`propose_skill(kind, name, space_id, description, content, reason)`** (Stufe 2,
  vorschlagend): `kind=change` für einen der Skills, die der Lauf nutzen darf (nach
  seinem Namen in der Liste), `kind=new` für einen neuen Skill in `space_id` (ohne:
  organisationsweit). Ein Vorschlag in einem Bereich braucht `page.edit` dort für den
  Lauf (also nur innerhalb seines Schreibbereichs) und nur, was das Publikum des
  Bereichs sehen darf (wie bei jedem schreibenden Werkzeug); ein organisationsweiter
  Vorschlag nur, was aus offenen Bereichen stammt (alle mit KI lesen ihn später).
  Wirkung und Journaleintrag in einer Transaktion (Wiedergabe schreibt nichts
  doppelt). Fehler: „nicht gefunden“, `skill.name_taken`, `skill.name_invalid`,
  `skill.description_invalid`, `skill.content_invalid`, `skill_proposal.no_change`,
  `skill_proposal.skill_archived`, `skill_proposal.invalid_reason`.
- **Tabelle `skill_proposal`**: Art (`change|new`), Bereich (leer: organisationsweit),
  Skill (bei `new` erst nach dem Annehmen), Name (nur `new`), `base_number` (neueste
  Version des Skills beim Vorschlag, nur `change`), Beschreibung, Text, Begründung
  (≤ 300), Urheber (Principal) mit `run_id`, Zustand `open|accepted|rejected`,
  entschieden von, wann, Ablehnungsgrund, die erzeugte Skill-Version, `version`.
- **Sehen**: wer ihn entscheiden darf (`skill.manage`; bei einem Bereich auch
  `page.moderate` dort, mit `ai.use`) und sein Urheber, solange er den Bereich lesen
  darf; ohne `ai.use` und `skill.manage` niemand. Alles andere antwortet 404
  `skill_proposal.not_found` wie eine unbekannte ID (die Liste ohne KI: 404
  `skill.not_found`).
- **Endpunkte**: `GET /api/skill-proposals?space_id=&org_wide=&state=&limit=&cursor=`
  (neueste zuerst, `space_id` eines unlesbaren Bereichs: 404 `space.not_found`),
  `GET /api/skill-proposals/{id}` (mit `proposed`, bei `change` dem Skill jetzt als
  `current` mit `version` und `number` und `outdated`), `POST …/accept`
  `{version, description?, content?, skill_version?}`, `POST …/reject`
  `{version, reason?}`. Entscheiden: 403 ohne das Recht (ein Lauf entscheidet nie),
  409 `skill_proposal.not_open`, `skill_proposal.version_conflict`.
- **Basis**: Hat der Skill seit dem Vorschlag eine neuere Version, antwortet `accept`
  409 `skill_proposal.base_outdated` mit `details = {skill_version, current:
  {description, content}, proposed: {description, content}}` und schreibt nichts. Die
  Moderatorin nimmt erneut an, mit `skill_version` und, wo gewünscht, dem endgültigen
  Text; ist der Skill inzwischen wieder anders, wieder 409.
- **Annehmen** erzeugt die Skill-Version über die Skill-Dienste (Audit wie dort): mit
  dem Agenten als Urheber, wenn der Text wie vorgeschlagen bleibt, sonst mit der
  Moderatorin (wie bei Seitenvorschlägen); ein neuer Skill entsteht im Bereich des
  Vorschlags. Ein archivierter Skill nimmt nichts an (409
  `skill_proposal.skill_archived`), ein inzwischen vergebener Name 409
  `skill.name_taken`.
- **Aktivität** (Grund `skill_proposal`, an den Vorschlag gebunden: `skill_proposal`
  `{id, space_id}` in `/api/activity`, kein Gespräch): beim Vorschlag für die
  Moderatoren des Bereichs nach Mitgliedschaft bzw. für Owner und Admins bei
  organisationsweiten, beim Entscheiden für einen Urheber, der eine Person ist. Sie
  steht nur, solange die Person den Vorschlag sieht (dieselbe Regel; wer die
  Moderation verliert, verliert den Eintrag).
- **Live**: `skill_proposal.changed` mit `proposal_id`, je Person (wer entscheiden
  darf, der Urheber), bei jedem Ereignis. Ereignisse `skill_proposal.created|
  accepted|rejected` tragen nur IDs.

**Seitenvorschläge** (`modules/proposals`): sichtbar für alle, die im Bereich Seiten
bearbeiten dürfen (`page.edit`, strenger als Lesen: ein Vorschlag zeigt unveröffentlichte
Inhalte und frühere Stände), und für den Urheber; entscheiden mit `page.moderate`. Die
Regel beim Annehmen: Gleicht die Seite noch dem Stand, auf dem der Vorschlag beruht
(Inhalt verglichen, nicht die Nummer), wird er übernommen; sonst 409
`proposal.base_outdated` mit einem Drei-Wege-Abgleich, und die Moderatorin bestätigt den
zusammengeführten Text ausdrücklich. Endpunkte und Codes in
[`WIKI.md`](WIKI.md#vorschläge-seit-m6).

### Gedächtnis (Einzelheiten)

`backend/app/modules/agents/memory.py` (Regeln), `memory_repository.py`, Werkzeug in
`agents/toolbox/memory_tools.py`, Kontext über `agents/briefing.py`.

- **Eine normale Wiki-Seite je Agent und Bereich** unter
  `_agenten/<agent>/gedaechtnis` (Titel „Gedächtnis“, darüber die Ordner „Agenten“ mit
  dem Slug `_agenten` und der Name des Agenten). Sie hat die Rechte des Bereichs,
  Versionen, Generationen und das Live-Bearbeiten wie jede Seite; Menschen korrigieren
  sie im Editor. Welche Seite es ist, steht in der Tabelle `agent_memory` (Agent,
  Bereich, Seite; Fremdschlüssel mit `CASCADE`): Umbenennen oder Verschieben der Seite
  oder des Agenten ändert nichts. Eine Seite im Papierkorb (oder, falls es je einen Weg
  gäbe, in einem anderen Bereich) gilt nicht mehr; das nächste `update_memory` legt
  eine neue an. Zwei Agenten mit gleichem Namen teilen sich den Ordner, die zweite
  Seite heißt dann `gedaechtnis-2`.
- **`update_memory(space_id, content)`** (Stufe 2, schreibend, direkt erlaubt, auch
  wenn der Bereich Änderungen von Agenten nur als Vorschlag annimmt): ersetzt den
  ganzen Text. Das erste Mal legt es die fehlenden Ordner und die Seite an,
  veröffentlicht (unter der Baumsperre des Bereichs), danach eine neue Version. Jede
  Version trägt Quelle `agent`, den Agenten als Urheber und die `run_id` (KI-Kennzeichen
  wie bei `update_page`). Nur wo der Lauf `page.edit` hat (Rechte der Person ∩ Rolle
  des Agenten ∩ Schreibbereich des Ortes; sonst „Not allowed here.“, ein unlesbarer
  Bereich „nicht gefunden“), nur was das Publikum des Bereichs sehen darf (wie jedes
  schreibende Werkzeug), nie auf einer für KI gesperrten Seite (403 `memory.locked`,
  geprüft unter der Zeilensperre der Seite), höchstens 8.000 Zeichen (sonst
  `memory.too_long` mit der Bitte zu kürzen). Aus einer Direktnachricht allein mit dem
  Agenten nur in einen Bereich, den außer der fragenden Person niemand liest (kein
  anderes Mitglied, direkt oder über eine Gruppe, und nicht offen; Admins, die kraft
  Amtes hineinsehen, zählen nicht, ihr Blick wird protokolliert); sonst
  `memory.shared_space`, als Werkzeugfehler für das Modell. Denn was das Modell dort
  schreibt, kann Worte der Direktnachricht enthalten, die keine Prüfung als gelesen
  zählt. Aus einem Kanal oder Thread des Bereichs schreibt es wie zuvor. Die Hilfe des
  Werkzeugs sagt es dem Modell. `update_page` lehnt Gedächtnisseiten ab, damit diese
  Regel der einzige Weg bleibt. Wirkung und Journaleintrag in einer Transaktion.
- **Im Kontext** stehen nach den Skills die Gedächtnisseiten der Bereiche, die der
  Lauf lesen darf (sein Lesebereich, also auch das Publikum des Ortes) und deren
  KI-Richtlinie die Verbindung des Laufs zulässt; nicht gesperrt, im Papierkorb oder
  außerhalb ihres Bereichs. Reihenfolge: der Bereich des Ortes zuerst, dann nach
  Bereichsname. **Zusammen höchstens 4.000 Zeichen**: Jede Seite bekommt einen
  gleichen Anteil am Rest (mindestens 400, solange so viel übrig ist); was eine Seite
  nicht braucht, geht an die folgenden. Ein Schnitt endet mit
  `[… cut: the rest of this memory page is not shown]`; Seiten ohne Platz fehlen, eine
  Zeile nennt ihre Zahl. Rahmen und Überschriften kommen dazu. Jede Seite ist gerahmt
  wie ein Werkzeugergebnis (`<untrusted source="memory" space=… space_id=…
  page_id=…>`): Notizen, keine Anweisungen.
- **Gelesen**: Bereiche und Seiten des geladenen Gedächtnisses zählen als gelesen
  (Richtlinie und Rechte vor jedem Modellaufruf, Publikumsregel beim Schreiben). Folge:
  Ein Lauf im Gespräch allein mit dem Agenten, der Gedächtnis aus Team-Bereich A
  geladen hat, schreibt nichts in einen Bereich, dessen Publikum A nicht sieht, auch
  nicht in dessen Gedächtnis. Das ist gewollt: So trägt das Gedächtnis kein Wissen aus
  einem Team-Bereich in einen anderen.
- Ohne Gedächtnis sagt der Kontext nichts dazu. Bei jeder Wiederaufnahme wird es neu
  bestimmt.
- **Seitenbaum**: Der Baum (`GET /api/spaces/{id}/pages/tree`) kommt flach nach Pfad;
  Geschwister ordnet die Oberfläche nach `sort_order`. Den Ordner `_agenten` (Pfad
  `_agenten` auf oberster Ebene) stellt die Oberfläche ans Ende; der Server ordnet ihn
  nicht um.

## Betrieb

### Wie ein Lauf arbeitet

Ein Lauf entsteht in der Transaktion der auslösenden Nachricht oder Zuweisung (Zustand
`queued`). Der **Worker** (`HERD_ROLE=worker`, in `all` enthalten) beansprucht ihn
(`FOR NO KEY UPDATE SKIP LOCKED`, Sperrfrist `HERD_RUN_LEASE_SECONDS`), höchstens
`HERD_RUN_CONCURRENCY` zugleich je Worker und höchstens `max_concurrency` je Verbindung
über alle Worker, mit `requests_per_minute` je Verbindung (Fenster in der Datenbank).
Die Laufschleife (`app/runtime/loop.py`, der einzige Ort, der Pydantic AI importiert)
ruft das Modell, führt Werkzeuge über die Dienste aus und schreibt jeden Schritt fest:

- **Kontext:** Nutzer-Beiträge sind nur die Nachrichten der fragenden Person,
  Assistenten-Beiträge nur die eigenen früheren Antworten des Agenten. Nachrichten
  anderer Personen und Agenten gehen als ein Block `<untrusted source="conversation">`
  mit `<message author="…">` je Nachricht an das Modell (`<` im Text maskiert). Die
  Rahmenanweisung sagt in der Direktnachricht allein „eine Person“, sonst „mehrere lesen
  mit, nur <Name> fragt“ (`app/runtime/context.py`, `agents/place.py`).
- **Journal:** Jede Modellantwort (Text, Werkzeugaufrufe, Verbrauch) und jedes
  Werkzeugergebnis (vollständig, mit den Bereichen, aus denen es stammt) ist ein
  `run_event`. Ein **schreibendes Werkzeug schreibt seine Wirkung und seinen
  Journaleintrag in derselben Transaktion**: entweder beides oder nichts.
- **Warten:** Braucht ein Lauf eine Freigabe oder Antwort, steht er auf `waiting` bis
  `wait_until`; dabei hält er keine Sperrfrist und keinen Worker. Die Entscheidung setzt
  ihn in ihrer Transaktion wieder auf `queued`. Läuft die Zeit ab, beendet ihn die
  Laufschleife (`approval_expired` bzw. `waiting_timeout`).
- **Abbruch:** ein eigener Datensatz `run_cancel_request`, geprüft vor jedem Schritt und
  in der Transaktion des Abschlusses (Abbruch und Abschluss sperren dieselbe Zeile).
- **Stopgründe:** `completed`, `max_steps`, `deadline`, `no_progress` (dritter gleicher
  Werkzeugaufruf), `rights_revoked`, `policy_blocked`, `provider_refused` (401, 402, 403,
  429; ohne Wiederholung), `error`, `cancelled`, `waiting_timeout`, `approval_expired`,
  `budget` (ein Tagesbudget ist erreicht, siehe [KI.md](KI.md#budgets-apiaibudgets-aimanage)).
  Die Antwort ist genau eine Nachricht `kind: agent`; jeder andere Stopp steht als
  Hinweis im Gespräch bzw. Thread.
- Während eines Anbieteraufrufs hält ein Lauf weder eine Transaktion noch eine
  Datenbankverbindung. Live gehen nur IDs und der Schrittzähler (`run.progress`).
- **Grenzen eines Werkzeugschritts:** Ein Werkzeug wartet in seinem Schritt höchstens
  5 s auf eine Sperre (etwa die eines Seitenbaums während eines Imports) und eine
  Anweisung läuft höchstens 20 s, nie über die Laufzeit hinaus. Wird das überschritten,
  wird der Schritt zurückgerollt, und das Modell bekommt als Ergebnis
  `tool_timeout: …` (im Journal wie jedes Ergebnis); der Lauf geht weiter. Die Laufzeit
  (`max_runtime_seconds`) schneidet einen Werkzeugaufruf ab wie einen Modellaufruf
  (`deadline`). Dieselbe Grenze gilt für die Prüfungen vor einem Modellaufruf und das
  Festhalten danach, ab ihrer ersten Anweisung (auch für die Sperre der Zeile des
  Laufs): Wartet einer davon länger, endet der Lauf mit `error` (der Verbrauch eines
  schon gemachten Aufrufs wird nachgebucht), statt unbegrenzt zu hängen.
- **Sperrfrist und lange Schritte:** Die Erneuerung der Sperrfristen eines Workers
  überspringt Läufe, deren Zeile gerade ein Schritt dieses Workers hält (er lebt ja);
  der Schritt setzt die Sperrfrist, wenn er festschreibt. Ein langer Schritt hält so
  die übrigen Läufe des Workers nicht auf. `herd_runs_stuck` zählt einen Lauf, dessen
  Zeile gerade ein Schritt hält, nicht mit, auch wenn seine Sperrfrist schon
  abgelaufen ist (er arbeitet).
- **Verklemmung:** Wählt die Datenbank einen Schritt als Opfer eines Deadlocks oder
  scheitert er an der Serialisierung (SQLSTATE `40P01`, `40001`), wird er einmal
  wiederholt (Log `runs.step_retried`); beim zweiten Mal endet der Lauf mit `error`.

Warum kein DBOS: Ein Werkzeug und sein Journaleintrag stehen in derselben Transaktion
der Anwendungsdatenbank; damit ist jede Wirkung innerhalb der Datenbank genau einmal. Ein
Werkzeug für dauerhafte Abläufe mit eigener Zustandsablage sichert das nicht zu
(Spezifikation E10, geändert in M6). Auch die Zeitpläne der Aufgaben (M7) kommen ohne
DBOS aus: [Aufgaben im Worker](#aufgaben-im-worker-m7).

### Was bei einem Neustart des Workers passiert

- **SIGTERM** (Rollout): Der Worker beendet seine Läufe nicht, er gibt sie ab; nach Ablauf
  ihrer Sperrfrist nimmt ein Worker sie wieder auf.
- **Absturz** (SIGKILL, Knoten weg): ebenso, nach Ablauf der Sperrfrist (bei 30 s und
  Erneuerung alle 10 s also 20 bis 30 s später; gemessen 27 bis 31 s, siehe
  [Steckbrief](STECKBRIEF.md#agenten-m6)).
- **Wiederaufnahme spielt das Journal ein:** Festgeschriebene Modellantworten und
  Werkzeugergebnisse werden nicht noch einmal angefragt oder ausgeführt; der Lauf setzt
  nach dem letzten festgeschriebenen Schritt fort. Ein festgeschriebener Werkzeugaufruf
  ohne Ergebnis wird jetzt ausgeführt (seine Wirkung war nicht festgeschrieben, sonst
  stünde das Ergebnis da). Verloren geht höchstens ein Modellaufruf, dessen Antwort noch
  nicht gespeichert war: Er wird wiederholt (Kosten, keine Wirkung).
- **Externe Werkzeuge** (M8) wirken außerhalb der Datenbank, dort gibt es kein „beides
  oder nichts“. Deshalb schreibt der Lauf **vor** dem Senden einen Journaleintrag für
  den Aufruf mit dem Ergebnis `external_outcome_unknown` und schreibt ihn fest; die
  Antwort des Servers kommt danach als zweiter Eintrag für denselben Aufruf (das Journal
  nimmt den späteren). Stirbt der Worker dazwischen, findet die Wiederaufnahme nur den
  ersten: Der Aufruf wird **nicht noch einmal gesendet**, lesend wie schreibend, und das
  Modell erfährt, dass der Ausgang unbekannt ist und es im externen System nachsehen
  soll, bevor es neu aufruft. Eine Freigabe ist mit dem Senden verbraucht (`ran`).
- Was der Lauf gelesen hatte, zählt für Richtlinie und Rechte wie zuvor; er beantwortet
  das Gespräch bis zu seinem ersten Start.
- `attempt` zählt jede Aufnahme, `recoveries` nur die nach einem verlorenen Worker; nach
  der dritten solchen endet der Lauf mit `error` (Detail `attempts`).
- Ohne laufenden Worker gehen keine Läufe verloren; sie warten (`HerdRunsQueued`,
  `HerdWorkerAbsent`).

### Aufgaben im Worker (M7)

**Die Fälligkeits-Schleife.** Jeder Worker (auch in `all`, nicht Teil von `/ready`)
sieht alle 5 s nach fälligen Terminen und arbeitet ohne Pause weiter, solange er volle
Stapel (50) findet. Je Termin **eine** Transaktion: die Aufgabe mit
`FOR UPDATE SKIP LOCKED` gesperrt (die fälligste zuerst), der Lauf (`queued`, auslösende
Person = die Eigentümerin, Bahn `lane_id` = die Aufgabe) oder der Vermerk
„übersprungen“, die Zeile im Protokoll `automation_firing` und der nächste Termin.

- **Genau einmal, ohne DBOS:** Ein Termin, den ein anderer Worker gerade hält, wird
  übergangen (`SKIP LOCKED`); einer, den er inzwischen gefeuert und festgeschrieben hat,
  ist beim Sperren nicht mehr fällig (Postgres prüft die Bedingung an der neuesten
  Zeile erneut). Lauf, Protokoll und nächster Termin stehen in derselben Transaktion:
  Stürzt ein Worker vor dem Commit ab, bleibt der Termin fällig und der nächste
  Durchlauf (hier oder in einem anderen Worker) feuert ihn; nichts doppelt, nichts
  verloren. Der eindeutige Index `(automation_id, due_at)` des Protokolls sichert es
  zusätzlich. Geprüft mit drei Schleifen und echten Commits (Tests) und mit drei
  Worker-Prozessen und 1.000 zugleich fälligen Terminen ([Steckbrief](STECKBRIEF.md#automatisierung-m7)).
  Es braucht weder einen Leader noch einen Zeitplaner außerhalb der Datenbank.
- **Termine** werden aus „jetzt“ berechnet: Nach einem Ausfall läuft eine Aufgabe einmal
  nach. Zeitumstellung: Eine Ortszeit, die es nicht gibt, fällt auf den nächsten gültigen
  Zeitpunkt (02:30 → 03:00), eine doppelte läuft einmal (beim ersten Mal); stündliche
  Termine laufen in beiden doppelten Stunden, sie liegen eine echte Stunde auseinander.
  Zwei der nächsten fünf Termine näher als 15 Minuten lehnt das Speichern ab. Die Zeit
  kommt von einer Uhr (`core/clock.py`), die Tests stellen.
- **Prüfungen eines Termins**, in dieser Reihenfolge: Agent nicht aktiv →
  `skipped_paused_agent`; die Eigentümerin darf die Aufgabe nicht mehr ausführen →
  **angehalten** (`owner`; der Termin wird nicht protokolliert und bleibt fällig); der
  Agent darf aus anderem Grund nicht laufen (verantwortliche Person inaktiv, Verbindung
  nicht verfügbar, persönliche Agenten abgeschaltet) → `skipped_paused_agent`; der Ort ist
  archiviert oder seine KI-Richtlinie lässt die Verbindung nicht zu → `skipped_policy`;
  ein Tagesbudget der Eigentümerin, des Agenten oder der Organisation ist erreicht →
  `skipped_budget`; der vorige Lauf der Aufgabe ist noch offen (in der Warteschlange,
  laufend oder auf eine Antwort wartend) → `skipped_busy`. Eine einmalige Aufgabe ist nach ihrem
  Termin erledigt, auch wenn er übersprungen wurde.
- „Darf ausführen“ (`automations/standing.py`): `ai.use`; der Agent nicht im Entwurf und
  erreichbar (ein persönlicher nur für seine Eigentümerin); Direktnachricht: die
  Eigentümerin allein mit genau diesem Agenten; Kanal und Ticket-Thread: lesen,
  `channel.post` im Bereich (am Ticket dazu `ticket.read`) und der Agent Mitglied des
  Bereichs.
- Dieselbe Schleife geht in jeder Runde bis zu 20 Schritte des täglichen
  Prüfdurchlaufs der Wiki-Seiten ([`WIKI.md`](WIKI.md#prüffrist-veraltete-seiten-seit-m7))
  und löscht einmal je Minute alte Protokollzeilen ([Aufbewahrung](#aufbewahrung)).
- Sie teilt sich die Event-Loop des Workers mit der Laufschleife: Allein feuert sie einen
  Termin in rund 21 ms; während die eben gestarteten Läufe rechnen, in rund 100 ms. 1.000
  zugleich fällige Termine brauchten mit einem Worker 104 s, mit dreien 48–65 s
  (Steckbrief). Mehr Worker teilen sich die Termine.
- **Ein Termin, der sich nicht feuern lässt** (seine Transaktion scheitert, etwa an
  einem Fehler oder einer kaputten Zeile), hält keinen anderen auf: Die Schleife stellt
  die Aufgabe in einer eigenen Transaktion zurück (nächster Versuch nach 1, 2, 4 …
  Minuten, höchstens nach einer Stunde; `automation.term_errors` zählt die Fehlschläge
  in Folge, die Ansicht der Aufgabe nennt sie) und macht mit dem nächsten Termin
  weiter. Ein protokollierter Termin setzt die Zählung zurück. Im Log
  `automations.term_failed` (Aufgaben-ID und Fehlertyp), gezählt in
  `herd_automation_terms_set_aside_total`. Ebenso übergeht der Prüfdurchlauf einen
  Bereich, dessen Schritt scheitert, für den Rest der Runde (`wiki.review_step_failed`).
  Feuern, Prüfdurchlauf und Aufräumen laufen in jeder Runde, was die anderen auch tun.
- Bis zu zwei Datenbankverbindungen (Feuern, Gauges); Fehler im Log als
  `automations.pass_failed` bzw. `automations.metrics_failed` (nur der Fehlertyp).

**Der Lauf einer Aufgabe** ist ein Lauf wie jeder andere (Journal, Freigaben,
Rückfragen, Abbruch, Grenzen, Wiederaufnahme), mit diesen Besonderheiten:

- Er beginnt mit dem Auftrag als Wort der Eigentümerin, als einzigem Zug; Früheres am Ort
  bekommt er nicht mit (seine Werkzeuge lesen den Ort, als nicht vertrauenswürdige
  Angabe gerahmt). Die Anweisungen sagen, dass eine geplante Aufgabe der Eigentümerin
  fragt. Den Auftrag liest er aus seinem Termin (`automation_firing.instruction`, beim
  Feuern kopiert): Ändert die Eigentümerin den Auftrag, während der Lauf wartet oder
  wieder aufgenommen wird, arbeitet er mit dem alten weiter.
- Ort der Antwort: in der Direktnachricht oben; im Kanal ist die Wurzel des Threads je
  Termin ein Systemeintrag `automation.started` (die Eigentümerin als Akteurin, die
  Aufgabe per `automation_id`, nie der Auftragstext; die Trigger-Funktion der
  Nachrichten lässt ihn oben im Kanal nur zu, wenn er einen Termin einer Aufgabe dieses
  Kanals nennt, und er nimmt Antworten an), darin die Antwort und die Karten; im
  Ticket-Thread steht derselbe Eintrag oben und die Antwort ebenfalls oben. Der Ort der
  Antwort wird nie aus der Bahn abgeleitet.
- Freigaben und Rückfragen gehen an die Eigentümerin (`run.user_id`). Ein Lauf einer
  Aufgabe reiht nach seinem Ende keinen Folgelauf für Nachrichten ein, die währenddessen
  kamen; ebenso kein Lauf, den ein Tagesbudget gestoppt hat.
- Fehlschläge: `automation.failures` zählt Läufe in Folge, die nicht `completed` enden;
  ein abgeschlossener setzt zurück, ein abgebrochener oder von einem Budget gestoppter
  zählt nicht und setzt nicht zurück; beim dritten hält die Aufgabe an (`failing`).
  Fortsetzen und Übernehmen setzen den Zähler zurück.
- Aktivitäten zum Anhalten: Grund `automation`, gebunden an die Aufgabe
  (`notification.automation_id`; jedes Anhalten meldet sich neu), der Agent als Autor,
  kein Gespräch; `owner` an die verantwortliche Person des Agenten und die Verwaltenden
  des Bereichs (Rolle `admin` über eine Mitgliedschaft; bei einer Direktnachricht nur
  die verantwortliche Person), `failing` an die Eigentümerin. Gelistet wird ein Eintrag
  nur, solange die Person die Aufgabe noch sieht.
- Übernehmen (`POST /api/automations/{id}/take-over`): sperrt die Aufgabe, prüft
  `version` und „dürfte sie anlegen“, setzt die Eigentümerin, lässt sie wieder laufen
  (ein verpasster Termin einmal), auditiert `automation.taken_over` (von, an).

**Heartbeat.** Ein Fenster der aktiven Stunden gehört zum Wochentag, an dem es öffnet;
ist „bis“ nicht später als „von“, geht es über Mitternacht (Freitag 22:00–06:00 reicht
bis Samstagmorgen), „von“ = „bis“ ist der ganze Tag, aneinanderstoßende Tage sind ein
Fenster. Der nächste Termin liegt einen Abstand nach „jetzt“, solange er im Fenster
liegt, sonst bei der nächsten Öffnung, aber nie weniger als einen Abstand nach dem
letzten Termin, auch über den Rand eines Fensters hinweg; außerhalb entsteht keiner. Eine Öffnung, deren
Ortszeit es nicht gibt, fällt auf den nächsten gültigen Zeitpunkt; ein Fenster über die
doppelte Stunde dauert seine echten Stunden. Ein Termin, den die Schleife mehr als
15 Minuten zu spät und außerhalb der Stunden holt, wird `skipped_off_hours`. Die
Anweisungen nennen dem Modell die Regel `HEARTBEAT_OK`; eine solche Antwort (nach
Trimmen) wird nirgends zugestellt, nur `automation_firing.heartbeat_ok` vermerkt sie,
und der Lauf endet `completed`. Deshalb schreibt der Termin eines Heartbeats den
Systemeintrag `automation.started` nicht beim Feuern, sondern erst der Lauf, wenn er
etwas zuzustellen hat (Antwort, Karte, den Hinweis seines Endes).

**Ereignis-Regel.** Ein Outbox-Handler (`automation_events`) gibt jedes Ereignis der Arten
`page.published`, `ticket.created`, `attachment.uploaded` (ein Upload über die Route;
ein Import sendet keines) und `page.review_due` an die aktiven Regeln seiner Art im
Bereich des Ereignisses, je Regel gesperrt in fester Reihenfolge:

1. Ein Ereignis, das ihr eigener Lauf an einem Objekt verursacht hat, um das es in
   diesem Lauf ging, startet nichts.
2. Die Filter (`ticket.created`: Tag, Art) werden am Ticket gelesen, wie es beim
   Zustellen ist (ein Tag, das kurz nach dem Anlegen gesetzt wird, zählt vielleicht
   nicht; ein gelöschtes Tag passt auf nichts).
3. Ein Objekt, das der Lauf am Ort nicht lesen dürfte, wird nicht aufgenommen: kein
   Lauf, keine Zählung, kein Protokolleintrag (`event_sight.py`). Ist der Ort selbst
   gesperrt oder archiviert, protokolliert der Termin `skipped_policy`.
4. Jedes Ereignis wird je Regel einmal aufgenommen (`automation_event`, Schlüssel Regel +
   Ereignis): Eine zweite Zustellung bewirkt nichts.
5. **Tiefe:** Ereignisse, die ein Schritt eines Laufs verursacht, nennen den Lauf
   (`event_outbox.run_id`, gesetzt vom Schritt-Host für alles, was das Werkzeug des
   Schritts auslöst; die Schlussantwort eines Laufs ist kein Schritt). Ein Lauf daraus
   bekommt `chain_depth` + 1 (dasselbe Feld zählt Übergaben); ein Ereignis eines Laufs
   der Tiefe 3 wird `skipped_depth`. So enden auch zwei Regeln im Kreis.
6. **Ruhezeit:** Liegt der letzte Termin der Regel weniger als `quiet_seconds` zurück,
   wartet das Ereignis, und `next_due_at` wird das Ende der Ruhezeit
   (`automation.quiet_until`); dann feuert die Fälligkeits-Schleife alle wartenden als
   **einen** Termin, mit der größten Tiefe, und der Lauf erfährt Art, Anzahl und die
   IDs der neuesten 20 Objekte (`<untrusted source="event">`, ein Ticket mit
   Schlüssel), nie, wer es verursacht hat. Sonst feuert der Handler den Termin sofort
   (mit allen noch wartenden). Jeder Termin beginnt eine neue Ruhezeit; ohne wartende
   Ereignisse hat eine Regel keinen Termin und ist nie erledigt. Eine angehaltene Regel
   verpasst, was in ihrer Pause geschieht; Ereignisse, die schon warteten, behält sie.
7. **Freigabe im Lauf:** Im Lauf einer Ereignis-Regel wird jedes Werkzeug der Stufe 3,
   dessen Erlaubnis `allow` ist, wie `confirm` behandelt (`toolbox/policy.watched`,
   geprüft vom Schritt-Host bei jedem Aufruf; `Working.event_rule` aus der Art der
   Aufgabe). Die Freigabe geht an die Eigentümerin (die fragende Person des Laufs).
   Stufe 2 bleibt unverändert (Review M7, Befund 8), außer externen Werkzeugen: Auch
   ein lesendes wartet dort auf die Eigentümerin (Review M8 1, Befund 5).

Die Termine, die der Handler feuert, gehen durch dieselben Prüfungen (`term.fire`) und
zählen in derselben Metrik, sobald seine Zustellung festgeschrieben ist.

**Live.** Jede Änderung einer Aufgabe (API, Anhalten durch das System, Übernahme) und
jeder protokollierte Termin schreiben in ihrer Transaktion ein Outbox-Ereignis
`automation.updated` (nur die ID); der Handler `automation_live` macht daraus je Person,
die die Aufgabe jetzt sieht, ein SSE-Ereignis `automation.changed` (`automation_id`,
`space_id`, bei einer Direktnachricht `null`), auch für eine gelöschte. Ein Ereignis,
das in einer Ruhezeit wartet, meldet nichts.

### Aufgaben-API (M7)

Alle Routen unter `/api/automations`; Listen seitenweise (`limit` ≤ 100, `cursor`,
neueste zuerst). Jede Änderung nennt die gelesene `version` (sonst 409
`automation.version_conflict` mit `details.current_version`) und steht im Audit nur mit
IDs, Arten und Feldnamen, nie mit dem Auftragstext (`automation.created`,
`automation.updated`, `automation.paused`, `automation.resumed`, `automation.deleted`,
`automation.run_now`, `automation.taken_over`). Wer was darf:
[Aufgaben verwalten](#aufgaben-verwalten-seit-m7).

**Routen.**

- `POST /api/automations` (201): `{"agent_id", "place", "instruction", "schedule"}`.
  Ort `place`: `{"type": "dm"}` (die Direktnachricht der Person mit dem Agenten, wird
  bei Bedarf eröffnet), `{"type": "channel", "conversation_id"}` oder
  `{"type": "ticket", "ticket_number"}` (der Thread des Tickets entsteht beim
  Speichern, falls er fehlt). Auftrag 1 bis 4.000 Zeichen. Zeitplan `schedule` nach
  `kind`: `once` (`at`, Zeitpunkt mit Zone, in der Zukunft), `recurring` (`cron`,
  `time_zone`), `heartbeat` (`interval_minutes`, `active_days` 1 = Montag bis 7,
  `active_from`, `active_until`, `time_zone`), `event` (`event_type`, `quiet_seconds`
  60 bis 86.400, Standard 300, bei `ticket.created` wahlweise `filter_tag_id` und
  `filter_ticket_kind`). Höchstens `HERD_AI_AUTOMATIONS_MAX` aktive oder angehaltene
  Aufgaben je Eigentümerin (409 `automation.limit`; gezählt unter einer Sperre je
  Person).
- `POST /api/automations/preview` mit `{"schedule"}`: `{"terms": [...]}`, die nächsten
  fünf Termine (einmalig: der eine; Ereignis-Regel: keine), ohne zu speichern; mit den
  Fehlern des Anlegens.
- `GET /api/automations`: die eigenen. `GET /api/agents/{agent_id}/automations`: die
  eines Agenten (nur `agent.manage`, sonst 404 `agent.not_found`).
  `GET /api/spaces/{space_id}/automations`: die mit einem Ort im Bereich, die man sieht
  (wer den Bereich nicht lesen darf: 404 `space.not_found`). Ohne `ai.use` und ohne
  `agent.manage`: 404 `ai.not_found`.
- `GET /api/automations/{id}`: die Aufgabe mit Agent, Eigentümerin, Ort (`type`,
  `conversation_id`, `space_id`, `name`, `ticket_number`), Zeitplanfeldern,
  `next_due_at`, den nächsten fünf Terminen (`upcoming`), dem letzten Termin
  (`last_run`: Ergebnis, Lauf, dessen Zustand und Stopgrund, `heartbeat_ok`), `version`
  und `abilities` (`edit`, `pause`, `resume`, `delete`, `run`, `take_over`: was die
  fragende Person jetzt damit tun darf).
- `PATCH /api/automations/{id}` mit `{"version", "instruction"?, "schedule"?}`: Die Art
  bleibt (422 `automation.kind_immutable`); ein neuer Zeitplan berechnet den nächsten
  Termin neu, eine erledigte einmalige Aufgabe mit neuem Zeitpunkt wird wieder aktiv.
  Ein schon laufender Lauf arbeitet mit dem alten Auftrag weiter.
- `POST /api/automations/{id}/pause` und `/resume` mit `{"version"}`: anhalten nur eine
  aktive (409 `automation.not_active`), fortsetzen nur eine angehaltene (409
  `automation.not_paused`) und nur, solange die Eigentümerin sie ausführen darf (409
  `automation.owner_unable`: dann übernehmen). Fortsetzen setzt die Fehlschläge zurück
  und behält den Termin: ein verpasster läuft einmal.
- `POST /api/automations/{id}/run` (ohne Körper, ändert `version` nicht): ein Termin
  außer der Reihe mit allen Prüfungen eines fälligen (Budget, Richtlinie, Agent,
  Eigentümerin); der Zeitplan bleibt. Ist der vorige Lauf noch offen, wird der Termin
  als `skipped_busy` protokolliert, kein zweiter Lauf. Darf die Eigentümerin sie nicht
  mehr ausführen, wird sie angehalten. Nicht für Ereignis-Regeln (409
  `automation.not_runnable`) und nicht für angehaltene oder erledigte (409
  `automation.not_active`). Die Antwort zeigt das Ergebnis in `last_run`.
- `POST /api/automations/{id}/take-over` mit `{"version"}`: siehe
  [Aufgaben im Worker](#aufgaben-im-worker-m7); 403 `automation.not_allowed`, wer sie
  nicht anlegen dürfte.
- `DELETE /api/automations/{id}?version=n` (204): Die Aufgabe bekommt den Zustand
  `deleted` und ist für die API und die Aktivitäten verschwunden; ihre Läufe und deren
  Journal bleiben als Geschichte, das Protokoll bis zu seiner
  [Aufbewahrungsfrist](#aufbewahrung). Ein offener Lauf wird nicht
  abgebrochen, er endet, wie er geendet hätte (abbrechen über die Laufansicht).
- `GET /api/automations/{id}/firings`: das Protokoll, je Termin `due_at`, `fired_at`,
  `outcome`, `run_id`, `heartbeat_ok`, neueste zuerst.

Fehler beim Anlegen und Ändern (422): `automation.in_the_past`, `automation.invalid_cron`,
`automation.invalid_time_zone`, `automation.too_frequent` (zwei der nächsten fünf
Termine näher als 15 Minuten), `automation.invalid_interval`, `automation.invalid_hours`,
`automation.invalid_place` (Ereignis-Regel in einer Direktnachricht),
`automation.agent_not_member` (der Agent ist nicht Mitglied des Bereichs des Ortes),
`automation.invalid_filter` (Filter außer bei `ticket.created`, ein Tag weder des
Bereichs noch systemweit); 403 `automation.not_allowed`; ein unbekannter oder nicht
erreichbarer Agent 404 `agent.not_found`, ein nicht lesbarer Kanal 404
`conversation.not_found`, ein nicht lesbares Ticket 404 `ticket.not_found`.

### Läufe im Einzelnen

Jede neue Nachricht der Person in einer solchen Direktnachricht (nicht in einem Thread)
legt in derselben Transaktion einen Lauf an. Die Antwort auf das Senden nennt ihn in
`agent_run: {"id", "reason"}`; ohne Lauf steht der Grund in `reason`:
`ai.unavailable`, `agent.paused`, `agent.draft`, `agent.responsible_inactive`,
`agent.connection_unavailable`, `agent.personal_disabled`, `run.thread_reply`,
`run.waiting` (der Lauf des
Gesprächs wartet auf eine Antwort, siehe unten); `agent_id` nennt den Agenten. Läufe
aus Erwähnungen und Ticket-Zuweisungen: siehe
[Auslöser](#auslöser-erwähnung-ticket-zuweisung-übergabe). Je Gespräch läuft höchstens
ein Lauf; Nachrichten, die währenddessen kommen, beantwortet der nächste Lauf gemeinsam
(in Kanälen gilt das je Thread, siehe [Ein offener Lauf je
Thread](#ein-offener-lauf-je-thread)).

Ein Lauf arbeitet im Worker (`backend/app/worker/runs.py`,
`backend/app/modules/agents/executor.py`, Schleife `backend/app/runtime/loop.py`):

- Er liest mit den Rechten der Person, begrenzt auf die Bereiche des Agenten
  (`read_scope`): seine Mitgliedschaften und die offenen Bereiche, und darin auf das,
  was das Publikum des Orts sehen darf, an dem er antwortet (Spec 5.6, M6;
  `backend/app/modules/agents/scope.py`; Tabelle und Beispiele unter
  [Die Publikumsregel](#die-publikumsregel-wer-liest-mit); in der Direktnachricht
  allein setzt der Ort dem Schreiben keine Grenze, es gelten nur die Rechte). Hat S einen Gast als Mitglied (direkt oder über eine Gruppe), zählen die offenen
  Bereiche nicht (Gäste lesen keine offenen Bereiche; strenger als Spec 5.6).
  Deaktivierte Teilnehmende zählen nicht; bleibt nur die fragende Person, gilt
  „allein“. Außerhalb von `write_scope` darf der Lauf lesen, was Rechte und
  `read_scope` erlauben, aber nichts schreiben (auch kein Posten, auch für Admins);
  die eine Rechteprüfung (`core/access.py`) wendet beides auf jeden Akteur an, ohne
  Agenten zu kennen. Vor jedem
  Modell- und Werkzeugaufruf wird das neu bestimmt; wer `ai.use` oder den Zugang zu
  einem schon gelesenen Bereich verliert, beendet den Lauf (`rights_revoked`), ebenso
  ein Agent, der währenddessen pausiert oder dessen verantwortliche Person deaktiviert
  wird.
- Werkzeuge: `search` (Volltext über Seiten und Tickets, nur in Bereichen, deren
  Richtlinie die Verbindung zulässt, ohne gesperrte Seiten), `read_page`,
  `read_ticket`. Ergebnisse gehen gerahmt (`<untrusted>`) und auf 8.000 Zeichen gekürzt
  an das Modell und vollständig in `run_event`. Seit M6 außerdem (alle Stufe 1, lesend):
  - `list_tree`: ohne `space_id` die lesbaren Bereiche (Name, Art, ID), mit `space_id`
    die Seiten des Bereichs nach Pfad (ID, Pfad, Titel; kein Inhalt; Entwürfe nur mit
    Bearbeitungsrecht), seitenweise mit `cursor`.
  - `list_versions`: die Versionen einer Seite (Nummer, Zeit, Autor, Quelle, Name,
    Änderungstext; kein Inhalt), nur mit `page.edit` wie für Menschen.
  - `search_tickets`: Text und Filter (Statuskategorien, mir oder niemandem
    zugewiesen, Art, Priorität, Bereich), zuletzt geänderte zuerst.
  - `read_conversation`: nur das Gespräch, in dem der Lauf antwortet (kein Argument
    nennt ein Gespräch): neueste Nachrichten, ältere mit `before`, Antworten auf eine
    Nachricht mit `replies_to`; ohne Zeitleisten-Einträge.
  - `search_past_runs`: frühere Läufe dieses Agenten für dieselbe fragende Person
    (nie der laufende): ein Werkzeugergebnis nur, solange jeder Bereich, aus dem es
    stammt, jetzt lesbar ist und seine Richtlinie die Verbindung zulässt (dieselbe
    Regel wie bei der Schwärzung in `GET /api/runs/{id}/events`); die eigenen Worte des
    Modells nur, solange jeder Bereich lesbar ist, den ihr Lauf gelesen hat. Außerhalb
    einer Direktnachricht allein mit dem Agenten nur Läufe desselben Gesprächs. Enthält
    ein Ergebnis Worte des Modells oder einen Treffer aus einem Lauf, der keinen Bereich
    gelesen hat, liest es in der Laufansicht nur die fragende Person (Attribut
    `asker_only`; für alle anderen geschwärzt, gleich aus welchen Bereichen die übrigen
    Treffer stammen).
  - `submit_result`: gibt das Ergebnis ab; sein Text ist die Antwort, der Lauf endet
    `completed` ohne weiteren Modellaufruf (auch nach einer Wiederaufnahme genau einmal).
  - `ask_user`: stellt der fragenden Person eine Frage (Karte im Gespräch, siehe
    „Freigaben und Rückfragen“) und wartet auf die Antwort.

  Schreibende Werkzeuge (M6; `backend/app/modules/agents/toolbox/{wiki,ticket,message}_tools.py`)
  gehen durch dieselben Dienste wie Menschen, mit dem Akteur des Laufs (Rechte, Lese-
  und Schreibbereich, Rolle des Agenten, `no_ai`). Was sie schreiben, nennt den Agenten
  als Autor und den Lauf (`run_id`); Ereignisse und Zeitleisten nennen den Agenten
  (`actor.type = "agent"`, `run_id`). Nichts, was der Lauf in einem anderen Bereich
  gelesen hat, geht in einen Bereich, dessen Publikum es nicht sehen darf (Antwort
  „Not allowed: what you have read in this run …“, nichts geschrieben). Kein Werkzeug löscht, legt in den
  Papierkorb oder entscheidet Vorschläge.
  - Stufe 2: `propose_page_change`, `propose_new_page` (Vorschläge, nur mit
    `page.edit` für den Lauf), `comment_ticket` (Nachricht `kind: agent` im
    Ticket-Thread), `set_ticket_status` (höchstens Kategorie `review`; `done` und
    `cancelled` setzt nur eine Person, die Antwort nennt die erlaubten Status),
    `create_ticket` (meldend: der Agent), `link_ticket_page` (einmal je Seite),
    `propose_skill` und `update_memory` (siehe
    [Skill-Vorschläge](#skill-vorschläge-propose_skill-apiskill-proposals) und
    [Gedächtnis](#gedächtnis-einzelheiten)).
  - Stufe 3: `update_page` in zwei Schritten: der erste Aufruf liefert den Diff zur
    aktuellen Version und ein `token` (gebunden an Lauf, Seite, Version und beide
    Inhalte), erst der zweite Aufruf mit diesem Token schreibt, als Version der Quelle
    `agent` mit neuer Generation (laufende Sitzungen enden). Nur in Bereichen mit
    `agent_write_policy = direct`, sonst die Antwort „propose instead“; eine Seite mit
    `no_ai` wird nie geschrieben (auch nicht, wenn sie zwischen Diff und Schreiben
    gesperrt wird). Die Gedächtnisseite eines Agenten (`_agenten/…`) schreibt
    `update_page` nie, von keinem Ort aus (Antwort: „use update_memory“): Gedächtnis
    ändert nur `update_memory`, das die Regeln für das Gedächtnis hält. `assign_ticket` (an Person oder Agent, mit Grund als Kommentar im
    Ticket-Thread; Agenten nur als Mitglied mit mindestens Rolle `editor` des Bereichs).
    `post_message` nur in das Gespräch des Laufs oder in einen Kanal eines Bereichs, in
    dem der Agent Mitglied ist.
  - Jede Wirkung steht in derselben Transaktion wie ihr Journaleintrag; nach einer
    Wiederaufnahme wird der Aufruf aus dem Journal eingespielt, nicht wiederholt.
    Abgelehnte Schreibversuche nehmen alles zurück (Savepoint) und antworten mit dem
    Fehlercode (`Not allowed (…)`, `Refused (…)`, `Changed meanwhile (…)`).

  Listen lassen wie `search` schon in der Abfrage weg, was die Verbindung nicht
  empfangen darf (Richtlinie, `no_ai`); was nicht lesbar ist, antwortet wie nicht
  vorhanden. Jedes Ergebnis nennt die Bereiche, aus denen es stammt (`spaces`).
- Vor jedem Modellaufruf: die strengste Richtlinie aller gelesenen Bereiche (das
  Gespräch selbst zählt als `any`) muss den `data_location` der Verbindung erlauben,
  sonst endet der Lauf mit `policy_blocked`, bevor etwas gesendet wird. Gezählt wird
  der Bereich, in dem gelesen wurde, und der, in dem die gelesene Seite oder das
  Ticket jetzt liegt: wird eine Seite während des Laufs verschoben, gilt auch der neue
  Bereich (für Richtlinie und Zugang); eine seither gesperrte, gelöschte oder in den
  Papierkorb gelegte Seite und ein gelöschtes Ticket beenden den Lauf ebenfalls mit
  `policy_blocked`. Das gilt auch für Treffer der Suche.
- Der Verlauf: Gesendet werden die eigenen Nachrichten des Gesprächs (Person und
  Agent, ohne Threads). Hat eine frühere Antwort des Agenten Inhalt aus einem Bereich
  zitiert, gehört dieser Text nun zum Gespräch und geht mit dem Verlauf an das Modell,
  auch wenn der Bereich seither strenger eingestellt ist oder der Agent eine andere
  Verbindung nutzt (bewusst so entschieden: das Gespräch ist der Inhalt der Person
  und zählt als `any`). Wer das nicht will, löscht die betreffende Antwort.
- Ist die Nachricht, die einen Lauf ausgelöst hat, gelöscht, bevor er beginnt (keine
  Nachricht der Person nach der letzten Antwort), endet er mit `completed` ohne
  Aufruf, Antwort oder Hinweis.
- Stopgründe: `completed`, `max_steps`, `deadline`, `no_progress` (dritter gleicher
  Werkzeugaufruf), `rights_revoked`, `policy_blocked`, `provider_refused` (401, 402,
  403, 429; ohne Wiederholung), `error` (auch sofort, wenn ein Schritt nicht
  gespeichert werden kann oder ein Werkzeug scheitert; kein blindes Wiederholen),
  `cancelled` (Abbruch angefordert), `waiting_timeout` (niemand hat rechtzeitig
  geantwortet), `approval_expired` (niemand hat rechtzeitig freigegeben). Die
  Antwort ist eine Nachricht `kind: agent`
  mit `client_id` = Lauf-ID (genau einmal); bei jedem anderen Stopp steht im Gespräch
  ein Zeitleisten-Eintrag `system.key = "run.stopped"` mit dem Grund in
  `system.new.value`.
- Live: `run.progress` (`conversation_id`, `run_id`, `step`) nach jedem Modellaufruf,
  an die Person im Gespräch.
- `GET /api/runs/{id}` und `GET /api/runs/{id}/events` (seitenweise): für die Person,
  die gefragt hat, und die verantwortliche Person (je mit `ai.use`) und für
  `agent.manage`; sonst 404 `run.not_found`. Die Person, die gefragt hat, sieht ihre
  Läufe vollständig. Alle anderen sehen ein Werkzeugergebnis nur, solange sie jeden
  Bereich lesen dürfen, aus dem es stammt (jedes Ergebnis nennt seine Bereiche in
  `spaces`), und eines, das einen Entwurf las (`read.drafts`), nur mit `page.edit` in
  dessen Bereich; sonst kommt das Ereignis mit `redacted: true` und nur Schritt,
  Werkzeugname und Quelle. Wer als Admin einen Team- oder persönlichen Bereich nur
  kraft Admin-Rechts liest, bekommt den Inhalt und einen Audit-Eintrag
  `space.admin_access` (einmal je Admin, Bereich und Tag), wie beim direkten Lesen
  einer Seite. Die eigenen Worte des Modells (Text und Argumente) gehören zum Gespräch
  und bleiben der Person vorbehalten; Admins lesen sie nur über die begründete,
  protokollierte Einsicht in Direktnachrichten, die Agenten-Nachrichten mit der
  KI-Kennzeichnung und Stopps als Hinweis zeigt. Verbrauch, Modell und Stopp sehen alle,
  denen der Lauf sichtbar ist.
- Verbrauch wird je Modellaufruf einmal gebucht, in derselben Transaktion wie der
  Schritt (`run_event`, eindeutig je Lauf, Versuch und Schritt); Ausnahmen siehe
  [`KI.md`](KI.md#verbrauch-apiaiusage) und [Bekannte Grenzen](#bekannte-grenzen).

#### Journal, Warten, Abbruch

- **Journal**: `run_event` ist das Laufprotokoll. `seq` zählt über alle Aufnahmen eines
  Laufs fort (der Stopp hat `seq` 0), `attempt` nennt die Aufnahme, die den Schritt
  geschrieben hat. Jede Modellantwort (Text, Werkzeugaufrufe mit Argumenten, Verbrauch)
  und jedes Werkzeugergebnis (vollständig, mit den Bereichen und den gelesenen Seiten
  und Tickets) steht dort.
- **Wiederaufnahme**: siehe [Was bei einem Neustart des Workers
  passiert](#was-bei-einem-neustart-des-workers-passiert). Der Lauf beantwortet das
  Gespräch bis zu seinem ersten Start (`started_at`), gleich in welcher Aufnahme.
- **Schreibende Werkzeuge** schreiben ihre Wirkung und ihren Journaleintrag in
  derselben Transaktion: entweder beides oder nichts. Eine Wirkung entsteht daher
  innerhalb der Datenbank genau einmal, auch wenn der Worker vor, während oder nach
  dem Schreiben stirbt.
- **Externe Werkzeuge** (M8, `agents/external_step.py`): zwei kurze Transaktionen um
  den Aufruf, keine offen, während der Server antwortet. Die erste prüft wie jeder
  Werkzeugschritt (Lauf, Abbruch, Freigabe des Werkzeugs, Person und Agent), dann die
  Richtlinie für den Datenort des Servers, ob das Werkzeug noch aufrufbar ist und der
  Zugang da ist (geteilter Konnektor oder der eigene der fragenden Person; das
  Geheimnis nur im Kopf der Anfrage, nie im Journal), bei einem schreibenden Werkzeug
  die Freigabe; dann schreibt sie den Eintrag `external_outcome_unknown` fest. Der
  Aufruf liest die Werkzeugliste im selben Gespräch mit dem Server und ruft nur auf,
  wenn das Werkzeug genau wie freigegeben gelistet ist (sonst wird es `changed` bzw.
  `missing` und nichts gesendet). Die zweite Transaktion schreibt das Ergebnis.
  Scheitert der Aufruf vorher (nicht aufrufbar, nicht verbunden, Richtlinie), steht
  das als Ergebnis im Journal, und nichts wurde gesendet.
- `attempt` zählt jede Aufnahme (auch nach dem Warten), `recoveries` nur die nach
  einem verlorenen Worker (`recoveries` > 2: `error`).
- **Warten**: Braucht ein Lauf eine Antwort (Freigabe, Rückfrage), steht er auf
  `waiting` bis `wait_until` (`HERD_AI_APPROVAL_HOURS`, Standard 72 Stunden, für
  Freigaben und Rückfragen). Dabei hält er nichts: keine
  Sperrfrist, keinen Worker. Das Gespräch bleibt belegt: Eine neue Nachricht startet
  keinen Lauf (`run.waiting`); wenn der wartende Lauf endet, legt er für die
  Nachrichten, die seit seinem Start gekommen sind, einen neuen Lauf an. Die Antwort
  setzt den Lauf in ihrer Transaktion wieder auf `queued`; er spielt sein Journal ein
  und führt den Werkzeugaufruf, auf den er wartete, erneut aus. Läuft `wait_until` ab,
  beendet die Laufschleife ihn mit `waiting_timeout` und einem Hinweis im Gespräch.
  `GET /api/runs/{id}` nennt `wait_until`.
- **Abbruch**: ein eigener Datensatz `run_cancel_request` (einmal je Lauf, mit der
  anfragenden Person). Geprüft wird vor jedem Schritt und in der Transaktion des
  Abschlusses; er gewinnt dort auch gegen eine fertige Antwort (`cancelled`, keine
  Antwort, ein Hinweis). Ein wartender Lauf endet bei der nächsten Runde der
  Laufschleife, ein Lauf in der Warteschlange, sobald er aufgenommen wird. Ein schon
  beendeter Lauf bleibt, wie er ist. Den Endpunkt beschreibt der nächste Abschnitt.

#### Laufansicht und Abbruch (API)

- `GET /api/runs` („meine Läufe“): die Läufe, die man selbst ausgelöst hat, neueste
  zuerst, seitenweise (`limit` ≤ 100, `cursor`). Filter: `agent_id`, `state`
  (`queued`, `running`, `waiting`, `done`), `stop_reason`, `since` (einschließlich) und
  `until` (ausschließlich), beide mit Zeitzone (sonst 422). Nur mit `ai.use` oder
  `agent.manage`, sonst 404 `ai.not_found`.
- `GET /api/agents/{id}/runs`: alle Läufe eines Agenten, für seine verantwortliche
  Person (mit `ai.use`) und `agent.manage`; sonst 404 `agent.not_found` wie für einen
  unbekannten Agenten. Dieselben Filter außer `agent_id`.
- `GET /api/runs/{id}`: wer den Lauf sehen darf (siehe oben), sonst 404
  `run.not_found`. Auch ein Lauf, den die Antwort auf eine Nachricht schon genannt hat,
  kann danach 404 antworten: Ein Lauf einer Direktnachricht, der noch in der
  Warteschlange stand, entfällt, wenn ein wartender Lauf desselben Gesprächs nach
  Freigabe oder Antwort weitermacht (`control_repository.drop_queued`); was er
  beantwortet hätte, beantwortet ein neuer Lauf nach dessen Ende. Clients behandeln
  das 404 wie einen beendeten Lauf ohne eigene Antwort. Listen und Einzelansicht zeigen dieselbe Form: Agent (ID, Name),
  fragende Person (ID, Name; alle, die einen Lauf sehen, dürfen Personen nach Namen
  finden), Ort (`place`: Art des Gesprächs `dm`, `channel`, `thread_page`,
  `thread_ticket`, seine ID; Bereich, Seite und Ticketnummer nur, wenn die lesende
  Person den Bereich lesen darf, sonst leer), Zustand, Stopgrund, `attempt`,
  `recoveries`, `steps`, Start, Ende, `wait_until`, Verbrauch aus den
  Verbrauchseinträgen (`usage`: Aufrufe, Token ein/aus/gecacht, Kosten der Aufrufe mit
  Preis, sonst leer) und `cancel_requested`. Listen filtern in SQL und brauchen je
  Seite zwei Abfragen, gleich wie lang sie ist.
- `GET /api/runs/{id}/events`: das Journal wie oben (Schwärzung und Audit
  unverändert). Neu je Ereignis, wo der Schritt es festgehalten hat: `tokens_in`,
  `tokens_out`, `tokens_cached`, `cost` (Modellaufrufe mit Preis) und `duration_ms`
  (Modell- und Werkzeugaufrufe; ältere Werkzeugaufrufe ohne). Diese Zahlen sehen alle,
  denen der Lauf sichtbar ist, auch bei geschwärzten Ereignissen.
- `POST /api/runs/{id}/cancel`: abbrechen darf, wer den Lauf sehen darf (die fragende
  Person, die verantwortliche Person, `agent.manage`); sonst 404 `run.not_found`. Der
  Abbruch wird einmal gespeichert; ein Lauf in der Warteschlange oder ein wartender
  Lauf endet sofort in derselben Transaktion mit `cancelled` und seinem Hinweis im
  Gespräch, ein laufender vor seinem nächsten Schritt oder in der Transaktion seines
  Abschlusses (höchstens ein Modellaufruf, der schon unterwegs ist, wird noch bezahlt).
  Ein abgebrochener Lauf schreibt danach nichts mehr: keine Antwort und keinen neuen
  Lauf für Nachrichten, die währenddessen kamen. Ein zweiter Abbruch antwortet wie der
  erste (200); ein Lauf, der anders zu Ende ging, antwortet 409 `run.finished`. Einen
  Worker aufzuwecken ist nicht nötig: Was sofort endet, braucht keinen, und das
  Outbox-Ereignis des Hinweises weckt die Laufschleife ohnehin. Abbruch und Abschluss
  sperren beide die Zeile des Laufs: Entweder sieht der Abschluss den Abbruch
  (`cancelled`, keine Antwort), oder der Abbruch findet den Lauf beendet (409); ebenso
  gegen eine gleichzeitige Wiederaufnahme eines wartenden Laufs. Auf die Zeile wartet
  der Abbruch wie die Rücknahme einer Zuweisung höchstens 0,5 s
  (`REASSIGN_LOCK_TIMEOUT_SECONDS`): Hält ein Schritt des Laufs sie gerade, antwortet er
  409 `conflict.retry` mit `Retry-After: 1` (seit M7, Plan-Entscheidung 15); die
  Weboberfläche schickt ihn einmal von selbst erneut.

#### Auslöser: Erwähnung, Ticket-Zuweisung, Übergabe

`backend/app/modules/agents/triggers.py`, Orte und Verlauf `place.py`. Neben der
Direktnachricht starten Läufe so:

- **Erwähnung**: Eine neue Nachricht einer Person in einem Kanal, einem Seiten- oder
  Ticket-Thread, deren `mentions` einen Agenten nennen, startet einen Lauf des ersten
  genannten Agenten, der Mitglied des Bereichs ist und kein Entwurf, wenn die Person
  `ai.use` hat. Ohne `ai.use` oder bei einem Agenten außerhalb des Bereichs startet
  nichts und die Antwort verrät nichts (`agent_run: null`, die ID steht wie jede
  Unbekannte in `not_notified`; das Verzeichnis zeigt solchen Personen ohnehin keine
  Agenten). Sonst nennt `agent_run` den Lauf oder den Grund (`agent.paused`, …,
  `run.waiting`: im Thread ist schon ein Lauf offen) und
  `agent_id`. Der Lauf liest den Thread der erwähnenden Nachricht (Wurzel und
  Antworten bis zu seinem Start) und antwortet dort als Antwort; seine Stopp-Meldung
  steht ebenfalls im Thread. Eine Bearbeitung, die einen Agenten neu erwähnt, startet
  nichts; Nachrichten von Agenten erwähnen niemanden, Agenten starten so keine Agenten.
- **Persönliche Agenten** fragt nur ihre Eigentümerin oder ihr Eigentümer (Erwähnung,
  Zuweisung, Übergabe; für alle anderen ist er wie nicht vorhanden: keine Antwort,
  `ticket.assignee_invalid`), und Mitglied ist er nur im persönlichen Bereich.
- **Richtlinie des Orts**: Was ein Lauf in einem Kanal oder Thread gefragt wird, ist
  Inhalt dieses Bereichs; dessen KI-Richtlinie gilt (z. B. `none` → `policy_blocked`
  vor dem ersten Aufruf), anders als in einer Direktnachricht, die als `any` zählt.
  Im Thread einer Seite gilt zudem die Seite selbst als gelesen: Ist sie für KI
  gesperrt (`no_ai`), endet ein Lauf, den eine Erwähnung dort startet, ebenso mit
  `policy_blocked` vor dem ersten Aufruf (der Lauf entsteht, das Modell bekommt
  nichts; der Thread zeigt den Hinweis).
- **Ticket-Zuweisung** an einen Agenten (Regeln in `docs/TICKETS.md`): Der Lauf hat
  den Ticket-Thread als Ort, die zuweisende Person als Fragende und das Ticket als
  Aufgabe (`run.work_item_id`; das Modell bekommt den Schlüssel und liest das Ticket
  mit `read_ticket`); seine Antwort ist ein Kommentar im Thread. Kann er nicht starten
  (Agent pausiert, …, oder im Thread ist schon ein Lauf offen: ein Lauf je Ticket),
  bleibt das Ticket zugewiesen, der Thread nennt den Grund (Systemmeldung
  `run.refused`, Akteur der Agent, `to` der Code) und die verantwortliche Person des
  Agenten bekommt einen Aktivitätseintrag (`run_stopped`); ebenso, wenn ein Lauf an
  einem Ticket ohne Antwort endet (außer bei Abbruch).
- **Übergabe**: Weist ein Lauf mit `assign_ticket` das Ticket einem anderen Agenten
  zu, startet dessen Lauf für dieselbe Person (der Lauf handelt als die Person, die
  den ersten fragte), eine Stufe tiefer (`run.chain_depth`, höchstens 3); er folgt dem
  übergebenden Lauf im selben Thread. Ein Lauf auf Stufe 3 übergibt nicht mehr: das
  Werkzeug lehnt ab (`run.handover_limit`), der Thread vermerkt es (`run.refused`).
  Ein Lauf übergibt höchstens 5 Tickets an Agenten (`MAX_HANDOVERS_PER_RUN`, neben der
  Tiefengrenze in `agents/run_models.py`; gezählt im Journal des Laufs); darüber hinaus
  lehnt das Werkzeug ab (`run.handovers`), nur als Fehler für das Modell.
- **Zuweisung zurückgenommen**: Wird ein Ticket einem Agenten weggenommen (jemand
  anderem zugewiesen oder niemandem), bittet dieselbe Transaktion dessen offene Läufe
  an diesem Ticket (Zuweisung, Übergabe) über `run_cancel_request` aufzuhören; ein
  laufender hält vor seinem nächsten Schritt, ein wartender oder noch nicht begonnener
  endet `cancelled`, wenn die Laufschleife ihn als Nächstes sieht. Der Lauf, der das
  Ticket selbst übergibt, arbeitet weiter. Auf die Zeile des Laufs (`FOR NO KEY
  UPDATE`) wartet die Anfrage höchstens 0,5 s (`REASSIGN_LOCK_TIMEOUT_SECONDS`, kürzer
  als Postgres' `deadlock_timeout`): Hält ein Schritt des Laufs sie gerade, antwortet
  sie 409 `conflict.retry` mit `Retry-After: 1`, statt bis zum Ende des Schritts zu
  hängen oder eine Verklemmung abzuwarten. Die Weboberfläche schickt eine solche
  Anfrage einmal von selbst erneut (nach `Retry-After`, höchstens 2 s;
  `frontend/src/lib/retry.ts`).
- Je Thread ist höchstens ein Lauf offen: [Ein offener Lauf je
  Thread](#ein-offener-lauf-je-thread).
- Laufansicht: `trigger_message_id` ist bei Ticket-Läufen `null`, `chain_depth` zeigt
  die Stufe.

#### Freigaben und Rückfragen (API)

`backend/app/modules/agents/approvals/`. Ein Werkzeug, dessen wirksame Freigabe am
Agenten `confirm` ist, wird dem Modell angeboten wie jedes erlaubte; sein Aufruf läuft
erst nach der Freigabe einer Person:

- Der Aufruf legt eine **Freigabe** an (`approval`: Lauf, Schritt und Aufruf-ID,
  Werkzeug, kanonische Argumente, betroffene Objekte mit Version und Bereich,
  `fingerprint`), postet eine **Karte** im Gespräch des Laufs (Nachricht
  `kind: approval` des Agenten, `card: {"type", "id"}`, Text: Werkzeug und die
  genannten IDs, nie Inhalt) mit einem Aktivitätseintrag (Grund `approval`) für die
  fragende Person, und der Lauf wartet (`HERD_AI_APPROVAL_HOURS`, Standard 72).
  Ein Aufruf, der nichts ändert (die Vorschau von `update_page`), braucht keine
  Freigabe.
- **Fingerabdruck**: SHA-256 über Werkzeugname, Argumente als kanonisches JSON und
  Art, ID, Version und Bereich jedes betroffenen Objekts. Je Werkzeug: Seite
  (`propose_page_change`, `update_page` mit Token), Bereich und ggf. Elternseite
  (`propose_new_page`), Ticket (`comment_ticket`, `set_ticket_status`,
  `assign_ticket`), Bereich (`create_ticket`), Ticket und Seite (`link_ticket_page`),
  Gespräch (`post_message`), Gedächtnisseite mit Version, vor der ersten der Bereich
  (`update_memory`), Skill mit Version bzw. Bereich oder Organisation
  (`propose_skill`); lesende Werkzeuge nur Name und Argumente.
- `POST /api/approvals/{id}/decide` (`decision: approve|reject`, `reason`, `version`):
  nur die fragende Person, und nur, wenn sie die Wirkung jetzt selbst ausführen dürfte
  (die Aktion des Werkzeugs in jedem betroffenen Bereich, mit ihren eigenen Rechten;
  bei `assign_ticket` dieselbe Regel wie im Ticket-Service: ein freies Ticket sich
  selbst zuweisen oder die eigene Zuweisung lösen braucht `ticket.edit`, alles andere
  `ticket.assign`; 403 `approval.not_permitted`; andere, die die Freigabe sehen: 403
  `approval.not_addressed`). 409: `approval.decided` (schon entschieden),
  `approval.expired`, `approval.run_ended` (Lauf beendet oder Abbruch angefordert),
  `approval.version_conflict`. Die Entscheidung setzt den Lauf in ihrer Transaktion
  wieder auf `queued` (zuerst wird der Lauf gesperrt, dann die Freigabe; der Ablauf
  sperrt in derselben Reihenfolge).
- Beim Fortsetzen: Fingerabdruck neu berechnet; weicht er ab, läuft nichts und das
  Werkzeugergebnis ist `approval_stale` (das Modell kann neu anfragen). Dann die Rechte
  des Laufs erneut (Freigabe am Agenten, Person, Agent, Aktion je Objekt): entzogen →
  `rights_revoked`. Abgelehnt → Werkzeugergebnis `approval_rejected` mit dem Grund
  (gerahmt wie jedes Ergebnis). Abgelaufen → Stopgrund `approval_expired`. Endet ein
  Lauf anders (Abbruch), sind seine offenen Freigaben und Fragen `expired`.
- `GET /api/approvals?state=pending` (seitenweise): meine. `GET /api/approvals/{id}`:
  wer den Lauf sehen darf (wie `GET /api/runs/{id}`), sonst 404
  `approval.not_found`; die Argumente (`args`), `diff_url` und die Begründung einer
  Ablehnung (`reason`) nur für die fragende Person, für alle anderen `null` mit
  `redacted: true` (wie in der Laufansicht). `GET /api/approvals/{id}/diff`: die Seite jetzt gegen den Inhalt des Aufrufs
  (nur für die fragende Person, bei Seitenwerkzeugen).
  `step` und `call_id` nennen den Aufruf wie das Protokoll des Laufs. `outcome` sagt,
  was nach der Freigabe aus ihm wurde: `ran` (ausgeführt), `stale` (nicht
  ausgeführt, weil sich ein Objekt geändert hat) oder `failed` (nicht ausgeführt: der
  Schritt lief in seine Sperr- oder Anweisungsgrenze und wurde ganz zurückgerollt; das
  Modell bekam `tool_timeout`); gesetzt in der Transaktion des Aufrufs, zusammen mit
  Wirkung und Journaleintrag (`failed` in der, die das Zeitlimit als Ergebnis
  festhält), und live als `card.changed` gemeldet (Outbox `approval.settled`, nur
  IDs). Die Karte zeigt „Nicht ausgeführt“.
- **Rückfragen**: `ask_user` legt `run_question` an, postet die Frage als Karte
  (`kind: question`, Aktivität `question`), der Lauf wartet. `POST
  /api/questions/{id}/answer` (`text` bis 4.000 Zeichen, `version`) nur durch die
  fragende Person (403 `question.not_addressed`; 409 `question.answered`,
  `question.expired`, `question.run_ended`, `question.version_conflict`); die Antwort
  geht als gerahmtes Werkzeugergebnis an das Modell. Ohne Antwort endet der Lauf mit
  `waiting_timeout`. `GET /api/questions/{id}` wie Freigaben: Frage (`question`) und
  Antwort nur für die fragende Person, für alle anderen `null` mit `redacted: true`
  (die Karte im Gespräch zeigt die Frage dem Publikum des Ortes ohnehin).
- Outbox und Live-Ereignisse tragen nur IDs (`approval.decided`,
  `question.answered`, `message.created` der Karte, `notification.created`).
- Die verantwortliche Person springt für die fragende nicht ein: Ein Lauf, dessen
  Person nicht mehr aktiv ist, endet vor jedem Werkzeugaufruf mit `rights_revoked`,
  fragt also nie. Auch Läufe von Aufgaben haben eine fragende Person (die Eigentümerin);
  kann sie die Aufgabe nicht mehr ausführen, hält die Aufgabe an, statt Freigaben
  weiterzugeben ([Aufgaben im Worker](#aufgaben-im-worker-m7)).

### Grenzen

| Grenze | Wert |
|---|---|
| Schritte je Lauf | `max_steps` am Agenten, 1 bis 25 |
| Laufzeit je Aufnahme | `max_runtime_seconds` am Agenten, 10 bis 600 s |
| gleicher Werkzeugaufruf | der dritte beendet den Lauf (`no_progress`) |
| Wiederaufnahmen nach Absturz | 2, die dritte endet mit `error` |
| Warten auf Freigabe oder Antwort | `HERD_AI_APPROVAL_HOURS`, Standard 72 h, höchstens 720 |
| Übergaben | Kettentiefe höchstens 3 |
| Anweisungen | 20.000 Zeichen |
| Gesprächsverlauf im Prompt | 24.000 Zeichen (die neuesten 200 Nachrichten, dann nach Zeichen gekürzt; die Nachricht, die den Lauf auslöste, bleibt immer, zuerst fallen die ältesten anderen) |
| Werkzeugergebnis im Prompt | 8.000 Zeichen (im Journal vollständig) |
| externes Werkzeug | Aufruf 60 s (und die Laufzeit des Laufs), Antwort höchstens 512 KiB, Beschreibung im Prompt 1.000 Zeichen; höchstens `HERD_MCP_MAX_CALLS_PER_RUN` gesendete Aufrufe je Lauf (Standard 20, 1 bis 500) |
| Skill-Text je `load_skill` | 7.000 Zeichen je Teil, Skill höchstens 50.000 |
| Skills im Kontext | 25, Beschreibung je 300 Zeichen |
| Gedächtnis | 8.000 Zeichen je Seite, 4.000 Zeichen zusammen im Kontext |
| Rückfrage-Antwort | 4.000 Zeichen |
| persönliche Agenten | `HERD_AI_PERSONAL_AGENTS_MAX`, Standard 5, 0 bis 100 |
| Aufgaben je Person | `HERD_AI_AUTOMATIONS_MAX`, Standard 20, 0 bis 1.000 (erledigte und gelöschte zählen nicht) |
| offene Läufe | einer je Thread, Gespräch, Seite oder Ticket |
| Werkzeugschritt | 5 s Warten auf eine Sperre, 20 s je Anweisung (dann `tool_timeout` für das Modell) |

### Umgebungsvariablen

| Variable | Standard | Wer liest sie | Bedeutung |
|---|---|---|---|
| `HERD_RUN_CONCURRENCY` | 4 | Worker | Läufe je Worker zugleich (1 bis 64); der Worker braucht dafür bis zu diesem Wert + 3 Datenbankverbindungen |
| `HERD_RUN_LEASE_SECONDS` | 30 | Worker | Sperrfrist eines laufenden Laufs (mindestens 3), alle Drittel erneuert; bestimmt, wie schnell ein Absturz aufgefangen wird |
| `HERD_AI_APPROVAL_HOURS` | 72 | Worker | Wartezeit auf eine Freigabe oder Antwort (höchstens 720) |
| `HERD_AI_PERSONAL_AGENTS_MAX` | 5 | API | persönliche Agenten je Person (0 bis 100) |
| `HERD_AI_AUTOMATIONS_MAX` | 20 | API | Aufgaben je Eigentümerin (0 bis 1.000; erledigte und gelöschte zählen nicht) |
| `HERD_SECRET_KEY`, `HERD_SECRET_KEY_PREVIOUS` | – | API, Worker | Schlüssel für `enc:`-Geheimnisse ([`KI.md`](KI.md#schlüssel)) |
| `HERD_AI_EGRESS_PROXY` | – | API, Worker | Proxy für Anbieteraufrufe ([`KI.md`](KI.md#ausgehende-aufrufe-ssrf-sperre)) |
| `HERD_AI_CHECK_TIMEOUT_SECONDS` | 20 | API | Zeitlimit für Verbindungstest und Modellliste |
| `HERD_MCP_ALLOWED_HOSTS` | leer | API, Worker | private Hosts, auf denen externe MCP-Server laufen dürfen (Hostnamen oder private Netze, kommagetrennt; [`MCP.md`](MCP.md#externe-mcp-server)) |
| `HERD_MCP_CATALOG_DIR` | leer | API | Verzeichnis mit eigenen Katalog-Vorlagen der Installation (`*.yaml`, zusätzlich zu GitHub und GitLab; Chart `mcp.catalogConfigMap`; [`MCP.md`](MCP.md#katalog)) |
| `HERD_MCP_MAX_CALLS_PER_RUN` | 20 | Worker | gesendete Aufrufe externer Werkzeuge je Lauf (1 bis 500); der nächste wird nicht gesendet (Chart `mcp.maxCallsPerRun`) |
| `HERD_MCP_RATE_PER_MINUTE` | 120 | API | Aufrufe je Zugangstoken und Minute an `/mcp` (Chart `mcp.ratePerMinute`; [`MCP.md`](MCP.md#betrieb)) |
| `HERD_AI_<NAME>` | – | API, Worker | Anbieterschlüssel, auf die Verbindungen mit `env:` verweisen |

**Compose:** die Schlüssel in der optionalen Datei `deploy/compose/ai.env` (Vorlage
`ai.env.example`), die übrigen in `.env`; siehe [`deploy/compose/README.md`](../deploy/compose/README.md).
**Helm:** `ai.existingSecret` (ein Secret, dessen Schlüssel diese Variablen sind; geht an
API und Worker, nie an den Migrations-Job), `ai.checkTimeoutSeconds`,
`ai.personalAgentsMax`, `ai.automationsMax` (API), `ai.approvalHours`, `ai.runConcurrency`,
`ai.runLeaseSeconds`, `mcp.maxCallsPerRun` (Worker), `mcp.allowedHosts` (API und Worker),
`mcp.ratePerMinute`, `mcp.catalogConfigMap` (API). Mit `networkPolicy.enabled` erreichen API und Worker
**keinen Anbieter**, bis `networkPolicy.aiEgress` Regeln nennt (zum Anbieter, oder nur
zum Proxy aus `HERD_AI_EGRESS_PROXY`); das Chart legt dafür eine eigene NetworkPolicy
nur für API und Worker an. Ohne sie antworten Verbindungstests `timeout` oder
`unreachable`, und Läufe enden mit `error`.

### Metriken und Alarme

Nur Prozesse mit Worker exportieren sie (die API nicht); die Zähler aus der Datenbank
liest jeder Worker alle 10 s, Labels sind nur Aufzählungswerte, nie Inhalte.

| Metrik | Art | Bedeutung |
|---|---|---|
| `herd_runs_total{reason}` | Zähler | beendete Läufe dieses Workers je Stopgrund |
| `herd_run_duration_seconds` | Histogramm | Dauer einer Aufnahme |
| `herd_runs_queued` | Gauge | Läufe in der Warteschlange |
| `herd_runs_oldest_queued_seconds` | Gauge | Alter des ältesten wartenden Laufs |
| `herd_runs_stuck` | Gauge | laufende Läufe mit abgelaufener Sperrfrist oder deren aktuelle Aufnahme (`taken_at`) länger zurückliegt, als jeder Lauf darf; ein Lauf, der nach langem Warten wieder läuft, zählt nicht |
| `herd_runs_waiting` | Gauge | Läufe, die auf eine Freigabe oder Antwort warten |
| `herd_automation_firings_total{outcome}` | Zähler | Termine von Aufgaben, die dieser Worker gefeuert hat (Fälligkeits-Schleife und Handler der Ereignis-Regeln, gezählt nach dem Commit), je Ergebnis: `started`, `skipped_busy`, `skipped_paused_agent`, `skipped_budget`, `skipped_policy`, `skipped_off_hours`, `skipped_depth`, `paused_owner` |
| `herd_automation_terms_set_aside_total` | Zähler | Termine, die die Fälligkeits-Schleife dieses Workers nicht feuern konnte (ihre Transaktion scheiterte) und zurückstellte (seit Review M7) |
| `herd_automations_due` | Gauge | aktive Aufgaben, deren Termin gekommen ist und die noch kein Worker gefeuert hat |
| `herd_automations_oldest_due_seconds` | Gauge | Wartezeit des ältesten fälligen Termins (0 ohne einen) |
| `herd_automations_paused{reason}` | Gauge | angehaltene Aufgaben je Grund (`manual`, `owner`, `failing`) |
| `herd_budget_stops_total{scope}` | Zähler | Läufe, die dieser Worker an einem erreichten Tagesbudget beendet hat, je Geltung (`user`, `agent`, `organisation`); übersprungene Termine zählen als `skipped_budget` oben |
| `herd_wiki_review_reminders_total` | Zähler | Seiten, deren Prüffrist der tägliche Durchlauf dieses Workers gemeldet hat ([`WIKI.md`](WIKI.md#prüffrist-veraltete-seiten-seit-m7)) |
| `herd_wiki_review_spaces_unchecked` | Gauge | Bereiche mit Prüffrist, die der Durchlauf heute (UTC) noch nicht gesehen hat; tagsüber 0 |
| `herd_external_tool_calls_total{outcome,effect}` | Zähler | Aufrufe externer MCP-Werkzeuge in Läufen dieses Workers (seit M8), gezählt nach dem Commit ihres Schritts, je Ergebnis (`ok`, `error`: das Werkzeug meldet selbst einen Fehler, `refused`: nicht gesendet wegen einer Regel, `limited`: Grenze des Laufs, `failed`, `timeout`, `unknown`: gesendet, Ergebnis nicht festgehalten, auch wenn die Laufzeit den Aufruf abschnitt) und Wirkung (`read`, `write`); nie Server, Werkzeug oder Argumente |
| `herd_external_tool_definitions_left_out_total` | Zähler | Externe Werkzeuge, die die Grenze von 100.000 Zeichen für alle externen Werkzeugbeschreibungen eines Modellaufrufs aus den Läufen dieses Workers weglässt, gezählt bei jedem Start und jeder Fortsetzung eines Laufs (Review M8 2, Befund G5); nie ein Name |

Die Metriken von `/mcp`, der OAuth-Erneuerung und des Katalogs (auch von API-Pods)
stehen in [`MCP.md`](MCP.md#metriken-und-alarme).

Alarme in der PrometheusRule des Charts (mit promtool-Tests):

- `HerdRunsStuck`: `herd_runs_stuck` > 0 seit 5 Minuten. Kein Worker übernimmt Läufe
  mit abgelaufener Sperrfrist; Logs `runs.failed`, `runs.renew_failed`,
  `runs.claim_failed`.
- `HerdRunsQueued`: ältester wartender Lauf älter als 5 Minuten. Worker ausgelastet
  (`HERD_RUN_CONCURRENCY`, `max_concurrency`, `requests_per_minute`) oder fehlend.
- `HerdRunsFailing`: mehr als die Hälfte der Läufe der letzten 15 Minuten (mindestens
  3) endete mit `provider_refused` oder `error`, 5 Minuten lang. Meist ein Schlüssel,
  ein Kontingent oder die Netzfreigabe: Verbindung in der KI-Verwaltung testen.
- `HerdAutomationsLagging` (seit M7): der älteste fällige Termin wartet seit über
  3 Minuten, 5 Minuten lang. Die Fälligkeits-Schleife kommt nicht nach (viele Termine
  zugleich bei wenigen Workern, siehe [Steckbrief](STECKBRIEF.md#automatisierung-m7):
  1.000 zugleich brauchten mit einem Worker rund 100 s) oder scheitert immer wieder an
  einer Runde (`automations.pass_failed`, etwa die Datenbank nicht erreichbar; ein
  einzelner Termin, der scheitert, wird zurückgestellt: `automations.term_failed`). Ein Worker eines
  älteren Releases kann Heartbeats und Ereignis-Regeln nicht feuern. Abhilfe: mehr
  Worker, Log lesen.
- `HerdAutomationsFailing` (seit M7): mindestens 5 Aufgaben mehr binnen einer Stunde
  wegen dreier Fehlschläge in Folge angehalten. Meist eine gemeinsame Ursache (Anbieter,
  Schlüssel, Werkzeug; siehe `HerdRunsFailing`); danach setzen die Eigentümerinnen oder
  die Verwaltenden der Bereiche sie fort.
- `HerdExternalToolsFailing` (seit M8): mehr als die Hälfte der gesendeten externen
  Aufrufe der letzten 15 Minuten (mindestens 3) scheiterte oder lief in das Zeitlimit,
  5 Minuten lang; zurückgehaltene (`refused`, `limited`) zählen nicht. Server in der
  KI-Verwaltung testen, `mcp.tool_call` im Log des Workers lesen; die übrigen
  MCP-Alarme in [`MCP.md`](MCP.md#metriken-und-alarme).
- Dazu wie bisher `HerdWorkerAbsent` (deckt auch „kein Worker feuert Aufgaben“ ab: dann
  fehlen die Gauges), `HerdWorkerStalled`, `HerdNotReady`.

Einen Alarm für wartende Läufe, deren Frist abgelaufen ist, ohne dass die Laufschleife
sie beendet hat (`HerdRunsWaitingExpired`), gibt es nicht: Keine Metrik zählt solche
Läufe (`herd_runs_waiting` zählt alle wartenden). Die Schleife beendet sie in jeder
Runde (etwa jede Sekunde); bleibt sie aus, melden `HerdWorkerAbsent` oder
`HerdWorkerStalled` den Worker.

Die Läufe und die Fälligkeits-Schleife zählen nicht zur Bereitschaft (`/ready`) des
Workers: Ein langsamer Anbieter soll den Worker nicht als hängend erscheinen lassen.

### Was wo gespeichert ist

| Was | Wo |
|---|---|
| Agent, Werkzeugeinträge, Skills des Agenten | `agent`, `agent_tool`, `agent_skill` |
| Lauf und Journal | `run`, `run_event` (Prompts, Modellantworten, Werkzeugargumente und -ergebnisse vollständig), `run_cancel_request` |
| Freigaben und Rückfragen | `approval` (Argumente, Fingerabdruck, Entscheidung, `outcome` `ran`/`stale`/`failed`), `run_question`; die Karten als Nachrichten `kind: approval|question` |
| Antworten, Kommentare | Nachrichten `kind: agent` (`client_id` = Lauf) |
| Verbrauch | `usage_record` je Modellaufruf ([`KI.md`](KI.md#verbrauch-apiaiusage)) |
| Vorschläge | `page_proposal`, `skill_proposal` |
| Skills | `skill`, `skill_version` |
| Gedächtnis | normale Wiki-Seiten, Zuordnung in `agent_memory` |
| Aufgaben und ihr Protokoll | `automation` (Auftrag bzw. Checkliste, Termin, Zustand, Fehlschläge in Folge, beim Heartbeat Abstand und aktive Stunden, bei der Ereignis-Regel Art, Filter und Ruhezeit), `automation_firing` (je Termin: Ergebnis, Lauf, der Auftrag des gestarteten Laufs, ob ein Heartbeat `HEARTBEAT_OK` antwortete); der Lauf nennt seine Aufgabe (`run.automation_id`); Aktivitäten zu angehaltenen Aufgaben (`notification.automation_id`); die aufgenommenen Ereignisse einer Ereignis-Regel (`automation_event`: Objekt, IDs, Tiefe, der Termin, der sie nahm); der verursachende Lauf eines Ereignisses (`event_outbox.run_id`) |

Läufe und ihr Journal werden nicht automatisch gelöscht; sie gehen mit ihrem Gespräch
bzw. Ticket (eine gelöschte Aufgabe behält ihre Läufe). Inhalte stehen nie in Logs,
Outbox, `NOTIFY` oder Metriken: Dort stehen nur IDs, Zähler und Codes.

### Aufbewahrung

Das Protokoll der Aufgaben wächst mit jedem Termin (`automation_firing`) und jedem
aufgenommenen Ereignis (`automation_event`). Die Fälligkeits-Schleife jedes Workers
löscht einmal je Minute, in Stapeln von höchstens 1.000 Zeilen (je eine Transaktion,
Zeilen eines anderen Workers übersprungen):

- aufgenommene Ereignisse 7 Tage nach ihrem Termin (`EVENT_RETENTION`);
- Termine nach 90 Tagen (`FIRING_RETENTION`), mit ihren Ereignissen (Index auf
  `automation_firing.fired_at`, Migration `a3d5f7b9c1e2`);
- nie einen Termin, dessen Lauf noch offen ist, und nie seine Ereignisse (der Lauf liest
  seinen Auftrag aus dem Termin, die Regel „nicht auf die eigene Wirkung“ seine
  Ereignisse); nie ein Ereignis, das bei einer aktiven Regel noch auf das Ende einer
  Ruhezeit wartet, wie alt es auch ist;
- wartende Ereignisse einer gelöschten Regel, und die einer angehaltenen Regel, die sie
  vor mehr als 7 Tagen aufgenommen hat (`automation_event.taken_at`; eine angehaltene
  Regel nimmt nichts Neues auf, sie ruht also so lange). Ein Termin zählt die
  wartenden Ereignisse in SQL und liest nur die Kennungen der neuesten 20; dem Lauf
  werden Art, Anzahl und diese Kennungen beim Feuern in die Zeile des Termins kopiert,
  jede Wiederaufnahme liest diese Kopie, nie die Regel;
- die Aufrufzeilen von `/mcp` (`mcp_call`, siehe [`MCP.md`](MCP.md#nutzung-je-token))
  nach 90 Tagen (`MCP_CALL_RETENTION`; Index auf `mcp_call.created_at`, Migration
  `729e9c8f5547`);
- Zeilen, deren Zeit abgelaufen ist (`app/worker/upkeep.py`, seit M9): beendete
  Anmeldesitzungen eine Stunde nach ihrem Ende, OAuth- und OIDC-Abläufe bei Ablauf,
  Collab-Berechtigungen eine Stunde nach Ablauf, Treffer der Ratenbegrenzung nach ihrem
  Fenster (60 s), Ratenfenster der KI-Verbindungen eine Stunde nach Beginn. Die Module
  räumen unterwegs weiter selbst auf (beim Anmelden, beim nächsten Ablauf, bei der
  nächsten Berechtigung); die Fälligkeits-Schleife erfasst, wozu niemand zurückkommt.

Die Fristen stehen im Aufbewahrungskatalog `app/core/retention.py` (eine Regel je
Tabelle, siehe [`SICHERUNG.md`](SICHERUNG.md#aufbewahrung-je-tabelle)), keine
Einstellungen. Folge: Eine
Aufgabe, die 90 Tage nicht gefeuert hat, zeigt keinen letzten Lauf mehr (ihre Läufe
bleiben in der Laufliste).

### API im Überblick

- Läufe, Freigaben und Rückfragen: [Laufansicht und Abbruch
  (API)](#laufansicht-und-abbruch-api), [Freigaben und Rückfragen
  (API)](#freigaben-und-rückfragen-api); wer einen Lauf liest: [Läufe im
  Einzelnen](#läufe-im-einzelnen).
- Agenten, Werkzeuge, Skills: [Verwaltung](#verwaltung); Seitenvorschläge:
  [`WIKI.md`](WIKI.md#vorschläge-seit-m6).
- Antwort auf das Senden einer Nachricht: `agent_run: {id, reason, agent_id}` oder `null`;
  Gründe ohne Lauf: `ai.unavailable`, `agent.paused`, `agent.draft`,
  `agent.responsible_inactive`, `agent.connection_unavailable`,
  `agent.personal_disabled`, `agent.external` (ein externer Agent, M8),
  `run.thread_reply`, `run.waiting`.
- Aufgaben: [Aufgaben-API (M7)](#aufgaben-api-m7); Budgets:
  [`KI.md`](KI.md#budgets-apiaibudgets-aimanage).
- Live: `run.progress` (`conversation_id`, `run_id`, `step`), `card.changed`,
  `proposal.changed`, `skill_proposal.changed`, `automation.changed`
  (`automation_id`, `space_id`), Aktivitätsgründe `approval`, `question`,
  `run_stopped`, `proposal`, `skill_proposal`.

### Bekannte Grenzen

- **Ein Schritt über seine Sperrfrist hinaus zählt nicht für `max_concurrency`:**
  Hält ein Schritt die Zeile seines Laufs länger als die Sperrfrist
  (`HERD_RUN_LEASE_SECONDS`, 30 s; ein Schritt darf bis zu 5 s auf Sperren warten und
  je Anweisung 20 s rechnen), steht `lease_until` bis zum Festschreiben in der
  Vergangenheit, und das Aufnehmen eines weiteren Laufs auf derselben Verbindung zählt
  ihn nicht mit; so kann die Verbindung kurz einen Lauf mehr bedienen. Den Lauf selbst
  nimmt niemand auf (seine Zeile ist gesperrt). Eine genaue Zählung müsste gesperrte
  Zeilen erkennen; als laufend zählen auch abgelaufene Läufe ohne Sperre würde einen
  abgestürzten Lauf seine eigene Wiederaufnahme blockieren lassen. Werkzeugschritte
  dauern Millisekunden bis Sekunden, daher bleibt es dabei.
- **Verbrauch wird in zwei seltenen Fällen zu wenig gezählt**, nie doppelt: Ein
  Anbieteraufruf eines Workers, der danach abstürzt oder seine Sperrfrist verliert, ist
  bezahlt, aber nicht gebucht; und scheitern beim Abschluss eines Schritts sowohl das
  Speichern des Schritts als auch das Nachbuchen in eigener Transaktion, fehlt dieser
  eine Aufruf ([`KI.md`](KI.md#verbrauch-apiaiusage)).
- **Freigaben gehen nur an die fragende Person**, auch bei Aufgaben (die Eigentümerin).
  Einen Ersatz durch die verantwortliche Person gibt es nicht (Spezifikation 5.4,
  geändert in M7): Kann die Eigentümerin die Aufgabe nicht mehr ausführen, hält sie an,
  und jemand übernimmt sie ausdrücklich. Ist die fragende Person nicht mehr aktiv, endet
  ein laufender Lauf vor dem nächsten Werkzeugaufruf mit `rights_revoked`.
- **Aufgaben (M7):**
  - Eine Regel reagiert nur dann nicht auf ihre eigene Wirkung, wenn ihr Lauf dasselbe
    Objekt betrifft; die Wirkung auf ein anderes Objekt kann sie erneut auslösen, bis die
    Tiefe 3 die Kette beendet.
  - Filter von `ticket.created` lesen das Ticket beim Zustellen; ein Tag, das erst danach
    gesetzt wird, zählt nicht.
  - Eine angehaltene Ereignis-Regel verpasst die Ereignisse ihrer Pause.
  - Ein Tagesbudget kann je gleichzeitig laufendem Lauf um einen Modellaufruf
    überschritten werden; ein Euro-Limit gilt nur für Aufrufe mit hinterlegtem Preis.
  - Die Fälligkeits-Schleife teilt sich die Event-Loop mit den Läufen; viele zugleich
    fällige Termine kommen je Worker nacheinander (1.000 in rund 100 s mit einem Worker).
  - Die Budgetprüfung mit einem Budget der Organisation liest jede Verbrauchszeile des
    Tages (bei 100.000 Zeilen rund 60–80 ms je Modellaufruf, Steckbrief); eine
    Tagessumme gibt es nicht.
  - Eine Aufgabe in einer Direktnachricht hält an, sobald die Eigentümerin dort nicht
    mehr allein mit dem Agenten ist.
  - Eine gelöschte Aufgabe bricht ihren offenen Lauf nicht ab (das geht in der
    Laufansicht).
- **Skills sind nur ihre SKILL.md**: zusätzliche Dateien (Referenzen, Vorlagen, Skripte)
  werden beim Import nicht übernommen, und Felder wie `license` gehen beim Export
  verloren.
- Ein Lauf, der auf eine Freigabe wartet, hält seinen Thread (bzw. das Gespräch oder
  Ticket) bis zu 72 Stunden; Erwähnungen dort antworten so lange „Lauf wartet“.
- Wird ein Werkzeug während des Wartens gesperrt, bietet die Wiederaufnahme es nicht
  mehr an; der eingespielte Aufruf läuft nicht, der Lauf kann aber zu Ende kommen.
- Ein Lauf, der vor einer geänderten Zuordnung seiner Besitzerin begann, arbeitet mit
  der alten Verbindung zu Ende, zählt für `max_concurrency` aber schon bei der neuen
  (die Zählung liest die Verbindung, die jetzt am Agenten steht).
- Für Agenten aus anderen Systemen (agentskills.io) sind Skripte in Skills nur Text;
  ein Werkzeug, das Code ausführt, gibt es nicht.

### Rolling Update (aus M5, M6 und M7)

Bisher ist kein Release mit M5, M6 oder M7 erschienen; die Hinweise gelten, sobald eins auf
ein älteres folgt. Alle Migrationen sind nur erweiternd, aber:

- Neue Aufzählungswerte entstehen erst durch dieses Release: Zustand `waiting`,
  Stopgründe `cancelled`, `waiting_timeout`, `approval_expired`, Nachrichtenarten
  `approval` und `question`, Versionsquelle `agent`, Aktivitätsgründe `proposal`,
  `approval`, `question`, `run_stopped`, `skill_proposal`, Freigabe-Ausgang `failed`
  (Migration `a1c3e5f7b9d2`, nur die Prüfung erweitert), Agentenstufe 4 (M8, Migration
  `f4c6e8a0b2d4`, nur die Prüfung erweitert; der vorige Release liest die Stufe als
  Zahl), Läufe ohne auslösende
  Nachricht (Ticket-Läufe), Systemmeldungen als Antworten in Kanal-Threads. Ein Pod des
  vorigen Releases liest solche Zeilen nicht (Versionsliste, Aktivität, Laufansicht
  scheitern dort), bis er ersetzt ist.
- M7: Stopgrund `budget` (Migration `e7a9c1b3d5f7`, nur die Prüfung erweitert, dazu die
  neue Tabelle `ai_budget` und ein Index). Ein Pod ohne M7 schreibt ihn nie und prüft
  keine Budgets; Laufansicht und Laufliste scheitern dort an einem solchen Lauf, bis er
  ersetzt ist.
- M7, Lauf einer Aufgabe (Migration `f2a4c6e8b0d1`): Haltegründe `owner` und `failing`,
  Protokoll-Ergebnisse `skipped_budget` und `skipped_policy`, der Aktivitätsgrund
  `automation` (ohne Gespräch) und Systemeinträge `automation.started` oben in einem
  Kanal (die Trigger-Funktion der Nachrichten lässt sie zu, wenn sie einen Termin einer
  Aufgabe dieses Kanals nennen). Ein Pod des vorigen Releases schreibt nichts davon;
  seine Aktivitätsansicht scheitert an einem solchen Eintrag, und ein Worker ohne den
  Lauf von Aufgaben beendet deren Läufe nach seinen Versuchen mit `error`. Aufgaben
  entstehen erst mit diesem Release (Verwaltungs-API); Worker zügig ersetzen.
- M7, Heartbeats (Migration `c665b1a02d23`): die Art `heartbeat` mit Abstand und aktiven
  Stunden, das Ergebnis `skipped_off_hours` und `automation_firing.heartbeat_ok`. Ein
  Worker des vorigen Releases, der einen fälligen Heartbeat greift, scheitert an der
  Terminberechnung; die Transaktion wird zurückgerollt und der Termin bleibt fällig,
  bis ein Worker dieses Releases ihn auslöst.
- M7, Ereignis-Regeln (Migration `5e2b9c7d4a18`): `event_outbox.run_id`, die Art `event`
  mit ihren Feldern, `automation_event` und das Ergebnis `skipped_depth`. Ein Pod des
  vorigen Releases schreibt `run_id` nicht (seine Läufe verursachen dann Ereignisse
  ohne Tiefe) und hat den Handler nicht; ein Worker des vorigen Releases, der eine
  Regel mit wartenden Ereignissen greift, scheitert an der Terminberechnung, und der
  Termin bleibt fällig. Worker zügig ersetzen.
- M7, Verwaltungs-API (Migration `8c4e1a7f3b26`): der Zustand `deleted` (nur die
  Prüfungen erweitert). Ein Pod des vorigen Releases kennt ihn nicht: Seine Schleife
  und sein Handler der Ereignis-Regeln greifen eine gelöschte Aufgabe nicht (sie ist
  nicht aktiv), aber seine
  Aktivitätsansicht listet Einträge zu gelöschten Aufgaben noch. Ein Downgrade löscht
  gelöschte Aufgaben endgültig.
- M7, Prüffrist (Migration `d4f6b8a0c2e4`): Felder an Bereich und Seite, der
  Aktivitätsgrund `review_due` ([`WIKI.md`](WIKI.md#prüffrist-veraltete-seiten-seit-m7));
  die Aktivitätsansicht eines Pods des vorigen Releases scheitert an einem solchen
  Eintrag, bis er ersetzt ist.
- M7, Aufbewahrung (Migration `a3d5f7b9c1e2`): nur ein Index. Ein Worker des vorigen
  Releases löscht nichts aus dem Protokoll; das holt der erste Worker dieses Releases
  nach.
- M7, Nachbesserung nach Review (Migration `b7e9c1d3f5a7`): neue Spalten
  `automation.term_errors`, `automation_firing.event_type/event_count/event_objects`,
  `automation_event.taken_at` (mit Vorgabewerten oder leer). Ein Pod des vorigen
  Releases schreibt sie nicht: Ein Lauf, dessen Termin ein alter Worker gefeuert hat
  und den ein neuer aufnimmt, bekommt nur den Auftrag, keine Ereignisse genannt.
- M7 zusammengefasst: Worker zuerst und zügig ersetzen. Ein Worker des vorigen Releases
  greift Termine, die er nicht kennt, und rollt sie zurück (sie bleiben fällig, bis ein
  neuer Worker sie feuert); `HerdAutomationsLagging` meldet es, wenn es dauert. Während
  des Rollouts können API-Pods des vorigen Releases Aktivitäten zu Aufgaben, zur
  Prüffrist und Läufe mit Stopgrund `budget` nicht anzeigen.
- Die Migration der Bahnen (`b2d4f6a8c0e1`) ersetzt den Index „ein Lauf in der
  Warteschlange je Gespräch“, auf den sich ein Release vor ihr beim Einreihen beruft
  (`ON CONFLICT (conversation_id)`): Solange ein solcher API-Pod läuft, schlagen
  Direktnachrichten an Agenten und Erwähnungen über ihn fehl. Rollout daher zügig
  durchziehen (oder alte API-Pods vor dem Start der neuen beenden).
- Ein Worker des vorigen Releases arbeitet keine Läufe ab, die er nicht kennt (wartende,
  Ticket-Läufe); er sollte nicht neben neuen Workern weiterlaufen.
- M8, persönliche Marke (Migration `5b7d9f1a3c6e`): die Ereignisart `mark` (nur die
  Prüfung erweitert). Die Wiedergabe des Journals eines Workers des vorigen Releases
  übergeht sie; die Laufansicht eines API-Pods des vorigen Releases scheitert an einem
  Lauf mit `mark` (500), bis er ersetzt ist. Ab diesem Release übergeht die Laufansicht
  (API und Oberfläche) jede Ereignisart, die sie nicht kennt (Review M8 3, Befund H6).
- M8, „Neu beginnen“ (Migration `f3a7c9e1b5d8`): die Spalte `conversation.fresh_start_at`
  (nullbar, ohne Umschreiben). Ein Worker des vorigen Releases liest sie nicht und gibt
  Läufen weiter den ganzen Verlauf (die Marke hält dann wie zuvor), bis er ersetzt ist;
  den Schnitt setzt nur ein API-Pod dieses Releases.

### Woran man Probleme erkennt

- **Agent antwortet nicht, Karte „arbeitet“ bleibt:** `herd_runs_queued` und
  `herd_runs_oldest_queued_seconds` (läuft ein Worker? `HerdWorkerAbsent`), dann
  `herd_runs_stuck`. In der Laufansicht Zustand und Versuche.
- **Läufe enden mit „Anbieter lehnt ab“ oder „Fehler“:** Verbindung in der
  KI-Verwaltung testen; Netzfreigabe (`networkPolicy.aiEgress`) und Proxy prüfen;
  `HerdRunsFailing`.
- **„Durch die Richtlinie des Bereichs gestoppt“ (`policy_blocked`):** Ein gelesener
  Bereich lässt die Verbindung des Agenten nicht zu, oder eine gelesene Seite (auch die
  Seite, in deren Thread gefragt wurde) ist für KI gesperrt; das ist gewollt
  ([`KI.md`](KI.md)).
- **Viele wartende Läufe** (`herd_runs_waiting`): Freigaben bleiben liegen; die Liste
  „Freigaben“ der fragenden Personen zeigt sie.
- **Aufgabe läuft nicht:** das Protokoll der Aufgabe (übersprungen mit Grund?), ihr
  Zustand (angehalten mit Grund?), dann `herd_automations_oldest_due_seconds` und
  `automations.pass_failed` im Log der Worker. „Übersprungen: Tagesbudget“: die Budgets in
  der KI-Verwaltung; der Verbrauch des Tages steht dort.
- Logs der Läufe: `runs.claim_failed`, `runs.failed`, `runs.renew_failed`,
  `runs.metrics_failed` (mit Lauf-ID und Fehlerklasse, nie Inhalt), dazu
  `ai.provider_call` (Pfad, Zustand, Dauer) bei Verbindungstests. Die HTTP-Clients
  (`httpx`, `httpcore`, `hpack`, `httpx2`, `httpcore2`, `openai`) bleiben auch bei
  `HERD_LOG_LEVEL=DEBUG` auf WARNING, weil sie sonst Kopfzeilen der Anbieter
  protokollieren.