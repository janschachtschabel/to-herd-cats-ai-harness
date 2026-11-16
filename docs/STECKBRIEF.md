# Steckbrief to-herd-cats-ai

Stand: M9a (Produktion, erster Teil: Sicherung und Wiederherstellung, Anmeldung über
OIDC mit Freigabe, Collab-Berechtigungen, volles Chart, ASVS-Prüfung, Lasttest) auf
Meilenstein 8 (Öffnung: MCP), M7 (Automatisierung), M6 (Agenten als Mitarbeiter) und
M5 Tasks 1 bis 7 (KI-Grundlage), 16.11.2026, Version 0.1.0. Der Steckbrief wird mit jedem Meilenstein aktualisiert
(Spezifikation 12.7). Die Messwerte aus M2 (Image, Compose, `docker stats`) bleiben
stehen. Ohne Docker, an Prozessen auf der Maschine, sind gemessen: die Nachrichten aus
M3, die Tickets aus M4, die Sprints und Boards aus M4b, die Agenten aus M6, die
Automatisierung aus M7 und der Endpunkt `/mcp` aus M8 (Abschnitte
[Gemessen: Nachrichten](#gemessen-nachrichten-m3-ohne-docker),
[Tickets (M4)](#tickets-m4), [Sprints und Boards (M4b)](#sprints-und-boards-m4b),
[Agenten (M6)](#agenten-m6), [Automatisierung (M7)](#automatisierung-m7) und
[MCP (M8)](#mcp-m8)), dazu aus M9 (Task 10, 16.11.2026) der Lasttest mit 200
Personen auf zwei API-Prozessen, die tatsächlich genutzten Datenbankverbindungen,
Sicherung und Wiederherstellung von 10.000 Seiten mit 1 GiB Anhängen und die
Schreibgrenze durch `NOTIFY` ([Lasttest](#gemessen-lasttest-mit-200-personen-m9),
[Sicherung](#gemessen-sicherung-und-wiederherstellung-m9),
[NOTIFY](#gemessen-schreibgrenze-durch-notify-m9)). Was nicht gemessen ist, steht unter
[Nicht gemessen](#nicht-gemessen-hier-nicht-möglich-oder-nicht-gemacht).

## Kurzbeschreibung

Selbst betriebenes Arbeitssystem für Teams: Wiki, Aufgaben und Kanäle in Bereichen
mit einem Rechtemodell, KI-Agenten als Teammitglieder. **Vorhanden (M1):**
Anmeldung mit Sitzungen, Personen, Gruppen, Bereiche (offen, Team, persönlich),
Rollen und Rechteprüfung, Audit, Verzeichnissuche, Oberfläche mit Navigation und
Verwaltung. **Vorhanden (M2):** Wiki je Bereich mit Seitenbaum, Markdown-Editor,
Live-Bearbeitung (Collab-Prozess, Generationen), Versionen mit Diff und
Wiederherstellung, Papierkorb, Tags (systemweit und je Bereich), Anhänge,
Volltextsuche, Markdown-Import und -Export. **Vorhanden (M3):** Kanäle je Bereich,
Direktnachrichten, Threads, Erwähnungen, Reaktionen, Lesestand, Diskussion je Wiki-Seite
mit Systemmeldungen, Aktivität „Für mich“, Suche in Nachrichten, Live-Zustellung über
Server-Sent Events (auch über mehrere API-Knoten), Outbox mit Worker, Einsicht der
Verwaltung in Direktnachrichten mit Begründung und Audit. **Vorhanden (M4):** Tickets je
Bereich (Epic, Story, Aufgabe, Fehler mit Hierarchie), Status-Workflow je Bereich nach
Kategorien, Zuweisung, Liste und „Meine Tickets“, Board, Epic-Übersicht, Ticket-Diskussion
mit Systemmeldungen, Ticket-Karten in Nachrichten, Verknüpfung mit Wiki-Seiten, Tags,
Suche. **Vorhanden (M4b):** Sprints je Bereich (höchstens einer läuft; Abschluss mit
Bilanz), Vorrat, „Mein Board“ über alle Bereiche nach Kategorie, Daily-Ansicht des
Boards nach Person. **Vorhanden (M5, Tasks 1 bis 7):** KI-Verbindungen zu Anbietern
mit OpenAI-Protokoll (Schlüssel verschlüsselt oder als Verweis auf eine Variable,
ausgehende Aufrufe hinter einer SSRF-Sperre), Zuordnung von Modellen zu Personen und
Gruppen, Verbrauch je Aufruf, KI-Richtlinie je Bereich und KI-Sperre für Seiten,
Agenten mit Direktnachricht und Laufschleife im Worker. **Vorhanden (M6):** Agenten als
Mitarbeiter: Stufen 1 bis 3 mit Werkzeugfreigaben (22 Werkzeuge), Erwähnung in Kanal
und Thread, Ticket-Zuweisung und Übergabe, Freigaben und Rückfragen, Laufansicht und
Abbruch, Wiederaufnahme nach Absturz aus dem Journal, Seiten- und Skill-Vorschläge,
Skills (SKILL.md), Gedächtnis je Bereich, persönliche Agenten. **Vorhanden (M7):**
Aufgaben der Agenten ohne Anstoß im Gespräch: einmal, wiederkehrend (Cron mit
Zeitzone), als Heartbeat mit Checkliste und aktiven Stunden und als Ereignis-Regel eines
Bereichs (mit Ruhezeit und Tiefengrenze); jede gehört einer Person und hat einen Ort;
Tagesbudgets in Tokens und Euro je Organisation, Person und Agent; Prüffrist für
Wiki-Seiten mit täglichem Durchlauf. **Vorhanden (M8):** der Endpunkt `/mcp` für
externe KI-Clients (Claude Code, Codex) mit persönlichen Zugangstoken (Umfang, Ablauf,
nur gehasht gespeichert), lesenden und schreibenden Werkzeugen im Rahmen der Rechte der
Person und der KI-Richtlinie; externe Agenten mit Agenten-Token und Ticket-Abholung;
externe MCP-Server als Werkzeugquelle der eigenen Agenten mit Freigabe je Werkzeug und
Fingerabdruck (schreibende Werkzeuge auf Stufe 4, immer mit Freigabe der fragenden
Person), Konnektoren (Token oder OAuth mit PKCE, geteilt oder persönlich) und ein
Katalog mit GitHub und GitLab. **Vorhanden (M9a):** Sicherung des ganzen Datenstands
(Datenbank und Anhänge aus einem Snapshot) über die Kommandozeile, nach Zeitplan mit
Aufbewahrung, Offsite-Kopie mit restic und Alarmen; Wiederherstellung in eine leere
Installation mit Probe ([`SICHERUNG.md`](SICHERUNG.md)); Anmeldung über OpenID Connect
(Google als Vorlage, jeder andere Anbieter mit Discovery), Selbstregistrierung für
erlaubte Domains nur mit Freigabe durch einen Admin ([`ANMELDUNG.md`](ANMELDUNG.md));
der Collab-Prozess bekommt kurzlebige, seitengebundene Berechtigungen statt des
Sitzungs-Cookies; Autoskalierung und PodDisruptionBudgets im Chart; Aufbewahrungsregel
für jede Tabelle; Prüfung gegen OWASP ASVS 5.0 Stufe 2 ([`SICHERHEIT.md`](SICHERHEIT.md)).
Hybride Suche und Embeddings (M5 Tasks 8 bis 11) und M9b (Einspielen im Betrieb und in
der Verwaltung, S3, mehrere Collab-Instanzen, TOTP, ASVS-Lücken J7–J14) folgen.

| | |
|---|---|
| Dienst-ID | `to-herd-cats-ai` (Log-Feld `service`, `OTEL_SERVICE_NAME`, Image, Chart) |
| Image | `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y`, ein Image für alle Rollen (`HERD_ROLE=api\|migrate\|all\|worker\|collab`) |
| Chart | `oci://ghcr.io/<owner>/charts/to-herd-cats-ai`, `version` = `appVersion` = Dienstversion |
| Prozesse | API (Python, Uvicorn: öffentlicher und interner Server in einem Prozess); Collab-Prozess (Node 22, Hocuspocus) für die Live-Bearbeitung. `HERD_ROLE=all`: die API startet ihn als Kindprozess auf `127.0.0.1:1234`; im Chart ein eigenes Deployment (`HERD_ROLE=collab`, genau eine Replika). Worker (Python, Verteiler der Outbox und seit M5 die Läufe der Agenten, nur interner Port): in `HERD_ROLE=all` im API-Prozess, im Chart ein eigenes Deployment (`HERD_ROLE=worker`, Standard 1 Replika, mehrere sicher) |
| Ports | 8080 öffentlich (API, SPA, WebSocket `/collab/`, Server-Sent Events `/api/stream`, MCP `/mcp`); 9090 intern (`/health`, `/ready`, `/metrics`, `/internal/*`); 1234 Collab-Prozess (nur von der API erreichbar) |
| Speicher | PostgreSQL (alle Daten, auch Seiten, Versionen, Yjs-Stände); Volume `/data` (`HERD_DATA_DIR`) für Anhänge und temporäre Dateien von Upload, Import und Export; seit M9 ein Volume für Sicherungsarchive (`HERD_BACKUP_DIR`, Standard `/backups`) |
| Lizenz | Apache-2.0 |

## Funktionen mit Laufzeit und Kosten

Gemessen gegen die Compose-Referenz (ein App-Container mit `HERD_ROLE=all`, also API und
Collab-Prozess, ein PostgreSQL), Maschine und Ablauf siehe [Messung](#messung). Laufzeit
ist die Antwortzeit am Client, inklusive Docker-Portweiterleitung; alle Antworten waren
200, Fehlerquote 0 %.

| Funktion | Endpunkt | P50 / P90, leicht (2 Clients) | P50 / P90, Last (20 Clients) | Durchsatz unter Last |
|---|---|---|---|---|
| Anmelden | `POST /api/auth/login` | nicht gemessen | 981 / 1119 ms | 10,1 Anmeldungen/s |
| Bereiche auflisten (gleichzeitig mit den Anmeldungen) | `GET /api/spaces?limit=50` (22 Bereiche) | nicht gemessen | 127 / 183 ms | 74/s |
| Seitenbaum (100 Seiten) | `GET /api/spaces/{id}/pages/tree?limit=100` | 25 / 31 ms | 307 / 396 ms | 63/s |
| Seite lesen | `GET /api/spaces/{id}/pages/by-path` | 19 / 25 ms | 171 / 219 ms | 112/s |
| Volltextsuche (100 Seiten à 2 KB, Wort in allen) | `GET /api/search?q=…&limit=20` | 23 / 31 ms | 174 / 224 ms | 109/s |
| Seite lesen, während 10 Personen live tippen | `GET /api/pages/{id}` (4/s, sequenziell) | 14 / 18 ms | – | – |
| Live-Bearbeitung: Änderung erscheint bei den anderen | WebSocket `/collab/` | 10 Editoren: 5 / 9 ms (P99 12 ms) | – | 20 Änderungen/s gesamt |
| Speichern im Markdown-Modus beendet die Live-Sitzung | `PATCH /api/pages/{id}` → Close-Code 4409 | 10 Editoren: 0,3 s und 4,4 s (zwei Läufe) | – | – |

Die Lastzeilen der Wiki-Endpunkte liefen einzeln (je 20 s, nur dieser Endpunkt); der
Durchsatz um 100 Anfragen/s ist vermutlich die Grenze eines Prozesses (ein Event-Loop,
Python); die CPU der Container wurde in diesen Läufen nicht aufgezeichnet. Mehr
Durchsatz gibt es über mehr API-Replikas. Die zweite Zeit beim Beenden der Live-Sitzung hängt davon ab, wann
der Collab-Prozess das nächste Mal prüft (alle 5 s) oder speichert.

### Nachrichten (M3)

Ohne Docker gemessen: zwei API-Prozesse (`HERD_ROLE=api`) und ein Worker an einem
lokalen PostgreSQL, 200 offene SSE-Verbindungen (40 Personen mit je 5, je zur Hälfte an
Knoten A und B), 20 Nachrichten je Sekunde über 60 s an Knoten A, alle in einem Kanal,
den alle 40 sehen (Ablauf unter [Messung](#messung)). Zahlen aus Lauf 3 (Lauf 2 in
Klammern).

| Funktion | Endpunkt | P50 / P90 / P99 | Durchsatz |
|---|---|---|---|
| Nachricht schreiben | `POST /api/conversations/{id}/messages` | 29 / 40 / 55 ms (23 / 36 / 61 ms) | 20/s, 0 Fehler |
| Zustellung: Senden bis Ereignis in jeder offenen Verbindung | `GET /api/stream` (`message.created`) | 55 / 72 / 111 ms, höchstens 216 ms (48 / 67 / 100, höchstens 191 ms) | 4.000 Ereignisse/s an 200 Verbindungen, keines fehlte |
| davon an Knoten A (schreibt) / Knoten B (nur liest) | | 56 / 74 / 106 ms und 54 / 69 / 112 ms | |
| 200 Verbindungen öffnen | `GET /api/stream` | alle offen nach 0,67 s (0,52 s) | |

Die Zustellzeit enthält den ganzen Weg: Commit, Worker (`publish_live`), `NOTIFY`, je
API-Prozess eine Abfrage, wer das Ereignis sehen darf, und das Schreiben in die
Verbindungen; gemessen vom Absenden der POST-Anfrage bis zur Zeile `event:` im Client.
Die Outbox stand dabei nie über 0 offenen Ereignissen bei den Abfragen alle 2 s
(`herd_outbox_pending`; in Lauf 1 höchstens 12, das älteste 0,75 s alt: der Worker war
auch dort nicht der Engpass). **Unter fremder Last:** Lauf 1 lief, während andere Prozesse die
Maschine auslasteten (Lastmittel 8–10 bei 4 Kernen): Alle 240.000 Ereignisse kamen an,
aber Knoten A (der zugleich die Schreibanfragen bediente) fiel zurück: P50 7,6 s, P90
16,0 s, höchstens 19 s; Knoten B blieb bei P50 0,47 s, P90 1,2 s; Schreiben P50 295 ms,
P90 933 ms. Die Ursache ist nicht gesondert gemessen; naheliegend ist, dass die
Zustellung eines Prozesses Ereignis für Ereignis nacheinander prüft und dafür mit den
Schreibanfragen um den Datenbank-Pool und die CPU konkurriert. Ein Knoten, der viele
Schreibanfragen und viele Verbindungen zugleich bedient, ist damit der erste Engpass.

**Nach der Überarbeitung der Zustellung (Stapel, 13.11.2026):** Ein API-Prozess prüft
jetzt alles, was angekommen ist (bis 200 Ereignisse), mit höchstens zwei Abfragen und
verwirft die Warteschlange mit `resync`, wenn sie mehr als 5 s nachhängt. Gemessen ohne
Docker: ein API-Prozess (`HERD_ROLE=api`) und ein Worker an einem lokalen PostgreSQL,
100 Personen mit je einer SSE-Verbindung am selben Prozess, eine von ihnen schreibt
50 Nachrichten je Sekunde über 20 s in einen Team-Kanal, den alle sehen (der Lastgenerator
lief auf derselben Maschine, Lastmittel 2–4,5 bei 4 Kernen):

| Lauf | Schreiben P50 / P95 / max | Zustellung (Senden bis `event:`) P50 / P99 / max | angekommen, `resync` |
|---|---|---|---|
| 1 | 237 / 571 / 741 ms | 408–423 / 1.076–1.100 / 1.262 ms | 1.000 von 1.000 je Verbindung, 0 |
| 2 | 41 / 116 / 389 ms | 109–117 / 431–442 / 541 ms | 1.000 von 1.000 je Verbindung, 0 |

Die Zahlen gelten für die erste und die letzte der 100 Verbindungen. Im Prozess
(`herd_live_delivery_lag_seconds`, vom `NOTIFY` bis zur Übergabe) lagen alle 2.000
Ereignisse unter 1 s, 1.812 unter 250 ms. Zum Vergleich der alte Stand (Ereignis für
Ereignis eine Abfrage) im selben Aufbau, aber unter fremder Last: P50 17,0 s, P99
21,2 s, höchstens 22,3 s, ohne Grenze nach oben. Der Rest der Zustellzeit im Lauf 1 ist
die CPU des API-Prozesses, der zugleich die Schreibanfragen bedient (Schreiben P50
237 ms); nicht profiliert. **Unter fremder Last** (andere Prozesse auf der Maschine,
Schreiben P50 0,5–1,9 s) lag die Zustellung des neuen Stands bei P50 1,0–3,7 s und P99
bis 9,7 s; in zwei Läufen griff die 5-s-Grenze (zweimal bzw. einmal `resync`; 798
bzw. 899 von 1.000 Ereignissen kamen einzeln an, der Rest über das Nachladen).

### Tickets (M4)

Ohne Docker gemessen: ein Prozess mit `HERD_ROLE=all` (API und Worker, ohne Collab-Prozess
in Benutzung) an einem lokalen PostgreSQL 16, **10.000 Tickets in einem Team-Bereich**
(50 Epics, der Rest Aufgaben, Fehler und Stories, über die fünf Standardstatus verteilt,
30 % der Admin-Person zugewiesen, 40 % mit Fälligkeit, die Hälfte unter einem Epic, je 30
Wörter Beschreibung), alle über die API angelegt. Ein Client misst je Endpunkt 200
Anfragen nacheinander nach 10 zum Aufwärmen, dann 10 Clients 20 s lang gleichzeitig.
Lastmittel der Maschine 0,9–1,6 (4 Kerne). „Abfragen“ sind die SQL-Anweisungen je
Aufruf, gezählt im Prozess an derselben Datenbank (davon 3 für Sitzung und Rechte, die
jeder angemeldete Aufruf hat); sie hängen nicht von der Zahl der Tickets ab.

| Funktion | Endpunkt | P50 / P95, 1 Client | Abfragen |
|---|---|---|---|
| Liste eines Bereichs, 50 je Seite (zuletzt geändert) | `GET /api/tickets?space_id=…&limit=50` | 30 / 44 ms | 4 |
| dieselbe nach Priorität / Fälligkeit | `…&sort=priority`, `…&sort=due` | 31 / 42 ms, 29 / 39 ms | 4 |
| dieselbe, 20. Seite über den Cursor | `…&cursor=…` | 28 / 38 ms | 4 |
| nur offene | `…&status_category=open` | 19 / 25 ms | 4 |
| Meine Tickets (der Admin-Person sind 30 % zugewiesen) | `GET /api/tickets?assignee=me&status_category=…` | 24 / 31 ms | 4 |
| Kinder eines Epics | `GET /api/tickets?parent=…` | 14 / 18 ms | 4 |
| Liste mit Volltext (ein Wort, das in fast jeder Beschreibung steht: 30 Wörter je Ticket aus 12) | `GET /api/tickets?space_id=…&q=…` | 34 / 62 ms | 4 |
| Board (5 Spalten zu je 50 Karten mit Anzahl, 151 KB) | `GET /api/spaces/{id}/board?limit=50` | 41 / 58 ms | 7 |
| Board, nächste 50 einer Spalte | `GET /api/spaces/{id}/board/{status_id}?cursor=…` | 19 / 25 ms | 6 |
| Epic-Übersicht (50 Epics mit Fortschritt) | `GET /api/spaces/{id}/epics?limit=50` | 23 / 30 ms | 6 |
| Zähler der Seitenleiste | `GET /api/tickets/counts` | 14 / 19 ms | 3 |
| Suche, nur Tickets | `GET /api/search?q=…&types=ticket&limit=20` | 70 / 102 ms | 3 |

Unter 10 gleichzeitigen Clients (eine Sitzung je Client, kein Fehler): Liste P50 117 ms,
P95 236 ms, 75 Anfragen/s; Board P50 249 ms, P95 524 ms, 34 Anfragen/s. Der Prozess
bediente dabei nur diese Anfragen; die Grenze ist ein Python-Prozess (ein Event-Loop),
mehr Durchsatz gibt es über mehr API-Replikas.

**Anlegen:** 300 Tickets nacheinander mit einem Client 41 je Sekunde (P50 23 ms, P95
32 ms); 9.650 mit 8 Clients gleichzeitig 54 je Sekunde (P50 126 ms, P95 302 ms). Mit
getrenntem API-Prozess und Worker (`HERD_ROLE=api` und `worker`, 3.000 Tickets) 49 je
Sekunde nacheinander und 60 je Sekunde mit 8 Clients (P50 116 ms, P95 261 ms).

**Worker unter Anlagelast:** Ein angelegtes Ticket ergibt 2 bis 3 Ereignisse
(`ticket.created` und je Systemmeldung ein `message.created`), bei 10.000 Tickets 23.054.
In `HERD_ROLE=all` stand die Outbox am Ende der Anlagen bei 9.681 offenen Ereignissen
(der Worker im selben Prozess kam neben der Anlagelast kaum voran) und war 182 s danach
leer. Mit eigenem Worker-Prozess stand sie bei 3.000 Tickets höchstens bei 1.396 und war
32 s nach der letzten Anlage leer; der Worker schaffte also rund 90 Ereignisse je
Sekunde, weniger als die gut 130 je Sekunde, die 60 Anlagen je Sekunde erzeugen.
Folge: Systemmeldungen und Live-Ereignisse kamen bei Massenanlagen über die API später
an; nichts ging verloren.

**Worker mit Bahnen (Review M4 P3, nach M4):** Seit jeder Handler eine eigene Bahn hat
und ein Stapel eine Transaktion ist, verteilt ein Worker deutlich mehr. Messung (ohne
Docker, lokales PostgreSQL 17, Lastmittel 5–9 durch andere Prozesse auf der Maschine):
1.200 Tickets ohne laufenden Worker angelegt (`HERD_ROLE=api`), dann eigene
Worker-Prozesse gestartet und die Zeit gemessen, bis die Outbox leer war (2.401
Ereignisse: die Tickets, ihre Systemmeldungen, ein `access.changed`).

| Worker | vorher (M4) | nachher |
|---|---|---|
| 1 | 96–99 Ereignisse/s | 427–488 Ereignisse/s |
| 2 | 572–613 Ereignisse/s¹ | 707 Ereignisse/s |

¹ Hier gemessen; im Review waren es 226/s. Warum zwei alte Worker hier mehr als das
Fünffache von einem schafften, ist nicht untersucht. Ein Worker braucht nun rund 2,8
Datenbankanweisungen je Ereignis (vorher 8,8) und ist durch die CPU begrenzt (rund
0,6 ms je Anweisung, überwiegend SQLAlchemy). Ein hängender Handler (Sperre auf
`notification` für 45 s) hält die Live-Zustellung nicht mehr auf: Nachrichten kamen nach
0,07–0,17 s im Stream an (vorher nach 30 s bzw. erst nach dem Ende der Sperre). Platz: `work_item` mit 10.000 Tickets 9,5 MB (mit Indizes), die ganze
Datenbank 53 MB (mit 13.054 Systemmeldungen und der Outbox).

### Sprints und Boards (M4b)

Ohne Docker gemessen, 14.11.2026: getrennte Prozesse `HERD_ROLE=migrate`, `api` und
`worker` aus dem Stand von Commit `7957f73` an einer Wegwerf-Datenbank auf dem lokalen
PostgreSQL, Python-Skript mit httpx auf derselben Maschine (nicht eingecheckt). Die
Maschine (4 Kerne) war von anderen Prozessen mitbenutzt, Lastmittel 3,4–5,7 während der
Messung; die Zahlen sind deshalb eher zu hoch als zu niedrig. **Daten**, alle über die
API angelegt: ein Team-Bereich mit **10.000 Tickets** (50 Epics, sonst wie in M4: Art,
Priorität und Status zufällig über die fünf Standardstatus, 40 % mit Fälligkeit, die
Hälfte unter einem Epic, 30 Wörter Beschreibung), 30 % der Admin-Person zugewiesen, 60 %
über 20 weitere Personen verteilt, 10 % niemandem; **3.000 davon im laufenden Sprint**,
ein zweiter Sprint geplant. Da alle Tickets am Messtag angelegt sind, ist in der
Daily-Ansicht jede Karte „geändert“, und „Erledigt“ auf „Mein Board“ zeigt alle
erledigten. Je Endpunkt 200 Anfragen nacheinander nach 10 zum Aufwärmen, dann 10
Clients 20 s lang gleichzeitig. Abfragen gezählt wie in M4 (im Prozess, an derselben
Datenbank, 3 davon für Sitzung und Rechte); sie hängen nicht von der Zahl der Tickets
ab.

| Funktion | Endpunkt | P50 / P95, 1 Client | Antwort | Abfragen |
|---|---|---|---|---|
| Mein Board (4 Spalten zu je 50 Karten mit Anzahl; der Admin-Person sind 3.000 zugewiesen) | `GET /api/tickets/my-board?limit=50` | 96 / 122 ms | 148 KB | 6 |
| Mein Board, nächste 50 einer Spalte | `GET /api/tickets/my-board/{category}?cursor=…` | 78 / 108 ms | 36 KB | 5 |
| Daily, ganzer Bereich (21 Zeilen × 5 Status, je Zelle 20 Karten) | `GET /api/spaces/{id}/board?group_by=assignee&limit=20` | 257 / 434 ms | 1,6 MB | 7 |
| Daily, laufender Sprint (wie die Oberfläche fragt) | `…&group_by=assignee&sprint=…&limit=20` | 207 / 366 ms | 1,4 MB | 7 |
| dasselbe mit 5 Karten je Zelle | `…&limit=5` | 92 / 225 ms | 0,4 MB | 7 |
| Board des Sprints (50 je Spalte) | `GET /api/spaces/{id}/board?sprint=…&limit=50` | 35 / 46 ms | 186 KB | 7 |
| Vorrat (unerledigt, nach Priorität, 50) | `GET /api/tickets?space_id=…&sprint=none&sort=priority&status_category=…&limit=50` | 24 / 32 ms | 35 KB | 4 |
| Sprint-Liste | `GET /api/spaces/{id}/sprints?limit=100` | 7 / 11 ms | 0,5 KB | 4 |

Unter 10 gleichzeitigen Clients (kein Fehler): Mein Board P50 314 ms, P95 621 ms, 29
Anfragen/s; **Daily des Sprints P50 2,2 s, P95 3,3 s, 5 Anfragen/s**. Die Daily-Ansicht
ist die teuerste Ansicht bisher: Ihre Zeit wächst mit der Zahl der gelieferten Karten
(Zeilen × Status × Karten je Zelle; mit 5 statt 20 Karten je Zelle rund ein Drittel der
Zeit und Größe), nicht mit der Zahl der Abfragen. Bei 100 Personenzeilen (der Grenze)
wären es rund fünfmal so viele Karten. Für ein Daily, das ein Team einmal am Tag
gemeinsam öffnet, reicht das; als Ansicht, die viele zugleich offen halten (jedes
Ticket-Ereignis des Bereichs lädt sie neu), wäre eine kleinere erste Seite je Zelle
günstiger.

**Ticket in den Sprint legen:** 3.000 Änderungen mit 8 Clients 58 je Sekunde (P50
133 ms, P95 192 ms); der Worker hielt mit (Outbox 0,3 s nach der letzten Änderung leer).

**Sprint abschließen** (3.000 Tickets im Sprint, 590 erledigt, 628 verworfen, **1.782
unerledigte in den nächsten Sprint**): Die Anfrage dauerte **2,9 s** (eine Transaktion;
die Tickets des Sprints sind so lange gesperrt). Nachbesserung nach dem Modul-Review:
Die Ereignisse gehen in einem INSERT (`emit_many`); 2.000 verschobene Tickets brauchten
im Test (ein Prozess, ASGI ohne Netz) **0,16 bis 0,21 s statt 2,9 bis 3,3 s**. Sie schreibt 1.783 Ereignisse (je
verschobenem Ticket ein `ticket.updated`, dazu `sprint.closed`); daraus schreibt der
Worker 1.782 Systemmeldungen, also noch einmal so viele `message.created`. **Ein
Worker-Prozess hatte alle rund 3.570 Ereignisse 8,5 s nach dem Ende der Anfrage
verteilt** (rund 420 je Sekunde, so viel wie mit Bahnen nach M4 gemessen). Während
dieser Zeit kam eine Erwähnung in einem Kanal nach **183 ms** in der Aktivität der
erwähnten Person an (andere Bahn, wartet nicht); die erste Systemmeldung eines in dieser
Zeit angelegten Tickets dagegen erst nach **7,9 s**, weil sie in derselben Bahn
(`ticket_timeline`) hinter den Systemmeldungen des Abschlusses stand. Platz: Tabelle
`sprint` 96 KB, `work_item` 12 MB, die ganze Datenbank 92 MB (mit rund 25.500
Systemmeldungen und der Outbox).

**Kosten:** Ohne KI-Verbindung ruft die Anwendung keine kostenpflichtigen Dienste auf
(kein externer Speicher). Es fallen nur die Ressourcen unten an, dazu der Platz der
Anhänge auf dem Volume (eine Datei je Inhalt und Organisation, höchstens 25 MiB je
Anhang). Mit KI kosten die Modellaufrufe beim Anbieter (siehe [Agenten (M6)](#agenten-m6)).

**Engpass Anmeldung:** Die Passwortprüfung ist argon2id (64 MiB, 3 Durchläufe,
4 Lanes) und läuft in Worker-Threads, höchstens `HERD_PASSWORD_HASH_CONCURRENCY`
(Standard 2) gleichzeitig je Prozess; höchstens `HERD_PASSWORD_HASH_QUEUE` (Standard
16) Anfragen je Prozess warten, weitere bekommen sofort 429 `server.busy` mit
`Retry-After: 1`. Eine wartende oder prüfende Anfrage hält weder eine
Datenbankverbindung noch eine Sperre; eine abgewiesene kostet keine Abfrage. Gemessen
hier: 10 Anmeldungen je Sekunde bei rund 3 Kernen. In M1 waren es 14–16 je Sekunde, als
argon2 noch im Event-Loop lief und dabei alle anderen Anfragen blockierte (die
Bereichsliste brauchte unter Anmeldelast damals 249 ms im Median, jetzt 127 ms). Dass
der geringere Anmeldedurchsatz an der Begrenzung auf zwei gleichzeitige Prüfungen
liegt, ist naheliegend, aber nicht gesondert gemessen. Je Client-Adresse (IPv6: je /64)
sind höchstens `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE` (Standard 30) Anmeldeversuche je
Minute erlaubt, fehlgeschlagene je Adresse und E-Mail höchstens
`HERD_LOGIN_RATE_LIMIT_PER_MINUTE` (Standard 5); in der Messung waren beide
hochgesetzt. Ein Live-Test aus M1 (200 gleichzeitige Fehlanmeldungen von 200 Adressen:
18 × 401, 182 × 429 in 2,0 s, `/ready` höchstens 649 ms, kein 503) ist nicht wiederholt
worden.

### Agenten (M6)

Ohne Docker gemessen, 14.11.2026: getrennte Prozesse `HERD_ROLE=migrate`, `api` und ein
oder zwei `worker` aus dem Stand von Commit `c1e700a` an einer Wegwerf-Datenbank auf dem
lokalen PostgreSQL. Als Anbieter diente der Stub aus den Tests
(`backend/tests/support/openai_stub.py`, eigener Prozess, Verbindung der Art `local`).
Gemessen hat ein Python-Skript mit httpx und asyncpg auf derselben Maschine (nicht
eingecheckt). Die Maschine (4 vCPU) war von anderen Prozessen mitbenutzt: Lastmittel
0,4–2 zu Beginn, 5–6 während einiger Durchläufe.

**Daten**, über die API angelegt:

- 20 Agenten (Stufe 1, `HERD_RUN_CONCURRENCY` 4, Sperrfrist 30 s) und 10 Personen;
- 200 Direktnachrichten Person–Agent;
- 5 veröffentlichte Seiten in einem offenen Bereich, damit `search` etwas findet;
- eine Verbindung mit `max_concurrency` 100 und `requests_per_minute` 100.000, damit
  ihre Grenzen nicht bremsen.

Der Stub antwortet sofort (dann zeigt die Messung die Arbeit des Servers) oder nach 1 s
(ein langsamer Anbieter, ohne Netz). Die Zeit eines echten Modells kommt zu allen
Zahlen hinzu, ebenso seine Kosten.

**Antwortzeit**: je 30 Läufe nacheinander, ein Worker, Stub ohne Verzögerung. „Client“
misst vom Absenden der Nachricht, bis `GET /api/runs/{id}` „fertig“ meldet (Abfrage alle
20 ms). „Server“ ist `finished_at − created_at` des Laufs.

| Lauf | Client P50 / P95 / max | Server P50 / P95 / max |
|---|---|---|
| 1 Schritt (Antwort) | 194 / 254 / 552 ms | 143 / 175 / 462 ms |
| 5 Schritte (4 × `search`, dann Antwort) | 537 / 719 / 795 ms | 488 / 644 / 742 ms |

Jeder weitere Schritt kostet also rund 85 ms Arbeit des Servers: Antwort einspielen,
Journal schreiben, Rechte und Richtlinie prüfen, `search` ausführen.

**200 Läufe in der Warteschlange**: 200 Nachrichten in 200 Direktnachrichten, je 20
zugleich abgeschickt (4,7–7 s für alle 200), danach erst die Worker gestartet. Läufe je
Minute = 200 / (erster Start bis letztes Ende).

| Worker | Stub | Läufe zugleich | Läufe/min | Dauer | höchstens laufend | Laufdauer P50 / P95 (Start bis Ende) | Worker-RSS max |
|---|---|---|---|---|---|---|---|
| 1 | sofort | 4 | 581 und 538 (2 Durchläufe) | 20,7 / 22,3 s | 4 | 343 / 482 ms, 368 / 545 ms | 208 / 210 MiB |
| 2 | sofort | 4 je Worker | 1.055 und 1.052 | 11,4 s | 8 | rund 365 / 494 ms | 199–205 MiB je Worker |
| 1 | 1 s | 4 | 196 | 61,2 s | 4 | 1.163 / 1.325 ms | 234 MiB |
| 2 | 1 s | 4 je Worker | 366 | 32,8 s | 8 | 1.207 / 1.432 ms | 210 / 217 MiB |
| 1 | 1 s | 16 | 553 | 21,7 s | 16 | 1.502 / 1.796 ms | 249 MiB |

- In jedem Durchlauf endeten alle 200 Läufe mit genau einer Antwort, jeder im ersten
  Versuch.
- Vom Start des Workers bis zum ersten Lauf vergingen 2,2–2,4 s (Start des Prozesses).
- Ein zweiter Worker verdoppelt den Durchsatz fast. Bei einem langsamen Anbieter
  bestimmt `HERD_RUN_CONCURRENCY` den Durchsatz: 4 Läufe zugleich mit je 1 s ergeben
  3,3 je Sekunde, 16 zugleich fast das Dreifache.
- Die Grenzen der Verbindung (`max_concurrency`, `requests_per_minute`) bremsen hier
  nicht; im Betrieb tun sie es, und sie gelten über alle Worker.

**Neustart nach Absturz**: Worker 1 bearbeitet einen Lauf, Worker 2 läuft daneben.
Worker 1 wird mit SIGKILL beendet, während sein Anbieteraufruf unterwegs ist.

| Fall | Sperrfrist | Wiederaufnahme nach dem Kill | fertig nach dem Kill |
|---|---|---|---|
| 1 Schritt, 3 × | 30 s | 26,8–26,9 s | 27,2–27,3 s |
| 5 Schritte, Kill während Aufruf 3, 2 × | 30 s | 30,6–30,7 s | 31,3 s |
| 1 Schritt, 3 × | 6 s | 4,5–6,4 s | 5,1–6,9 s |

- In den Fällen mit 30 s endete jeder Lauf im zweiten Versuch (`recoveries` 1) mit genau
  einer Antwort; die Fälle mit 6 s zeigen nur, dass die Zeit mit der Sperrfrist sinkt.
- Im Fall mit 5 Schritten blieben die Journaleinträge des ersten Versuchs (`seq` 1–4)
  stehen, der zweite setzte mit `seq` 5–7 fort.
- Wiederholt wurde nur der verlorene Anbieteraufruf: im Fall mit einem Schritt 2
  Aufrufe statt 1. Im Fall mit 5 Schritten verbrauchte der verlorene Aufruf eine der
  vorbereiteten Antworten des Stubs; der Lauf hatte deshalb 4 Schritte mit 5 Aufrufen.
  Mit einem echten Anbieter wären es 5 Schritte mit 6 Aufrufen.
- Die Wiederaufnahme hängt an der Sperrfrist: Sie wird alle 10 s erneuert, also kommt
  ein anderer Worker 20 bis 30 s nach dem Absturz zum Zug, dazu eine Runde seiner
  Schleife.

**Journal**: über alle 2.668 Läufe der Messung (5.588 Einträge).

| Lauf | Einträge `run_event` | Byte je Lauf (Zeilen) | davon JSON-Inhalt |
|---|---|---|---|
| 1 Schritt | 2 (Modellaufruf, Stopp) | rund 440 | rund 190 |
| 5 Schritte | 10 | rund 3,7 KB | rund 2,1 KB |

- Die Tabelle `run_event` belegte mit Indizes 2,3 MB, rund 900 Byte je Lauf.
- Dazu je Modellaufruf ein Eintrag `usage_record` (über alle Läufe der Messung 1,05 je
  Lauf, die meisten mit einem Schritt).
- Echte Läufe sind größer: Antworten und Werkzeugergebnisse stehen vollständig im
  Journal, eine gelesene Seite also ganz. Ein Lauf braucht mindestens so viel Platz wie
  alle seine Werkzeugergebnisse zusammen.
- Läufe und Journal werden nicht automatisch gelöscht.

**Worker-Speicher**: im Leerlauf 173 MiB RSS (30 s nach `/ready`). In M3 waren es
104 MiB. Den Unterschied machen vermutlich die Bibliotheken der Laufschleife (Pydantic AI,
OpenAI-Client); einzeln gemessen ist das nicht. Unter Last mit 4 Läufen zugleich bis
234 MiB, mit 16 zugleich bis 249 MiB.

**Kosten**: Jeder Modellaufruf kostet beim Anbieter Token. Die Anwendung bucht sie je
Aufruf (`usage_record`, mit Preis, wenn an der Verbindung einer hinterlegt ist) und
zeigt sie unter `GET /api/ai/usage` ([`KI.md`](KI.md#verbrauch-apiaiusage)). Ein Lauf
mit n Schritten macht n Modellaufrufe; dazu kommt höchstens ein wiederholter Aufruf je
Absturz.

### Automatisierung (M7)

**Lokale Messung** ohne Docker, 14.11.2026: getrennte Prozesse `HERD_ROLE=migrate`,
`api` und ein oder drei `worker` aus dem Stand von Commit `90da855` an einer
Wegwerf-Datenbank auf dem lokalen PostgreSQL (Port 5433), der Stub aus den Tests als
Anbieter (eigener Prozess, Verbindung der Art `local`, antwortet sofort). Angelegt über
die API: die Inhaberin, die Verbindung als Standard, ein aktiver Agent und ihre
Direktnachricht mit ihm. Die Aufgaben, Seiten und Verbrauchszeilen der Messung hat ein
Python-Skript direkt in die Datenbank geschrieben (an der API vorbei, also auch an der
Obergrenze `HERD_AI_AUTOMATIONS_MAX`); dasselbe Skript hat gemessen (SQLAlchemy, httpx,
`/proc/<pid>/status` alle 0,25 s; nicht eingecheckt). Die Maschine (4 vCPU) war von
anderen Prozessen mitbenutzt; das Lastmittel steht bei jeder Zeile.

**1.000 Aufgaben zugleich fällig.** 1.000 wiederkehrende Aufgaben (täglich, Ort die
Direktnachricht, eine Eigentümerin, ein Agent), alle fällig zum selben Zeitpunkt T,
20 s nach dem Start der Worker. „Verzug“ ist `fired_at − due_at` des Termins im
Protokoll, „fertig“ das Ende des letzten Laufs nach T. Jeder Worker arbeitete die
gestarteten Läufe zugleich ab (`HERD_RUN_CONCURRENCY` 4).

| Worker | Verzug P50 / P95 / max | alle Läufe fertig | Gauge `herd_automations_oldest_due_seconds` max | Termine je Worker | Worker-RSS Leerlauf / max | Lastmittel |
|---|---|---|---|---|---|---|
| 1 | 52,1 / 98,4 / 103,6 s (ein zweiter Durchlauf: 102,6 s max) | 133,5 s | 101 s | 1.000 | 174 / 229 MiB | 1,1 → 1,6 |
| 3 | 26,0 / 45,6 / 47,9 s | 66,7 s | 40 s | 310 / 365 / 325 | 173–174 / 220–223 MiB | 1,6 → 4,5 |
| 3 | 32,3 / 62,5 / 65,4 s | 87,7 s | 61 s | 360 / 336 / 304 | 173–174 / 221–225 MiB | 4,5 → 8,2 |

- **Genau einmal**, in jedem der vier Durchläufe: 1.000 Termine im Protokoll für 1.000
  verschiedene Aufgaben, alle `started`; 1.000 Läufe, jeder genau einem Termin
  zugeordnet (`automation_firing.run_id`), keine Aufgabe mit mehr als einem Lauf, alle
  Läufe `completed`. Bei drei Workern summieren sich ihre Zähler
  `herd_automation_firings_total{outcome="started"}` auf genau 1.000.
- Der erste Termin wartete 0,3–0,6 s: Die Fälligkeits-Schleife schaut alle 5 s nach und
  arbeitet danach ohne Pause, solange sie volle Stapel (50) findet.
- **Wohin die Zeit geht:** Allein, ohne Laufschleife daneben (dieselbe
  Fälligkeits-Schleife in einem eigenen Prozess), feuert ein Worker einen Termin in
  21 ms (1.000 in 20,9 s): Rechte der Eigentümerin, Budgetprüfung, Lauf, Protokoll und
  nächster Termin in einer Transaktion. Im Worker teilt sie sich die Event-Loop mit der
  Laufschleife, die die eben gestarteten Läufe schon abarbeitet (der Stub antwortet
  sofort, die Läufe sind reine Rechenarbeit); dann sind es rund 100 ms je Termin. Mit
  einem echten Anbieter warten die Läufe meist auf das Netz, und die Schleife feuert
  schneller.
- Drei Worker teilen sich die Termine (`SKIP LOCKED`) und brauchen etwa die Hälfte der
  Zeit; die Maschine hatte für drei Worker, API und PostgreSQL nur 4 vCPU.
- Der Alarm `HerdAutomationsLagging` (ältester fälliger Termin über 3 Minuten, 5 Minuten
  lang) bleibt bei 1.000 Terminen auf einmal und einem Worker still; nach diesen Zahlen
  meldet er sich bei einem Worker ab etwa 2.000 zugleich fälligen Terminen, die länger
  als 5 Minuten anstehen.

**Kosten der Budgetprüfung je Modellaufruf.** `budget_exhausted` vor jedem Aufruf, im
Prozess gemessen (300 Aufrufe je Fall, je eine Transaktion), mit 100.000
Verbrauchszeilen des Tages und 100.000 des Vortags in der Organisation; Budgets so
hoch, dass keines erreicht ist (dann werden alle Summen gebildet).

| Fall | P50 / P95 / max | Lastmittel |
|---|---|---|
| kein Budget (eine Abfrage über `ai_budget`) | 1,3 / 1,9 / 25 ms | 6 |
| Budgets für Organisation, Person und Agent; alle 100.000 Zeilen des Tages von dieser Person und diesem Agenten | 83 / 203 / 258 ms (erster Durchlauf: 72 / 108 / 123 ms) | 6–7 |
| dieselben drei Budgets; die Zeilen verteilt (2 % der Person, 5 % des Agenten) | 63 / 94 / 116 ms | 6 |
| Budgets nur für Person und Agent, Zeilen verteilt | 14 / 18 / 84 ms | 6 |

- Die Summe der Organisation liest jede Zeile des Tages (Plan: paralleler Seq Scan,
  rund 25 ms für 100.000 Zeilen); die Summen von Person und Agent gehen über ihre
  Indizes (rund 5 ms für 6.000 Zeilen).
- **Bewertung:** Eine Summentabelle ist für M7 nicht nötig. Ohne Budget kostet die
  Prüfung eine indizierte Abfrage; mit Budgets für Personen und Agenten bleibt sie klein.
  Ein Budget der Organisation kostet mit jeder Zeile des Tages mehr: bei 100.000
  Modellaufrufen am Tag im Mittel des Tages rund 35 ms Datenbankzeit je Aufruf (gegen
  Sekunden für den Aufruf selbst). Wer deutlich mehr Aufrufe am Tag mit einem Budget der
  Organisation erwartet, braucht eine Tagessumme (Tabelle oder deckender Index); das
  ist ein Folgepunkt, nicht gebaut.

**Prüfdurchlauf über 10.000 fällige Seiten.** 10 Team-Bereiche mit Prüffrist 30 Tage,
die Inhaberin jeweils Admin (Moderatorin), je 1.000 veröffentlichte Seiten, zuletzt vor
31 Tagen geprüft. Ein Worker, danach gestartet.

| Was | Zeit |
|---|---|
| Durchlauf fertig (alle 10 Bereiche für heute geprüft, 10.000 Ereignisse `page.review_due`) | 8,8 s nach dem Start des Workers (darin rund 2,5 s Prozessstart); die Ereignisse entstanden in 6,0 s (erster Durchlauf: 5,1 s) |
| Outbox leer (je Seite ein Eintrag im Seiten-Thread und eine Aktivität, dazu der Blick der Ereignis-Regeln) | 172 s nach dem Start (Zustellung über 168 s; erster Durchlauf 167 s) |
| `herd_outbox_oldest_pending_seconds` max | 154 s |
| Worker-RSS max | 182 MiB |

- Ergebnis: 10.000 verschiedene Seiten erinnert, 10.000 Einträge in den Seiten-Threads,
  10.000 Aktivitäten, je Seite genau einmal. Lastmittel 4,7 → 1,5.
- Der Durchlauf selbst ist schnell (Stapel von 100 Seiten je Transaktion); die Arbeit
  liegt bei den Handlern der Outbox (rund 60 Ereignisse je Sekunde mit einem Worker).
  Bei 10.000 Seiten, die am selben Tag fällig werden, bleibt `HerdOutboxBacklog`
  (5 Minuten) still; ab etwa 20.000 am selben Tag würde er mit einem Worker kurz
  anschlagen. Mehr Worker teilen sich die Bahnen der Outbox.

**Worker-Speicher**: Leerlauf 173–174 MiB wie in M6; mit 1.000 Terminen und ihren
Läufen bis 229 MiB, beim Prüfdurchlauf bis 182 MiB. Die Empfehlung für den Worker
bleibt (Limit 384Mi).

**Platz**: je Termin eine Zeile `automation_firing` (mit dem Auftragstext, wenn ein Lauf
startete), je aufgenommenem Ereignis eine Zeile `automation_event` (nur IDs). Der Worker
löscht Ereignisse 7 Tage nach ihrem Termin und Termine nach 90 Tagen, nie solange ihr
Lauf noch offen ist ([`AGENTEN.md`](AGENTEN.md#aufbewahrung)). Läufe und ihr Journal
bleiben wie in M6.

**Zeitzonen**: Termine rechnet `zoneinfo` aus der Standardbibliothek. Das Basis-Image
(`python:3.13-slim` mit dem Digest aus dem `Dockerfile`) bringt die Zonendaten von
Debian mit (Paket `tzdata` 2026f, geprüft am 14.11.2026); das Python-Paket `tzdata`
(Laufzeitabhängigkeit, Apache-2.0) ist der Rückfall, wo ein System keine hat. Das Image
braucht nichts weiter; neue Zonenregeln kommen mit einem neuen Basis-Digest.

### MCP (M8)

**Lokale Messung** ohne Docker, 15.11.2026: ein Prozess `HERD_ROLE=all` (API und
Worker in einem Prozess, ohne Collab-Prozess) aus dem Stand von Commit `df90369` (der
Code von `/mcp` ist seit Task 4 von M8 unverändert) an einer Wegwerf-Datenbank auf dem
lokalen PostgreSQL 16.15 (Port 5433), `HERD_MCP_RATE_PER_MINUTE=10000`, damit die
Ratenbegrenzung nicht bremst (Standard 120 je Token und Minute). Angelegt über die API:
ein Team-Bereich mit 100 veröffentlichten Seiten (je rund 2 KB Text) und 50 Tickets,
der MCP-Schalter an, ein `read`-Token für „alle meine Bereiche“ (drei Bereiche).
Gemessen hat ein Python-Skript (httpx, ein Prozess, auf derselben Maschine; nicht
eingecheckt): je Fall 20 Aufrufe zum Aufwärmen, dann 500 Aufrufe nacheinander
(1 Client) bzw. 2.000 mit 10 gleichzeitigen Clients auf einem Token, jeder ein
`POST /mcp` mit einer JSON-RPC-Nachricht ohne `initialize` (zustandslos); `read_page`
reihum über die 100 Seiten, `search` reihum über 12 Wörter, die in vielen Seiten stehen.
CPU und RSS des App-Prozesses aus `/proc/<pid>/stat` und `/proc/<pid>/status`. Die
Maschine (4 vCPU Intel Xeon @ 2,10 GHz, 16 GB RAM) war von anderen Prozessen
mitbenutzt; das Lastmittel steht bei jedem Lauf. Zwei Läufe.

| Fall | Lauf 1 (Lastmittel 4–6): P50 / P95 / max | je s | CPU | Lauf 2 (Lastmittel 6–9): P50 / P95 / max | je s |
|---|---|---|---|---|---|
| `tools/list`, 1 Client | 22,6 / 35,9 / 57 ms | 42 | 68 % | 25,9 / 41,6 / 338 ms | 35 |
| `read_page`, 1 Client | 24,4 / 38,4 / 57 ms | 38 | 69 % | 31,5 / 47,6 / 68 ms | 30 |
| `search`, 1 Client | 33,2 / 46,0 / 345 ms | 28 | 64 % | 44,5 / 63,6 / 114 ms | 22 |
| `tools/list`, 10 Clients | 139 / 182 / 406 ms | 69 | 98 % | 176 / 244 / 622 ms | 54 |
| `read_page`, 10 Clients | 174 / 234 / 622 ms | 55 | 92 % | 177 / 241 / 485 ms | 54 |
| `search`, 10 Clients | 225 / 309 / 708 ms | 43 | 86 % | 205 / 287 / 505 ms | 46 |

100 % CPU = ein Kern (Lauf 2 ähnlich: 50–98 %). Zum Vergleich im selben Prozess:
`GET /api/spaces` mit Sitzung, nacheinander, P50 9,2 ms / P95 15,0 ms.

- **Wohin die Zeit geht:** Jeder Aufruf löst das Token neu auf (Suche nach dem Hash,
  Rechte und Umfang), zählt die Ratenbegrenzung in PostgreSQL (eine Schreibtransaktion
  mit Commit), baut einen Server des MCP-SDK für diese eine Anfrage, ruft das Werkzeug
  über dieselben Dienste wie die REST-API und schreibt die Zeile `mcp_call`. Ein Aufruf
  kostet so rund das 2,5-Fache eines gewöhnlichen lesenden REST-Aufrufs.
- **Mit 10 Clients ist der Prozess an einem Kern** (eine Event-Loop): Der Durchsatz
  liegt bei 45–70 Aufrufen je Sekunde, die Latenz wächst mit der Warteschlange.
  `/mcp` hält nichts im Prozess, mehr API-Pods teilen sich die Last also ohne
  Abstimmung; die Ratenbegrenzung zählt über alle Pods in PostgreSQL.
- **Ein Client wie Claude Code** ruft Werkzeuge nacheinander und selten (Sekunden
  zwischen den Aufrufen, während das Modell denkt); bei 120 Aufrufen je Token und
  Minute (2 je Sekunde) kostet ein solcher Client einen Bruchteil eines Kerns.
- **Speicher:** RSS des Prozesses 225–237 MiB vor den Läufen (nach dem Anlegen der
  Daten), höchstens 238 MiB unter Last: Die Aufrufe halten nichts fest.
- **Platz:** je Werkzeugaufruf eine Zeile `mcp_call` (nur IDs, Werkzeug, Ergebnisart,
  Dauer); nach beiden Läufen 10.164 Zeilen. Sie werden nicht automatisch gelöscht
  (wie das Audit); bei dauerhaft vielen Aufrufen wächst die Tabelle um eine kleine
  Zeile je Aufruf.
- **Externe MCP-Server** (die eigenen Agenten als Client) sind nicht gemessen: Ihre
  Dauer bestimmt der fremde Server (Zeitlimit 60 s je Aufruf); jeder Aufruf öffnet
  eine neue Verbindung, liest die Werkzeugliste und ruft dann auf (drei bis vier
  Anfragen je Aufruf, Task 6).

## Abhängigkeiten

| Dienst | Pflicht | Hinweis |
|---|---|---|
| PostgreSQL ≥ 16 | ja | Zustandsablage (Daten, Sitzungen, Ratenlimits, Sperren, Volltextindex, Yjs-Stände der Live-Bearbeitung). Compose und Chart nutzen `pgvector/pgvector:pg17` per Digest; M2 braucht pgvector noch nicht |
| Volume für `/data` | ja (mit Anhängen) | Anhänge und temporäre Dateien von Upload, Import und Export. Compose: Volume `app-data`; Chart: PVC `<release>-data`, voreingestellt **ReadWriteMany** (alle API-Replikas schreiben); ohne RWX-Speicherklasse `api.replicas=1` und `persistence.accessModes={ReadWriteOnce}` |
| Worker | für Live-Zustellung, Benachrichtigungen, Systemmeldungen | im selben Image (`HERD_ROLE=worker`, in `all` enthalten); nur Datenbank, keine eingehenden Anfragen außer 9090. Ohne Worker gehen keine Nachrichten verloren, aber nichts kommt live an, bis einer läuft |
| Collab-Prozess | für Live-Bearbeitung | im selben Image (Node 22, Hocuspocus); spricht nur mit der API (`/internal/collab/*` auf 9090, Token `HERD_INTERNAL_TOKEN` und seit M9 je Verbindung eine kurzlebige Berechtigung `herd_cg_…` für genau eine Seite und Generation statt des Sitzungs-Cookies), speichert nie selbst in die Datenbank. Ohne Token ist die Live-Bearbeitung aus, der Markdown-Editor geht weiter |
| Volume für Sicherungen (seit M9) | für Sicherungen | Archive von `python -m app.ops backup …`; Compose: Volume `backups` des Dienstes `backup`; Chart: PVC `<release>-backups` des CronJobs (`backup.persistence.*`, bleibt beim Deinstallieren). Archive sind unverschlüsselt: wie die Datenbank schützen |
| restic-Repository (seit M9) | nein | Offsite-Kopie der Archive (`HERD_BACKUP_OFFSITE_REPOSITORY`, S3, B2, SFTP …), clientseitig verschlüsselt; ausgehend nur vom Sicherungsdienst bzw. -Job; Chart: `backup.offsite.egress` |
| OIDC-Anbieter (seit M9) | nein | Anmeldung über Google oder einen eigenen Anbieter (Keycloak, Entra ID …); ausgehend nur von der API (Discovery, Token-Endpunkt, JWKS) über die SSRF-Sperre, nie über den KI-Proxy; private Hosts nur aus `HERD_OIDC_ALLOWED_HOSTS`; Chart: `oidc.egress`. Ohne Anbieter gilt die Anmeldung mit Passwort |
| OTLP-Collector | nein | Tracing nur, wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist (Chart: `tracing.otlpEndpoint`) |
| Prometheus | nein | scrapt `/metrics` auf 9090; ServiceMonitor und PrometheusRule im Chart |
| kube-state-metrics | nur für Alarm | `HerdNotReady` braucht es |
| KI-Anbieter (OpenAI-Protokoll) | nein (nur für KI) | ausgehend von API (Verbindungstest, Modellliste) und Worker (Läufe), nur zu Verbindungen, die ein Admin anlegt, über die SSRF-Sperre oder `HERD_AI_EGRESS_PROXY`; Chart: `networkPolicy.aiEgress`. Ohne Anbieter läuft alles außer KI |
| Externe MCP-Server und OAuth-Anbieter (seit M8) | nein | ausgehend von API (Werkzeuglisten, Test, OAuth-Code und -Erneuerung) und Worker (Werkzeugaufrufe in Läufen, Erneuerung), nur zu Servern und OAuth-Clients, die ein Admin anlegt, nur https, über die SSRF-Sperre oder `HERD_AI_EGRESS_PROXY`; private Hosts nur aus `HERD_MCP_ALLOWED_HOSTS` (direkt, nicht über den Proxy); Chart: `networkPolicy.aiEgress`. Ohne sie läuft alles außer den externen Werkzeugen |
| MCP-Clients (seit M8) | nein | eingehend auf `/mcp` (Port 8080, Bearer-Token); nichts davon nötig für den Betrieb |

Keine ausgehenden Verbindungen zu Dritten außer zu angelegten KI-Verbindungen (siehe
[`KI.md`](KI.md#ausgehende-aufrufe-ssrf-sperre)) und seit M8 zu angelegten MCP-Servern
und OAuth-Anbietern ([`MCP.md`](MCP.md#betrieb)), keine Drittanbieter-Anfragen im Browser.
Die API-Dokumentation `/api/docs` (Swagger UI, lädt ihre Skripte von einem CDN) gibt
es deshalb nur außerhalb von `HERD_ENVIRONMENT=production`; das Image setzt
`production`. Das OpenAPI-Dokument `/api/openapi.json` bleibt immer erreichbar.

## Clusterfähigkeit

- **Zustandslos:** Sitzungen, Login-Ratenlimit und Sperren liegen in PostgreSQL; jede
  Replika kann jede Anfrage bedienen. Chart-Standard: 2 API-Replikas. Anhänge liegen
  auf einem Volume (`/data`), das alle API-Replikas teilen (Chart: PVC mit
  `ReadWriteMany`).
- **Autoskalierung und Wartungen (M9):** Auf Wunsch je ein HorizontalPodAutoscaler
  (`autoscaling/v2`, CPU-Ziel 70 % des Requests) für API (2 bis 6 Pods) und Worker
  (1 bis 3), Standard aus; herunter höchstens ein Pod je 2 Minuten. PodDisruptionBudgets
  (`maxUnavailable: 1`, nicht bereite Pods dürfen immer gehen) für API und Worker ab
  zwei Pods; der Collab-Prozess (eine Replika) bekommt keins. Die Grenzen (API 2 bis 6,
  Worker 1 bis 3) bleiben nach dem Lasttest: Zwei API-Prozesse tragen die Referenz
  (200 Personen, 95 Anfragen/s) an der Grenze der Ziele, sechs also rund das Dreifache
  (im Cluster nicht gemessen). **Datenbankverbindungen (gemessen, M9):** je API- oder
  Worker-Prozess ein Pool von 5, unter Last bis 15 (SQLAlchemy: `pool_size` 5,
  `max_overflow` 10), dazu eine für LISTEN, also höchstens 16. Gemessen in
  `pg_stat_activity` mit 2 API und 1 Worker ([Lasttest](#gemessen-lasttest-mit-200-personen-m9)):
  10 nach dem Start (API je 2, Worker 6), 18 mit 200 angemeldeten Personen und offenen
  Streams (API je 6), unter Last bis 33 (API je 16: der Pool war in Spitzen ausgeschöpft;
  Worker 6, ohne Agenten-Läufe). Die 16 je API-Pod werden also wirklich erreicht. Mit den
  Obergrenzen 6 API + 3 Worker: in Ruhe rund 54, in der Spitze bis 144, mit Backup-Job
  (Engine und `pg_dump`) und Migrations-Job rund 150. PostgreSQL erlaubt ab Werk 100:
  Für die vollen Grenzen `max_connections` ≥ 160 oder kleinere `maxReplicas`. Das
  mitgelieferte PostgreSQL des Charts läuft mit `postgresql.maxConnections` (Standard
  200, als Serverargument); das Chart rendert nicht, wenn 16 × (höchste Zahl der API-
  und Worker-Pods) + 10 darüber liegt (Chart-Regel in `chart-rules-scaling.sh`). Bei
  einer externen Datenbank kennt das Chart die Grenze nicht. Kein
  PgBouncer im Chart (`HERD_DB_PGBOUNCER` aus 12.4 entsteht erst mit einem Leser).
- **Collab-Prozess (Live-Bearbeitung):** genau eine Replika mit `strategy: Recreate`
  (Spezifikation 12.4, Stufe 1). Ein Live-Dokument liegt im Speicher dieses Prozesses;
  zwei Prozesse würden die Bearbeitenden einer Seite aufteilen. Der Zustand wird über
  die API in PostgreSQL gespeichert (spätestens 10 s nach einer Änderung und beim
  Beenden); nach einem Neustart verbinden sich die Browser selbst neu. Ungespeicherte
  Änderungen der letzten Sekunden (höchstens 10 s) im Speicher des Prozesses gehen dabei
  verloren, sofern kein Browser sie wieder einspielt. Mehrere Collab-Instanzen
  (Spezifikation 12.4, Stufe 2) kommen mit M9b Task 15, ohne Redis/Valkey: Jede Seite
  wird in PostgreSQL an eine Instanz gebunden (Plan M9, Entscheidung 17; Abweichung von
  12.4).
- **Mehrere API-Knoten und Live-Zustellung (M3):** Eine Nachricht, die an einem Knoten
  geschrieben wird, kommt an den SSE-Verbindungen jedes Knotens an (`NOTIFY herd_live`,
  jeder API-Prozess lauscht mit einer eigenen Datenbankverbindung außerhalb des Pools);
  Sticky Sessions sind nicht nötig. Geprüft mit zwei echten Prozessen
  (`tests/test_live_two_nodes.py`, `docs/demo/m3.md`) und in der CI mit
  `SMOKE_NODES=1 bash deploy/compose/smoke.sh`. Die Grenze von 5 Verbindungen je
  Anmeldung gilt je API-Prozess. Bei SIGTERM schließt die API ihre Verbindungen zuerst;
  die Browser verbinden sich nach 5 s mit einem anderen Pod und laden nach.
- **Worker (M3, Bahnen seit Review M4 P3):** beliebig viele Replikas (getrennte Zeilen
  per `SKIP LOCKED`, Zustellung mindestens einmal, Wirkung genau einmal, Handler
  idempotent; geprüft mit zwei Verteilern, auch mit scheiternden Nachbarn im Stapel, und
  mit einem Verteiler, der mitten im Handler abgeschossen wird). Je Worker bis zu eine
  Datenbankverbindung je Handler (zurzeit fünf), eine fürs Verteilen, eine für die
  Metriken und eine für LISTEN. **Läufe der Agenten (M6):** Jeder Worker beansprucht
  Läufe per `SKIP LOCKED` mit einer Sperrfrist (`HERD_RUN_LEASE_SECONDS`, alle Drittel
  erneuert), höchstens `HERD_RUN_CONCURRENCY` zugleich, dafür bis zu so vielen
  Datenbankverbindungen mehr plus drei. Stirbt ein Worker, nimmt ein anderer seine Läufe
  nach Ablauf der Sperrfrist auf und setzt sie aus dem Journal fort (gemessen
  27–31 s bei 30 s Sperrfrist). Je Thread höchstens ein offener Lauf, gesichert durch
  eindeutige Teilindizes, nicht durch eine Sperre im Speicher. **Aufgaben (M7):** Jeder
  Worker feuert fällige Termine per `SKIP LOCKED`, je Termin eine Transaktion (Lauf oder
  Vermerk, Protokoll, nächster Termin); ein eindeutiger Index je Aufgabe und Termin sichert
  es zusätzlich. Gemessen: drei Worker, 1.000 zugleich fällige Termine, genau 1.000
  Läufe, keiner doppelt ([Automatisierung (M7)](#automatisierung-m7)). Der tägliche
  Prüfdurchlauf der Wiki-Seiten beansprucht Bereiche ebenso. Kein DBOS, kein
  Leader-Prozess.
- **MCP (M8):** `/mcp` ist zustandslos (keine Sitzungen, keine Streams, je `POST` eine
  Antwort); jeder API-Knoten beantwortet jede Anfrage, Sticky Sessions sind nicht
  nötig. Token, Ratenbegrenzung, OAuth-`state` und PKCE-Prüfwerte liegen in
  PostgreSQL; die Erneuerung eines OAuth-Tokens sperrt die Zeile des Konnektors, sodass
  von zwei Workern nur einer den Anbieter fragt (geprüft mit echten Commits).
- **Erststart:** Das Anlegen der Organisation und der ersten Person ist über eine
  Advisory-Sperre gegen gleichzeitig startende Replikas geschützt.
- **Migrationen:** Im Cluster ein Job (`HERD_ROLE=migrate`); mit externer Datenbank als
  `pre-install,pre-upgrade`-Hook. `/ready` bleibt während eines Upgrades bereit, wenn
  die Datenbank schon neuer ist als der Code (Migrationen nach expand/contract).
- **Ein Prozess je Pod** (zwei Uvicorn-Server in einer Event-Loop). Mehrere Uvicorn-
  Worker würden `PROMETHEUS_MULTIPROC_DIR` brauchen; das Chart nutzt keine.
- **Pod Security „restricted“:** uid 10001, nur lesbares Root-Dateisystem (`/tmp` als
  `emptyDir`), keine Capabilities. SIGTERM über tini, geordnetes Herunterfahren
  (gemessen in M1/Task 11: `docker compose stop app` in 0,7 s).

## Zeitpläne

Ein CronJob im Chart: die Sicherung (M9, `backup.schedule`, Standard 02:30 UTC; in
Compose der Dienst `backup`, [`SICHERUNG.md`](SICHERUNG.md)). Die **Fälligkeits-Schleife** jedes Workers (M7) schaut alle 5 s nach
fälligen Terminen der Aufgaben (bis 50 je Durchlauf, ohne Pause weiter, solange es mehr
gibt), geht in jeder Runde bis zu 20 Schritte des täglichen Prüfdurchlaufs der
Wiki-Seiten (ein Bereich je Schritt, höchstens einmal je UTC-Tag) und löscht einmal je
Minute Protokollzeilen der Aufgaben, die niemand mehr braucht (höchstens 1.000 je
Transaktion). Die **Laufschleife** der Agenten (M5, M6) wacht bei jedem Commit mit
Ereignissen auf (über das `NOTIFY` der Outbox), sonst jede Sekunde, und beendet in jeder
Runde wartende Läufe, deren Frist abgelaufen ist; jeder laufende Lauf erneuert seine Sperrfrist alle
`HERD_RUN_LEASE_SECONDS` / 3. Seit M3 läuft der **Worker** als Schleife: Er wacht bei jedem Commit
mit Ereignissen auf (`NOTIFY herd_outbox`), sonst alle 2 s, verteilt neue Ereignisse
auf die Bahnen der Handler (bis 500 je Durchlauf), und jede Bahn arbeitet bis 100
Ereignisse je Stapel ab; einmal je Minute löscht er verteilte Ereignisse, die älter als
7 Tage sind (höchstens 1.000 auf einmal). Jeder API-Prozess mit offenen SSE-Verbindungen
prüft alle 30 s, ob deren Anmeldungen noch gelten, und schickt nach 15 s Ruhe einen
Heartbeat. Der Collab-Prozess
prüft alle 5 s für jedes offene Dokument Generation und Rechte über die API (kein
Zeitplan, nur solange jemand live bearbeitet). Beim Start entfernt die API liegen
gebliebene temporäre Dateien unter `HERD_DATA_DIR/tmp`, die älter als 24 Stunden sind. Abgelaufene und beendete Sitzungen (jeder
Person), die seit mehr als einer Stunde abgelaufen sind, löscht jede Anmeldung mit, höchstens 500 auf einmal. Alte Ratenlimit-Einträge (jedes
Schlüssels) löscht jede Anmeldeprüfung mit, höchstens 500 auf einmal. Seit M9 räumt die
Fälligkeits-Schleife einmal je Minute außerdem alles Abgelaufene nach dem
Aufbewahrungskatalog (`backend/app/core/retention.py`) auf: Sitzungen, OAuth- und
OIDC-Abläufe, Collab-Berechtigungen, Ratenlimit-Einträge, KI-Ratenfenster, Grabsteine
gelöschter Dateien (nach 48 h) und Sicherungsläufe, deren Prozess starb
([`SICHERUNG.md`](SICHERUNG.md#aufbewahrung-je-tabelle)).

## Ressourcen

### Messung

- **Maschine:** Sandbox-VM, 4 vCPU Intel Xeon @ 2,10 GHz, 16 GB RAM, Linux 6.18,
  Docker 29.9.2, Compose 5.6.1. Lastgenerator und Container liefen auf derselben
  Maschine und teilten sich die CPUs.
- **Image:** `to-herd-cats-ai:local`, gebaut aus Commit `6fee158` mit einer Variante
  des Dockerfiles, die nur in den drei Build-Stufen (Frontend, Collab, Python) die
  TLS-Zertifizierungsstelle der Sandbox ergänzt; die Laufzeitstufe ist unverändert, bis
  auf die Debian-Updates, die hier nicht eingespielt werden konnten (siehe
  [Image-Größe](#image-größe)).
- **Allgemeine Last** (`deploy/compose/load.sh`, eigenes Compose-Projekt mit
  Wegwerf-Volumes und `HERD_INTERNAL_TOKEN`, also mit laufendem Collab-Prozess): Start,
  30 s Ruhe, 5 Stichproben `docker stats` (**Leerlauf**); Anmeldung, 20 Team-Bereiche
  anlegen, 10 s Aufwärmen mit 2 Clients, 10 s Ruhe, 5 Stichproben (**warm**); dann 60 s
  **Last** mit 20 parallelen Clients (`hey` 0.1.4: 10 melden sich an, 10 listen
  Bereiche), Stichprobe etwa alle 2 s. Das Login-Ratenlimit ist nur in diesem
  Wegwerf-Projekt hochgesetzt, damit jede Anmeldung eine echte argon2-Prüfung ist.
- **Wiki-Endpunkte:** eigenes Compose-Projekt, ein Team-Bereich mit 100
  veröffentlichten Seiten (je rund 2 KB Text aus 15 Wörtern, Baum mit 10 Ästen), je
  Endpunkt `hey` 20 s mit 2 und mit 20 Clients und einer Sitzung.
- **Tickets (M4), ohne Docker:** eine Wegwerf-Datenbank auf dem lokalen PostgreSQL 16,
  daran ein Prozess `HERD_ROLE=all` aus dem Arbeitsstand nach Commit `2d277cb` (der
  Anwendungscode ist seit `6cb34d7` unverändert), Python-Skript mit httpx auf derselben
  Maschine (nicht eingecheckt; Ablauf oben unter [Tickets (M4)](#tickets-m4)). Die
  Abfragezahl zählt ein Ereignis-Listener der Datenbankanbindung (`before_cursor_execute`)
  an der öffentlichen App im selben Python-Prozess wie das Skript, an derselben
  Datenbank, jeder Aufruf einmal nach einem Aufruf zum Aufwärmen. Zum Vergleich der
  Anlagen ein zweiter Lauf mit getrennten Prozessen (`migrate`, `api`, `worker`) auf
  einer zweiten Wegwerf-Datenbank.
- **Sprints und Boards (M4b), ohne Docker:** eine Wegwerf-Datenbank auf dem lokalen
  PostgreSQL, daran `HERD_ROLE=migrate`, dann je ein Prozess `api` und `worker` aus dem
  Stand von Commit `7957f73`; Python-Skript mit httpx auf derselben Maschine (nicht
  eingecheckt; Ablauf oben unter [Sprints und Boards (M4b)](#sprints-und-boards-m4b)).
  Die Outbox zählt das Skript direkt in der Datenbank (Ereignisse ohne
  `dispatched_at` und `failed_at`, alle 0,25 s), die Zeitpunkte der Verteilung stehen in
  `event_outbox.dispatched_at`. Abfragen gezählt wie bei den Tickets (M4).
- **Nachrichten (M3), ohne Docker:** eine Wegwerf-Datenbank auf dem lokalen
  PostgreSQL 16 (auf derselben Maschine, von anderen Prozessen mitbenutzt), daran
  `HERD_ROLE=migrate`, dann Knoten A und B (`HERD_ROLE=api`) und ein Worker
  (`HERD_ROLE=worker`), Code-Stand von Commit `d24ad9b` (der Anwendungscode ist seit
  `7c99087` unverändert), ohne Collab-Prozess. Ein
  Python-Skript (httpx, ein Prozess) legt 40 Personen (Rolle `editor`) in einem
  Team-Bereich mit einem Kanal an, öffnet je Person 5 Verbindungen `/api/stream`
  (gerade Personen an A, ungerade an B), wartet 20 s und schickt dann 60 s lang 20
  Nachrichten je Sekunde von 4 Personen an Knoten A (Lauf 2: an Knoten B). Gemessen:
  Zeit vom Absenden jeder POST-Anfrage bis zum Ereignis `message.created` mit ihrer ID
  in jeder der 200 Verbindungen; CPU (aus `/proc/<pid>/stat`) und RSS (`VmRSS`) der drei
  Prozesse alle 2 s; `herd_outbox_pending` und `herd_outbox_oldest_pending_seconds` am
  Worker. Drei Läufe; Lastmittel der Maschine durch andere Prozesse 8–10 (Lauf 1)
  bzw. 3–4 (Läufe 2 und 3). Das Leerlauf-RSS von `HERD_ROLE=all` (ohne Collab-Prozess)
  ist ein eigener Start, 30 s nach `/ready`.
- **Agenten (M6), ohne Docker:** eine Wegwerf-Datenbank auf dem lokalen PostgreSQL,
  daran `HERD_ROLE=migrate`, dann ein Prozess `api`, ein oder zwei `worker` und der
  Stub-Anbieter als eigener Prozess, alles aus dem Stand von Commit `c1e700a`;
  Python-Skript mit httpx und asyncpg (nicht eingecheckt; Ablauf oben unter
  [Agenten (M6)](#agenten-m6)). RSS aus `/proc/<pid>/status` (`VmRSS`) während der
  Durchläufe, Zeiten des Servers aus `run.created_at`, `started_at` und `finished_at`,
  Größen mit `pg_column_size` und `pg_total_relation_size`.
- **Lasttest 200 Personen (M9), ohne Docker:** eine Wegwerf-Datenbank auf dem lokalen
  PostgreSQL 16 (`max_connections` 100, `shared_buffers` 128 MB, `fsync` an), daran
  `HERD_ROLE=migrate`, dann zwei API-Prozesse (`api`, A und B, mit dem gebauten SPA über
  `HERD_STATIC_DIR`), ein Worker und ein Collab-Prozess (`collab`), Code-Stand
  `709d006`. Das Login-Ratenlimit ist nur in dieser Wegwerf-Installation hochgesetzt.
  Daten über die öffentliche API (`deploy/compose/loadsetup.py`): 200 Personen in 4
  Team-Bereichen zu je 50 (Rolle `editor`), je Bereich 250 veröffentlichte Seiten (rund
  2 KB), ein Kanal und 250 Tickets. Szenario `deploy/compose/loadmix.py`: Jede Person
  meldet sich an Knoten A oder B an (abwechselnd), öffnet dort `/api/stream`; nach 20 s
  Ruhe wiederholt sie 180 s lang ihre Tätigkeit mit einer Pause von 2 s × 0,5…1,5
  (Läufe 1 und 2) bzw. 4 s (Lauf 3). Mischung nach Entscheidung 20 (je Person): Seite
  lesen 40 %, Suchen 10 %, Nachricht schreiben 15 %, Ticket in den nächsten Status
  ziehen 10 %, Board und „meine Tickets“ im Wechsel 15 %, eigene Seite speichern 10 %;
  SSE offen 100 %. Live-Zustellung: vom Absenden einer Nachricht bis `message.created`
  mit ihrer ID in jedem der 50 Streams ihres Bereichs. Ausgewertet mit
  `deploy/compose/loadreport.py` (P95 je Endpunkt gegen sein Ziel, getestet in
  `backend/tests/test_loadgen_report.py`). Alle 2 s `deploy/scripts/measure-processes.sh`:
  CPU und RSS je Prozess aus `/proc`, seine TCP-Verbindungen zur Datenbank, die
  Backends der Datenbank aus `pg_stat_activity` (Zahl, CPU, Pss) und die Auslastung der
  Maschine. Lastgenerator (ein Python-Prozess mit httpx), Datenbank und App teilten sich
  die 4 vCPU; das Lastmittel steht bei jedem Lauf.
- **Live-Bearbeitung:** eigenes Compose-Projekt, eine Seite, 10 Personen (Rolle
  `editor`, je eigene Sitzung). Statt 10 Browsern 10 Yjs-Clients
  (`@hocuspocus/provider` wie im Browser, Node-Skript auf derselben Maschine) über
  `/collab/` am öffentlichen Port, also durch die Weiterleitung der API und mit allen
  Prüfungen. Jede Person tippt alle 500 ms ein Wort (20 Änderungen/s insgesamt), 60 s
  lang; dabei liest eine weitere Sitzung die Seite viermal je Sekunde per REST. Gemessen:
  `docker stats` fortlaufend, die Zeit, bis ein Wort bei jeder der 9 anderen ankommt
  (Zeitstempel beim Senden bis zum Yjs-Update beim Empfänger, ohne Darstellung im
  Browser), Speicherungen, Versionen, Markdown-Speichern mit allen 10 verbunden. Zwei
  Läufe auf je frischer Installation.

### Gemessen: allgemeine Last

| Phase | Container | CPU Ø | CPU max | Speicher Ø | Speicher max |
|---|---|---|---|---|---|
| Leerlauf | app | 0,2 % | 0,2 % | 108 MiB | 108 MiB |
| Leerlauf | db | 3,2 % | 9,8 % | 37 MiB | 38 MiB |
| warm | app | 0,4 % | 0,5 % | 111 MiB | 111 MiB |
| warm | db | 0,9 % | 4,2 % | 44 MiB | 45 MiB |
| Last | app | 309 % | 322 % | 218 MiB | 253 MiB |
| Last | db | 32 % | 41 % | 71 MiB | 76 MiB |

100 % CPU = ein Kern. Der App-Container enthält seit M2 den Collab-Prozess: Im Leerlauf
sind das rund 35 MiB mehr als in M1 (108 statt 73 MiB). Unter Anmeldelast braucht er
mehr Speicher als in M1 gemessen (Spitze 253 statt 156 MiB), weil jetzt zwei
argon2-Prüfungen (je 64 MiB) gleichzeitig laufen.

### Gemessen: Live-Bearbeitung mit 10 Editoren

| Phase | Container | CPU Ø | CPU max | Speicher Ø | Speicher max |
|---|---|---|---|---|---|
| vor dem Verbinden | app | 0,2 % | 0,2 % | 112 MiB | 112 MiB |
| 10 verbunden, Ruhe | app | 1,7 % | 6,8 % | 119 MiB | 120 MiB |
| 10 tippen (60 s) | app | 12,4 % | 39,8 % | 124 MiB | 127 MiB |
| danach | app | 8,1 % | 34,4 % | 126 MiB | 127 MiB |
| 10 tippen (60 s) | db | 1,7 % | 7,4 % | 56 MiB | 57 MiB |

(Lauf 2; Lauf 1: tippen app 16,7 % Ø / 55,8 % max, 121 / 129 MiB; db 2,6 % / 9,6 %.)

- **Verbinden:** 10 Editoren verbunden und synchronisiert in 0,38 s (Lauf 1: 0,48 s);
  `herd_collab_connections` = 10.
- **Ankunft einer Änderung bei den anderen:** 10.827 Messpunkte, P50 5 ms, P90 9 ms,
  P99 12 ms, höchstens 18 ms (Lauf 1: 7 / 11 / 16 / 28 ms). Jede Änderung kam bei allen
  9 anderen an.
- **REST nebenbei:** `GET /api/pages/{id}` P50 14 ms, P90 18 ms (Lauf 1: 19 / 23 ms).
- **Gespeichert:** 1.203 Wörter in 60 s; 1,6 s nach dem letzten Wort stand jedes davon
  im Markdown der Seite, alle 10 Dokumente waren gleich. 8 Speicherungen
  (`herd_collab_saves_total{result="saved"}`), daraus 2 Versionen mit Quelle `collab`
  (Versionen derselben Sitzung werden über 60 s zusammengefasst). In Lauf 1 enthielten
  die Wörter eckige Klammern, die der Markdown-Serializer maskiert (`\[`); die Prüfung
  „jedes Wort im Markdown“ schlug deshalb fehl, obwohl nichts fehlte (die Dokumente waren
  gleich, die Länge passte; die Maskierung ist mit einem Einzeltest bestätigt). Lauf 2
  nutzt Wörter ohne Sonderzeichen.
- **Speichern im Markdown-Modus** bei 10 offenen Verbindungen: alle 10 bekamen 4409
  nach 4,4 s (Lauf 1: 0,3 s); der gespeicherte Stand blieb danach unverändert.
- **Prozesse im App-Container** beim Tippen (`VmRSS`): API (Python) 103 MiB,
  Collab-Prozess (Node) 92 MiB. Die Summe liegt über dem Wert von `docker stats`, weil
  RSS gemeinsam genutzte Seiten (Bibliotheken) je Prozess zählt, die cgroup sie einmal.
  Im Cluster läuft der Collab-Prozess als eigener Pod; ihn allein hat hier niemand
  gemessen, sein RSS ist der beste Anhaltspunkt.

### Gemessen: Nachrichten (M3, ohne Docker)

Lauf 3 (Schreiben an Knoten A, Lastmittel der Maschine 3):

| Phase | Prozess | CPU Ø | CPU max | RSS Ø | RSS max |
|---|---|---|---|---|---|
| Leerlauf | API A / API B | 0,1 % / 0,4 % | 0,5 % | 109 / 107 MiB | 109 / 107 MiB |
| Leerlauf | Worker | 0,6 % | 1,0 % | 104 MiB | 104 MiB |
| 200 Verbindungen offen, Ruhe (20 s) | API A / API B | 1,6 % / 2,1 % | 14 % / 20 % | 122 / 122 MiB | 122 / 122 MiB |
| 20 Nachrichten/s an 200 Verbindungen (60 s) | API A (schreibt und liefert 100 Verbindungen) | 45 % | 50 % | 123 MiB | 124 MiB |
| 20 Nachrichten/s | API B (liefert 100 Verbindungen) | 16 % | 18 % | 122 MiB | 122 MiB |
| 20 Nachrichten/s | Worker | 20 % | 24 % | 106 MiB | 107 MiB |
| danach (15 s) | API A / API B / Worker | 0,8 / 0,4 / 0,6 % | 4,5 % | 124 / 122 / 107 MiB | |

100 % CPU = ein Kern. Lauf 2 (Schreiben an Knoten B) spiegelbildlich: schreibender
Knoten 44 % Ø, nur liefernder 15 %, Worker 20 %, RSS gleich. Lauf 1 unter fremder Last:
API A 42 % Ø / 76 % max, 130 / 132 MiB; B 14 %; Worker 16 %.

- **Leerlauf je Rolle** (RSS 30 s nach `/ready`, ohne Verbindungen): API 107–109 MiB,
  Worker 104 MiB, `HERD_ROLE=all` (API und Worker in einem Prozess, ohne
  Collab-Prozess) 107 MiB. Ein eigener Worker-Prozess kostet also gut 100 MiB, im
  Prozess der API fast nichts.
- **Je offene SSE-Verbindung** rund 0,14 MiB im API-Prozess (100 Verbindungen: +14 MiB).
- **Datenbank:** nicht getrennt gemessen (die PostgreSQL-Instanz teilten sich andere
  Prozesse). Seit der Überarbeitung je Stapel angekommener Ereignisse (bis 200)
  höchstens zwei Abfragen je API-Prozess mit passenden Verbindungen (Lauf oben: eine
  Abfrage je Ereignis), dazu die Arbeit des Workers (Zustellnachweis je Handler) und
  alle 10 s je Worker das Zählen der offenen und aufgegebenen Ereignisse.

### Gemessen: Speicherprüfung und Größenmessung der Live-Bearbeitung

Im Prozess (Node 22, 4 Kerne, ohne Image; Fix-Welle 2 der Prüfung M2), die Wiki-Seite
`collab/test/corpus/it-handbuch.md` so oft hintereinander, bis die Größe erreicht ist:

| Seite (Zeichen Markdown) | Speicherprüfung je Speicherung (Median / max) |
|---|---|
| 980 | 14 ms / 17 ms |
| 20.620 | 142 ms / 154 ms |
| 150.244 | 1.110 ms / 1.310 ms |

- Die Speicherprüfung (Markdown schreiben, mit dem Parser der Seitenansicht wieder
  lesen, vergleichen, Prüfung wie beim Öffnen) läuft bei jeder Live-Speicherung, also
  höchstens alle 2 s je Seite, auf der Event-Loop des Collab-Prozesses; solange sie
  läuft, wartet jede andere Nachricht. Vor einer Optimierung in derselben Welle waren es
  43 ms / 371 ms / 3,2 s.
- Die genaue Größenmessung nahe der Grenze (Kopie des Dokuments und Markdown) kostet
  bei 150.000 Zeichen etwa 130 ms (Kopie) plus 90–120 ms (Markdown), höchstens einmal je
  Sekunde und Seite, und nur, wenn die Seite höchstens ein paar hundert Zeichen unter
  der Grenze liegt.
- Die Messung mit 10 Editoren oben stammt von vor Fix-Welle 2 (Image, `docker stats`);
  sie ist mit der Speicherprüfung nicht wiederholt (`docker build` geht in dieser
  Sandbox nicht).

### Gemessen: Lasttest mit 200 Personen (M9)

Je Lauf 200 Personen mit offenem Stream; Antwortzeiten am Client in ms (P50 / P95 /
P99), Ziele nach Entscheidung 20: Lesen P95 ≤ 300 ms, Schreiben ≤ 500 ms, Live-Zustellung
≤ 2 s, keine 5xx.

| Endpunkt | Ziel P95 | Lauf 1: Pause 2 s | Lauf 2: Pause 2 s | Lauf 3: Pause 4 s |
|---|---|---|---|---|
| Seite lesen `GET /api/pages/{id}` | 300 | 26 / **228** / 430 | 31 / **307** / 545 | 13 / **34** / 123 |
| Suchen `GET /api/search` | 300 | 66 / **277** / 507 | 76 / **361** / 553 | 51 / **80** / 256 |
| Board `GET /api/spaces/{id}/board` | 300 | 43 / **292** / 493 | 53 / **401** / 586 | 25 / **51** / 352 |
| Meine Tickets `GET /api/tickets?assignee=me` | 300 | 29 / **192** / 407 | 34 / **285** / 451 | 16 / **32** / 216 |
| Nachricht schreiben `POST …/messages` | 500 | 43 / **300** / 585 | 54 / **441** / 704 | 24 / **62** / 307 |
| Ticket ziehen `PATCH /api/tickets/{n}` | 500 | 38 / **282** / 483 | 45 / **392** / 597 | 21 / **53** / 226 |
| Seite speichern `PATCH /api/pages/{id}` | 500 | 38 / **301** / 512 | 47 / **381** / 615 | 21 / **55** / 356 |
| Live-Zustellung an 50 Streams | 2.000 | 98 / **456** / 749 | 122 / **643** / 964 | 62 / **144** / 415 |
| Anfragen/s (alle Endpunkte) | | 95 | 94 | 48 |
| Zustellungen (verloren) | | 129.150 (0) | 127.050 (0) | 66.600 (0) |
| Fehler (5xx, Abbrüche) | 0 | 0 | 0 | 0 |
| Ergebnis | | alle Ziele erreicht | Lesen verfehlt (307, 361, 401) | alle Ziele erreicht |
| Lastmittel vor / während | | 0,5 / 3,1 | 1,7 / 3,0 | 1,6 / 1,7 |

**Ergebnis:** Bei 95 Anfragen/s auf zwei API-Prozessen (jede Person alle 2 s eine
Aktion, weit mehr als im Alltag) liegen die Ziele an der Grenze: Lauf 1 erreichte alle,
Lauf 2 verfehlte drei Leseziele um 7 bis 101 ms; Schreiben, Live-Zustellung und
Fehlerfreiheit hielten in beiden. Bei 48 Anfragen/s (Pause 4 s) liegt jedes P95 unter
100 ms. **Engpass:** die CPU der Maschine, nicht ein einzelner Prozess. Die 4 vCPU
trugen alles zugleich (zwei API-Prozesse je 0,6 Kerne, Datenbank 0,5, Worker 0,3,
Lastgenerator 0,16, Messung) und waren zu 65–95 % belegt; jeder API-Prozess blieb unter
0,9 Kernen. Dazu war der Pool jedes API-Prozesses in Spitzen ausgeschöpft (16
Verbindungen), Anfragen warteten dann auf eine Verbindung. **Folgeaufgabe:** der
Lasttest im Cluster (Pods mit eigenen Kernen, Ingress, Autoscaler; `load.sh` mit
`docker stats` bzw. `loadmix.py` gegen den Ingress). Erst wenn dort das Lese-P95 bei
95 Anfragen/s auf zwei Pods über 300 ms bleibt: die Poolgröße als Einstellung und ein
Profil der Leseendpunkte. Bis dahin hält der Autoscaler mit dem gemessenen Request
(siehe [Empfehlung](#empfehlung-request-und-limit)) die Last je Pod im Bereich von
Lauf 3.

Prozesse (Lauf 1; 100 % CPU = ein Kern; Datenbank: alle Backends der Datenbank, Pss
statt RSS, die Verbindungen aus `pg_stat_activity`):

| Phase | Prozess | CPU Ø | CPU max | RSS Ø | RSS max | DB-Verbindungen Ø / max |
|---|---|---|---|---|---|---|
| Leerlauf (nach dem Start) | API A / API B | 0,2 % / 0,2 % | 0,5 % | 203 / 198 MiB | 203 / 198 MiB | 2 / 2 |
| Leerlauf | Worker | 2,4 % | 3,7 % | 200 MiB | 201 MiB | 6 / 6 |
| Leerlauf | Collab | 0,1 % | 0,5 % | 98 MiB | 98 MiB | 0 |
| Leerlauf | Datenbank | 0,6 % | 2,0 % | 51 MiB | 53 MiB | 10 / 10 |
| warm (200 angemeldet, 200 Streams, Ruhe) | API A / API B | 0,2 % / 0,3 % | 0,9 % | 221 / 218 MiB | 221 / 218 MiB | 6 / 6 |
| warm | Worker | 1,9 % | 3,0 % | 201 MiB | 201 MiB | 6 / 6 |
| warm | Datenbank | 0,5 % | 1,5 % | 87 MiB | 87 MiB | 18 / 18 |
| Last (180 s) | API A | 61 % | 75 % | 240 MiB | 242 MiB | 6,7 / 16 |
| Last | API B | 61 % | 74 % | 238 MiB | 242 MiB | 6,9 / 16 |
| Last | Worker | 32 % | 45 % | 209 MiB | 213 MiB | 6 / 6 |
| Last | Collab | 0 % | 0 % | 98 MiB | 98 MiB | 0 |
| Last | Datenbank | 51 % | 68 % | 165 MiB | 222 MiB | 20 / 32 |
| Last | Lastgenerator | 16 % | 19 % | 332 MiB | 336 MiB | – |

- **Lauf 2** (Pause 2 s): API 61 % Ø, 77 % / 86 % max, RSS 245 MiB; Worker 31 % Ø,
  39 % max; Datenbank 48 % Ø, 67 % max, bis 33 Verbindungen. **Lauf 3** (Pause 4 s):
  API je 33 % Ø, 52–54 % max, RSS 249 MiB, höchstens 7 Verbindungen je Prozess; Worker
  18 % Ø, 25 % max, 217 MiB; Datenbank 32 % Ø, 54 % max, 184 MiB, 18–19 Verbindungen.
- **Höchster Speicher** (`VmHWM`): API 340–377 MiB, erreicht beim Anmelden der 200
  Personen vor dem Lauf (zwei argon2-Prüfungen zugleich, je 64 MiB) und nach dem Lauf
  nicht wieder freigegeben (RSS im nächsten Leerlauf 242–249 MiB); Worker 213–217 MiB;
  Collab 131 MiB (beim Start).
- **Leerlauf je Rolle** ist seit M3 um rund 90 MiB gewachsen (API 107 → 198–203 MiB,
  Worker 104 → 200 MiB): Seither laden die Prozesse die Module von KI, Agenten, MCP,
  OIDC und Sicherung.
- Der Collab-Prozess war im Szenario unbeteiligt (keine Live-Bearbeitung; Messung mit
  10 Editoren siehe oben).

### Gemessen: Sicherung und Wiederherstellung (M9)

Wegwerf-Datenbank mit 10.000 Seiten (über die API angelegt, Datenbank 67 MB) und 64
Anhängen zu 16 MiB (zufällige Bytes, nicht komprimierbar; zusammen 1.073.736.320 Bytes =
1 GiB) auf dem lokalen Datenträger, ohne laufende App, mit `python -m app.ops` aus dem
Code-Stand `709d006`; Lastmittel 0,7–0,9. Spitze RSS: der größte Prozess (Python oder
`pg_dump`/`pg_restore`).

| Schritt | Dauer | Spitze RSS |
|---|---|---|
| `backup create` | 10,1–11,3 s (vier Läufe; der erste nach einem Neustart der VM 33,1 s) | 119 MiB |
| `backup verify` | 2,8–2,9 s | 100 MiB |
| `restore check` (leere Datenbank, leere Ablage) | 2,8 s | 108 MiB |
| `restore apply` (69 Tabellen, 64 Dateien) | 8,4–8,7 s (einmal nach dem Leeren des Seitencaches der VM) | 121 MiB |

- **Archivgröße:** 1.081.149.440 Bytes (1,007 GiB): die Anhänge unverändert (das Archiv
  komprimiert nicht) plus 7,4 MB für Datenbank-Dump und Manifest; das Manifest daneben
  18 KB. Der Dump ist hier 11 % der Datenbankgröße (Indizes werden nicht gesichert,
  Seitentext komprimiert gut).
- Die Dauer hängt am Lesen der Anhänge: Der erste Lauf nach dem Neustart las von einem
  kalten Datenträger (rund 32 MB/s), die übrigen aus dem Cache des Hosts. Auf
  Netzspeicher ist mit der Lesegeschwindigkeit des Volumes zu rechnen.

### Gemessen: Schreibgrenze durch NOTIFY (M9)

Ein Python-Skript (asyncpg, nicht eingecheckt) an einer eigenen Datenbank desselben
PostgreSQL 16: N Verbindungen schreiben je 10 s in einer Schleife eine Transaktion aus
einem `INSERT` (100 Bytes) und, im zweiten Fall, einem `pg_notify` mit eigener Nutzlast
(rund 180 Bytes, wie ein Live-Ereignis), während eine Verbindung lauscht (sie bekam
jedes). Lastmittel vorher 0,7.

| Verbindungen | Commits/s ohne NOTIFY | Commits/s mit NOTIFY |
|---|---|---|
| 1 | 2.487 | 1.749 |
| 4 | 5.865 | 4.138 |
| 16 | 8.487 | 4.686 |
| 32 | 7.724 | 4.487 |

PostgreSQL reiht die Commits mit `NOTIFY` hintereinander (eine Sperre auf die
Benachrichtigungswarteschlange beim Commit); ab etwa vier Verbindungen bleibt es hier bei
4.100–4.700 je Sekunde. In der App schickt jede schreibende Transaktion mit Ereignissen
ein `NOTIFY herd_outbox` (in einer Transaktion zusammengefasst); der Worker schickt je
Live-Ereignis ein `NOTIFY herd_live`, committet aber einen Stapel einer Bahn (bis 100
Ereignisse) auf einmal. Jede schreibende Aktion kostet also einen solchen Commit an der
API und einen Anteil an einem Stapel des Workers: **Schreibgrenze** auf dieser
Datenbank rund 2.000 bis 4.000 schreibende Aktionen je Sekunde. Der Lasttest schrieb
33 je Sekunde (Seiten, Nachrichten, Tickets), mehr als 60-mal weniger; vorher ist die
CPU der API-Prozesse die Grenze.

### Nicht gemessen (hier nicht möglich oder nicht gemacht)

- Echte Browser als Editoren in dieser Zahl (Last und Darstellung im Browser); die
  Demo (`docs/demo/m2.md`) lief mit zwei echten Chromium-Instanzen, ohne Zeitmessung.
- Betrieb hinter einem echten Ingress-Controller (WebSocket-Upgrade, Leerlauf-Timeouts),
  mehrere API-Replikas, der Collab-Prozess als eigener Pod, Neustart des
  Collab-Prozesses unter Last. Kein Kubernetes in der Sandbox.
- Mehr als eine Seite mit Live-Bearbeitung gleichzeitig, große Seiten (nahe 200.000
  Zeichen oder 5 MiB Yjs-Zustand), Uploads und Importe unter Last. Die Dauer eines
  großen Imports ist nur ohne Image gemessen (Review M2 R19, im Prozess gegen das lokale
  PostgreSQL, 2.000 Seiten in einem Ordner mit Tags): vorher 80 s, jetzt 11 s
  (6,7 statt 28,6 SQL-Anweisungen je Seite).
- Das Image mit Debian-Updates (siehe unten), Trivy.
- **M3 ohne Image:** Für die Nachrichten gibt es keine Messung mit `docker stats`,
  keine eigene Image-Größe von M3 (keine neuen Abhängigkeiten; Task 11 baute für seine
  Compose-Prüfung eine Variante mit der CA der Sandbox und ohne `apt-get upgrade` und
  nennt 544 MB, M2 hatte 537 MB ebenfalls ohne eingespielte Updates) und
  keinen Lauf von `deploy/compose/load.sh`. `docker build` geht in dieser Sandbox nicht
  unverändert, und das Docker der Sandbox war für diese Messung aus.
- **Tickets (M4):** keine Messung mit `docker stats` und kein Lauf von `load.sh`;
  CPU und Speicher von App und Datenbank während der Ticket-Messung nicht aufgezeichnet;
  echte Browser mit einem Board von 10.000 Tickets (geladen werden je Spalte 50; die
  Darstellung und das Ziehen bei vielen Karten sind nicht gemessen); viele Bereiche oder
  Organisationen mit Tickets zugleich (die Messung hat einen Bereich); 20 Status je
  Bereich; Epics mit sehr vielen Kindern; gleichzeitige Änderungen desselben Tickets unter
  Last (Wettläufe sind nur als Tests mit echten Commits geprüft); die Suche über Seiten,
  Nachrichten und Tickets zusammen bei großen Mengen; ein zweiter Worker unter
  Anlagelast; Ticket-Ereignisse über zwei API-Knoten unter Last (die Demo
  `docs/demo/m4.md` prüft den Weg A → B mit zwei Knoten, ohne Last).
- **Sprints und Boards (M4b):** CPU und Speicher während der Messung; die Daily-Ansicht
  mit 100 Personenzeilen (gemessen sind 21) und in einem echten Browser mit 1,4 MB
  Antwort; ein Abschluss mit mehr als 1.782 verschobenen Tickets und mehrere Abschlüsse
  zugleich; zwei Worker beim Abschluss; „Mein Board“ einer Person mit Tickets in vielen
  Bereichen (gemessen ist ein Bereich); eine Daily-Ansicht, in der nur ein Teil der
  Karten seit dem letzten Arbeitstag geändert ist (hier alle).
- **Lasttest und Sicherung (M9):** im Container und im Cluster (`load.sh` mit `docker
  stats`, Pods mit eigenen Kernen, Ingress, der Autoscaler beim Hoch- und
  Herunterskalieren), mehr als zwei API-Prozesse, eine Datenbank auf eigener Maschine,
  echte Browser (SPA-Dateien, Neuladen), Live-Bearbeitung, Hochladen und Importe im Mix,
  Agenten-Läufe und Aufgaben unter dieser Last, die Dauer der 200 Anmeldungen vor dem
  Lauf (nur ihr Speicher), eine Sicherung während des Lasttests, Sicherung auf
  Netzspeicher, S3 oder mit vielen kleinen Dateien (gemessen: 64 große), Offsite-Kopie
  mit restic, Wiederherstellung einer Datenbank mit Millionen Zeilen, die
  Schreibgrenze mit der App selbst (gemessen: PostgreSQL allein).
- Nachrichten: Speicher und CPU der Datenbank für Nachrichten allein (seit M9 nur im
  ganzen Mix des Lasttests), echte Browser statt eines Skripts als
  Empfänger, mehr als ein Kanal oder viele Organisationen, Direktnachrichten und Threads
  unter Last, die Suche über viele Nachrichten, die Wirkung eines Proxys vor
  `/api/stream`, der Verlust der LISTEN-Verbindung unter Last (`resync`) und ein
  Neustart eines API-Pods mit 100 offenen Verbindungen.
- **Agenten (M6):** ein echter Anbieter (Netz, Latenz, Token-Zahlen, Kosten); der
  Worker im Image und mit `docker stats`; CPU von Worker, API und Datenbank während der
  Durchläufe; der Speicher der API; große Gesprächsverläufe, Werkzeugergebnisse und
  Gedächtnisseiten (der Stub antwortet kurz); Freigaben unter Last; die Grenzen einer
  Verbindung (`max_concurrency`, `requests_per_minute`) als Bremse; Erwähnungen in
  vielen Threads zugleich; Übergabeketten; mehr als zwei Worker; ein Rollout mit
  SIGTERM während laufender Läufe (gemessen ist nur SIGKILL).
- **Automatisierung (M7):** Termine in Kanälen und Ticket-Threads (gemessen ist die
  Direktnachricht: im Kanal kommt je Termin ein Systemeintrag dazu); Heartbeats und
  Ereignis-Regeln unter Last (die Ruhezeit ist nur als Test mit drei Workern geprüft);
  viele Eigentümerinnen und Agenten (gemessen: eine, einer); ein echter Anbieter; CPU von
  Worker und Datenbank; die Budgetprüfung unter gleichzeitigen Läufen (gemessen im
  Prozess, nacheinander); die Löschung alter Protokollzeilen bei großen Mengen; der
  Prüfdurchlauf mit mehreren Workern unter Last (geprüft als Test).
- **MCP (M8):** `/mcp` mit mehreren API-Prozessen, hinter einem Proxy und mit vielen
  Token zugleich (gemessen: ein Prozess, ein Token); schreibende Werkzeuge über `/mcp`
  unter Last; echte Clients (Claude Code, Codex) gegen die Installation; Aufrufe
  externer MCP-Server und OAuth-Erneuerungen unter Last (nur als Tests gegen Stubs);
  CPU und Speicher der Datenbank; das Image mit dem MCP-SDK (keine Image-Größe von M8:
  `docker build` geht in dieser Sandbox nicht, der Docker-Dienst läuft nicht).

### Empfehlung Request und Limit

Seit M9 aus dem [Lasttest](#gemessen-lasttest-mit-200-personen-m9) (ohne Docker, RSS
statt cgroup-Speicher); das Chart setzt diese Werte als Standard (`values.yaml`, geprüft
in `deploy/helm/scripts/chart-rules-scaling.sh`):

| Container | CPU Request | CPU Limit | Speicher Request | Speicher Limit | Chart-Standard |
|---|---|---|---|---|---|
| api (je Pod, ohne Collab-Prozess) | 500m | keins | 320Mi | 512Mi | gleich (bis M9: 100m / 256Mi) |
| worker (je Replika) | 250m | keins | 256Mi | 384Mi | gleich (bis M9: 50m / 192Mi) |
| collab (eine Replika) | 50m | keins | 128Mi | 1Gi | gleich |
| db (mitgeliefert) | 250m | keins | 256Mi | 1Gi | gleich (bis M9: 100m) |
| Sicherungs-Job | 50m | keins | 128Mi | 512Mi | gleich |

- **api CPU:** je Prozess 0,2 % im Leerlauf, 33 % Ø / 54 % max bei 48 Anfragen/s auf
  zwei Prozessen (P95 ≤ 80 ms) und 61 % Ø / 75–86 % max bei 95 Anfragen/s (P95 an der
  Grenze der Ziele). Mit dem Ziel des Autoscalers (70 %) bekommt ein Pod ab 350m Hilfe,
  also zwischen der bequemen und der knappen Messung; ohne Autoscaler reserviert der
  Request, was ein Pod bei der halben Referenzlast braucht. Kein CPU-Limit: Anmeldungen
  (argon2) brauchen kurz mehrere Kerne (M2: 3,2 Kerne bei 20 gleichzeitigen
  Anmeldungen), ein Limit würde nur drosseln.
- **api Speicher:** RSS 198–203 MiB nach dem Start, 238–249 MiB unter Last und danach,
  höchstens 340–377 MiB beim Anmelden von 200 Personen (zwei argon2-Prüfungen zu
  64 MiB zugleich). Request = Last 246 MiB + 20 % ≈ 300 → 320Mi; Limit 512Mi = Spitze
  377 MiB + 35 %.
- **worker:** CPU 2 % im Leerlauf (Fälligkeits-Schleife, Metriken), 18 % Ø bei 48 und
  31–32 % Ø / 39–45 % max bei 95 Anfragen/s; Request 250m (der Autoscaler hilft ab
  175m, der Last von Lauf 3). Speicher: RSS 200–217 MiB ohne Agenten-Läufe, in M6 bis
  249 MiB mit 16 Läufen zugleich; Request 256Mi, Limit 384Mi. Wer
  `HERD_RUN_CONCURRENCY` erhöht, gibt dem Worker mehr Speicher.
- **collab:** CPU beim Tippen von 10 Personen bis 0,4 Kerne für den ganzen Container
  (API, Weiterleitung und Collab-Prozess zusammen), Speicher (RSS) 92 MiB mit einem
  kleinen Dokument. Große Seiten kosten viel mehr (Prüfung M4-1 P12, gemessen im
  Browser über die Weiterleitung, RSS des Collab-Prozesses): 8 Seiten mit je 4.998
  Tabellenzellen zugleich geöffnet 438 MB, 8 Textseiten mit 190.000 Zeichen 401 MB, 16
  Tabellen-Seiten 508 MB (11 geöffnet, 5 abgewiesen als „ausgelastet“), 20 Textseiten
  521 MB (17 geöffnet, 3 abgewiesen), 8 Tabellen-Seiten mit Tippen und Speichern 493 MB;
  20 s nach dem Verlassen 113–136 MB. Der Collab-Prozess hält seine geladenen Dokumente
  unter `HERD_COLLAB_MEMORY_BUDGET_MB` (400, Schätzung, `docs/WIKI.md`); Faustregel
  Limit ≥ (130 MB + 250 MB je Prüf-Thread + Budget) / 0,8 = 975 MB. Das Chart setzt
  128Mi/1Gi (vorher 512Mi: drei bis fünf große Tabellen-Seiten brachten ihn darüber).
- **db:** 32 Backends, CPU 48–51 % Ø / 67–68 % max bei 95 Anfragen/s, 32 % Ø bei 48;
  Pss aller Backends 165–184 MiB Ø, höchstens 222 MiB (`shared_buffers` 128 MB anteilig
  gezählt). Request 250m (die halbe Referenzlast), Speicher 256Mi/1Gi wie bisher; mit
  echten Daten wächst der Bedarf. Produktiv ist die Datenbank ohnehin extern; das
  mitgelieferte PostgreSQL hat `max_connections` 200 (`postgresql.maxConnections`, siehe
  [Clusterfähigkeit](#clusterfähigkeit)).
- **Sicherungs-Job:** gemessen höchstens 119–121 MiB RSS je Prozess
  ([Sicherung](#gemessen-sicherung-und-wiederherstellung-m9)); 128Mi/512Mi bleiben.
- **Autoscaler-Grenzen:** API 2 bis 6, Worker 1 bis 3 bleiben. Zwei API-Pods trugen die
  Referenz knapp, sechs tragen rund das Dreifache (nicht im Cluster gemessen); die
  Datenbankverbindungen der vollen Grenzen (bis 144) stehen unter
  [Clusterfähigkeit](#clusterfähigkeit).
- **Volume `/data`:** Anhänge (je Inhalt einmal) und temporäre Dateien von Upload,
  Import und Export (bis 100 MiB je laufendem Import). Das Chart legt 10Gi an.

## Image-Größe

| | |
|---|---|
| entpackt | 537 MB (537.145.299 Byte), M1: 333 MB |
| komprimiert | 125,7 MB (`docker save \| gzip`), M1: 76,0 MB |
| Plattform | linux/amd64 |
| Basis | `python:3.13-slim` per Digest; tini 0.19.0 mit Prüfsumme; Node 22 nur als Binärdatei aus `node:22-slim` (per Digest) für den Collab-Prozess |

Gemessen am Image aus Commit `6fee158`. **M4:** Das Image aus dem Stand nach `6687a74`
(gebaut mit der Variante mit der CA der Sandbox, ohne `apt-get upgrade`, für `smoke.sh`
und die Demo) ist entpackt 545 MB (545.020.933 Byte), komprimiert 126,5 MB; M4 bringt
keine neue Laufzeitabhängigkeit im Backend, im Frontend `@dnd-kit/core` (im
SPA-Bündel). Den Zuwachs gegenüber M1 machen die
Node-Binärdatei (rund 120 MB) und `collab/` mit seinen Produktionsabhängigkeiten
(26 MB) aus. Die Laufzeitstufe spielt Debian-Sicherheitsupdates ein (`apt-get
upgrade`); hier mit 0 eingespielten Paketen, weil die Sandbox `deb.debian.org` nicht
auflösen kann. Die Größe mit Updates steht im Build-Protokoll der CI.

## Ansprechperson und Vertretung

| | |
|---|---|
| Ansprechperson | T4 (Jans Antwort J5, 15.11.2026) |
| Vertretung | nicht benannt |

## Sicherheitshinweise

Die Sicherheitshinweise (Vertrauensbereich des Collab-Prozesses, Anmeldung, Sitzungen,
Kryptografie, Verbindungen, Datenklassen, Protokolle) und die Prüfung gegen OWASP ASVS
5.0 Stufe 2 mit den offenen Lücken, ihrer Planung (M9b Tasks 16 und 18) und den
dokumentierten Abweichungen (MFA für lokale Passwortkonten, TLS zwischen API und
Collab-Prozess) stehen in [`SICHERHEIT.md`](SICHERHEIT.md).

## Betriebshinweise

Die bekannten Grenzen (mitgeliefertes PostgreSQL, Migrations-Job, `/ready` und
expand/contract, kube-state-metrics, NetworkPolicy, amd64, Trivy, CI-Werkzeuge, CSP,
Datenbank-Passwort, Anmeldelast, seit M2: internes Token, Live-Bearbeitung und
WebSocket hinter einem Ingress, `/data` und ReadWriteMany, Größen von Anfragen,
Anhängen und Importen) stehen im README unter
[Betriebshinweise](../README.md#betriebshinweise), die Bedienung und der Betrieb des
Wikis in [`WIKI.md`](WIKI.md), der Nachrichten (Worker, Outbox, SSE hinter einem Proxy)
in [`NACHRICHTEN.md`](NACHRICHTEN.md), der KI-Anbindung in [`KI.md`](KI.md), der Agenten
(Worker, Läufe, Alarme, Rolling Update) in [`AGENTEN.md`](AGENTEN.md), von MCP
(`/mcp` hinter einem Proxy, Token, externe Server, Konnektoren, Katalog) in
[`MCP.md`](MCP.md#betrieb), seit M9 Sicherung, Wiederherstellung und Aufbewahrung in
[`SICHERUNG.md`](SICHERUNG.md) und die Anmeldung über OIDC mit Freigabe in
[`ANMELDUNG.md`](ANMELDUNG.md).

## Metriken und Alarme (seit M3)

| Metrik | Art | Bedeutung |
|---|---|---|
| `herd_outbox_pending` | Gauge (nur Prozesse mit Worker, alle 10 s) | offene Ereignisse der Outbox |
| `herd_outbox_oldest_pending_seconds` | Gauge (nur mit Worker) | Alter des ältesten offenen Ereignisses |
| `herd_outbox_failed` | Gauge (nur mit Worker) | aufgegebene Ereignisse in der Datenbank |
| `herd_worker_last_pass_timestamp_seconds` | Gauge (nur mit Worker) | Unix-Zeit des letzten abgeschlossenen Durchlaufs |
| `herd_outbox_dispatch_total{handler,result}` | Zähler | Zustellungen je Handler: `ok`, `duplicate`, `error`, `timeout`, `failed` (aufgegeben) |
| `herd_sse_connections` | Gauge (API) | offene SSE-Verbindungen |
| `herd_live_events_total{type}` | Zähler (API) | empfangene Live-Ereignisse je Typ |
| `herd_live_queue_depth` | Gauge (API) | empfangene, noch nicht verteilte Live-Ereignisse |
| `herd_live_delivery_lag_seconds` | Histogramm (API) | Eintreffen des `NOTIFY` bis Übergabe an die Verbindungen |
| `herd_live_resyncs_total{reason}` | Zähler (API) | `resync` an Verbindungen: `lag`, `overflow`, `reconnect`, `check_failed` |
| `herd_runs_total{reason}` | Zähler (nur mit Worker) | beendete Läufe dieses Workers je Stopgrund |
| `herd_run_duration_seconds` | Histogramm (nur mit Worker) | Dauer einer Aufnahme eines Laufs |
| `herd_runs_queued` | Gauge (nur mit Worker, alle 10 s) | Läufe in der Warteschlange |
| `herd_runs_oldest_queued_seconds` | Gauge (nur mit Worker) | Alter des ältesten wartenden Laufs |
| `herd_runs_stuck` | Gauge (nur mit Worker) | laufende Läufe mit abgelaufener Sperrfrist oder länger als jeder Lauf darf (zählt auch einen Lauf, der nach langem Warten wieder läuft; [`AGENTEN.md`](AGENTEN.md#bekannte-grenzen)) |
| `herd_runs_waiting` | Gauge (nur mit Worker) | Läufe, die auf eine Freigabe oder Antwort warten |
| `herd_automation_firings_total{outcome}` | Zähler (nur mit Worker) | gefeuerte Termine (Fälligkeits-Schleife und Ereignis-Regeln) je Ergebnis: `started`, `skipped_*`, `paused_owner` |
| `herd_automations_due` | Gauge (nur mit Worker, alle 10 s) | fällige, noch nicht gefeuerte Aufgaben |
| `herd_automations_oldest_due_seconds` | Gauge (nur mit Worker) | Wartezeit des ältesten fälligen Termins |
| `herd_automations_paused{reason}` | Gauge (nur mit Worker) | angehaltene Aufgaben je Grund: `manual`, `owner`, `failing` |
| `herd_budget_stops_total{scope}` | Zähler (nur mit Worker) | Läufe, die ein Tagesbudget beendet hat, je Geltung: `user`, `agent`, `organisation` |
| `herd_wiki_review_reminders_total` | Zähler (nur mit Worker) | Seiten, deren Prüffrist der Durchlauf gemeldet hat |
| `herd_wiki_review_spaces_unchecked` | Gauge (nur mit Worker) | Bereiche mit Prüffrist, die der Durchlauf heute (UTC) noch nicht gesehen hat |
| `herd_mcp_calls_total{tool,outcome}` | Zähler (API) | Werkzeugaufrufe über `/mcp` je eingebautem Werkzeug und Ergebnis (`ok`, `refused`, `invalid`, `failed`) |
| `herd_external_tool_calls_total{outcome,effect}` | Zähler (nur mit Worker) | Aufrufe externer MCP-Werkzeuge in Läufen: `ok`, `error`, `refused`, `limited`, `failed`, `timeout`, `unknown`; `read` oder `write` |
| `herd_external_tool_definitions_left_out_total` | Zähler (nur mit Worker) | Externe Werkzeuge, die die Grenze aller Werkzeugbeschreibungen eines Modellaufrufs (100.000 Zeichen) weglässt; ohne Namen |
| `herd_oauth_refreshes_total{status}` | Zähler (API und Worker) | Erneuerungen von OAuth-Token je Antwort des Anbieters |
| `herd_mcp_catalog_problems` | Gauge (API) | übersprungene Katalog-Dateien |

Alarme in der PrometheusRule des Charts: `HerdOutboxBacklog` (ältestes offenes
Ereignis älter als 5 Minuten, kritisch), `HerdOutboxFailed` (Zahl der aufgegebenen
Ereignisse gestiegen, Warnung), `HerdWorkerStalled` (ein Worker seit über 3 Minuten
ohne abgeschlossenen Durchlauf, Warnung), `HerdWorkerAbsent` (API-Pods ohne Worker
ihres Releases, 5 Minuten, kritisch), dazu wie bisher `HerdNotReady` (deckt die
Worker-Pods mit ab). Seit M6 für die Läufe der Agenten, je als Warnung: `HerdRunsStuck` (Läufe hängen,
5 Minuten), `HerdRunsQueued` (ältester wartender Lauf älter als 5 Minuten) und
`HerdRunsFailing` (mehr als die Hälfte der Läufe der letzten 15 Minuten, mindestens 3,
endete mit `provider_refused` oder `error`, 5 Minuten lang). Seit M7 für die Aufgaben,
je als Warnung: `HerdAutomationsLagging` (ältester fälliger Termin über 3 Minuten,
5 Minuten lang) und `HerdAutomationsFailing` (mindestens 5 Aufgaben mehr binnen einer
Stunde wegen Fehlschlägen angehalten). Seit M8, je als Warnung:
`HerdExternalToolsFailing` (mehr als die Hälfte der gesendeten externen Aufrufe von
15 Minuten, mindestens 3, gescheitert oder im Zeitlimit, 5 Minuten lang),
`HerdOAuthRefreshFailing` (mindestens 3 gescheiterte Erneuerungen in 30 Minuten außer
`invalid_grant`), `HerdMcpAuthFailures` (mehr als 50 Antworten 401 an `/mcp` in
5 Minuten, 10 Minuten lang; aus `herd_http_requests_total{route="/mcp"}`) und
`HerdMcpCatalogProblems` (übersprungene Katalog-Dateien, 15 Minuten). Bedeutung und
Abhilfe in [`AGENTEN.md`](AGENTEN.md#metriken-und-alarme) und
[`MCP.md`](MCP.md#metriken-und-alarme). Seit M9: `HerdBackupTooOld`,
`HerdBackupFailing`, `HerdOffsiteBackupFailing`, `HerdBackupNeverRan`
([`SICHERUNG.md`](SICHERUNG.md)), `HerdOidcFailing` ([`ANMELDUNG.md`](ANMELDUNG.md))
und `HerdAutoscalerAtMax` (ein Autoscaler des Charts 30 Minuten am Maximum, Warnung;
braucht kube-state-metrics). Alle mit promtool-Tests (`tests/rules-test.yaml`). Nachrichteninhalte
stehen nie in Labels.

## Tests (Stand M9a; ältere Zeilen zum Vergleich)

| Paket | Tests | Stand |
|---|---|---|
| Backend (`pytest`, echtes PostgreSQL), M9a | 2.813 (Backend-Stand von Commit `2f5207f`, Abschluss M9a) | 16.11.2026: 2.813 grün, 1 Warnung (SADeprecationWarning); 41:27 min. ruff, ruff format, mypy (strict, 560 Dateien) sauber, `check_migrations` grün |
| Frontend (`vitest`), M9a | 632 in 113 Dateien | 16.11.2026: 632 grün im ersten Lauf |
| Collab (`node --test`), M9a | 280 | 16.11.2026: 279 grün, 1 übersprungen |
| Browser (`e2e/`, Playwright, echte App in Rolle `all`), M9a | 73 in 22 Dateien | 16.11.2026: erster Lauf 72 grün, 1 rot: `oidc.spec.mjs` „a person links an account…“ legte dora@e2e.example an, die `ai-agents.spec.mjs` schon mit anderem Passwort angelegt hatte (401 bei der Anmeldung; nur im ganzen Lauf, behoben mit einer eigenen Person). Danach 73 grün, 9,8 min |
| Backend (`pytest`, echtes PostgreSQL), M7 | 2.037 (Backend-Stand von Commit `51d3dc5`) | 14.11.2026: 2.034 grün, 3 rot: `test_wiki_review_pass.py::test_a_due_page_is_reminded_once_per_interval` (der Test rechnete „später am Tag“ als jetzt + 3 h und lief nach 21 Uhr UTC; behoben in `4631d15`), `test_run_cancel_races.py::test_a_cancel_before_the_finish_wins` (409 `conflict.retry` der kurzen Sperrgrenze unter Last, danach ein Deadlock beim Leeren der Tabellen) und als Folge `::test_a_cancel_during_the_finish_waits_and_finds_it_done` (Reste des vorigen Tests); die Datei allein dreimal grün; 33:06 min. ruff, ruff format, mypy (strict, 413 Dateien) sauber |
| Backend (`pytest`, echtes PostgreSQL), M6 | 1.716 (Backend-Stand von Commit `c1e700a`, gleich dem von `aab401b`) | 14.11.2026: 1.715 grün, 1 rot: `test_run_replay.py::test_a_run_goes_on_after_its_last_recorded_step` (der Stub gab die zweite vorbereitete Antwort nicht zurück; unter Last der Maschine, danach die Datei allein dreimal grün); 27:40 min. ruff, ruff format, mypy (strict, 363 Dateien) sauber. Ein später hinzugekommener Test (`95f8273`) ist hier nicht mitgezählt |
| Frontend (`vitest`) | 412 in 71 Dateien (Stand `aab401b`) | 14.11.2026: 411 grün, 1 rot unter Last (`SkillProposals.test.tsx`, „a space's moderators find them beside the skills“: die Navigation „Skills und Vorschläge“ nicht gefunden), die Datei allein grün (10 von 10) |
| Browser (`e2e/`, Playwright, echte App in Rolle `all`) | 60 in 17 Dateien (Stand `60aa00c`, gezählt mit `playwright test --list`): 18 Live-Bearbeitung, 5 Nachrichten, 13 Tickets, 15 KI und Agenten, 9 Aufgaben (M7, mit der Uhr des Testgeschirrs) | 14.11.2026: 60 grün, 9,8 min (Stand `5c1a25b`) |
| Compose (`smoke.sh`) | einfach und `SMOKE_NODES=1` | beide `SMOKE OK` mit dem Image der Demo (13.11.2026); für M6 nicht wiederholt (`docker build` geht in dieser Sandbox nicht) |
