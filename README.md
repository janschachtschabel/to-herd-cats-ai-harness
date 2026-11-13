# to-herd-cats-ai

Ein selbst betriebenes Arbeitssystem für Teams: Wissen im Wiki, Arbeit in Aufgaben,
Austausch in Kanälen, und KI-Agenten als Teammitglieder mit denselben Rechten wie
Menschen. Die Spezifikation steht in
[`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md`](docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md).

**Stand: Meilenstein 2 (Wiki) ist gebaut.** Aus M1: Anmeldung, Personen, Gruppen,
Bereiche (offen, Team, persönlich), Rollen, die eine Rechteprüfung, Audit, die
Oberfläche mit Navigation und Verwaltung, Image, Compose, Helm-Chart und CI. Aus M2
ein Wiki in jedem Bereich:

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

Kanäle (M3), Aufgaben (M4) und KI-Agenten (ab M5) folgen. Bedienung und Betrieb des
Wikis: [`docs/WIKI.md`](docs/WIKI.md).

Weitere Dokumente: [Steckbrief](docs/STECKBRIEF.md) (Betriebsdaten, gemessene
Ressourcen), [Demo M1](docs/demo/m1.md), [Demo M2](docs/demo/m2.md),
[Compose-Referenz](deploy/compose/README.md),
[Helm-Chart](deploy/helm/to-herd-cats-ai/values.yaml).

## Schnellstart mit Docker Compose

Voraussetzung: Docker mit Compose v2.

```bash
cd deploy/compose
cp .env.example .env          # jeden Wert ersetzen, z. B. mit `openssl rand -hex 24`
docker compose up -d --build --wait
```

Dann <http://127.0.0.1:8080> öffnen und mit `HERD_BOOTSTRAP_ADMIN_EMAIL` und
`HERD_BOOTSTRAP_ADMIN_PASSWORD` aus `.env` anmelden. Diese erste Person (Inhaberin)
entsteht nur beim allerersten Start; das Passwort danach in der App ändern (Menü oben
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
mit TLS, NetworkPolicy, ServiceMonitor, PrometheusRule). Vor dem Einsatz die
[Betriebshinweise](#betriebshinweise) lesen.

> **Wichtig – Volume für Anhänge:** Das Chart legt den PersistentVolumeClaim
> `<release>-data` (10Gi, `/data`) mit **`ReadWriteMany`** an, weil alle API-Replikas
> (Standard 2) dieselben Dateien lesen und schreiben. Gibt es im Cluster keine
> Speicherklasse mit ReadWriteMany (etwa NFS, CephFS, Azure Files, EFS), bleibt der
> Claim `Pending` und die API-Pods starten nicht. Dann
> `--set api.replicas=1 --set 'persistence.accessModes={ReadWriteOnce}'` setzen (mehr
> Replikas mit ReadWriteOnce lehnt das Chart ab) oder mit `persistence.existingClaim`
> einen eigenen Claim nutzen. Der Claim bleibt bei `helm uninstall` erhalten.

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
  HERD_BOOTSTRAP_ADMIN_PASSWORD=admin-password-123 HERD_LOG_FORMAT=text \
  uv run python -m app.launch          # migriert, dann API auf :8080, Proben auf :9090

cd frontend && npm ci && npm run dev   # Vite; leitet /api und /collab an http://localhost:8080 weiter
```

`HERD_ROLE` wählt, was der Prozess tut: `all` (Standard: migrieren, dann bedienen),
`api`, `migrate` oder `collab` (nur der Live-Bearbeitungsprozess, `node
collab/server.mjs`). In `all` startet die API den Collab-Prozess als Kindprozess auf
`127.0.0.1:${HERD_COLLAB_PORT}`, wenn `HERD_INTERNAL_TOKEN` gesetzt ist (dafür
`cd collab && npm ci`); ohne Token bleibt die Live-Bearbeitung aus. Alle
Einstellungen sind `HERD_*`-Variablen (`backend/app/core/config.py`). Nach Änderungen
an der API `npm run generate:api` im Frontend ausführen.

Regeln für Beiträge: [`CLAUDE.md`](CLAUDE.md) (Schichten, `org_id`, Paginierung,
Fehlerform, i18n, Lizenzen, Commit-Format). Neue Funktionen beginnen mit einem
fehlschlagenden Test.

## Prüfbefehle

Die Tests brauchen PostgreSQL (`HERD_TEST_DATABASE_URL`, Standard
`postgresql+asyncpg://herd:herd@localhost:5433/herd_test`).

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy app scripts
cd frontend && npm run lint && npm run typecheck && npm test && npm run build \
  && node scripts/check-i18n.mjs && npm run check:api
cd collab && npm run lint && npm test && npm run test:integration   # Integration: echte API,
                                       # Wegwerf-Datenbank (psql, uv nötig), zwei Yjs-Clients
docker build -t to-herd-cats-ai:local . && bash deploy/compose/smoke.sh   # endet mit SMOKE OK
bash deploy/compose/load.sh            # Ressourcen und Laufzeiten für den Steckbrief
```

Helm-Chart, Lizenzprüfung und Release stehen in `CLAUDE.md`. Die CI
(`.github/workflows/ci.yml`) führt für jeden Pull Request, jeden Push auf `main` und
(über `release.yml`) jedes Release-Tag alles davon aus, dazu `pip-audit`,
`npm audit`, `kubeconform`, `promtool` und Trivy.

## Betriebshinweise

Bekannte Grenzen und bewusste Entscheidungen aus M1 und M2. Wer betreibt, sollte sie
kennen.

- **Datenbank-Passwort** nur über `HERD_DATABASE_PASSWORD` oder
  `HERD_DATABASE_PASSWORD_FILE` (beides zugleich ist ein Startfehler), nie in
  `HERD_DATABASE_URL`. Das Chart lehnt eine URL mit Passwort ab und legt das Passwort
  als Datei ein; Compose reicht `POSTGRES_PASSWORD` als `HERD_DATABASE_PASSWORD` durch.
- **Mitgeliefertes PostgreSQL im Chart** (`postgresql.enabled`, Standard `true`) ist
  zum Ausprobieren gedacht: ein Pod, keine Replikation, keine Sicherung. In Produktion
  `postgresql.enabled=false` und eine externe Datenbank setzen.
  Sein Passwort erzeugt das Chart einmal und liest es danach per `lookup` aus dem
  Cluster. Wer mit `helm template` ausrollt (Argo CD, Flux), bekommt dabei bei jedem
  Rendern ein neues Passwort, das nicht mehr zum Datenvolume passt: dort
  `database.existingSecret` auf ein selbst angelegtes Secret setzen.
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
  wie die REST-API und reicht erst dann Frames an den Collab-Prozess
  (`HERD_COLLAB_URL`, Standard `ws://127.0.0.1:1234`) weiter. Abgelehnt wird mit
  Schließcodes, die der Browser lesen kann: 4401 (keine gültige Sitzung), 4403 (kein
  Recht, oder Recht entzogen), 4404 (Seite nicht sichtbar), 4409 (die Generation ist
  beendet: Seite neu laden), 4413 (Zustand zu groß), 4422 (`collab.not_roundtrip_safe`:
  der Live-Editor würde die Bedeutung des Markdowns ändern, siehe `docs/WIKI.md`; der
  Browser bietet den Markdown-Editor an), 4502/4503 (Collab-Prozess nicht
  erreichbar bzw. aus), 1013 (später erneut versuchen). Gespeichert wird höchstens alle
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
  Änderungen gehen verloren). Ein WebSocket-Frame hat höchstens 1 MiB, ein Live-Zustand höchstens
  5 MiB. Der Zähler `herd_collab_connections` zeigt offene Verbindungen,
  `herd_collab_saves_total{result}` die Speicherungen.
