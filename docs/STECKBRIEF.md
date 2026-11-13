# Steckbrief to-herd-cats-ai

Stand: Meilenstein 1 (Fundament), 12.11.2026, Version 0.1.0. Der Steckbrief wird mit
jedem Meilenstein aktualisiert (Spezifikation 12.7).

## Kurzbeschreibung

Selbst betriebenes Arbeitssystem für Teams: Wiki, Aufgaben und Kanäle in Bereichen
mit einem Rechtemodell, KI-Agenten als Teammitglieder. **In M1 vorhanden:**
Anmeldung mit Sitzungen, Personen, Gruppen, Bereiche (offen, Team, persönlich),
Rollen und Rechteprüfung, Audit, Verzeichnissuche, Oberfläche mit Navigation und
Verwaltung. Wiki (M2), Aufgaben, Kanäle und Agenten folgen.

| | |
|---|---|
| Dienst-ID | `to-herd-cats-ai` (Log-Feld `service`, `OTEL_SERVICE_NAME`, Image, Chart) |
| Image | `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y`, ein Image für alle Rollen (`HERD_ROLE=api\|migrate\|all`) |
| Chart | `oci://ghcr.io/<owner>/charts/to-herd-cats-ai`, `version` = `appVersion` = Dienstversion |
| Ports | 8080 öffentlich (API, SPA); 9090 intern (`/health`, `/ready`, `/metrics`) |
| Lizenz | Apache-2.0 |

## Funktionen mit Laufzeit und Kosten

