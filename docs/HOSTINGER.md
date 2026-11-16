# Installation auf einem Hostinger-VPS (Docker Manager)

Der einfachste Weg zu einer eigenen Installation: ein Hostinger-VPS mit dem Docker
Manager, die Datei [`docker-compose.yml`](../docker-compose.yml) aus dem Hauptordner
dieses Repositorys und ein paar Einträge in einer Einstellungsdatei. Keine
Kommandozeile nötig, kein eigener Proxy, keine Zertifikate von Hand: HTTPS übernimmt
der Traefik, den Hostinger auf dem VPS mitbringt.

Wer selbst baut, eigene Ports braucht, Sicherungen außer Haus (restic) oder mehrere
API-Knoten möchte, nimmt die Referenz unter [`deploy/compose/`](../deploy/compose/README.md)
oder das Helm-Chart (README, „Kubernetes mit Helm“).

## Was du brauchst

- Einen Hostinger-VPS mit dem **Docker Manager** (Betriebssystem-Vorlage „Docker“).
  Speicher: mindestens 2 GB RAM, besser 4 GB (App mit Worker und Live-Bearbeitung
  plus PostgreSQL; Messwerte im [Steckbrief](STECKBRIEF.md)).
- Einen Namen für die App: eine eigene (Sub-)Domain wie `wiki.meine-firma.de`, deren
  DNS du ändern kannst, **oder** den Hostnamen des VPS (`srvNNNNNN.hstgr.cloud`, steht
  im hPanel beim VPS). Der hat schon DNS und bekommt ebenfalls ein Zertifikat.
- Eine E-Mail-Adresse und ein Passwort für die erste Person (die Inhaberin).

## Schritt für Schritt

### 1. Bereitstellen ohne Werte

Im hPanel: VPS → **Docker Manager** → **Compose** → **Compose from URL**.

- URL: `https://github.com/janschachtschabel/to-herd-cats-ai-harness`
- Anwendungsname: den Vorschlag übernehmen (er wird zum Projektnamen, z. B.
  `to-herd-cats-ai-harness`; unten `<projekt>`).
- **Bereitstellen**.

Hostinger nimmt die `docker-compose.yml` aus dem Hauptordner (Zweig `main`) und legt
`.env.example` als `.env` an. Der erste Start kommt ganz ohne Werte aus: Der Dienst
`init` erzeugt einmalig das Datenbankpasswort und die Schlüssel der App und legt sie in
eigene Volumes; Domain und erste Person überspringt er, solange sie fehlen. Danach
laufen `db`, `app` und `backup`; `init` steht auf „beendet“ (Exit 0) – das ist richtig
so.

### 2. `.env` ausfüllen und neu bereitstellen

Im Docker Manager beim Projekt **Bearbeiten** → `.env`:

```
DOMAIN=wiki.meine-firma.de
ADMIN_EMAIL=chefin@meine-firma.de
ADMIN_PASSWORD=ein-langes-eigenes-passwort
```