- **Genau ein Collab-Prozess.** Ein Live-Dokument liegt im Speicher dieses einen
  Prozesses; zwei Prozesse würden die Bearbeitenden einer Seite aufteilen, und keiner
  sähe die Änderungen des anderen. Das Chart setzt deshalb `replicas: 1` und
  `strategy: Recreate` (beim Update erst den alten Pod beenden, der dabei speichert).
  Fällt der Prozess aus, verbinden sich die Browser neu; Änderungen der letzten
  Sekunden (höchstens 10 s), die noch nicht gespeichert waren, spielt ein noch offener
  Browser beim Wiederverbinden erneut ein; ist er geschlossen, sind sie verloren. Mehrere Collab-Replikas (mit Redis/Valkey) sind für M9
  geplant. In Compose (`HERD_ROLE=all`) ist der Collab-Prozess ein Kindprozess der API.
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
- **Größenlimits am Ingress:** Die App nimmt je Anfrage höchstens 1 MiB an
  (`HERD_MAX_BODY_BYTES`), Anhänge bis 25 MiB (`HERD_ATTACHMENT_MAX_BYTES`, nur
  `POST /api/pages/<id>/attachments`) und Importe bis 100 MiB (`HERD_IMPORT_MAX_BYTES`,
  nur `POST /api/spaces/<id>/import`). Ein Ingress davor muss mindestens das größte
  davon durchlassen, sonst antwortet er vor der App mit 413: ingress-nginx
  `nginx.ingress.kubernetes.io/proxy-body-size: 100m` (Standard 1m; so in
  `ci/production-values.yaml`), nginx `client_max_body_size 100m`. Die App prüft ihre
  Grenzen je Route selbst. Ein WebSocket-Frame der Live-Bearbeitung hat höchstens
  1 MiB. Während der Körper eines Uploads oder Imports ankommt, hält die App keine
  Datenbankverbindung; kommt `HERD_BODY_READ_TIMEOUT_SECONDS` (Standard 30) lang kein
  weiteres Stück an, antwortet sie 408 `request.timeout`.
- **NetworkPolicy** ist standardmäßig aus. Eingeschaltet lässt ein leeres
  `networkPolicy.internalFrom` niemanden an Port 9090 außer dem Collab-Prozess, also
  auch Prometheus nicht: Prometheus dort eintragen. Den Collab-Prozess (Port 1234)
  erreichen nur die API-Pods; er selbst darf nur zu DNS und Port 9090 der API. Mit externer Datenbank braucht es eine Egress-Regel zu
  ihr (`networkPolicy.egress`).
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
  Volume (Compose: `app-data`, Helm: `<release>-data`, siehe oben). Das Image legt
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
  Ein Import läuft in einer Transaktion; große Archive brauchen entsprechend lange.
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

## Lizenz

Apache-2.0, siehe [`LICENSE`](LICENSE).