Gemessen mit `deploy/compose/load.sh` gegen die Compose-Referenz (ein App-Container,
ein PostgreSQL), Maschine siehe [Messung](#messung). Laufzeit ist die Antwortzeit am
Client, inklusive Docker-Portweiterleitung.

| Funktion | Endpunkt | P50 / P90, leicht (2 Clients) | P50 / P90, Last (20 Clients) | Durchsatz unter Last | Kosten |
|---|---|---|---|---|---|
| Anmelden | `POST /api/auth/login` | 65 / 76 ms | 670 / 974 ms (hey); 776 / 1712 ms (Python-Schleife) | 14–16 Anmeldungen/s | keine externen |
| Bereiche auflisten | `GET /api/spaces?limit=50` (22 Bereiche) | 11 / 59 ms | 249 / 371 ms (hey); 251 / 442 ms (Python-Schleife) | 39/s (hey) | keine externen |

Alle Antworten unter Last waren 200, Fehlerquote 0 %. Nicht einzeln gemessen: die
übrigen Endpunkte (Personen, Gruppen, Mitglieder, Audit, Verzeichnis); sie sind wie die
Bereichsliste einfache, indizierte Abfragen mit Seitengröße ≤ 100.

**Kosten:** M1 ruft keine kostenpflichtigen Dienste auf (keine KI, kein externer
Speicher). Es fallen nur die Ressourcen unten an.

**Engpass Anmeldung:** Die Passwortprüfung ist argon2id (64 MiB, 3 Durchläufe,
4 Lanes). Die Zahlen oben sind **vor** fix wave 1 gemessen (Commit `ac8433f`), als sie
noch im Event-Loop lief: ein Pod schaffte 14–16 Anmeldungen je Sekunde bei rund
2,6 Kernen (rechnerisch 0,17 CPU-Sekunden je Anmeldung) und blockierte während jeder
Prüfung alle anderen Anfragen dieses Pods (daher die Bereichsliste mit 250 ms statt
11 ms unter Anmeldelast). Seit fix wave 1 läuft argon2 in Worker-Threads, höchstens
`HERD_PASSWORD_HASH_CONCURRENCY` (Standard 2) gleichzeitig je Prozess; der Event-Loop,
die Probes und andere Anfragen bleiben dabei bedienbar. Je Client-Adresse sind
höchstens `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE` (Standard 30) Anmeldeversuche je
Minute erlaubt, gleich mit welcher E-Mail; fehlgeschlagene Versuche je Adresse und
E-Mail höchstens `HERD_LOGIN_RATE_LIMIT_PER_MINUTE` (Standard 5). Neu gemessen ist das
noch nicht. Mehr Anmeldungen je Sekunde gibt es weiterhin über mehr Replikas.

## Abhängigkeiten

| Dienst | Pflicht | Hinweis |
|---|---|---|
| PostgreSQL ≥ 16 | ja | einzige Zustandsablage (Daten, Sitzungen, Ratenlimits, Sperren). Compose und Chart nutzen `pgvector/pgvector:pg17` per Digest; M1 braucht pgvector noch nicht |
| OTLP-Collector | nein | Tracing nur, wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist (Chart: `tracing.otlpEndpoint`) |
| Prometheus | nein | scrapt `/metrics` auf 9090; ServiceMonitor und PrometheusRule im Chart |
| kube-state-metrics | nur für Alarm | `HerdNotReady` braucht es |

Keine ausgehenden Verbindungen zu Dritten, keine Drittanbieter-Anfragen im Browser.

## Clusterfähigkeit

- **Zustandslos:** Sitzungen, Login-Ratenlimit und Sperren liegen in PostgreSQL; jede
  Replika kann jede Anfrage bedienen. Chart-Standard: 2 API-Replikas.
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

Keine. M1 hat weder Cronjobs noch Hintergrundaufträge. Abgelaufene Sitzungen einer
Person werden bei ihrer nächsten Anmeldung gelöscht. Alte Ratenlimit-Einträge (jedes
Schlüssels) löscht jede Anmeldeprüfung mit, höchstens 500 auf einmal. Der Sicherungs-CronJob (Spezifikation 12.6) ist
noch nicht gebaut; Sicherung bis dahin mit `pg_dump` (siehe
`deploy/compose/README.md`).

## Ressourcen

### Messung

- **Maschine:** Sandbox-VM, 4 vCPU Intel Xeon @ 2,10 GHz, 16 GB RAM, Linux 6.18,
  Docker 29.9.2, Compose 5.6.1. Lastgenerator und Container liefen auf derselben
  Maschine und teilten sich die CPUs.
- **Image:** `to-herd-cats-ai:local`, gebaut aus Commit `ac8433f` mit
  einer Variante des Dockerfiles, die nur in den beiden Build-Stufen die
  TLS-Zertifizierungsstelle der Sandbox ergänzt; die Laufzeitstufe ist unverändert.
- **Ablauf** (`deploy/compose/load.sh`, eigenes Compose-Projekt mit Wegwerf-Volumes):
  Start, 30 s Ruhe, 5 Stichproben `docker stats` (**Leerlauf**); Anmeldung, 20
  Team-Bereiche anlegen, 10 s Aufwärmen mit 2 Clients, 10 s Ruhe, 5 Stichproben
  (**warm**); dann 60 s **Last** mit 20 parallelen Clients, Stichprobe etwa alle 2 s.
  Das Login-Ratenlimit ist nur in diesem Wegwerf-Projekt hochgesetzt, damit jede
  Anmeldung eine echte argon2-Prüfung ist statt einer billigen 429-Antwort.
- **Werkzeug:** `hey` 0.1.4 (installiert mit `go install`), zwei parallele Ströme: 10
  Clients melden sich an, 10 listen Bereiche mit einer Sitzung. Zur Kontrolle ein
  zweiter Lauf mit dem Python-Ersatz (`deploy/compose/loadgen.py`, 20 Clients, je
  Schleife Anmelden und Auflisten). `oha` war nicht installiert.
- **Datenbestand:** fast leer: eine Person, 22 Bereiche, unter 2.000 Sitzungen.

### Gemessen

| Phase | Container | CPU Ø | CPU max | Speicher Ø | Speicher max |
|---|---|---|---|---|---|
| Leerlauf | app | 0,2 % | 0,2 % | 73 MiB | 73 MiB |
| Leerlauf | db | 1,0–1,5 % | 7,6 % | 36 MiB | 38 MiB |
| warm | app | 0,2 % | 0,2 % | 75–76 MiB | 76 MiB |
| warm | db | 1,1–2,1 % | 5,6 % | 46 MiB | 46 MiB |
| Last, hey | app | 250 % | 262 % | 125 MiB | 156 MiB |
| Last, hey | db | 8,7 % | 13,5 % | 79 MiB | 81 MiB |
| Last, Python | app | 268 % | 280 % | 129 MiB | 145 MiB |
| Last, Python | db | 7,4 % | 10,9 % | 79 MiB | 81 MiB |

100 % CPU = ein Kern. Schon ein einzelner Client, der sich fortlaufend anmeldet, lastet
die App mit etwa 2,6 Kernen aus (argon2 mit 4 Lanes); mehr Clients erhöhen nur die
Wartezeit.

### Empfehlung Request und Limit

Aus den Messwerten mit 20–30 % Puffer:

| Container | CPU Request | CPU Limit | Speicher Request | Speicher Limit | Chart-Standard heute |
|---|---|---|---|---|---|
| app (je Pod) | 250m | 3500m oder keins | 160Mi | 200Mi | Request 100m / 256Mi, Limit 512Mi |
| db (mitgeliefert) | 100m | keins | 100Mi | 105Mi | Request 100m / 256Mi, Limit 1Gi |

- **app CPU:** Limit = Lastspitze 2,8 Kerne + 25 %. Ein kleineres Limit bricht nichts,
  es senkt nur den Anmeldedurchsatz (rechnerisch etwa 6 je Sekunde bei 1 Kern; nicht
  gemessen). Der Request ist nicht gemessen, sondern gesetzt: Leerlauf und warm liegen
  bei 0,2 %; 250m tragen rechnerisch etwa 1,5 Anmeldungen je Sekunde dauerhaft.
- **app Speicher:** Request = Last-Durchschnitt 129 MiB + 25 %, Limit = Lastspitze
  156 MiB + 30 %, gemessen, als argon2 noch seriell im Event-Loop lief. Seit fix
  wave 1 laufen bis zu `HERD_PASSWORD_HASH_CONCURRENCY` (2) Prüfungen gleichzeitig,
  jede braucht 64 MiB: rechnerisch bis zu etwa 64 MiB mehr als gemessen (nicht neu
  gemessen). Das Chart behält 256Mi/512Mi.
- **db:** Die Formel ergibt 100Mi/105Mi, aber nur für eine fast leere Datenbank.
  PostgreSQLs `shared_buffers` ist ab Werk schon 128 MB; mit echten Daten wächst der
  Bedarf. Das Chart behält 256Mi/1Gi. Produktiv ist die Datenbank ohnehin extern.

## Image-Größe

| | |
|---|---|
| entpackt | 333 MB (333.170.294 Byte) |
| komprimiert | 76,4 MB (Docker „content size“); `docker save \| gzip`: 76,0 MB |
| Plattform | linux/amd64 |
| Basis | `python:3.13-slim` per Digest; tini 0.19.0 mit Prüfsumme; kein Node zur Laufzeit |

Gemessen am Image aus Commit `ac8433f`. Der spätere Commit `e3ac0b1` spielt in der
Laufzeitstufe Debian-Sicherheitsupdates ein (`apt-get upgrade`). Hier gebaut ergab das
333,2 MB, aber mit 0 eingespielten Paketen, weil die Sandbox `deb.debian.org` nicht
auflösen kann. Die Größe mit Updates ist noch nicht gemessen; sie steht nach dem
nächsten CI-Lauf im Build-Protokoll.

## Ansprechperson und Vertretung

| | |
|---|---|
| Ansprechperson | Jan (Projektverantwortung, hat die Spezifikation freigegeben) |
| Vertretung | noch nicht benannt |

## Betriebshinweise

Die bekannten Grenzen (mitgeliefertes PostgreSQL, Migrations-Job, `/ready` und
expand/contract, kube-state-metrics, NetworkPolicy, amd64, Trivy, CI-Werkzeuge, CSP,
Datenbank-Passwort, Anmeldelast) stehen im README unter
[Betriebshinweise](../README.md#betriebshinweise).