Dann **erneut bereitstellen**. `init` prüft die Werte zuerst. Ist etwas falsch,
schlägt die Bereitstellung fehl und das Protokoll von `init` sagt, was (siehe
[Diagnose](#diagnose)). Alle Felder: [Die Felder der `.env`](#die-felder-der-env).

### 3. DNS: der Name zeigt auf den VPS

Bei deinem Domain-Anbieter einen **A-Eintrag** für den Namen aus `DOMAIN` anlegen, der
auf die IPv4-Adresse des VPS zeigt (steht im hPanel). Mit IPv6 zusätzlich einen
AAAA-Eintrag. Sobald der Eintrag wirkt (Minuten bis wenige Stunden), holt Traefik das
Zertifikat von Let's Encrypt von selbst. Mit `srvNNNNNN.hstgr.cloud` entfällt dieser
Schritt.

Prüfen: `https://wiki.meine-firma.de` öffnen. Eine Seite „404 page not found“ mit einem
Zertifikat „TRAEFIK DEFAULT CERT“ heißt: DNS wirkt noch nicht, oder `DOMAIN` passt
nicht (siehe Diagnose).

### 4. Anmelden und das Einmal-Passwort wieder leeren

Mit `ADMIN_EMAIL` und `ADMIN_PASSWORD` anmelden. Diese erste Person entsteht nur, solange
es noch niemanden gibt; ein späteres Ändern der beiden Werte legt niemanden mehr an.

Danach:

1. Das Passwort in der App ändern (Menü oben rechts → „Profil und Einstellungen“).
2. In der `.env` `ADMIN_PASSWORD=` wieder **leeren** (die E-Mail darf stehen bleiben)
   und neu bereitstellen. `init` leert dann auch die Kopie des Passworts im Volume.

Weitere Personen legst du in der App an (Verwaltung → Personen → „Person anlegen“).

## Die Felder der `.env`

Alle Felder dürfen leer sein; leer gilt der genannte Standard. Werte ohne
Anführungszeichen eintragen und **kein `$`** verwenden (Compose würde es als Variable
lesen).

| Feld | Bedeutung | Leer |
|---|---|---|
| `DOMAIN` | Der Name der App, **nur der Hostname**: `wiki.meine-firma.de`, nicht `https://wiki.meine-firma.de`, ohne `/` am Ende, ohne Port. Daraus werden die Traefik-Regel und die öffentliche Adresse der App (`https://<DOMAIN>`, nötig für Anmeldung über OIDC und für OAuth-Konnektoren). | App läuft, ist von außen nicht erreichbar |
| `ADMIN_EMAIL` | E-Mail der ersten Person (Inhaberin, alle Rechte). | keine erste Person |
| `ADMIN_PASSWORD` | Ihr erstes Passwort: 10 bis 200 Zeichen, nicht auf der Liste geleakter Passwörter, ohne Wörter aus der E-Mail-Adresse oder dem Produktnamen. Nach der ersten Anmeldung leeren. | keine erste Person |
| `TRAEFIK_NETWORK` | Docker-Netz, über das Traefik die App erreicht; wird angelegt, wenn es fehlt. | `herd-web` |
| `TRAEFIK_ENTRYPOINT` | Name des HTTPS-Entrypoints von Hostingers Traefik. | `websecure` |
| `TRAEFIK_CERTRESOLVER` | Name des Zertifikat-Resolvers von Hostingers Traefik. | `letsencrypt` |
| `HERD_IMAGE_TAG` | Version des Images (`ghcr.io/janschachtschabel/to-herd-cats-ai`): `1.0` folgt jeder `1.0.x`, `1.0.3` bleibt genau dort. | `1.0` |
| `HERD_BACKUP_SCHEDULE` | Wann gesichert wird, Cron mit fünf Feldern in UTC. | `30 2 * * *` (täglich 02:30 UTC) |
| `HERD_BACKUP_KEEP_DAILY`, `…_WEEKLY`, `…_MONTHLY` | Wie viele Sicherungen bleiben (die neueste je Tag, Woche, Monat). | 7, 4, 6 |
| `HERD_BACKUP_ALERT_AFTER_HOURS` | Ab wie vielen Stunden ohne gute Sicherung die Metrik `HerdBackupTooOld` anschlägt. | 26 |
| `HERD_COLLAB_MEMORY_BUDGET_MB` | Speicher für Seiten in der Live-Bearbeitung; auf 2 GB RAM z. B. `200`. | 400 |
| `HERD_RUN_CONCURRENCY` | KI-Agenten-Läufe gleichzeitig. | 4 |
| `HERD_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` oder `ERROR`. | `INFO` |
| `HERD_FORWARDED_ALLOW_IPS` | Wessen `X-Forwarded-For` die App glaubt (der Proxy davor). Hostingers Traefik läuft im Netz des Hosts und kommt aus dem Docker-Netz. | `172.16.0.0/12,10.0.0.0/8,192.168.0.0/16` |

**Nicht in die `.env`:** Datenbankpasswort, `HERD_SECRET_KEY` und das interne Token der
Live-Bearbeitung. Sie erzeugt `init` beim ersten Start (je 256 Zufallsbits) und legt
sie in die Volumes `<projekt>_secrets` und `<projekt>_db-secret`; die Dienste lesen sie
als Dateien (`HERD_*_FILE`, `POSTGRES_PASSWORD_FILE`). Sie bleiben bei jeder weiteren
Bereitstellung gleich. **KI-Schlüssel** und **Client-Secrets** (OIDC, OAuth) trägst du
in der App ein; gespeichert werden sie verschlüsselt unter diesem `HERD_SECRET_KEY`
([`KI.md`](KI.md)).

## Was läuft

| Dienst | Aufgabe |
|---|---|
| `init` | einmal je Bereitstellung: Geheimnisse erzeugen (nur beim ersten Mal), `DOMAIN` und die Einmal-Werte prüfen; endet mit Exit 0 |
| `db` | PostgreSQL 17 mit pgvector; nur im internen Netz des Projekts |
| `app` | die ganze App in einem Container (`HERD_ROLE=all`): beim Start die Migrationen, dann API und Oberfläche, Worker (Benachrichtigungen, Agenten, Automationen) und die Live-Bearbeitung (unter `/collab` über die API) |
| `backup` | Sicherungen nach `HERD_BACKUP_SCHEDULE` in das Volume `<projekt>_backups` |

Kein Dienst belegt einen Port des VPS; Traefik erreicht die App über das Netz
`herd-web` (Labels am Dienst `app`, Router und Dienst `herd-app`).

## Updates

1. Vorher sichern (siehe unten): `docker compose exec backup python -m app.ops backup run`.
2. Mit `HERD_IMAGE_TAG=1.0` (Standard): im Docker Manager beim Projekt neu bereitstellen
   bzw. in der Webkonsole `cd /docker/<projekt> && docker compose pull && docker
   compose up -d`. Für eine neue Hauptversion (z. B. `1.1`) den Wert in der `.env`
   ändern und neu bereitstellen.
3. Die App migriert beim Start selbst. Zurück auf eine ältere Version nur mit der
   Sicherung aus Schritt 1 (README, „Freigaben und Updates“).

## Sicherungen

Der Dienst `backup` sichert Datenbank und Anhänge nach `HERD_BACKUP_SCHEDULE` als
geprüftes Archiv in das Volume **`<projekt>_backups`**, auf dem VPS unter
`/var/lib/docker/volumes/<projekt>_backups/_data/`. Alte Archive räumt er nach den
`HERD_BACKUP_KEEP_*`-Werten ab. In der Webkonsole:

```bash
cd /docker/<projekt>
docker compose exec backup python -m app.ops backup run    # jetzt sichern
docker compose exec backup python -m app.ops backup list   # was es gibt
ls -l /var/lib/docker/volumes/<projekt>_backups/_data/     # die Archive
```

**Wichtig:** Die Archive liegen auf demselben VPS. Geht der VPS verloren, sind sie mit
weg. Kopiere sie regelmäßig woandershin (z. B. `scp` von deinem Rechner) – und einmal
den Schlüssel `HERD_SECRET_KEY`: Ohne ihn sind nach einer Wiederherstellung auf einem
neuen Server die gespeicherten KI-Schlüssel und Client-Secrets unlesbar.

```bash
docker compose exec app cat /secrets/secret_key   # sicher aufbewahren, nicht weitergeben
```

Die Archive sind nicht verschlüsselt; das Volume ist nur für root lesbar. Sicherungen
außer Haus mit restic bietet dieser Stack nicht; dafür die Referenz unter
`deploy/compose/` nehmen. Wiederherstellen (nur in eine leere Installation) beschreibt
[`SICHERUNG.md`](SICHERUNG.md); die Volumes heißen hier `<projekt>_backups`,
`<projekt>_app-data` usw. (`docker volume ls`), und die App liest `HERD_SECRET_KEY`
selbst aus ihrem Volume.

## Diagnose

Die Webkonsole im Docker Manager ist eine Root-Shell.

```bash
cat /docker/<projekt>/.build.log                     # echte Ursache von „Bereitstellung fehlgeschlagen“
cd /docker/<projekt> && docker compose config -q && echo CONFIG-OK
docker compose ps -a                                 # init: exited (0), die anderen: running
docker compose logs init                             # was init geprüft und übersprungen hat
docker compose logs --tail 50 app                    # Start, Migrationen, Fehler der App
docker network ls                                    # herd-web ist da
ss -tlnp | grep -E ':(80|443) '                      # Traefik hält 80/443 (Host-Modus)
cat /docker/traefik/docker-compose.yml               # Namen von Entrypoint und Resolver
docker logs $(docker ps -q --filter name=traefik) --tail 40 2>&1   # Router- und Zertifikatsfehler
```

Meldungen von `init` (Exit 2: Bereitstellung bricht ab, nichts wird geändert):

| Meldung | Bedeutung, Abhilfe |
|---|---|
| `DOMAIN must be a bare host name …` | In `DOMAIN` steht eine Adresse statt eines Namens (`https://…`, `/` am Ende, Port, Leerzeichen). Nur den Hostnamen eintragen. |
| `ADMIN_PASSWORD is set but ADMIN_EMAIL is empty` | Beide zusammen setzen (oder beide leer lassen). |
| `ADMIN_EMAIL must be an e-mail address …` | Tippfehler in der Adresse. |
| `ADMIN_PASSWORD must be 10 to 200 characters long` | Längeres Passwort wählen. |
| `ADMIN_PASSWORD is easy to guess (auth.password_common)` | Das Passwort steht auf einer Liste geleakter Passwörter: ein anderes wählen. |
| `ADMIN_PASSWORD is easy to guess (auth.password_context)` | Es enthält ein Wort aus der E-Mail-Adresse oder dem Produktnamen: ein anderes wählen. |
| `… is empty: the volume is broken` (Exit 1) | Eine Geheimnis-Datei im Volume ist leer. Aus einer Kopie zurückholen; ein neues Datenbankpasswort würde die App aus ihrer Datenbank aussperren. |

Hinweise (Exit 0): `DOMAIN is empty: skipped` und `ADMIN_PASSWORD is empty: no one-time
admin (skipped)` sind beim ersten Start richtig.

Häufige Fälle:

- **„404 page not found“ mit „TRAEFIK DEFAULT CERT“:** DNS zeigt noch nicht auf den VPS,
  `DOMAIN` passt nicht zur aufgerufenen Adresse, oder Entrypoint/Resolver heißen in
  `/docker/traefik/docker-compose.yml` anders (dann `TRAEFIK_ENTRYPOINT` bzw.
  `TRAEFIK_CERTRESOLVER` setzen). Das Traefik-Protokoll nennt den Grund.
- **Anmeldung klappt nicht:** `docker compose logs app | grep bootstrap`.
  `bootstrap.skipped` heißt: Beim Start fehlten E-Mail oder Passwort; `.env` ausfüllen
  und neu bereitstellen. Gibt es schon eine Person, legt der Start niemanden mehr an.
- **Live-Bearbeitung verbindet nicht:** `DOMAIN` muss genau der Name sein, unter dem
  die App im Browser geöffnet wird.

## Grenzen

- Ein zweites Exemplar dieses Stacks auf demselben VPS bräuchte andere Namen für den
  Traefik-Router (`herd-app` ist fest); dafür die Referenz unter `deploy/compose/`
  nehmen.
- Sehr große Uploads (bis 25 MB je Anhang, 100 MB je Import) über eine langsame
  Leitung können an Zeitgrenzen von Hostingers Traefik scheitern; dessen Einstellungen
  gehören zu `/docker/traefik`, nicht zu diesem Stack.
- Die Compose-Datei ist für Web-Editoren schlicht gehalten (keine Tabs, Anker oder
  verschachtelten Variablen); `backend/tests/test_hostinger_compose.py` prüft das und
  die übrigen Regeln, die CI startet den Stack (`deploy/scripts/hostinger-smoke.sh`).
