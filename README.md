# to-herd-cats-ai

Ein selbst betriebenes Arbeitssystem für Teams: Wissen im Wiki, Arbeit in Aufgaben,
Austausch in Kanälen, und KI-Agenten als Teammitglieder mit denselben Rechten wie
Menschen. Die Spezifikation steht in
[`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md`](docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md).

**Version 1.0.0** (erste Freigabe; was sie enthält, Hinweise zum Update und bekannte
Grenzen: [`docs/RELEASE-1.0.0.md`](docs/RELEASE-1.0.0.md)).

**Stand: M9a (Produktion, erster Teil) ist gebaut, auf Meilenstein 8 (Öffnung: MCP),
M7, M6 und aus M5 der KI-Grundlage (Tasks 1 bis 7), dazu aus M9b der Wartungsmodus mit
dem Einspielen in eine laufende Installation und Anhänge in S3; hybride Suche und
Embeddings (M5 Tasks 8 bis 11) und der Rest von M9b fehlen noch.** Aus M1:
Anmeldung, Personen, Gruppen, Bereiche (offen, Team, persönlich), Rollen, die eine
Rechteprüfung, Audit, die Oberfläche mit Navigation und Verwaltung, Image, Compose,
Helm-Chart und CI. Aus M2 ein Wiki in jedem Bereich:

- **Seiten** in einem Baum (verschieben und sortieren per Dialog, per Tastatur
  bedienbar), Entwurf oder veröffentlicht, Wiki-Links `[[Titel]]`, Inhaltsverzeichnis.
  Markdown ist das gespeicherte Format; rohes HTML wird nie ausgeführt.
- **Zwei Editoren:** Markdown mit Vorschau (mit Konfliktdialog, wenn jemand
  dazwischen gespeichert hat) und „Gemeinsam bearbeiten“ (live, mit Anwesenheit und
  Cursorn der anderen). Speichern im Markdown-Modus, Wiederherstellen, Verschieben und
  Papierkorb beenden eine laufende Live-Sitzung sauber (Generationen).
- **Versionen** jeder Speicherung mit Quelle, Diff zweier Versionen, Benennen,
  Wiederherstellen als neue Version. **Papierkorb** statt Löschen; endgültig löschen
  nur Admins.
- **Tags** systemweit (Verwaltung → Tags, Recht `tag.manage`) und je Bereich
  (Moderatoren, in den Einstellungen des Bereichs); der Seitenbaum filtert danach.
- **Anhänge** (Bilder inline, alles andere als Download; SVG und HTML abgelehnt, am
  Inhalt erkannt), **Volltextsuche** (Strg+K, findet nur, was man lesen darf),
  **Import und Export** als Markdown-ZIP, jede Seite einzeln als `.md`.

Aus M3 Nachrichten:

- **Kanäle** je Bereich (lesen und schreiben, wer den Bereich lesen darf; anlegen ab
  Moderator), **Direktnachrichten** mit 2 bis 9 Personen, **Threads**, **Erwähnungen**
  mit Personenauswahl, **Reaktionen**, Ungelesen-Zähler und Lesestand.
- **Seiten-Diskussion** an jeder Wiki-Seite, mit grauen Systemmeldungen (angelegt,
  veröffentlicht, verschoben, Papierkorb, Version wiederhergestellt), ausblendbar.
- **Aktivität „Für mich“** (Erwähnungen und Antworten) mit Zähler in Seitenleiste und
  Fenstertitel; die **Suche** findet auch Nachrichten, nur aus sichtbaren Gesprächen.
- **Live-Zustellung** über Server-Sent Events (`/api/stream`), auch über mehrere
  API-Knoten; ein **Worker** (`HERD_ROLE=worker`, in `all` enthalten) verteilt die
  Ereignisse der Outbox.
- **Einsicht in Direktnachrichten** für Administratoren: nur lesend, mit Begründung,
  60 Minuten, im Audit, und die Teilnehmenden sehen, dass eingesehen wurde.

Aus M4 Tickets:

- **Tickets** je Bereich mit Schlüssel (`HC-42`): Epic, Story, Aufgabe, Fehler in einer
  Hierarchie von höchstens drei Ebenen, Priorität, Fälligkeit, zugewiesene Person
  („Übernehmen“, „Abgeben“, zuweisen ab Moderator), Markdown-Beschreibung.
- **Status-Workflow je Bereich** (Standard: Neu, In Arbeit, Zur Prüfung, Erledigt,
  Verworfen; anlegen, umbenennen, ordnen, löschen mit Ersatz); was zählt, ist die
  Kategorie des Status, nie sein Name.
- **Ansichten:** Liste über alle sichtbaren Bereiche mit Filtern in der Adresse und
  „Meine Tickets“ (mit Zähler in der Seitenleiste), **Board** je Bereich (ziehen, per
  Tastatur oder über das Menü, live bei allen), **Epic-Übersicht** mit Fortschritt.
- **Ticket-Diskussion** mit grauen Systemmeldungen je Änderung, ausblendbar;
  Zuweisungen und Kommentare zu eigenen Tickets in der Aktivität. **Kanäle bleiben frei
  von Ticketmeldungen:** Ein Schlüssel oder Link in einer Nachricht zeigt nur eine Karte,
  die sich selbst aktualisiert, und nur, wer das Ticket sehen darf.
- **Verknüpfte Seiten** (von beiden Seiten, auch über Bereichsgrenzen; sichtbar nur, wer
  beide Enden sieht), **Tags** und **Suche** (Strg+K findet Tickets, auch über
  `HC-42`).

Aus M4b Boards und Sprints:

- **Sprints je Bereich** (Reiter „Sprints“): anlegen, starten (höchstens einer läuft),
  abschließen mit der Wahl, ob Unerledigtes in den nächsten Sprint oder zurück in den
  Vorrat geht; die Bilanz (geplant, erledigt, übertragen) bleibt am Sprint. Der Wechsel
  des Sprints steht als Systemmeldung in der Ticket-Diskussion, nie in einem Kanal.
- **Vorrat** (Reiter „Vorrat“): Tickets ohne Sprint, mehrere auf einmal „in Sprint
  legen“. Am Ticket das Feld „Sprint“.
- **Mein Board** (Seitenleiste): alle mir zugewiesenen Tickets aller Bereiche, Spalten
  nach Kategorie; Ziehen setzt den ersten Status dieser Kategorie im Bereich des Tickets.
- **Daily-Ansicht:** das Board eines Bereichs „nach Person gruppiert“, voreingestellt
  auf den laufenden Sprint, mit Hervorhebung dessen, was seit dem letzten Arbeitstag den
  Status gewechselt hat; ein Klick auf eine Person filtert auf sie.

Aus M5 (Tasks 1 bis 7) die KI-Grundlage:

- **KI-Verbindungen** zu Anbietern mit OpenAI-Protokoll (auch kompatible und lokale),
  Schlüssel verschlüsselt oder als Verweis auf eine Umgebungsvariable, Verbindungstest,
  Modellliste; ausgehende Aufrufe nur über eine SSRF-Sperre oder einen Proxy.
- **Wer welches Modell nutzt**: Zuordnung je Person, Gruppe oder als Standard; daraus
  das Recht `ai.use`. **Verbrauch** je Aufruf (Token, Kosten) nach Tag, Person, Agent,
  Bereich oder Verbindung.
- **KI-Richtlinie je Bereich** (alle, nur bestimmte Datenorte, keine KI) und
  **KI-Sperre** für einzelne Seiten und Dateien.

Aus M6 Agenten als Mitarbeiter:

- **Agenten** mit Stufe (1 lesen, 2 vorschlagen, 3 intern schreiben) und
  Werkzeugfreigaben je Werkzeug („wie die Stufe“, „nur nach Freigabe“, „gesperrt“);
  sie sind Mitglied in Bereichen wie Personen und lesen nie mehr als die fragende
  Person, ihr eigenes Mitglied-Sein und das Publikum des Ortes erlauben.
- **Ansprechen**: Direktnachricht, `@`-Erwähnung in Kanal, Seiten- oder
  Ticket-Diskussion (Antwort im Thread), **Ticket-Zuweisung** mit Übergabe an andere
  Agenten; erledigt setzt immer ein Mensch.
- **Freigaben und Rückfragen** als Karten im Gespräch, Liste „Freigaben“;
  **Laufansicht** mit jedem Schritt, **Abbruch**; nach einem Absturz des Workers setzt
  ein anderer den Lauf aus seinem Journal fort, ohne eine Wirkung doppelt auszuführen.
- **Vorschläge** von Seiten und Skills mit Annehmen, Ablehnen und Zusammenführen;
  **Skills** (SKILL.md, organisationsweit oder je Bereich, mit Versionen, Import und
  Export); **Gedächtnis** je Agent und Bereich als normale Wiki-Seite; **persönliche
  Agenten** je Person; alles, was ein Agent schreibt, trägt das KI-Kennzeichen.

Aus M7 Automatisierung:

- **Aufgaben**: Ein Agent arbeitet ohne Anstoß, einmalig zu einem Zeitpunkt,
  wiederkehrend nach Zeitplan (in der Zeitzone der Aufgabe), als **Herzschlag** (meldet
  sich nur, wenn es etwas zu sagen gibt) oder als **Ereignisregel** (etwa „Ticket
  angelegt“, mit Ruhezeit und Ketten-Tiefe). Jede Aufgabe gehört einer Person und
  einem Ort, schreibt einen Verlauf jedes Termins und pausiert nach wiederholten
  Fehlschlägen; „Jetzt ausführen“, Pausieren und Übernehmen in der Oberfläche.
- **Budgets** je Organisation, Person oder Agent (Token oder Euro je UTC-Tag); ein Lauf
  über dem Budget endet mit dem Grund `budget`.
- **Prüffrist** je Bereich: Seiten, die zu lange nicht geprüft wurden, tragen „Prüfung
  fällig“; die Verantwortlichen bekommen eine Erinnerung.

Aus M8 die Öffnung über MCP:

- **`/mcp` für externe KI-Clients** (Claude Code, Codex): persönliche Zugangstoken
  (einmal angezeigt, nur gehasht gespeichert, mit Umfang und Ablauf), lesende und mit
  `write` schreibende Werkzeuge, nie mehr als die Person darf, nie Entwürfe oder
  KI-gesperrte Inhalte; was ein Token schreibt, trägt das KI-Kennzeichen.
- **Externe Agenten** als Teammitglieder mit Agenten-Token: holen zugewiesene Tickets
  ab und bringen sie bis „Zur Prüfung“.
- **Externe MCP-Server** als Werkzeugquelle der eigenen Agenten: jedes Werkzeug einzeln
  freigegeben (gesperrt, wenn der Server es ändert), schreibende nur mit Freigabe der
  fragenden Person; **Konnektoren** (Token oder OAuth, geteilt oder persönlich) und ein
  **Katalog** mit GitHub und GitLab, erweiterbar ohne Codeänderung.

Aus M9a der Betrieb in Produktion:

