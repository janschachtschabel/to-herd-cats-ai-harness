# to-herd-cats-ai

Ein selbst betriebenes Arbeitssystem für Teams: Wissen im Wiki, Arbeit in Aufgaben,
Austausch in Kanälen, und KI-Agenten als Teammitglieder mit denselben Rechten wie
Menschen. Die Spezifikation steht in
[`docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md`](docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md).

**Stand: Meilenstein 1 (Fundament) ist gebaut.** Anmeldung, Personen, Gruppen,
Bereiche (offen, Team, persönlich), Rollen, die eine Rechteprüfung, Audit, die
Oberfläche mit Navigation und Verwaltung, Image, Compose, Helm-Chart und CI. Wiki,
Aufgaben, Kanäle und Agenten folgen; als Nächstes M2 Wiki
([Plan](docs/superpowers/plans/2026-11-12-m2-wiki.md)).

Weitere Dokumente: [Steckbrief](docs/STECKBRIEF.md) (Betriebsdaten, gemessene
Ressourcen), [Demo M1](docs/demo/m1.md), [Compose-Referenz](deploy/compose/README.md),
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

`docker compose down` hält die Daten (Volume `db-data`), `down -v` löscht sie.
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

Zwei Werte betreffen jeden Betrieb hinter einem Ingress:

- `api.cookieSecure` (Standard `true`): Das Sitzungs-Cookie trägt `Secure`, der Browser
  schickt es nur über https (und an `localhost`, etwa bei `kubectl port-forward`). Nur
  auf `false` setzen, wenn die App absichtlich über reines http erreicht wird.
- `api.forwardedAllowIps` (`HERD_FORWARDED_ALLOW_IPS`): die Adressen der
  Ingress-Controller-Pods, z. B. das Pod-Netz `10.0.0.0/8`. Nur deren
  `X-Forwarded-For`/`-Proto` glaubt die App. Ohne den Wert hätte jeder Client die
  Adresse des Ingress-Pods (im Audit und für die Anmeldelimits, die dann für alle
  zusammen gälten). Mit `ingress.enabled` ist der Wert Pflicht; das Chart bricht sonst
  mit einer Meldung ab.

## Entwicklung

Voraussetzungen: Python 3.13 mit [`uv`](https://docs.astral.sh/uv/), Node 22 mit npm,
PostgreSQL 16 oder neuer. Die Standard-URLs erwarten die Rolle `herd` (Passwort
`herd`) auf `localhost:5433` mit den Datenbanken `herd` und `herd_test`.

```bash
cd backend && uv sync
cd backend && HERD_BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
  HERD_BOOTSTRAP_ADMIN_PASSWORD=admin-password-123 HERD_LOG_FORMAT=text \
  uv run python -m app.launch          # migriert, dann API auf :8080, Proben auf :9090

cd frontend && npm ci && npm run dev   # Vite; leitet /api an http://localhost:8080 weiter
```

`HERD_ROLE` wählt, was der Prozess tut: `all` (Standard: migrieren, dann bedienen),
`api` oder `migrate`. Alle Einstellungen sind `HERD_*`-Variablen
(`backend/app/core/config.py`). Nach Änderungen an der API `npm run generate:api`
im Frontend ausführen.

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
docker build -t to-herd-cats-ai:local . && bash deploy/compose/smoke.sh   # endet mit SMOKE OK
bash deploy/compose/load.sh            # Ressourcen und Laufzeiten für den Steckbrief
```

Helm-Chart, Lizenzprüfung und Release stehen in `CLAUDE.md`. Die CI
(`.github/workflows/ci.yml`) führt für jeden Pull Request, jeden Push auf `main` und
(über `release.yml`) jedes Release-Tag alles davon aus, dazu `pip-audit`,
`npm audit`, `kubeconform`, `promtool` und Trivy.

## Betriebshinweise

Bekannte Grenzen und bewusste Entscheidungen aus M1. Wer betreibt, sollte sie kennen.

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
  `networkPolicy.internalFrom`). Ein Token für interne Endpunkte kommt erst mit M2.
- **NetworkPolicy** ist standardmäßig aus. Eingeschaltet lässt ein leeres
  `networkPolicy.internalFrom` niemanden an Port 9090, also auch Prometheus nicht:
  Prometheus dort eintragen. Mit externer Datenbank braucht es eine Egress-Regel zu
  ihr (`networkPolicy.egress`).
- **Image nur für linux/amd64.** arm64 würde Cross-Builds der Node- und uv-Stufen
  brauchen.
- **Trivy** prüft das Image mit `ignore-unfixed`: Nicht behebbare CVEs der
  Debian-Basis lassen die CI nicht scheitern; behebbare HIGH/CRITICAL schon.
- **Werkzeugversionen der CI** (helm, kubeconform, promtool, pip-audit, uv) sind mit
  Prüfsummen festgelegt und werden von Hand angehoben; Renovate erfasst sie nicht.
- **CSP** erlaubt `style-src 'unsafe-inline'`, weil Radix (react-remove-scroll) ein
  `<style>` mit Laufzeitwerten einfügt. Skripte bleiben auf `'self'` beschränkt.
- **Anmeldelast**: Die Passwortprüfung (argon2id, 64 MiB, 4 Lanes) läuft in
  Worker-Threads, höchstens `HERD_PASSWORD_HASH_CONCURRENCY` (Standard 2) gleichzeitig
  je Prozess; jede braucht 64 MiB. Vor dieser Änderung (im Event-Loop) schaffte ein Pod
  auf der Messmaschine rund 15 Anmeldungen je Sekunde (siehe
  [Steckbrief](docs/STECKBRIEF.md)); neu gemessen ist das nicht.
- **Anmeldelimits**: je Client-Adresse `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE` (Standard
  30) Versuche je Minute, gleich mit welcher E-Mail; je Adresse und E-Mail
  `HERD_LOGIN_RATE_LIMIT_PER_MINUTE` (Standard 5) fehlgeschlagene Versuche. Die
  Client-Adresse stimmt nur, wenn der Reverse Proxy in `HERD_FORWARDED_ALLOW_IPS`
  steht; sonst teilen sich alle Clients die Adresse des Proxys.

## Lizenz

Apache-2.0, siehe [`LICENSE`](LICENSE).
