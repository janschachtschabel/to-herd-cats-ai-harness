# Steckbrief to-herd-cats-ai

Stand: Meilenstein 4 (Tickets), 13.11.2026, Version 0.1.0. Der Steckbrief wird mit
jedem Meilenstein aktualisiert (Spezifikation 12.7). Die Messwerte aus M2 (Image,
Compose, `docker stats`) bleiben stehen; die Nachrichten aus M3 und die Tickets aus M4
sind ohne Docker gemessen, an Prozessen auf der Maschine (Abschnitte
[Gemessen: Nachrichten](#gemessen-nachrichten-m3-ohne-docker) und
[Tickets (M4)](#tickets-m4)). Was nicht gemessen ist, steht unter
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
Suche. KI folgt ab M5.

| | |
|---|---|
| Dienst-ID | `to-herd-cats-ai` (Log-Feld `service`, `OTEL_SERVICE_NAME`, Image, Chart) |
| Image | `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y`, ein Image für alle Rollen (`HERD_ROLE=api\|migrate\|all\|worker\|collab`) |
| Chart | `oci://ghcr.io/<owner>/charts/to-herd-cats-ai`, `version` = `appVersion` = Dienstversion |
| Prozesse | API (Python, Uvicorn: öffentlicher und interner Server in einem Prozess); Collab-Prozess (Node 22, Hocuspocus) für die Live-Bearbeitung. `HERD_ROLE=all`: die API startet ihn als Kindprozess auf `127.0.0.1:1234`; im Chart ein eigenes Deployment (`HERD_ROLE=collab`, genau eine Replika). Worker (Python, Verteiler der Outbox, nur interner Port): in `HERD_ROLE=all` im API-Prozess, im Chart ein eigenes Deployment (`HERD_ROLE=worker`, Standard 1 Replika, mehrere sicher) |
| Ports | 8080 öffentlich (API, SPA, WebSocket `/collab/`, Server-Sent Events `/api/stream`); 9090 intern (`/health`, `/ready`, `/metrics`, `/internal/*`); 1234 Collab-Prozess (nur von der API erreichbar) |
| Speicher | PostgreSQL (alle Daten, auch Seiten, Versionen, Yjs-Stände); Volume `/data` (`HERD_DATA_DIR`) für Anhänge und temporäre Dateien von Upload, Import und Export |
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
Folge: Systemmeldungen und Live-Ereignisse kommen bei Massenanlagen über die API später
an; nichts geht verloren. Ein zweiter Worker oder langsameres Anlegen hilft; nicht
gemessen. Platz: `work_item` mit 10.000 Tickets 9,5 MB (mit Indizes), die ganze
Datenbank 53 MB (mit 13.054 Systemmeldungen und der Outbox).

**Kosten:** M2 bis M4 rufen keine kostenpflichtigen Dienste auf (keine KI, kein externer
Speicher). Es fallen nur die Ressourcen unten an, dazu der Platz der Anhänge auf dem
Volume (eine Datei je Inhalt und Organisation, höchstens 25 MiB je Anhang).

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

## Abhängigkeiten

| Dienst | Pflicht | Hinweis |
|---|---|---|
| PostgreSQL ≥ 16 | ja | Zustandsablage (Daten, Sitzungen, Ratenlimits, Sperren, Volltextindex, Yjs-Stände der Live-Bearbeitung). Compose und Chart nutzen `pgvector/pgvector:pg17` per Digest; M2 braucht pgvector noch nicht |
| Volume für `/data` | ja (mit Anhängen) | Anhänge und temporäre Dateien von Upload, Import und Export. Compose: Volume `app-data`; Chart: PVC `<release>-data`, voreingestellt **ReadWriteMany** (alle API-Replikas schreiben); ohne RWX-Speicherklasse `api.replicas=1` und `persistence.accessModes={ReadWriteOnce}` |
| Worker | für Live-Zustellung, Benachrichtigungen, Systemmeldungen | im selben Image (`HERD_ROLE=worker`, in `all` enthalten); nur Datenbank, keine eingehenden Anfragen außer 9090. Ohne Worker gehen keine Nachrichten verloren, aber nichts kommt live an, bis einer läuft |
| Collab-Prozess | für Live-Bearbeitung | im selben Image (Node 22, Hocuspocus); spricht nur mit der API (`/internal/collab/*` auf 9090, Token `HERD_INTERNAL_TOKEN`), speichert nie selbst in die Datenbank. Ohne Token ist die Live-Bearbeitung aus, der Markdown-Editor geht weiter |
| OTLP-Collector | nein | Tracing nur, wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist (Chart: `tracing.otlpEndpoint`) |
| Prometheus | nein | scrapt `/metrics` auf 9090; ServiceMonitor und PrometheusRule im Chart |
| kube-state-metrics | nur für Alarm | `HerdNotReady` braucht es |

Keine ausgehenden Verbindungen zu Dritten, keine Drittanbieter-Anfragen im Browser.
Die API-Dokumentation `/api/docs` (Swagger UI, lädt ihre Skripte von einem CDN) gibt
es deshalb nur außerhalb von `HERD_ENVIRONMENT=production`; das Image setzt
`production`. Das OpenAPI-Dokument `/api/openapi.json` bleibt immer erreichbar.

## Clusterfähigkeit

- **Zustandslos:** Sitzungen, Login-Ratenlimit und Sperren liegen in PostgreSQL; jede
  Replika kann jede Anfrage bedienen. Chart-Standard: 2 API-Replikas. Anhänge liegen
  auf einem Volume (`/data`), das alle API-Replikas teilen (Chart: PVC mit
  `ReadWriteMany`).
- **Collab-Prozess (Live-Bearbeitung):** genau eine Replika mit `strategy: Recreate`
  (Spezifikation 12.4, Stufe 1). Ein Live-Dokument liegt im Speicher dieses Prozesses;
  zwei Prozesse würden die Bearbeitenden einer Seite aufteilen. Der Zustand wird über
  die API in PostgreSQL gespeichert (spätestens 10 s nach einer Änderung und beim
  Beenden); nach einem Neustart verbinden sich die Browser selbst neu. Ungespeicherte
  Änderungen der letzten Sekunden (höchstens 10 s) im Speicher des Prozesses gehen dabei
  verloren, sofern kein Browser sie wieder einspielt. Mehrere Collab-Replikas
  (Spezifikation 12.4, Stufe 2 mit Redis/Valkey) kommen mit M9.
- **Mehrere API-Knoten und Live-Zustellung (M3):** Eine Nachricht, die an einem Knoten
  geschrieben wird, kommt an den SSE-Verbindungen jedes Knotens an (`NOTIFY herd_live`,
  jeder API-Prozess lauscht mit einer eigenen Datenbankverbindung außerhalb des Pools);
  Sticky Sessions sind nicht nötig. Geprüft mit zwei echten Prozessen
  (`tests/test_live_two_nodes.py`, `docs/demo/m3.md`) und in der CI mit
  `SMOKE_NODES=1 bash deploy/compose/smoke.sh`. Die Grenze von 5 Verbindungen je
  Anmeldung gilt je API-Prozess. Bei SIGTERM schließt die API ihre Verbindungen zuerst;
  die Browser verbinden sich nach 5 s mit einem anderen Pod und laden nach.
- **Worker (M3):** beliebig viele Replikas (getrennte Stapel per `FOR NO KEY UPDATE SKIP
  LOCKED`, Zustellung mindestens einmal, Handler idempotent; geprüft mit zwei
  Verteilern und mit einem Verteiler, der mitten im Handler abgeschossen wird). Je
  Worker drei Datenbankverbindungen (Stapel, Handler, LISTEN).
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

Keine Cronjobs. Seit M3 läuft der **Worker** als Schleife: Er wacht bei jedem Commit
mit Ereignissen auf (`NOTIFY herd_outbox`), sonst alle 2 s, und verteilt höchstens 50
Ereignisse je Durchlauf; einmal je Minute löscht er verteilte Ereignisse, die älter als
7 Tage sind (höchstens 1.000 auf einmal). Jeder API-Prozess mit offenen SSE-Verbindungen
prüft alle 30 s, ob deren Anmeldungen noch gelten, und schickt nach 15 s Ruhe einen
Heartbeat. Der Collab-Prozess
prüft alle 5 s für jedes offene Dokument Generation und Rechte über die API (kein
Zeitplan, nur solange jemand live bearbeitet). Beim Start entfernt die API liegen
gebliebene temporäre Dateien unter `HERD_DATA_DIR/tmp`, die älter als 24 Stunden sind. Abgelaufene und beendete Sitzungen (jeder
Person), die seit mehr als einer Stunde abgelaufen sind, löscht jede Anmeldung mit, höchstens 500 auf einmal. Alte Ratenlimit-Einträge (jedes
Schlüssels) löscht jede Anmeldeprüfung mit, höchstens 500 auf einmal. Der Sicherungs-CronJob (Spezifikation 12.6) ist
noch nicht gebaut; Sicherung bis dahin mit `pg_dump` (siehe
`deploy/compose/README.md`).

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
- Nachrichten: Speicher und CPU der Datenbank, echte Browser statt eines Skripts als
  Empfänger, mehr als ein Kanal oder viele Organisationen, Direktnachrichten und Threads
  unter Last, die Suche über viele Nachrichten, die Wirkung eines Proxys vor
  `/api/stream`, der Verlust der LISTEN-Verbindung unter Last (`resync`) und ein
  Neustart eines API-Pods mit 100 offenen Verbindungen.

### Empfehlung Request und Limit

Aus den Messwerten mit 20–30 % Puffer:

| Container | CPU Request | CPU Limit | Speicher Request | Speicher Limit | Chart-Standard heute |
|---|---|---|---|---|---|
| api (je Pod, ohne Collab-Prozess) | 250m | 3500m oder keins | 256Mi | 330Mi | Request 100m / 256Mi, Limit 512Mi |
| collab (eine Replika) | 50m | 500m | 128Mi | 256Mi | Request 50m / 128Mi, Limit 512Mi |
| worker (je Replika) | 50m | 300m | 128Mi | 140Mi | Request 50m / 192Mi, Limit 384Mi |
| db (mitgeliefert) | 100m | keins | 100Mi | 105Mi | Request 100m / 256Mi, Limit 1Gi |

- **api CPU:** Limit = Lastspitze 3,2 Kerne + 10 %. Ein kleineres Limit bricht nichts,
  es senkt nur den Anmeldedurchsatz. Der Request ist gesetzt, nicht gemessen: Leerlauf
  und warm liegen unter 1 %.
- **api Speicher:** Die Messung enthält den Collab-Prozess (rund 35 MiB im Leerlauf,
  92 MiB RSS beim Tippen). Request = Last-Durchschnitt 218 MiB + 20 %, Limit =
  Lastspitze 253 MiB + 30 %; ohne Collab-Prozess bleibt damit Reserve. Das Chart
  behält 256Mi/512Mi.
- **collab:** CPU beim Tippen von 10 Personen bis 0,4 Kerne für den ganzen Container
  (API, Weiterleitung und Collab-Prozess zusammen), Speicher (RSS) 92 MiB mit einem
  Dokument. Mehr gleichzeitige Seiten brauchen mehr Speicher (je Dokument der Yjs-Zustand,
  höchstens 5 MiB, nicht gemessen). Das Chart behält 128Mi/512Mi.
- **worker:** RSS 104–107 MiB in Ruhe und bei 20 Nachrichten je Sekunde, CPU 20–24 %
  (ohne Image gemessen). Request = 106 MiB + 20 %, Limit = 107 MiB + 30 %, CPU-Limit =
  24 % + Reserve. Das Chart setzt mehr (192Mi/384Mi); das bleibt, bis eine Messung im
  Container vorliegt.
- **api mit SSE:** 200 offene Verbindungen und 20 Nachrichten je Sekunde kosteten je
  Prozess +15 MiB und bis 50 % eines Kerns (ohne Anmeldelast); das bleibt im Rahmen der
  Empfehlung oben.
- **db:** Die Formel ergibt 100Mi/105Mi, aber nur für eine fast leere Datenbank.
  PostgreSQLs `shared_buffers` ist ab Werk schon 128 MB; mit echten Daten wächst der
  Bedarf. Das Chart behält 256Mi/1Gi. Produktiv ist die Datenbank ohnehin extern.
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
| Ansprechperson | Jan (Projektverantwortung, hat die Spezifikation freigegeben) |
| Vertretung | noch nicht benannt |

## Sicherheitshinweise

- **Vertrauensbereich Collab-Prozess (bewusst so, Review M2 R14):** Die API reicht beim
  Aufbau einer Live-Verbindung das Sitzungs-Cookie der Person an den Collab-Prozess
  weiter; die interne API nimmt Laden und Speichern für jede Seite an, die diese
  Person bearbeiten darf, solange die Sitzung gilt. API und Collab-Prozess bilden
  damit einen Vertrauensbereich: Ein übernommener Collab-Prozess könnte alle Seiten
  lesen und überschreiben, die eine gerade verbundene Person bearbeiten darf, in ihrem
  Namen, und Live-Sitzungen beliebiger Seiten beenden; erreicht er die öffentliche API,
  könnte er sie als diese Person aufrufen. Im Chart trennt die NetworkPolicy den
  Collab-Pod von der öffentlichen API; in Compose laufen beide im selben Container.
  Mit M9 ersetzen kurzlebige, an Seite und Generation gebundene Tokens das
  weitergereichte Cookie.

## Betriebshinweise

Die bekannten Grenzen (mitgeliefertes PostgreSQL, Migrations-Job, `/ready` und
expand/contract, kube-state-metrics, NetworkPolicy, amd64, Trivy, CI-Werkzeuge, CSP,
Datenbank-Passwort, Anmeldelast, seit M2: internes Token, Live-Bearbeitung und
WebSocket hinter einem Ingress, `/data` und ReadWriteMany, Größen von Anfragen,
Anhängen und Importen) stehen im README unter
[Betriebshinweise](../README.md#betriebshinweise), die Bedienung und der Betrieb des
Wikis in [`WIKI.md`](WIKI.md), der Nachrichten (Worker, Outbox, SSE hinter einem Proxy)
in [`NACHRICHTEN.md`](NACHRICHTEN.md).

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

Alarme in der PrometheusRule des Charts: `HerdOutboxBacklog` (ältestes offenes
Ereignis älter als 5 Minuten, kritisch), `HerdOutboxFailed` (Zahl der aufgegebenen
Ereignisse gestiegen, Warnung), `HerdWorkerStalled` (ein Worker seit über 3 Minuten
ohne abgeschlossenen Durchlauf, Warnung), `HerdWorkerAbsent` (API-Pods ohne Worker
ihres Releases, 5 Minuten, kritisch), dazu wie bisher `HerdNotReady` (deckt die
Worker-Pods mit ab). Alle mit promtool-Tests (`tests/rules-test.yaml`). Nachrichteninhalte
stehen nie in Labels.

## Tests (Stand M4)

| Paket | Tests | Stand |
|---|---|---|
| Backend (`pytest`, echtes PostgreSQL) | 980 | alle grün (13.11.2026, 8:07 min), dazu ruff, ruff format, mypy (strict) sauber |
| Frontend (`vitest`) | 246 in 48 Dateien | alle grün (13.11.2026) |
| Browser (`e2e/`, Playwright, echte App in Rolle `all`) | 31 in 10 Dateien: 18 Live-Bearbeitung, 5 Nachrichten, 8 Tickets | alle 31 in einem Lauf grün (4,4 min, davon gut 3 min die Öffnungsprobe der Live-Bearbeitung); die 8 Ticket-Tests zusätzlich in 3 Läufen grün (je rund 30 s mit Start der App, rund 24 s in den Tests) |
| Compose (`smoke.sh`) | einfach und `SMOKE_NODES=1` | beide `SMOKE OK` mit dem Image der Demo (13.11.2026) |
