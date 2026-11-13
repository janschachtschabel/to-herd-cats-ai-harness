# Steckbrief to-herd-cats-ai

Stand: Meilenstein 2 (Wiki), 13.11.2026, Version 0.1.0. Der Steckbrief wird mit jedem
Meilenstein aktualisiert (Spezifikation 12.7). Die Messwerte aus M1 sind durch neue
ersetzt (Abschnitt [Ressourcen](#ressourcen)).

## Kurzbeschreibung

Selbst betriebenes Arbeitssystem für Teams: Wiki, Aufgaben und Kanäle in Bereichen
mit einem Rechtemodell, KI-Agenten als Teammitglieder. **Vorhanden (M1):**
Anmeldung mit Sitzungen, Personen, Gruppen, Bereiche (offen, Team, persönlich),
Rollen und Rechteprüfung, Audit, Verzeichnissuche, Oberfläche mit Navigation und
Verwaltung. **Vorhanden (M2):** Wiki je Bereich mit Seitenbaum, Markdown-Editor,
Live-Bearbeitung (Collab-Prozess, Generationen), Versionen mit Diff und
Wiederherstellung, Papierkorb, Tags (systemweit und je Bereich), Anhänge,
Volltextsuche, Markdown-Import und -Export. Kanäle (M3), Aufgaben (M4) und KI (ab M5)
folgen.

| | |
|---|---|
| Dienst-ID | `to-herd-cats-ai` (Log-Feld `service`, `OTEL_SERVICE_NAME`, Image, Chart) |
| Image | `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y`, ein Image für alle Rollen (`HERD_ROLE=api\|migrate\|all\|collab`) |
| Chart | `oci://ghcr.io/<owner>/charts/to-herd-cats-ai`, `version` = `appVersion` = Dienstversion |
| Prozesse | API (Python, Uvicorn: öffentlicher und interner Server in einem Prozess); Collab-Prozess (Node 22, Hocuspocus) für die Live-Bearbeitung. `HERD_ROLE=all`: die API startet ihn als Kindprozess auf `127.0.0.1:1234`; im Chart ein eigenes Deployment (`HERD_ROLE=collab`, genau eine Replika) |
| Ports | 8080 öffentlich (API, SPA, WebSocket `/collab/`); 9090 intern (`/health`, `/ready`, `/metrics`, `/internal/*`); 1234 Collab-Prozess (nur von der API erreichbar) |
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

**Kosten:** M2 ruft keine kostenpflichtigen Dienste auf (keine KI, kein externer
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

Keine. M1 und M2 haben weder Cronjobs noch Hintergrundaufträge. Der Collab-Prozess
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

### Empfehlung Request und Limit

Aus den Messwerten mit 20–30 % Puffer:

| Container | CPU Request | CPU Limit | Speicher Request | Speicher Limit | Chart-Standard heute |
|---|---|---|---|---|---|
| api (je Pod, ohne Collab-Prozess) | 250m | 3500m oder keins | 256Mi | 330Mi | Request 100m / 256Mi, Limit 512Mi |
| collab (eine Replika) | 50m | 500m | 128Mi | 256Mi | Request 50m / 128Mi, Limit 512Mi |
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

Gemessen am Image aus Commit `6fee158`. Den Zuwachs gegenüber M1 machen die
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
Wikis in [`WIKI.md`](WIKI.md).