- **Sicherung** des ganzen Datenstands (Datenbank und Anhänge aus einem Snapshot) als
  geprüftes Archiv, über die Kommandozeile (`python -m app.ops backup …`) und nach
  Zeitplan (Compose-Dienst `backup`, CronJob im Chart) mit Aufbewahrung
  (Großvater-Vater-Sohn), verschlüsselter Offsite-Kopie mit restic und Alarmen;
  **Wiederherstellung** in eine leere Installation (`python -m app.ops restore …`), als
  Probe durchgespielt; seit M9b auch **im laufenden Betrieb** (`restore apply …
  --replace --confirm "<Organisation>"`): erst ein Sicherheitsarchiv, dann der
  **Wartungsmodus** (die API antwortet 503, der Worker pausiert), der Tausch in einer
  Transaktion (scheitert er, bleibt der alte Stand ganz), danach ist jede Person
  abgemeldet. Inhaber erledigen das alles auch in **Verwaltung → Sicherung**: sichern auf
  Knopfdruck, Archive herunter- und hochladen, gegen die Installation prüfen und
  einspielen (Bestätigung mit dem Namen der Organisation, danach die Wartungsseite).
- **Anmeldung über OpenID Connect**: Google als Vorlage (nur Client-ID und Secret
  eintragen), jeder andere Anbieter mit Discovery (Keycloak, Entra ID …); Konten
  verknüpfen im Profil. **Selbstregistrierung** für erlaubte Domains: das neue Konto
  wartet, bis ein Admin es freigibt („ohne Freigabe kommt niemand ins System“), und hat
  keine KI, bis ein Admin sie zuordnet.
- **Härtung**: Der Collab-Prozess bekommt kurzlebige, an eine Seite gebundene
  Berechtigungen statt des Sitzungs-Cookies; häufige und geleakte Passwörter werden
  abgelehnt; Cookies unter https mit `__Host-`; Admins melden eine Person überall ab;
  jede Tabelle hat eine Aufbewahrungsregel. Geprüft gegen OWASP ASVS 5.0 Stufe 2
  ([`docs/SICHERHEIT.md`](docs/SICHERHEIT.md)).
- **Chart** mit Autoskalierung (HPA) für API und Worker, PodDisruptionBudgets,
  Sicherungs-CronJob und gemessenen Requests; **Lasttest** mit 200 Personen
  ([Steckbrief](docs/STECKBRIEF.md#gemessen-lasttest-mit-200-personen-m9)).

Bedienung und Betrieb des Wikis: [`docs/WIKI.md`](docs/WIKI.md), der Nachrichten:
[`docs/NACHRICHTEN.md`](docs/NACHRICHTEN.md), der Tickets:
[`docs/TICKETS.md`](docs/TICKETS.md), der KI-Anbindung (Verbindungen, Schlüssel,
Zuordnung, Verbrauch, Richtlinie): [`docs/KI.md`](docs/KI.md), der Agenten (Bedienung,
Verwaltung, Worker, Metriken) und der Aufgaben: [`docs/AGENTEN.md`](docs/AGENTEN.md), von
MCP (Token, `/mcp` mit Claude Code und Codex, externe Agenten, Server, Konnektoren,
Katalog, Betrieb): [`docs/MCP.md`](docs/MCP.md), von Sicherung und Wiederherstellung:
[`docs/SICHERUNG.md`](docs/SICHERUNG.md), der Anmeldung (Passwort, OIDC, Freigabe):
[`docs/ANMELDUNG.md`](docs/ANMELDUNG.md), die Installation auf einem Hostinger-VPS:
[`docs/HOSTINGER.md`](docs/HOSTINGER.md), die Sicherheitsprüfung:
[`docs/SICHERHEIT.md`](docs/SICHERHEIT.md).

Weitere Dokumente: [Steckbrief](docs/STECKBRIEF.md) (Betriebsdaten, gemessene
Ressourcen), [Demo M1](docs/demo/m1.md), [Demo M2](docs/demo/m2.md),
[Demo M3](docs/demo/m3.md), [Demo M4](docs/demo/m4.md), [Demo M6](docs/demo/m6.md),
[Demo M7](docs/demo/m7.md), [Demo M8](docs/demo/m8.md), [Demo M9](docs/demo/m9.md),
[Compose-Referenz](deploy/compose/README.md),
[Helm-Chart](deploy/helm/to-herd-cats-ai/values.yaml).

## Installation auf einem Hostinger-VPS (der einfachste Weg)

Ohne Kommandozeile, ohne eigenen Proxy: Im Hostinger Docker Manager **Compose from URL**
mit `https://github.com/janschachtschabel/to-herd-cats-ai-harness` bereitstellen, dann
in der `.env` `DOMAIN`, `ADMIN_EMAIL` und `ADMIN_PASSWORD` eintragen und erneut
bereitstellen. Die [`docker-compose.yml`](docker-compose.yml) im Hauptordner nimmt das
fertige Image von GHCR, erzeugt alle Geheimnisse beim ersten Start selbst und bekommt
HTTPS von Hostingers Traefik. Schritt für Schritt, die Felder der `.env`, DNS, Updates,
Sicherungen und Diagnose: [`docs/HOSTINGER.md`](docs/HOSTINGER.md). Derselbe Stack läuft
auf jedem Server mit einem Traefik auf 80/443 (`docker compose up -d` im Hauptordner).

## Schnellstart mit Docker Compose

Voraussetzung: Docker mit Compose v2.

```bash
cd deploy/compose
cp .env.example .env          # jeden Wert ersetzen, z. B. mit `openssl rand -hex 24`
docker compose up -d --build --wait
```

Dann <http://127.0.0.1:8080> öffnen und mit `HERD_BOOTSTRAP_ADMIN_EMAIL` und
`HERD_BOOTSTRAP_ADMIN_PASSWORD` aus `.env` anmelden. Diese erste Person (Inhaberin)
entsteht nur beim allerersten Start. Ihr Passwort muss die Passwortregeln erfüllen
([`docs/ANMELDUNG.md`](docs/ANMELDUNG.md): 10 bis 200 Zeichen, nicht auf der Liste
geleakter Passwörter, kein Wort aus Organisation oder Adresse); sonst bricht der Start
mit „bootstrap refused“ und Exit-Status 4 ab, und es wird nichts angelegt. Das Passwort
danach in der App ändern (Menü oben
rechts → „Profil und Einstellungen“; dort ändert jede Person ihr eigenes Passwort und
ihre Sprache).

`docker compose down` hält die Daten (Volumes `db-data` für die Datenbank, `app-data`
für die Anhänge unter `/data`), `down -v` löscht sie. Zwei Werte in `.env` betreffen
das Wiki:

- `HERD_INTERNAL_TOKEN` (Pflicht in Compose, mindestens 32 Zeichen, `openssl rand -hex
  32`): das gemeinsame Geheimnis von API und Collab-Prozess; es schaltet die
  Live-Bearbeitung ein (der Collab-Prozess läuft im selben Container).
- `HERD_PUBLIC_URL` (optional, z. B. `https://wiki.example`): die Adresse, unter der
  Browser die App öffnen. WebSocket-Verbindungen der Live-Bearbeitung werden nur von
  dieser Origin angenommen; leer muss die Origin zum angefragten Host passen. Hinter
  einem Reverse Proxy, der den Host umschreibt, also setzen.

In Compose läuft alles in einem App-Container (`HERD_ROLE=all`: API, Worker der
Outbox und der Läufe der Agenten, Collab-Prozess). KI-Schlüssel (`HERD_SECRET_KEY`,
Anbieterschlüssel `HERD_AI_<NAME>`, optional `HERD_AI_EGRESS_PROXY`) gehören in die
optionale Datei `deploy/compose/ai.env` (Vorlage `ai.env.example`); ohne sie startet
die App wie bisher, nur ohne verschlüsselte Schlüssel. Zum Ausprobieren mehrerer API-Knoten gibt es die Überlagerung
`compose.nodes.yml`: zwei API-Dienste (`api-a`, `api-b` auf `HERD_HOST_PORT` und
`HERD_HOST_PORT_B`, Standard 8081), ein eigener `worker`, ein eigener `collab` und ein
einmaliger `migrate` statt `app`
(`docker compose -f compose.yml -f compose.nodes.yml up -d --wait`).

Sicherung, Wiederherstellung, Reverse-Proxy und alle Variablen:
[`deploy/compose/README.md`](deploy/compose/README.md).

## Kubernetes mit Helm

```bash
helm install herd deploy/helm/to-herd-cats-ai \
  --set postgresql.enabled=false \
  --set database.url=postgresql+asyncpg://herd@db.example:5432/herd \
  --set database.existingSecret=herd-db \
  --set secrets.existingSecret=herd-env
```

Das Secret `herd-db` enthält das Datenbank-Passwort unter dem Schlüssel `password`,
`herd-env` die Variablen `HERD_BOOTSTRAP_ADMIN_EMAIL` und
`HERD_BOOTSTRAP_ADMIN_PASSWORD`. Jeder Wert ist in [`values.yaml`](deploy/helm/to-herd-cats-ai/values.yaml) beschrieben;
`ci/production-values.yaml` ist ein vollständiges Beispiel (externe Datenbank, Ingress
mit TLS, NetworkPolicy, ServiceMonitor, PrometheusRule, Autoskalierung, Sicherung mit
Offsite, OIDC), `ci/full-values.yaml` schaltet alles zugleich ein. Vor dem Einsatz die
[Betriebshinweise](#betriebshinweise) lesen. Lokal ohne helm prüft
`cd backend && uv run python ../deploy/helm/scripts/check_values.py` jede Werte-Datei
gegen `values.schema.json` und jede `@param` gegen das Schema (auch als Test
`tests/test_chart_values.py`).

> **Wichtig – Volume für Anhänge:** Das Chart legt den PersistentVolumeClaim
> `<release>-data` (10Gi, `/data`) mit **`ReadWriteMany`** an, weil alle API-Replikas
> (Standard 2) dieselben Dateien lesen und schreiben. Gibt es im Cluster keine
> Speicherklasse mit ReadWriteMany (etwa NFS, CephFS, Azure Files, EFS), bleibt der
> Claim `Pending` und die API-Pods starten nicht. Dann
> `--set api.replicas=1 --set 'persistence.accessModes={ReadWriteOnce}'` setzen (mehr
> Replikas mit ReadWriteOnce lehnt das Chart ab) oder mit `persistence.existingClaim`
> einen eigenen Claim nutzen. Der Claim bleibt bei `helm uninstall` erhalten. Oder die
> Anhänge in einen S3-kompatiblen Speicher legen (`s3.enabled`, siehe
> [`docs/SICHERUNG.md`](docs/SICHERUNG.md#anhänge-in-s3)); dann genügt
> `persistence.enabled=false`.

Das Chart legt außerdem an: den Collab-Prozess (`<release>-collab`, Live-Bearbeitung)
mit genau einer Replika und `strategy: Recreate` (die Dokumente einer Live-Sitzung
liegen im Speicher dieses einen Prozesses; zwei Prozesse würden die Bearbeitenden einer
Seite aufteilen), ein erzeugtes Secret `<release>-internal-token` mit dem Token, das API
und Collab-Prozess teilen (bleibt bei Upgrades und Deinstallation erhalten; mit `helm
template`/GitOps stattdessen `collab.internalToken.existingSecret` setzen), und einen
PersistentVolumeClaim `<release>-data` für die Anhänge unter `/data`. Ihn lesen und
schreiben alle API-Replikas, deshalb ist `ReadWriteMany` voreingestellt; ohne solche
Speicherklasse `api.replicas=1` und `persistence.accessModes={ReadWriteOnce}` setzen
(mehr Replikas mit `ReadWriteOnce` lehnt das Chart ab). Live-Bearbeitung ist ein
WebSocket unter `/collab/` am selben Service wie die API; der Ingress-Controller muss
das Upgrade durchreichen (ingress-nginx und Traefik tun es ohne Einstellung). Zu
Leerlauf-Timeouts und Größenlimits am Ingress siehe
[Betriebshinweise](#betriebshinweise).

Seit M3 gehört dazu der Worker der Outbox: ein Deployment `<release>-worker`
(`HERD_ROLE=worker`, nur Port 9090; `worker.replicas`, Standard 1, mehrere sind sicher;
`worker.env` für eigene Variablen, `api.env` gilt dort nicht; `worker.resources`,
voreingestellt Request 250m/256Mi, Limit 384Mi, gemessen im Lasttest) mit einem headless Service
`<release>-worker`, über den der ServiceMonitor seine Metriken holt. Mit
`worker.replicas: 0` kommt nichts mehr live an; das meldet der Alarm `HerdWorkerAbsent`.
Die PrometheusRule hat vier neue Alarme: `HerdOutboxBacklog` (das älteste offene
Ereignis ist älter als 5 Minuten, kritisch), `HerdOutboxFailed` (die Zahl aufgegebener
Ereignisse in der Datenbank ist gestiegen, Warnung), `HerdWorkerStalled` (ein Worker hat
seit über 3 Minuten keinen Durchlauf abgeschlossen, Warnung) und `HerdWorkerAbsent`
(API-Pods laufen, aber kein Worker ihres Releases meldet sich, kritisch). Die Live-Zustellung (`/api/stream`, Server-Sent Events)
braucht am Ingress ungepufferte Antworten und ein Lese-Timeout von mindestens 1 h; das
Chart setzt keine Annotation dafür (Controller unterscheiden sich), `values.yaml`
beschreibt sie und `ci/production-values.yaml` setzt für ingress-nginx
`proxy-read-timeout` und `proxy-send-timeout` auf 3600.

Seit M5/M6 arbeitet der Worker auch die Läufe der Agenten ab, seit M7 auch die fälligen
Aufgaben. Die KI-Schlüssel kommen
aus einem eigenen Secret `ai.existingSecret` (Schlüssel = Variablennamen, etwa
`HERD_SECRET_KEY`, `HERD_AI_OPENAI_KEY`); es geht an API und Worker, nie an den
Migrations-Job. Die Grenzen stehen unter `ai.*` (`checkTimeoutSeconds`,
`personalAgentsMax` und `automationsMax` für die API; `approvalHours`, `runConcurrency`, `runLeaseSeconds`
für den Worker). Mit `networkPolicy.enabled` erreichen API und Worker keinen Anbieter,
bis `networkPolicy.aiEgress` Regeln nennt (zum Anbieter oder zum Proxy). Drei Alarme
kommen dazu: `HerdRunsStuck`, `HerdRunsQueued` und `HerdRunsFailing`, mit M7 zwei
weitere: `HerdAutomationsLagging` und `HerdAutomationsFailing` (alle Warnung).
Seit M8 begrenzt `mcp.ratePerMinute` (`HERD_MCP_RATE_PER_MINUTE`, Standard 120) die
Aufrufe je Zugangstoken und Minute, gezählt in PostgreSQL über alle API-Pods;
`mcp.maxCallsPerRun` (Worker, Standard 20) die Aufrufe externer Werkzeuge je Lauf,
`mcp.allowedHosts` (API und Worker) die privaten Hosts externer MCP-Server und
`mcp.catalogConfigMap` (API) eine ConfigMap eigener Katalog-Vorlagen. `/mcp` geht mit
dem Standardpfad `/` des Ingress an die API und braucht keine Annotation (kurze
JSON-Antworten). Vier Alarme kommen dazu: `HerdExternalToolsFailing`,
`HerdOAuthRefreshFailing`, `HerdMcpAuthFailures` und `HerdMcpCatalogProblems` (alle
Warnung; [`docs/MCP.md`](docs/MCP.md#betrieb)).
Einzelheiten: [`docs/AGENTEN.md`](docs/AGENTEN.md#umgebungsvariablen).

Seit M9 skaliert das Chart auf Wunsch selbst und hält Pods bei Wartungen: Mit
`api.autoscaling.enabled` bzw. `worker.autoscaling.enabled` (Standard aus) legt es je
einen HorizontalPodAutoscaler (`autoscaling/v2`) auf CPU an, Ziel 70 % des
CPU-Requests, API 2 bis 6 Pods, Worker 1 bis 3; das Deployment nennt dann keine
`replicas` mehr. Das braucht metrics-server und einen CPU-Request (sonst bricht das
Chart ab; voreingestellt sind die im Lasttest gemessenen 500m für die API und 250m für
den Worker, siehe [Steckbrief](docs/STECKBRIEF.md#empfehlung-request-und-limit)), mehr als ein API-Pod braucht die
Anhänge-PVC mit ReadWriteMany. Herunter geht es behutsam (ein Pod je 2 Minuten nach 5
ruhigen Minuten). Jeder Pod hält bis zu 16 Datenbankverbindungen; die Grenzen so
wählen, dass `max_connections` der Datenbank reicht (Rechnung im
[Steckbrief](docs/STECKBRIEF.md#clusterfähigkeit)). Der Alarm `HerdAutoscalerAtMax`
meldet einen Autoscaler, der 30 Minuten am Maximum steht (braucht kube-state-metrics).
`podDisruptionBudget` (Standard an, `maxUnavailable: 1`) legt für API und Worker je ein
PodDisruptionBudget an, sobald sie mindestens zwei Pods haben (Replikas oder
`minReplicas`); ein einzelner Pod und der Collab-Prozess (eine Replika) bekommen keins,
damit ein Knoten-Drain nie hängt. Dazu kommen der Sicherungs-CronJob
([`docs/SICHERUNG.md`](docs/SICHERUNG.md#betrieb-compose-und-helm)) und die Werte der
Anmeldung über OIDC (`oidc.*`, mit `oidc.egress` für die NetworkPolicy der API-Pods;
[`docs/ANMELDUNG.md`](docs/ANMELDUNG.md)). Geheimnisse kommen nur aus Secrets: Das
Schema lehnt in `api.env`, `worker.env` und `collab.env` Namen mit `PASSWORD`, `SECRET`,
`TOKEN`, `EGRESS_PROXY` oder `OFFSITE` ab.

Drei Werte betreffen jeden Betrieb hinter einem Ingress:

- `api.cookieSecure` (Standard `true`): Das Sitzungs-Cookie trägt `Secure`, der Browser
  schickt es nur über https (und an `localhost`, etwa bei `kubectl port-forward`). Nur
  auf `false` setzen, wenn die App absichtlich über reines http erreicht wird.
- `api.forwardedAllowIps` (`HERD_FORWARDED_ALLOW_IPS`): die Adressen der
  Ingress-Controller-Pods, z. B. das Pod-Netz `10.0.0.0/8`. Nur deren
  `X-Forwarded-For`/`-Proto` glaubt die App. Ohne den Wert hätte jeder Client die
  Adresse des Ingress-Pods (im Audit und für die Anmeldelimits, die dann für alle
  zusammen gälten). Mit `ingress.enabled` ist der Wert Pflicht; das Chart bricht sonst
  mit einer Meldung ab.
- `publicUrl` (`HERD_PUBLIC_URL`): die Adresse, unter der Browser die App öffnen;
  WebSocket-Verbindungen der Live-Bearbeitung müssen von ihr kommen. Leer nimmt das
  Chart den ersten Ingress-Host (mit TLS als https).

## Entwicklung

Voraussetzungen: Python 3.13 mit [`uv`](https://docs.astral.sh/uv/), Node 22 mit npm,
PostgreSQL 16 oder neuer. Die Standard-URLs erwarten die Rolle `herd` (Passwort
`herd`) auf `localhost:5433` mit den Datenbanken `herd` und `herd_test`.

```bash
cd backend && uv sync
cd backend && HERD_BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
  HERD_BOOTSTRAP_ADMIN_PASSWORD=lantern-orbit-73-q HERD_LOG_FORMAT=text \
  uv run python -m app.launch          # migriert, dann API auf :8080, Proben auf :9090

cd frontend && npm ci && npm run dev   # Vite; leitet /api und /collab an http://localhost:8080 weiter
```

`HERD_ROLE` wählt, was der Prozess tut: `all` (Standard: migrieren, dann bedienen),
`api`, `migrate`, `worker` (der Verteiler der Outbox, die Läufe der Agenten, die
fälligen Aufgaben und der
interne Port 9090; mehrere Worker nebeneinander sind sicher) oder `collab` (nur der
Live-Bearbeitungsprozess, `node collab/server.mjs`). `all` enthält den Worker. In
`all` startet die API den Collab-Prozess als Kindprozess auf
`127.0.0.1:${HERD_COLLAB_PORT}`, wenn `HERD_INTERNAL_TOKEN` gesetzt ist (dafür
`cd collab && npm ci`); ohne Token bleibt die Live-Bearbeitung aus. Alle
Einstellungen sind `HERD_*`-Variablen (`backend/app/core/config.py`); die meisten
beschreiben die Dokumente ihres Bereichs (Sicherung, Anmeldung, KI, Agenten, MCP, Wiki,
Nachrichten) und `deploy/compose/README.md`. Grundeinstellungen der Prozesse, die selten
zu ändern sind:

| Variable | Standard | Wirkung |
|---|---|---|
| `HERD_PUBLIC_PORT` | `8080` | Port der API und der Weboberfläche (`/api`, `/mcp`, `/collab`) |
| `HERD_INTERNAL_PORT` | `9090` | Port für Proben (`/health`, `/ready`), Metriken (`/metrics`) und die Rückrufe des Collab-Prozesses (`/internal/*`); nie nach außen freigeben |
| `HERD_BOOTSTRAP_ORG_NAME` | `Meine Organisation` | Name der Organisation, die der allererste Start anlegt (die Oberfläche ändert ihn nicht; `restore apply --replace` verlangt ihn als Bestätigung); ein Wort daraus darf nicht im Passwort der ersten Inhaberin stehen |
| `HERD_SESSION_COOKIE_NAME` | `herd_session` | Name des Sitzungs-Cookies; über https mit dem Präfix `__Host-` ([`docs/ANMELDUNG.md`](docs/ANMELDUNG.md)) |
| `HERD_COLLAB_API_URL` | `http://127.0.0.1:<HERD_INTERNAL_PORT>` | Wo der Collab-Prozess die API erreicht (ihren internen Port); nur für die Rolle `collab` in einem eigenen Container oder Pod nötig (Compose und Chart setzen sie) |
| `HERD_COLLAB_SCRIPT` | `collab/server.mjs` des Quellstands (im Image `/app/collab/server.mjs`) | Das Skript, das `node` als Collab-Prozess startet; nur für eigene Pfade |
| `HERD_COLLAB_ADVERTISE_URL` | in Rolle `all` `ws://127.0.0.1:<HERD_COLLAB_PORT>` | Wo die API eine Collab-Instanz erreicht (`ws://host:port`); Pflicht für die Rolle `collab` (ohne startet sie nicht; Chart: Pod-IP, Compose: Containername); in Rolle `all` setzt die App sie selbst ([`docs/WIKI.md`](docs/WIKI.md), „Mehrere Collab-Instanzen“) |

Nach Änderungen an der API `npm run generate:api` im Frontend ausführen.

Demodaten für eine frische Test-Installation (drei Personen, der Bereich „Team Nord“
mit zwei Seiten, Kanäle mit Threads, Erwähnungen und Reaktionen, eine Direktnachricht,
eine Seiten-Diskussion mit Systemmeldungen, dazu elf Tickets: ein Epic mit Stories,
Aufgaben und einem Fehler in mehreren Status samt einem eigenen Status „Blockiert“,
Zuweisungen, Tags, eine verknüpfte Seite, Kommentare und ein Ticket-Schlüssel im Kanal;
drei Sprints: „Sprint 45“ abgeschlossen mit Bilanz, „Sprint 46“ laufend, „Sprint 47“
geplant, und ein Vorrat; der Worker muss laufen):

```bash
cd backend && HERD_DEMO_ADMIN_PASSWORD=lantern-orbit-73-q HERD_DEMO_PASSWORD=seed-people-pw-123 \
  uv run python -m scripts.demo_seed --base http://127.0.0.1:8080 --admin admin@example.com
```

Mit einem Modell legt dasselbe Skript auch Agenten bei der Arbeit an (Hilda und Otto in
„Team Nord“, ein Gespräch, ein Ticket bis „Zur Prüfung“, ein offener Vorschlag, eine
Gedächtnisseite und eine wartende Freigabe): `HERD_DEMO_AI_KIND` schaltet das ein
(`local`, `openai` oder `openai_compatible`, dazu `HERD_DEMO_AI_URL`; mit dem Stub
außerdem `HERD_DEMO_AI_STUB`, damit die Demo seine Antworten vorgibt). Einzelheiten in
`backend/scripts/demo_ai.py` (das Modell: `demo_ai_model.py`). Mit `--mcp-stub <URL>`
kommt ein MCP-Server auf dem MCP-Stub dazu, mit `--oidc-stub <Issuer>` ein
Anmeldeanbieter „Demo-Anmeldung“ auf dem OIDC-Stub (`backend/tests/support/oidc_stub.py`;
Selbstregistrierung für `demo.example`, Konten warten auf Freigabe). Dafür braucht die
App `HERD_PUBLIC_URL`, den Host des Stubs in `HERD_OIDC_ALLOWED_HOSTS`, das Secret des
Stubs als `HERD_OIDC_STUB_SECRET` und sein Zertifikat in `SSL_CERT_FILE`
([Demo M9](docs/demo/m9.md)). Ohne diese Schalter erreicht die Demo kein fremdes Netz.

### KI ausprobieren

Ohne echten Anbieter geht es mit dem Stub aus den Tests (`backend/tests/support/openai_stub.py`;
Testcode, nicht im Image):

```bash
cd backend && uv run python -m tests.support.openai_stub --port 8099
```

Dann in der App (Verwaltung → KI): eine Verbindung der Art `local` mit
`http://127.0.0.1:8099/v1` einrichten (ohne Schlüssel), „Modelle abrufen“ oder das
Modell `gpt-6-luna` eintragen, testen und unter der Zuordnung als „Standard der
Organisation“ wählen. Danach unter
Verwaltung → Agenten einen Agenten anlegen (aktiv, mit verantwortlicher Person) und ihm
eine Direktnachricht schreiben; der Worker muss laufen (`HERD_ROLE=all` oder ein
eigener `worker`). Der Stub antwortet „stub reply“; was er sagen oder welche Werkzeuge
er aufrufen soll, legt `POST /_stub/script` fest ([`docs/KI.md`](docs/KI.md#testen-ohne-anbieter)).
In Compose läuft der Stub nicht mit; die Verbindung braucht dort eine Adresse, unter der
der App-Container den Stub erreicht (Stub mit `--host 0.0.0.0`). Diesen Weg hat hier
niemand geprüft.

Regeln für Beiträge: [`CLAUDE.md`](CLAUDE.md) (Schichten, `org_id`, Paginierung,
Fehlerform, i18n, Lizenzen, Commit-Format). Neue Funktionen beginnen mit einem
fehlschlagenden Test.

## Prüfbefehle

Die Tests brauchen PostgreSQL (`HERD_TEST_DATABASE_URL`, Standard
`postgresql+asyncpg://herd:herd@localhost:5433/herd_test`). Der Zwei-Knoten-Test der
Live-Zustellung (`backend/tests/test_live_two_nodes.py`) legt eine Wegwerf-Datenbank an
und braucht dafür CREATEDB für die Rolle `herd` (einmal als Superuser:
`ALTER ROLE herd CREATEDB`; in der CI ist `herd` Superuser).

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy app scripts && uv run python -m scripts.check_migrations
cd frontend && npm run lint && npm run typecheck && npm test && npm run build \
  && node scripts/check-i18n.mjs && npm run check:api
cd collab && npm run lint && npm test && npm run test:integration   # Integration: echte API,
                                       # Wegwerf-Datenbank (psql, uv nötig), zwei Yjs-Clients
cd e2e && npm ci && npx playwright install chromium && npx playwright test
                                       # Browser: Live-Bearbeitung, Nachrichten, Tickets und Agenten mit zwei
                                       # Personen in der echten App (Rolle all mit Worker,
                                       # Wegwerf-Datenbank); vorher
                                       # `npm run build` in frontend/. Ein vorhandenes Chromium
                                       # nimmt PLAYWRIGHT_CHROMIUM_EXECUTABLE.
docker build -t to-herd-cats-ai:local . && bash deploy/compose/smoke.sh   # endet mit SMOKE OK
SMOKE_NODES=1 bash deploy/compose/smoke.sh   # zwei API-Knoten und Worker: Nachricht an A,
                                       # live über /api/stream an B; beide Läufe legen
                                       # ein Ticket an und warten auf die Systemmeldungen
bash deploy/compose/load.sh            # Ressourcen und Laufzeiten für den Steckbrief
```

Helm-Chart, Lizenzprüfung und Release stehen in `CLAUDE.md`. Die CI
(`.github/workflows/ci.yml`) führt für jeden Pull Request, jeden Push auf `main` und
(über `release.yml`) jedes Release-Tag alles davon aus, dazu `pip-audit`,
`npm audit`, `kubeconform`, `promtool` und Trivy.

## Betriebshinweise

Bekannte Grenzen und bewusste Entscheidungen aus M1 bis M9a. Wer betreibt, sollte sie
kennen. Was beim Update auf eine neue Version zu beachten ist, steht unter
[Freigaben und Updates](#freigaben-und-updates).

Die Prüfung gegen OWASP ASVS 5.0 Stufe 2, die Betriebsvoraussetzungen der Sicherheit
(TLS am Ingress, eigener Hostname, Schutz der Protokolle) und die offenen Lücken stehen
in [`docs/SICHERHEIT.md`](docs/SICHERHEIT.md).

- **Sicherung** (M9): `python -m app.ops backup create|verify|list` schreibt und prüft
  Archive des ganzen Datenstands (Datenbank und Anhänge aus einem Snapshot) nach
  `HERD_BACKUP_DIR`; `backup run` dazu mit Aufbewahrung und restic-Kopie, nach Zeitplan
  im Compose-Dienst `backup` bzw. im CronJob des Charts, mit Alarmen; `restore
  check|apply` spielt in eine leere Installation ein, `restore apply --replace --confirm
  "<Organisation>"` ersetzt eine laufende (Sicherheitsarchiv, Wartungsmodus mit 503,
  `python -m app.ops maintenance status|off`). Format, Schlüssel, Fehlercodes und
  Betrieb in [`docs/SICHERUNG.md`](docs/SICHERUNG.md). Archive sind unverschlüsselt: das
  Volume schützen und `HERD_SECRET_KEY` getrennt aufbewahren.
- **Autoskalierung und Datenbankverbindungen** (M9): Jeder API- und Worker-Prozess hat
  einen Pool von 5 Verbindungen, der unter Last um bis zu 10 wächst, dazu eine für
  LISTEN: höchstens 16 je Pod, und das erreicht ein API-Pod unter Last auch (gemessen im
  Lasttest: 2 API und 1 Worker hielten bis 33 Verbindungen). Mit den Standardgrenzen der Autoscaler (API 6, Worker 3)
  sind das im Ruhezustand 54, in der Spitze 144 Verbindungen, mit Backup-Job und
  Migration rund 150. PostgreSQL hat ab Werk `max_connections = 100`: Für die vollen
  Grenzen eine externe Datenbank auf mindestens 160 setzen oder `maxReplicas` senken.
  Das mitgelieferte PostgreSQL des Charts startet mit `postgresql.maxConnections`
  (Standard 200), und das Chart rendert nicht, wenn 16 × (höchste Zahl der API- und
  Worker-Pods) + 10 darüber liegt. Einen Verbindungs-Pooler (PgBouncer) bringt das
  Chart nicht mit.
- **Datenbank-Passwort** nur über `HERD_DATABASE_PASSWORD` oder
  `HERD_DATABASE_PASSWORD_FILE` (beides zugleich ist ein Startfehler), nie in
  `HERD_DATABASE_URL`. Das Chart lehnt eine URL mit Passwort ab und legt das Passwort
  als Datei ein; Compose reicht `POSTGRES_PASSWORD` als `HERD_DATABASE_PASSWORD` durch.
- **TLS zur Datenbank (seit M9b):** `HERD_DATABASE_SSLMODE` (libpq-Modi; empfohlen für
  eine externe Datenbank `verify-full`) und `HERD_DATABASE_SSLROOTCERT` (CA-Datei; leer:
  die CAs des Systems) gelten für jede Verbindung der App und für
  `pg_dump`/`pg_restore` der Sicherung; sie gewinnen über ein `ssl`/`sslmode` in der
  URL. Chart `database.sslMode` und `database.caSecret` (Secret mit `ca.crt`).
- **Geheimnisse als Dateien:** Ebenso lesen `HERD_SECRET_KEY_FILE`,
  `HERD_INTERNAL_TOKEN_FILE`, `HERD_BOOTSTRAP_ADMIN_PASSWORD_FILE` und
  `HERD_S3_SECRET_ACCESS_KEY_FILE` den Wert aus einer Datei (ein Zeilenende am Schluss
  zählt nicht). Wert und Datei zugleich, eine unlesbare oder (bei Schlüsseln und
  Token) leere Datei sind Startfehler, die die Variable nennen, nie den Inhalt; ein
  leerer Wert neben der Datei (Compose: `${HERD_…:-}`) zählt als nicht gesetzt; eine
  leere Passwortdatei heißt „keine erste Person“. Die Regeln des Werts (Mindestlänge)
  gelten auch für die Datei. Der Hostinger-Stack
  ([`docs/HOSTINGER.md`](docs/HOSTINGER.md)) übergibt so jedes Geheimnis.
- **KI-Schlüssel** (M5): Verbindungen speichern den API-Schlüssel nie im Klartext,
  sondern als Verweis `env:HERD_AI_<NAME>` (Umgebungsvariable mit diesem Präfix; die
  eigenen Einstellungen mit dem Präfix wie `HERD_AI_EGRESS_PROXY` sind ausgenommen) oder
  verschlüsselt als `enc:` unter `HERD_SECRET_KEY` (mindestens 32 Zeichen, etwa
  `openssl rand -hex 32`; ohne ihn sind nur `env:`-Verweise möglich). Schlüsselwechsel:
  neuen Wert in `HERD_SECRET_KEY`, alten in `HERD_SECRET_KEY_PREVIOUS`, dann
  `cd backend && uv run python -m scripts.rotate_secrets`, danach
  `HERD_SECRET_KEY_PREVIOUS` entfernen. Das Skript ist nicht im Image: Es läuft aus
  einem Quellstand desselben Release gegen dieselbe Datenbank. Compose liest die
  Schlüssel aus `ai.env`, das Chart aus `ai.existingSecret`. Einzelheiten:
  [`docs/KI.md`](docs/KI.md).
- **Ausgehende Aufrufe an KI-Anbieter** gehen nur über die SSRF-Sperre
  (`backend/app/core/egress.py`: nur https, für die Art `local` auch http und private
  Adressen; Link-Local und Metadaten nie; keine Weiterleitungen; Proxy-Variablen der
  Umgebung werden nicht beachtet) oder über `HERD_AI_EGRESS_PROXY`. Im Chart sperrt die
  NetworkPolicy sie, bis `networkPolicy.aiEgress` sie freigibt; ohne Freigabe melden
  Verbindungstests `timeout` oder `unreachable`, und Läufe enden mit `error`.
- **Läufe der Agenten** (M5, M6) laufen im Worker: höchstens `HERD_RUN_CONCURRENCY`
  (Standard 4) je Worker, dafür bis zu so vielen Datenbankverbindungen mehr plus drei;
  `max_concurrency` und `requests_per_minute` einer Verbindung gelten über alle
  Worker. Stirbt ein Worker, nimmt ein anderer seine Läufe nach der Sperrfrist
  `HERD_RUN_LEASE_SECONDS` (Standard 30) auf und setzt sie aus dem Journal fort; ein
  Rollout (SIGTERM) gibt sie ebenso ab. Ohne Worker warten Läufe (`HerdRunsQueued`). Auf
  Freigaben und Rückfragen wartet ein Lauf höchstens `HERD_AI_APPROVAL_HOURS` (Standard
  72) und hält so lange seinen Thread. Läufe und Journal (Prompts, Antworten,
  Werkzeugergebnisse vollständig) werden nicht automatisch gelöscht. Der Worker braucht
  mit Läufen mehr Speicher (gemessen 173 MiB im Leerlauf, bis rund 250 MiB unter Last,
  [Steckbrief](docs/STECKBRIEF.md#agenten-m6)). Alarme, Metriken, bekannte Grenzen und
  das Rolling Update: [`docs/AGENTEN.md`](docs/AGENTEN.md#betrieb).
- **Aufgaben, Budgets, Prüffrist** (M7): Die Fälligkeits-Schleife jedes Workers sieht
  alle 5 Sekunden nach fälligen Aufgaben; mehrere Worker feuern jeden Termin genau
  einmal (Zeilensperre, eine Transaktion je Termin, eindeutiger Termin). Sie teilt sich
  den Prozess mit den Läufen: 1.000 gleichzeitig fällige Aufgaben waren mit einem
  Worker nach rund 100 Sekunden alle gefeuert, mit drei nach rund 50 bis 65
  ([Steckbrief](docs/STECKBRIEF.md#automatisierung-m7)); `HerdAutomationsLagging` meldet
  mehr als drei Minuten Rückstand. Höchstens `HERD_AI_AUTOMATIONS_MAX` Aufgaben je
  Person. Der Verlauf der Termine bleibt 90 Tage, aufgenommene Ereignisse 7 Tage;
  Ereignisse, die noch auf das Ende ihrer Ruhezeit warten, und alles, was ein offener
  Lauf noch liest, bleiben. Budgets gelten je UTC-Tag; jeder laufende Lauf kann eine
  Grenze um einen Aufruf überschreiten. Beim Update Worker zuerst ersetzen: Ein Worker
  des vorigen Releases lässt Herzschläge und Ereignisregeln fällig liegen. Einzelheiten:
  [`docs/AGENTEN.md`](docs/AGENTEN.md#aufgaben-im-worker-m7), [`docs/KI.md`](docs/KI.md),
  [`docs/WIKI.md`](docs/WIKI.md).
- **MCP** (M8): `/mcp` ist zustandsloses Streamable HTTP (je `POST` eine JSON-Antwort,
  keine Sitzungen, keine Streams) auf dem öffentlichen Port der API; jeder Knoten
  bedient jede Anfrage. Der Proxy reicht `Authorization` durch und setzt kein `Origin`
  (Anfragen mit `Origin` lehnt `/mcp` ab). Ohne den Schalter der Organisation (KI-Verwaltung,
  Standard aus) hat niemand Token, `/mcp` antwortet 401. Je Token höchstens
  `HERD_MCP_RATE_PER_MINUTE` Aufrufe je Minute; gemessen rund 25–45 ms je Aufruf allein
  und 45–70 Aufrufe je Sekunde mit 10 Clients an einem Prozess
  ([Steckbrief](docs/STECKBRIEF.md#mcp-m8)). Ausgehend rufen API (Werkzeuglisten,
  OAuth-Erneuerung) und Worker (Läufe) externe MCP-Server nur über die SSRF-Sperre oder
  `HERD_AI_EGRESS_PROXY` auf; private Hosts nur, wenn `HERD_MCP_ALLOWED_HOSTS` sie nennt.
  OAuth braucht `HERD_PUBLIC_URL` und `HERD_SECRET_KEY`. Ein Lauf sendet höchstens
  `HERD_MCP_MAX_CALLS_PER_RUN` externe Aufrufe; sie zählen zu keinem Budget.
  Einzelheiten, Metriken und Alarme: [`docs/MCP.md`](docs/MCP.md#betrieb).
- **Mitgeliefertes PostgreSQL im Chart** (`postgresql.enabled`, Standard `true`) ist
  zum Ausprobieren gedacht: ein Pod, keine Replikation, keine Sicherung. In Produktion
  `postgresql.enabled=false` und eine externe Datenbank setzen.
  Sein Passwort erzeugt das Chart einmal und liest es danach per `lookup` aus dem
  Cluster. Wer mit `helm template` ausrollt (Argo CD, Flux), bekommt dabei bei jedem
  Rendern ein neues Passwort, das nicht mehr zum Datenvolume passt: dort
  `database.existingSecret` auf ein selbst angelegtes Secret setzen.
- **Verklemmungen** (Deadlock, Serialisierungsfehler; SQLSTATE `40P01`, `40001`): Die
  Datenbank hat die Transaktion ganz zurückgerollt; die API antwortet 409
  `conflict.retry` mit `Retry-After: 1`, die Anfrage darf einfach wiederholt werden
  (Log `db.conflict_retry` mit dem SQLSTATE); die Weboberfläche wiederholt sie einmal
  von selbst (nach `Retry-After`, höchstens 2 s). Dieselbe Antwort gibt das Wegnehmen
  eines Tickets von einem Agenten, wenn ein Schritt seines Laufs dessen Zeile länger
  als 0,5 s hält. Ein Schritt eines Agentenlaufs wird bei einer Verklemmung einmal
  wiederholt (`runs.step_retried`).
- **Rollouts**: Ein API-Pod wartet beim Beenden 5 s (`preStop`), bis er aus den
  Endpunkten genommen ist, und hat dann bis zu 30 s, laufende Anfragen zu beenden
  (`terminationGracePeriodSeconds: 35`).
- **Migrations-Job**: Nur mit externer Datenbank ist er ein Helm-Hook
  (`pre-install,pre-upgrade`). Mit dem mitgelieferten PostgreSQL ist er ein normaler
  Job je Release-Revision, weil der Hook vor der Datenbank liefe; bis er fertig ist,
  starten die API-Pods neu.
- **Migrationen und `/ready`**: Ein Pod ist bereit, wenn die Datenbank auf dem Head
  seines Codes steht oder auf einer Revision, die sein Code nicht kennt (eine neuere
  Version hat vorab migriert). Nicht bereit ist er ohne Revision oder bei einer
  bekannten älteren. Deshalb müssen Migrationen mit der vorherigen Version verträglich
  sein: erst erweitern, frühestens eine Version später zurückbauen.
  `backend/alembic/RELEASED` nennt die Revision der letzten Freigabe (seit 1.0.0
  `9e4b6d2f8a17`; beim Taggen auf den Head setzen, `release.yml` prüft es). `scripts/check_migrations.py` (CI-Job
  `backend`) lehnt in jeder späteren Revision Löschen, Umbenennen und Typwechsel ab
  (`drop_*`, `rename_table`, `alter_column(type_=…/new_column_name=…)`, `op.execute`
  mit `DROP`/`RENAME`), außer die Revision erklärt `contract_of = "<Revision>"` und
  diese gehört schon zur Freigabe; außerdem genau ein Head.
- **Alarm `HerdNotReady`** braucht kube-state-metrics (`kube_pod_status_ready`,
  `kube_pod_container_info`). Ohne kube-state-metrics feuert er nie.
- **Port 9090** (`/health`, `/ready`, `/metrics`) hat keine Anmeldung; ihn schützt nur
  das Netz (Compose veröffentlicht ihn nicht, im Chart kein Ingress, optional
  `networkPolicy.internalFrom`). Die interne Collab-Schnittstelle `/internal/*` auf
  demselben Port verlangt zusätzlich den Header `X-Herd-Internal-Token` gleich
  `HERD_INTERNAL_TOKEN` (mindestens 32 Zeichen, etwa `openssl rand -hex 32`; API und
  Collab-Prozess brauchen denselben Wert). Ohne gesetztes Token antwortet `/internal/*`
  immer mit 503 (`internal.disabled`), und die Live-Bearbeitung ist aus.
- **Live-Bearbeitung**: Browser verbinden sich per WebSocket mit
  `/collab/<seiten-id>?generation=<collab_generation>` am öffentlichen Port; die API
  prüft Origin (gleich dem von `HERD_PUBLIC_URL`, ohne diese gleich dem angefragten
  Host; sonst HTTP 403), Sitzungs-Cookie, Sichtbarkeit, `page.edit` und die Generation
  wie die REST-API und reicht erst dann Frames an die Collab-Instanz weiter, an die die
  Seite gebunden ist (jede meldet ihre Adresse `HERD_COLLAB_ADVERTISE_URL`; in Rolle
  `all` der Kindprozess auf `127.0.0.1`; mehrere Instanzen: `docs/WIKI.md`, „Mehrere
  Collab-Instanzen“). Abgelehnt wird mit
  Schließcodes, die der Browser lesen kann: 4401 (keine gültige Sitzung), 4403 (kein
  Recht, oder Recht entzogen), 4404 (Seite nicht sichtbar), 4409 (die Generation ist
  beendet: Seite neu laden), 4413 (Zustand oder Markdown zu groß für die
  Live-Bearbeitung; der Browser bietet den Markdown-Editor an), 4400 (Speicherung aus
  anderem Grund abgelehnt), 4422 (`collab.not_roundtrip_safe`:
  der Live-Editor würde die Bedeutung des Markdowns ändern, siehe `docs/WIKI.md`; der
  Browser bietet den Markdown-Editor an), 4429 (zu viele Verbindungen dieser
  Anmeldung oder Person: höchstens 3 je Seite und 10 insgesamt je Anmeldung, 20 je
  Person über alle ihre Anmeldungen und nie mehr als ein Viertel aller 200, im
  Collab-Prozess einstellbar mit `HERD_COLLAB_MAX_PER_PAGE`,
  `HERD_COLLAB_MAX_PER_SESSION` und `HERD_COLLAB_MAX_PER_PERSON`), 4507 (der
  Collab-Prozess hält sein Speicherbudget: später erneut oder im Markdown-Editor; der
  Browser verbindet sich nicht selbst neu), 4502/4503
  (keine Collab-Instanz erreichbar, der Browser versucht es weiter, bzw. aus), 4504 (Prüfen und Verbinden dauerten
  länger als 10 s), 4408 (der Browser ist dem Dokument nicht binnen 10 s
  beigetreten, oder die Verbindung hat 15 Minuten lang nichts gesendet,
  `HERD_COLLAB_IDLE_MINUTES`; ein offener Editor meldet seine Anwesenheit alle 15 s), 1013 (später erneut versuchen); bei 4408, 4504 und 1013 verbindet
  sich der Browser selbst neu. Gespeichert wird höchstens alle
  2 s, spätestens nach 10 s; alle 5 s prüft der Collab-Prozess Generation und Rechte.
  Eine Speicherung im Markdown-Modus, Wiederherstellen, Verschieben und Papierkorb
  beenden die laufende Live-Sitzung (4409). Endet nur die Anmeldung (Abmelden,
  Ablauf), ist das kein Entzug: Was die Person getippt hat, wird sofort unter ihrem
  Namen gespeichert, dann wird nur ihre Verbindung mit 4401 getrennt; die anderen
  arbeiten in derselben Generation weiter. Dafür bleibt eine beendete Sitzung eine
  Stunde lang (abgelaufen) in `user_session` stehen, bevor eine Anmeldung sie
  aufräumt. Wer eine Seite mit ungespeicherten Änderungen verlässt, wird sofort
  gespeichert, und das Abmelden wartet bis zu 3 s, bis der Live-Editor alles
  übertragen hat. Verliert jemand das Recht (Rolle, Deaktivierung, Abmelden durch
  die Verwaltung oder ein Passwortwechsel), wird seine Verbindung mit 4403 getrennt;
  hatte er noch ungespeicherte Änderungen, endet die Generation, damit kein anderer
  Browser sie wieder einspielt (die anderen bekommen 4409, ihre ungespeicherten
  Änderungen gehen verloren). Ein Live-Zustand hat höchstens 5 MiB, ein WebSocket-Frame
  höchstens einen ganzen Zustand (5 MiB + 64 KiB), sein Markdown höchstens 200.000 Zeichen; das prüft der Collab-Prozess schon
  vor jeder Änderung, nicht erst beim Speichern: Wer eine Änderung schickt, die darüber
  führt, wird mit 4413 getrennt, die Änderung erreicht niemanden, die anderen arbeiten
  weiter. Der Zähler `herd_collab_connections` zeigt offene Verbindungen,
  `herd_collab_saves_total{result}` die Speicherungen (`unrepresentable`: ein Stand,
  der sich nicht als Markdown speichern ließ, siehe `docs/WIKI.md`).
- **Genau ein Collab-Prozess.** Ein Live-Dokument liegt im Speicher dieses einen
  Prozesses; zwei Prozesse würden die Bearbeitenden einer Seite aufteilen, und keiner
  sähe die Änderungen des anderen. Das Chart setzt deshalb `replicas: 1` und
  `strategy: Recreate` (beim Update erst den alten Pod beenden, der dabei speichert).
  Fällt der Prozess aus, verbinden sich die Browser neu; Änderungen der letzten
  Sekunden (höchstens 10 s), die noch nicht gespeichert waren, spielt ein noch offener
  Browser beim Wiederverbinden erneut ein; ist er geschlossen, sind sie verloren. Mehrere Collab-Replikas (mit Redis/Valkey) sind für M9
  geplant. In Compose (`HERD_ROLE=all`) ist der Collab-Prozess ein Kindprozess der API;
  er erbt von ihrer Umgebung nur `PATH`, `HOME`, `LANG`, `LC_ALL`, `TZ`, `NODE_*` und
  `HERD_COLLAB_*` und bekommt dazu Token und öffentliche URL, nie die
  Datenbank-Zugangsdaten oder andere Geheimnisse der API. Endet dieser Kindprozess (etwa
  weil der Kernel ihn wegen Speichermangels beendet), beendet sich die ganze App mit
  Code 3, und der Orchestrator (`restart: unless-stopped`, Kubernetes) startet sie neu;
  so ist die Live-Bearbeitung nie still aus.
- **Speicher des Collab-Prozesses.** Eine live geöffnete große Seite kostet ihn ein
  Vielfaches ihres gespeicherten Umfangs (gemessen: 190.000 Zeichen Text rund 18 MB,
  5.000 Tabellenzellen rund 25 MB). Er lädt deshalb keine weitere Seite, wenn seine
  Schätzung der geladenen Dokumente `HERD_COLLAB_MEMORY_BUDGET_MB` (Standard 400)
  überschritte; wer sie öffnet, liest „Der Live-Editor ist gerade ausgelastet“ (4507)
  und kann neu laden oder den Markdown-Editor nehmen. Tabellen einer Seite haben live
  höchstens 5.000 Zellen. Jede Prüfung (Öffnen, Speichern) darf höchstens
  `HERD_COLLAB_CHECK_TIMEOUT_SECONDS` (10) dauern. Faustregel für das Speicherlimit:
  (130 MB + 250 MB je Prüf-Thread + Budget) / 0,8, mit den Standards 975 MB; Chart und
  `compose.nodes.yml` setzen 1Gi. Metriken: `herd_collab_memory_estimate_bytes`,
  `…_budget_bytes`, `…_refusals_total`, `herd_collab_documents` am Port des
  Collab-Prozesses (`/metrics`; in Rolle `all` mit auf 9090). Einzelheiten:
  [`docs/WIKI.md`](docs/WIKI.md).
- **WebSocket hinter Ingress oder Reverse Proxy.** Die Live-Bearbeitung ist ein
  WebSocket auf `/collab/<seiten-id>` am öffentlichen Port; er bleibt offen, solange
  jemand bearbeitet. Die API schickt alle 20 s einen Ping, deshalb reicht jedes
  Leerlauf-Timeout ab 30 s. ingress-nginx und Traefik reichen das Upgrade ohne
  Einstellung durch (ingress-nginx: `proxy-read-timeout` Standard 60 s, passt);
  AWS ALB: Leerlauf 60 s, passt; HAProxy: `timeout tunnel` gilt, nicht `timeout
  client`. **GKE-Ingress** begrenzt über die BackendConfig (`timeoutSec`, Standard
  30 s) die gesamte Dauer einer WebSocket-Verbindung, nicht nur den Leerlauf: dort
  `timeoutSec` etwa auf 3600 setzen, sonst verbindet sich der Editor alle 30 s neu.
  Ein eigener nginx davor braucht `proxy_http_version 1.1` und die Header `Upgrade`
  und `Connection`. Beispiele: [`docs/WIKI.md`](docs/WIKI.md#betrieb-hinter-einem-reverse-proxy).
  Diese Hinweise folgen den Dokumentationen der Controller; ausprobiert ist hier nur
  der direkte Zugriff und Compose.
- **Keep-Alive.** Die App schließt leerlaufende HTTP-Verbindungen erst nach
  `HERD_KEEP_ALIVE_SECONDS` (Standard 150, erlaubt 5 bis 3600; Uvicorn ab Werk: 5 s).
  Regel: **länger als das Leerlauf-Timeout des Proxys zu seinen Upstreams.** Mit 150 s
  passen nginx und ALB (60 s), Traefik (90 s) und Caddy (120 s); Google-Load-Balancer
  halten Backend-Verbindungen 600 s (dort etwa 620), ein hochgesetztes ALB-Timeout
  braucht einen Wert darüber. So schließt immer der Proxy zuerst, und keine Anfrage
  trifft eine Verbindung, die die App gerade schließt (sonst gelegentlich 502).
- **Größenlimits am Ingress:** Die App nimmt je Anfrage höchstens 1 MiB an
  (`HERD_MAX_BODY_BYTES`), Anhänge bis 25 MiB (`HERD_ATTACHMENT_MAX_BYTES`, nur
  `POST /api/pages/<id>/attachments`) und Importe bis 100 MiB (`HERD_IMPORT_MAX_BYTES`,
  nur `POST /api/spaces/<id>/import`). Ein Ingress davor muss mindestens das größte
  davon durchlassen, sonst antwortet er vor der App mit 413: ingress-nginx
  `nginx.ingress.kubernetes.io/proxy-body-size: 100m` (Standard 1m; so in
  `ci/production-values.yaml`), nginx `client_max_body_size 100m`. Die App prüft ihre
  Grenzen je Route selbst. Ein WebSocket-Frame der Live-Bearbeitung hat höchstens
  5 MiB + 64 KiB (ein ganzer Live-Zustand). Während der Körper eines Uploads oder Imports ankommt, hält die App keine
  Datenbankverbindung; kommt `HERD_BODY_READ_TIMEOUT_SECONDS` (Standard 30) lang kein
  weiteres Stück an oder dauert der ganze Körper länger als
  `HERD_BODY_TOTAL_TIMEOUT_SECONDS` (Standard 900), antwortet sie 408 `request.timeout`.
- **NetworkPolicy** ist standardmäßig aus. Eingeschaltet lässt ein leeres
  `networkPolicy.internalFrom` niemanden an Port 9090 außer dem Collab-Prozess, also
  auch Prometheus nicht: Prometheus dort eintragen. Den Collab-Prozess (Port 1234)
  erreichen nur die API-Pods; er selbst darf nur zu DNS und Port 9090 der API. Mit externer Datenbank braucht es eine Egress-Regel zu
  ihr (`networkPolicy.egress`), für KI-Anbieter `networkPolicy.aiEgress` (API und
  Worker), für OIDC-Anbieter `oidc.egress` (nur API), für die Offsite-Sicherung
  `backup.offsite.egress` (nur der Backup-Job).
- **Image nur für linux/amd64.** arm64 würde Cross-Builds der Node- und uv-Stufen
  brauchen.
- **Trivy** prüft das Image mit `ignore-unfixed`: Nicht behebbare CVEs der
  Debian-Basis lassen die CI nicht scheitern; behebbare HIGH/CRITICAL schon.
- **Werkzeugversionen der CI** (helm, kubeconform, promtool, pip-audit, uv) sind mit
  Prüfsummen festgelegt und werden von Hand angehoben; Renovate erfasst sie nicht.
- **CSP** erlaubt `style-src 'unsafe-inline'`, weil Radix (react-remove-scroll) ein
  `<style>` mit Laufzeitwerten einfügt. Skripte bleiben auf `'self'` beschränkt. Die
  WebSocket-Verbindung der Live-Bearbeitung geht an denselben Host und fällt unter
  `default-src 'self'` (in Chromium ohne Verletzung geprüft); die CSP bleibt unverändert.
  Jede andere Antwort (API, Fehler, Downloads) trägt eine eigene, strengere CSP
  (`default-src 'none'`, `frame-ancestors 'none'`, Anhänge zusätzlich `sandbox`); nur
  Swagger UI außerhalb der Produktion hat keine ([`SICHERHEIT.md`](docs/SICHERHEIT.md)).
- **HSTS** (`max-age=31536000; includeSubDomains`) kommt nur auf Antworten über https
  (direkt oder über `X-Forwarded-Proto` eines vertrauten Proxys) und gilt auch für
  Subdomains des Hosts, unter dem die App läuft. Läuft sie direkt unter einer Domain,
  deren Subdomains noch http brauchen, gehört sie auf eine eigene Subdomain
  (`wiki.example.com`).
- **Anmeldelast**: Die Passwortprüfung (argon2id, 64 MiB, 4 Lanes) läuft in
  Worker-Threads, höchstens `HERD_PASSWORD_HASH_CONCURRENCY` (Standard 2) gleichzeitig
  je Prozess; jede braucht 64 MiB. Höchstens `HERD_PASSWORD_HASH_QUEUE` (Standard 16)
  Anfragen je Prozess warten auf einen Platz, weitere bekommen sofort 429
  (`server.busy`, `Retry-After: 1`). Wartende und prüfende Anfragen halten keine
  Datenbankverbindung und keine Sperre. Vor dieser Änderung (im Event-Loop) schaffte ein Pod
  auf der Messmaschine rund 15 Anmeldungen je Sekunde (siehe
  [Steckbrief](docs/STECKBRIEF.md)); neu gemessen ist das nicht.
- **Größe des Anfragekörpers**: höchstens `HERD_MAX_BODY_BYTES` (Standard 1048576,
  1 MiB) je Anfrage, für jeden Pfad; größere bekommen 413 (`request.too_large`), bevor
  irgendetwas den Körper puffert: sofort bei zu großem `Content-Length`, sonst (chunked)
  beim Lesen ab dem ersten Teil über der Grenze. Ein Ingress davor darf größer oder
  gleich eingestellt sein (ingress-nginx: `proxy-body-size`, Standard 1m); im Chart über
  `api.env` setzbar.
- **Anhänge**: Dateien liegen unter `HERD_DATA_DIR` (Standard `/data`; für die lokale
  Entwicklung auf ein beschreibbares Verzeichnis setzen), je Organisation und Inhalt
  einmal (`attachments/<org_id>/<sha256>`). Mehrere API-Replikas brauchen dasselbe
  Volume (Compose: `app-data`, Helm: `<release>-data`, siehe oben). Mit
  `HERD_STORAGE=s3` liegen sie stattdessen in einem S3-kompatiblen Bucket
  (`HERD_S3_*`; Compose `compose.s3.yml`, Helm `s3.*`; Umzug mit `python -m app.ops
  storage copy --to s3`, siehe [`docs/SICHERUNG.md`](docs/SICHERUNG.md#anhänge-in-s3)). Das Image legt
  `/data` mit dem Besitzer 10001 an, damit ein neues benanntes Volume dort beschreibbar
  ist; das Wurzeldateisystem bleibt nur lesbar. Ein Anhang hat
  höchstens `HERD_ATTACHMENT_MAX_BYTES` (Standard 26214400, 25 MiB); nur die
  Upload-Route nimmt so große Körper an, ein Ingress davor muss dort ebenso viel
  zulassen (ingress-nginx: `proxy-body-size`). Ein Upload wird bis 1 MiB im Speicher,
  darüber in einer temporären Datei unter `HERD_DATA_DIR/tmp` zwischengespeichert
  (nicht `TMPDIR`, das in Compose ein `tmpfs` im Arbeitsspeicher ist). Die Dateien sind
  namenlos oder sofort gelöscht; was trotzdem liegen bleibt, entfernt der Start, sobald
  es älter als 24 Stunden ist. Erlaubt sind PNG, JPEG, GIF, WebP, PDF, TXT, Markdown, CSV,
  JSON, DOCX, XLSX, PPTX und ZIP, erkannt am Inhalt; SVG und HTML werden abgelehnt.
  Eine Datei wird erst gelöscht, nachdem die Transaktion, die ihren letzten Anhang
  gelöscht hat, abgeschlossen ist; scheitert das Löschen danach, bleibt die Datei
  ungenutzt liegen (nie ein Anhang ohne Datei).
- **Import und Export**: Ein Bereich lässt sich als Markdown-ZIP exportieren (eine
  `.md` je Seite mit Front Matter `title`, `status`, `tags`, Anhänge unter
  `_attachments/`) und wieder importieren (Recht `space.manage`). Die ZIP-Datei darf
  gepackt höchstens `HERD_IMPORT_MAX_BYTES` (Standard 104857600, 100 MiB) groß sein
  (auch hier den Ingress anpassen), höchstens 2.000 Einträge und 200 MB entpackt
  enthalten; Einträge mit `..`, absolutem Pfad oder als Symlink werden übersprungen.
  Ein Import läuft in einer Transaktion; 2.000 Seiten brauchen gemessen etwa 11 s
  (ohne Anhänge, lokales PostgreSQL), ein Ingress-Timeout muss das abdecken.
  Import und Export nutzen dieselben temporären Dateien unter `HERD_DATA_DIR/tmp`.
  Der Export listet in
  `_attachments/manifest.json`, welcher Anhang jede Datei war; der Import lässt Links
  `/api/attachments/<id>` auf mitgebrachte Anhänge auf die neuen zeigen. Links auf
  andere Anhänge (nicht im Archiv, beim Import abgelehnt, anderer Host) bleiben.
- **Wiki-Diff**: Ein Vergleich zweier Seitenversionen vergleicht höchstens
  `HERD_DIFF_MAX_LINES` (Standard 20000) Zeilen, beide Versionen zusammen; darüber
  antwortet die API mit 422 (`page.diff_too_large`). Die Rechenzeit wächst mit den
  Zeilen und läuft in einem Worker-Thread.
- **Anmeldelimits**: je Client-Adresse `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE` (Standard
  30) Versuche je Minute, gleich mit welcher E-Mail; je Adresse und E-Mail
  `HERD_LOGIN_RATE_LIMIT_PER_MINUTE` (Standard 5) fehlgeschlagene Versuche; es zählen
  nur abgeschlossene Fehlversuche, gleichzeitige richtige Anmeldungen kommen alle
  durch (ein Versuch wartet höchstens 5 s, bis die laufenden entschieden sind). Eine
  IPv6-Adresse zählt dabei mit ihrem /64-Präfix (ein Anschluss hat meist ein ganzes
  /64), eine IPv4-Adresse für sich; das Audit-Log hält die volle Adresse fest. Die
  Client-Adresse stimmt nur, wenn der Reverse Proxy in `HERD_FORWARDED_ALLOW_IPS`
  steht; sonst teilen sich alle Clients die Adresse des Proxys.
- **Schreibgrenze je Person (seit M9b):** je Person und Minute höchstens
  `HERD_WRITE_RATE_PER_MINUTE` (Standard 120) Schreibvorgänge an Inhalten (Seiten,
  Nachrichten, Reaktionen, Tickets, Vorschläge, Schlagwörter) und getrennt davon
  `HERD_UPLOAD_RATE_PER_MINUTE` (Standard 30) Uploads (Anhänge, Importe); gezählt in
  PostgreSQL über alle Knoten, darüber 429 `rate.limited` mit `Retry-After`. Ein Agent
  hat seinen eigenen Zähler, ebenso groß; ein Werkzeug darüber schreibt nichts und
  meldet `rate.limited`. Lesen, Lesemarken, Verwaltung und Einstellungen zählen nicht.
  Die Lasttest-Mischung (200 Personen) bleibt weit darunter; Skripte, die in Massen
  anlegen (Demo-Daten, `loadsetup.py`), warten bei 429 die genannte Zeit ab. Metrik
  `herd_rate_limited_total{area}` (`write`, `upload`); Chart `writeLimit.perMinute`,
  `writeLimit.uploadsPerMinute`. Einzelheiten: [`SICHERHEIT.md`](docs/SICHERHEIT.md).
- **Virenscan (optional, seit M9b):** `HERD_CLAMAV_ADDRESS` (`host:port` eines eigenen
  `clamd`, nicht mitgeliefert; Chart `virusScan.clamavAddress`, Freigabe im Netz
  `virusScan.egress`) prüft Anhänge und Importe vor dem Speichern; Fund 422, Scanner
  nicht verfügbar 503 (fail closed). Leer (Standard): kein Scan. Einzelheiten:
  [`WIKI.md`](docs/WIKI.md).
- **Worker und Outbox (seit M3):** Jede ändernde Aktion schreibt in ihrer Transaktion
  ein Ereignis (nur IDs) in `event_outbox`; der Worker verteilt es an Benachrichtigungen,
  Systemmeldungen der Seiten- und Ticket-Diskussionen und die Live-Zustellung. Bis M7 ohne DBOS (Plan
  M3, Entscheidung 1). `HERD_ROLE=worker` hat nur den internen Port (`/ready` meldet, ob
  seine Schleife läuft, die Datenbank erreicht und innerhalb von vier Zeitgrenzen
  vorankommt); `HERD_ROLE=all` enthält den Worker und teilt
  mit ihm den Datenbank-Pool. Jeder Handler arbeitet eine eigene Bahn ab (seit Review M4
  P3): Ein hängender Handler hält die anderen nicht auf, ein Stapel ist eine Transaktion,
  ein Worker schafft gut 400 Ereignisse je Sekunde. Er braucht dafür bis zu eine
  Datenbankverbindung je Handler (zurzeit fünf) plus Verteilen, Metriken und LISTEN; ein
  Datenbank-Limit `max_connections` muss das je Worker-Replika einplanen. Mehrere Worker
  sind sicher (getrennte Zeilen, Zustellung mindestens einmal, Wirkung genau einmal,
  idempotente Handler). Ohne laufenden Worker gehen keine Nachrichten
  verloren, aber nichts kommt live an, Benachrichtigungen und Systemmeldungen bleiben aus,
  bis ein Worker läuft. Jeder Handler-Aufruf hat eine Zeitgrenze
  (`HERD_WORKER_HANDLER_TIMEOUT_SECONDS`, Standard 30 s; auch als `lock_timeout` und
  `statement_timeout` der Transaktion); eine Überschreitung zählt als gescheiterter
  Versuch. Scheiternde Handler werden je Ereignis mit Wartezeit (bis 5 Minuten)
  wiederholt, nach 10 Versuchen aufgegeben (`outbox.failed`). Metriken (nur von Prozessen mit Worker,
  alle 10 s aus der Datenbank): `herd_outbox_pending`,
  `herd_outbox_oldest_pending_seconds`, `herd_outbox_failed`,
  `herd_worker_last_pass_timestamp_seconds`, dazu
  `herd_outbox_dispatch_total{handler,result}`. Verteilte Ereignisse werden nach 7 Tagen
  gelöscht. Einzelheiten: [`docs/NACHRICHTEN.md`](docs/NACHRICHTEN.md#worker-und-outbox).
- **Live-Zustellung (SSE) hinter Ingress oder Reverse Proxy:** `GET /api/stream` bleibt
  offen, solange der Tab offen ist. Der Proxy darf die Antwort nicht puffern oder
  komprimieren (die App sendet `X-Accel-Buffering: no`), sein Lese-Timeout muss über den
  15 s des Heartbeats liegen (empfohlen 1 h, ingress-nginx
  `nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"`). Zum Browser HTTP/2, sonst
  belegt jeder Tab eine der 6 HTTP/1.1-Verbindungen je Host. Je Anmeldung höchstens 5
  und je Person höchstens 10 Verbindungen **je API-Prozess** (429
  `live.too_many_streams`); hinter einem Load Balancer gelten die Grenzen je Pod. Sticky
  Sessions sind nicht nötig: Jeder API-Pod lauscht mit einer eigenen Datenbankverbindung
  (außerhalb des Pools) auf `herd_live` und prüft je Stapel angekommener Ereignisse (bis
  200) mit höchstens zwei Abfragen, wer was sehen darf. Liegt das älteste wartende
  Ereignis länger als `HERD_LIVE_MAX_LAG_SECONDS` (Standard 5 s) zurück, verwirft der Pod
  die Warteschlange und schickt allen `resync` (Metriken `herd_live_queue_depth`,
  `herd_live_delivery_lag_seconds`, `herd_live_resyncs_total{reason}`). Bei SIGTERM beendet die API ihre
  Verbindungen zuerst, die Browser verbinden sich nach 5 s neu und laden nach; verpasste
  Ereignisse werden nicht nachgespielt. Beispiele:
  [`docs/NACHRICHTEN.md`](docs/NACHRICHTEN.md#betrieb-hinter-einem-reverse-proxy).
- **Datenbankverbindungen:** Zum Pool kommt je API-Prozess eine dauerhafte
  LISTEN-Verbindung, je Worker eine weitere (Worker: zwei aus dem Pool während einer
  Verteilung). `max_connections` der Datenbank danach bemessen.
- **Live-Zustellung bei geänderten Rechten (M3):** Wer in einen Bereich aufgenommen, aus
  ihm entfernt oder in der Rolle geändert wird (direkt oder über eine Gruppe), bekommt
  sofort `access.changed` (ohne IDs) und lädt neu; die Teilnehmenden einer
  Direktnachricht, in die die Verwaltung Einsicht nimmt, bekommen sofort `dm.inspected`.
  Der Browser fasst Aktualisierungen 250 ms lang zusammen. Die Art eines Bereichs
  (offen/Team) ändert sich nie.
- **Einsicht in Direktnachrichten** (`dm.inspect`, nur Inhaber und Administratoren):
  Begründung 10 bis 500 Zeichen, 60 Minuten, nur lesend, nur für die Person, die sie
  begonnen hat; Audit `dm.admin_lookup` (Liste der Gespräche einer Person) und
  `dm.admin_access` (mit Begründung). Sonst haben Administratoren in fremden
  Direktnachrichten kein Recht, auch nicht in der Suche.
- **Tickets (seit M4):** Schlüssel mit festem Präfix `HC`, Nummern je Organisation
  fortlaufend. Tickets werden nicht gelöscht, sondern verworfen (Status der Kategorie
  `cancelled`); mit ihrem Bereich verschwinden sie. Ein unsichtbares Ticket antwortet
  über seine Nummer genau wie eine freie Nummer (404 `ticket.not_found`). Kein Ticket
  schreibt in Kanäle oder Direktnachrichten. Ein Worker verarbeitet hier rund 90
  Ereignisse je Sekunde; Massenanlagen über die API (über 40 Tickets je Sekunde
  dauerhaft) lassen die Outbox wachsen, Systemmeldungen kommen dann später
  ([Steckbrief](docs/STECKBRIEF.md#tickets-m4)). Keine neuen Einstellungen. Einzelheiten:
  [`docs/TICKETS.md`](docs/TICKETS.md#betrieb).
- **Sprints und Boards (seit M4b):** zwei Migrationen, beide nur erweiternd (Tabelle
  `sprint`, `work_item.sprint_id`, `work_item.status_changed_at` mit Trigger); keine neuen
  Einstellungen. Das Abschließen eines Sprints ist eine Transaktion mit einem Ereignis je
  verschobenem Ticket; der Worker arbeitet sie in der Bahn der Systemmeldungen ab,
  andere Handler warten nicht darauf (gemessen im
  [Steckbrief](docs/STECKBRIEF.md#sprints-und-boards-m4b)). „Seit dem letzten
  Arbeitstag“ rechnet in UTC, Montag bis Freitag.
- **Nachrichteninhalte** und Titel oder Beschreibungen von Tickets stehen nie im Log, in
  `NOTIFY`-Nutzlasten, in Ereignissen der Outbox oder in Metrik-Labels; Live-Ereignisse
  tragen nur IDs.

## Freigaben und Updates

Eine Freigabe ist ein Tag `vX.Y.Z` (`.github/workflows/release.yml`); er veröffentlicht
das Image `ghcr.io/<owner>/to-herd-cats-ai:X.Y.Z` und `:X.Y` und das Chart als OCI unter
`ghcr.io/<owner>/charts`. Tag, Version in `backend/pyproject.toml` und `version` und
`appVersion` des Charts müssen gleich sein (`deploy/helm/scripts/check-chart-version.sh`).
Getaggt wird nur auf Jans Wort; die erste Freigabe ist `v1.0.0` nach dem Modul-Review
von M9a und seiner Fix-Welle (Antwort J1), beschrieben in
[`docs/RELEASE-1.0.0.md`](docs/RELEASE-1.0.0.md).

**Vor dem Taggen, von Hand:**

1. `backend/alembic/RELEASED` auf die Head-Revision setzen
   (`cd backend && uv run alembic heads`) und mit in den Commit nehmen, den der Tag
   trägt. `release.yml` setzt es nicht, prüft es aber: Nennt die Datei am Tag nicht den
   einen Head (`python -m scripts.check_migrations --require-released-head`), bricht die
   Freigabe ab, bevor etwas veröffentlicht wird.
2. Versionen anheben (pyproject, `Chart.yaml` `version` und `appVersion`), alle
   Prüfbefehle grün, dann taggen.

**Migrationsregel:** Ab einer Freigabe sind Migrationen nur erweiternd, damit ein Pod
der vorigen Version mit dem neuen Schema weiterläuft (`/ready` bleibt bereit, wenn die
Datenbank auf einer neueren, unbekannten Revision steht). `scripts/check_migrations.py`
lehnt in jeder Revision nach `RELEASED` Löschen, Umbenennen und Typwechsel ab
(`drop_*`, `rename_table`, `alter_column(type_=…/new_column_name=…)`, `op.execute` mit
`DROP`/`RENAME`). Zurückbauen geht frühestens eine Freigabe später, in einer Revision mit
`contract_of = "<Revision>"`, und nur für eine Revision, die schon zur Freigabe gehört.
Genau ein Head.

**Update einer Installation:**

1. Vorher sichern: `python -m app.ops backup run` (Compose:
   `docker compose exec backup python -m app.ops backup run`; Kubernetes: einen Job aus
   dem CronJob erzeugen, `kubectl create job --from=cronjob/<release>-backup …`).
2. Image bzw. Chart-Version wechseln. Compose: `docker compose pull && docker compose up
   -d --wait` (der App-Container migriert beim Start). Helm: `helm upgrade` (der
   Migrations-Job läuft vor den Pods bzw. als Job der Revision, siehe
   [Betriebshinweise](#betriebshinweise)). Worker zuerst ersetzen, wenn sie getrennt
   laufen.
3. Zurück zur vorigen Version nur mit dem Archiv aus Schritt 1, in eine leere Datenbank
   ([`docs/SICHERUNG.md`](docs/SICHERUNG.md#wiederherstellen-in-eine-leere-installation));
   eine neuere Revision spielt die alte Version nicht ein (`restore.archive_newer`), und
   `--replace` taugt dafür nicht (es hebt das Archiv auf den Head des laufenden Codes).

**Einmal abgemeldet nach dem Update auf M9:** Über https heißen die Cookies seit M9
`__Host-herd_session` und `__Host-herd_oidc` (ASVS V3.3.3). Das alte Cookie
`herd_session` zählt dort nicht mehr; wer über https angemeldet war, wird nach dem
Update einmal abgemeldet und meldet sich neu an. Über reines http (zum Ausprobieren)
ändert sich nichts. Laufende Live-Bearbeitungen verbinden sich nach der neuen Anmeldung
neu; ungespeicherte Änderungen der letzten Sekunden können dabei verloren gehen, also
das Update nicht mitten in der Arbeitszeit einspielen. Ebenso neu seit M9: Ein Collab-
Prozess der vorigen Version lehnt jede Verbindung der neuen API ab (keine
Übergangsschicht); API und Collab-Prozess gehören zur selben Version.

## Lizenz

Apache-2.0, siehe [`LICENSE`](LICENSE).
