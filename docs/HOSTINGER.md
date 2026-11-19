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

**Noch nicht freigegeben (Stand 19.11.2026):** Das Image
`ghcr.io/janschachtschabel/to-herd-cats-ai` erscheint erst mit der ersten
veröffentlichten Freigabe (ein Tag `vX.Y.Z`, siehe README, „Freigaben und Updates“).
Bis dahin findet der Docker Manager kein Image zu `HERD_IMAGE_TAG`, und die
Bereitstellung scheitert beim Holen. Was die nächste Freigabe gegenüber 1.0.0 ändert,
steht in [`RELEASE-NEXT.md`](RELEASE-NEXT.md).

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
ADMIN_PASSWORD='ein langes eigenes Passwort'
```

- `DOMAIN` klein geschrieben, ohne `https://`.
- Das Passwort **in einfachen Anführungszeichen** `'…'`. Nur so kommt es genau so an,
  wie du es getippt hast. Ohne Anführungszeichen schneidet Docker Compose es still ab:
  ab ` #` (Leerzeichen und Raute) gilt der Rest als Kommentar, und ein `$` wird als
  Variable gelesen. Aus `Gruene Wiese #7` würde `Gruene Wiese`, und mit diesem
  verkürzten Passwort entstünde die erste Person. Ein `'` darf im Passwort selbst
  nicht vorkommen.

Dann **erneut bereitstellen**. `init` prüft die Werte zuerst. Ist etwas falsch,
schlägt die Bereitstellung fehl und das Protokoll von `init` sagt, was (siehe
[Diagnose](#diagnose)). **Wichtig:** Docker hält dabei zuerst `app`, `db` und
`backup` an. Sie bleiben gestoppt, bis der Wert korrigiert und erneut bereitgestellt
ist; die App ist so lange nicht erreichbar. Daten gehen dabei nicht verloren. Alle
Felder: [Die Felder der `.env`](#die-felder-der-env).

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

**Ausgesperrt, gleich nach der Installation?** Klappt die Anmeldung mit dem Passwort
nicht (z. B. weil es ohne Anführungszeichen abgeschnitten wurde), hilft ein neues
`ADMIN_PASSWORD` nicht mehr: Die erste Person gibt es dann schon. Solange die
Installation noch **keine Daten** hat, fängst du in der Webkonsole einfach neu an:

```bash
cd /docker/<projekt>
docker compose down -v      # löscht ALLE Daten dieses Projekts: Datenbank, Anhänge, Sicherungen, Schlüssel
```

Dann die `.env` richtig ausfüllen (Passwort in `'…'`) und im Docker Manager erneut
bereitstellen (oder `docker compose up -d`). Hat die Installation schon Inhalte,
**nicht** so vorgehen: `down -v` würde sie löschen.

## Die Felder der `.env`

Alle Felder dürfen leer sein; leer gilt der genannte Standard. Die Werte stehen ohne
Anführungszeichen, **außer `ADMIN_PASSWORD`**: das in einfache Anführungszeichen
setzen (`ADMIN_PASSWORD='…'`), sonst schneidet Compose es bei ` #` ab und liest `$` als
Variable (siehe Schritt 2).

| Feld | Bedeutung | Leer |
|---|---|---|
| `DOMAIN` | Der Name der App, **nur der Hostname** und **klein geschrieben**: `wiki.meine-firma.de`, nicht `https://wiki.meine-firma.de` oder `Wiki.Meine-Firma.de`, ohne `/` am Ende, ohne Port. Keine IP-Adresse und kein Name ohne Punkt (dafür gibt es kein Zertifikat). Ein Name mit Umlauten steht in der `xn--`-Form (aus `müller.de` wird `xn--mller-kva.de`; `init` nennt sie dir). Daraus werden die Traefik-Regel und die öffentliche Adresse der App (`https://<DOMAIN>`, nötig für die Live-Bearbeitung, die Anmeldung über OIDC und OAuth-Konnektoren). | App läuft, ist von außen nicht erreichbar |
| `ADMIN_EMAIL` | E-Mail der ersten Person (Inhaberin, alle Rechte). | keine erste Person |
| `ADMIN_PASSWORD` | Ihr erstes Passwort, **in einfachen Anführungszeichen** (`'…'`, ohne `'` darin): 10 bis 200 Zeichen, nicht auf der Liste geleakter Passwörter, ohne Wörter aus der E-Mail-Adresse oder dem Produktnamen. Nach der ersten Anmeldung leeren. | keine erste Person |
| `TRAEFIK_NETWORK` | Docker-Netz, über das Traefik die App erreicht; wird angelegt, wenn es fehlt. | `herd-web` |
| `TRAEFIK_ENTRYPOINT` | Name des HTTPS-Entrypoints von Hostingers Traefik. | `websecure` |
| `TRAEFIK_CERTRESOLVER` | Name des Zertifikat-Resolvers von Hostingers Traefik. | `letsencrypt` |
| `HERD_IMAGE_TAG` | Version des Images (`ghcr.io/janschachtschabel/to-herd-cats-ai`): `1.0` folgt jeder `1.0.x` (jede Bereitstellung holt die neueste), `1.0.3` bleibt genau dort. | `1.0` |
| `HERD_BACKUP_SCHEDULE` | Wann gesichert wird, Cron mit fünf Feldern in UTC. | `30 2 * * *` (täglich 02:30 UTC) |
| `HERD_BACKUP_KEEP_DAILY`, `…_WEEKLY`, `…_MONTHLY` | Wie viele Sicherungen bleiben (die neueste je Tag, Woche, Monat). | 7, 4, 6 |
| `HERD_BACKUP_UPLOAD_MAX_BYTES` | Wie groß ein Archiv sein darf, das ein Inhaber unter Verwaltung → Sicherung hochlädt (Bytes). | 2147483648 (2 GiB) |
| `HERD_BACKUP_ALERT_AFTER_HOURS` | Ab wie vielen Stunden ohne gute Sicherung der Alarm `HerdBackupTooOld` anschlägt. **Nur mit einem eigenen Prometheus sichtbar**, den dieser Stack nicht mitbringt; ob die Sicherungen gelingen, zeigt hier `backup list` (siehe [Sicherungen](#sicherungen)). | 26 |
| `HERD_COLLAB_MEMORY_BUDGET_MB` | Speicher für Seiten in der Live-Bearbeitung; auf 2 GB RAM z. B. `200`. | 400 |
| `HERD_RUN_CONCURRENCY` | KI-Agenten-Läufe gleichzeitig. | 4 |
| `HERD_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` oder `ERROR`. | `INFO` |
| `HERD_FORWARDED_ALLOW_IPS` | Wessen Angabe zur Absender-Adresse (`X-Forwarded-For`) die App glaubt: die des Proxys davor. Besser enger setzen, siehe [unten](#absender-adressen-enger-fassen). | `172.16.0.0/12,10.0.0.0/8,192.168.0.0/16` |

### Absender-Adressen enger fassen

Die App merkt sich zu Anmeldungen und Änderungen die Adresse des Absenders (Protokoll,
Grenzen für Anmeldeversuche je Adresse). Hostingers Traefik reicht sie weiter. Der
Standard glaubt diese Angabe aber **jedem Container im Netz `herd-web`**, nicht nur
Traefik. Teilen sich andere Anwendungen auf dem VPS dieses Netz, könnte eine von ihnen
eine falsche Adresse vorgeben. Enger geht es so: In der Webkonsole die Adresse des
Netzes nachsehen, über die Traefik kommt (das „Gateway“),

```bash
docker network inspect herd-web --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}'
```

und genau sie eintragen, z. B. `HERD_FORWARDED_ALLOW_IPS=172.18.0.1`, dann neu
bereitstellen. Diese Adresse bleibt gleich, solange es das Netz gibt. Wird es gelöscht
und neu angelegt (z. B. nach `docker compose down`), kann sie sich ändern; dann glaubt
die App keiner Angabe mehr und protokolliert die Adresse von Traefik. Also danach kurz
wieder nachsehen.

### Was nicht in die `.env` gehört

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
   (oder in der Webkonsole `cd /docker/<projekt> && docker compose up -d`). Jede
   Bereitstellung holt das Image neu (`pull_policy: always`), also die neueste `1.0.x`.
   Für eine neue Hauptversion (z. B. `1.1`) den Wert in der `.env` ändern und neu
   bereitstellen. Ist die Registry (GHCR) gerade nicht erreichbar, schlägt die
   Bereitstellung fehl; die laufende App bleibt dabei, wie sie ist. Später erneut
   versuchen.
3. Die App migriert beim Start selbst. Zurück auf eine ältere Version nur mit der
   Sicherung aus Schritt 1 (README, „Freigaben und Updates“).

## Sicherungen

Der Dienst `backup` sichert Datenbank und Anhänge nach `HERD_BACKUP_SCHEDULE` als
geprüftes Archiv in das Volume **`<projekt>_backups`**, auf dem VPS unter
`/var/lib/docker/volumes/<projekt>_backups/_data/`. Zu jeder Sicherung gehören **zwei
Dateien**: das Archiv `herd-<zeit>-<version>.tar` und seine Beschreibung
`herd-<zeit>-<version>.manifest.json`. Alte Sicherungen räumt er nach den
`HERD_BACKUP_KEEP_*`-Werten ab. Einfacher geht es in der App: **Verwaltung →
Sicherung** (nur Inhaber) zeigt die Sicherungen, sichert auf Knopfdruck, lädt Archive
herunter und hoch, prüft und spielt sie ein ([`SICHERUNG.md`](SICHERUNG.md#in-der-verwaltung)).
In der Webkonsole:

```bash
cd /docker/<projekt>
docker compose exec backup python -m app.ops backup run    # jetzt sichern
docker compose exec backup python -m app.ops backup list   # die letzten Sicherungen
ls -l /var/lib/docker/volumes/<projekt>_backups/_data/     # die Dateien
```

**Gelingen die Sicherungen?** Einen Alarm, der dich benachrichtigt, bringt dieser Stack
nicht mit. Schau deshalb ab und zu mit `backup list` nach: In der Spalte `state` muss
bei der neuesten Zeile `ok` stehen, und ihr Datum (`started`, UTC) darf nicht älter
als einen Tag sein. `failed` heißt: Die Sicherung ist gescheitert; den Grund nennen die
Spalte `error` und `docker compose logs --tail 50 backup`.

### Sicherungen und Schlüssel außer Haus

Die Archive liegen auf demselben VPS. Geht der VPS verloren, sind sie mit weg. Kopiere
sie deshalb regelmäßig auf deinen eigenen Rechner, **immer beide Dateien** jeder
Sicherung (`.tar` und `.manifest.json`; ohne die Beschreibung lässt sich das Archiv
nicht einspielen). Auf deinem Rechner (Linux, macOS oder Windows mit PowerShell), mit
der IP-Adresse des VPS aus dem hPanel:

```bash
mkdir herd-sicherungen
scp 'root@<VPS-IP>:/var/lib/docker/volumes/<projekt>_backups/_data/herd-*' herd-sicherungen/
```

Bewahre außerdem **einmal** den Schlüssel `HERD_SECRET_KEY` auf, getrennt von den
Archiven (z. B. im Passwort-Manager). Ohne ihn sind nach einer Wiederherstellung auf
einem neuen Server die gespeicherten KI-Schlüssel und Client-Secrets unlesbar. In der
Webkonsole anzeigen:

```bash
docker compose exec app cat /secrets/secret_key   # sicher aufbewahren, nicht weitergeben
```

Die Archive sind nicht verschlüsselt und enthalten alle Inhalte; das Volume ist nur für
root lesbar. Behandle die Kopien entsprechend. Sicherungen außer Haus mit restic bietet
dieser Stack nicht; dafür die Referenz unter `deploy/compose/` nehmen.

### Wiederherstellen

**Auf demselben VPS, solange die App läuft,** geht es am einfachsten in der App:
**Verwaltung → Sicherung**, beim Archiv „Einspielen …“ (nur Inhaber; zur Bestätigung den
Namen der Organisation eintippen). Die App sichert vorher den jetzigen Stand
(`pre_restore`), zeigt allen die Wartungsseite, ersetzt Datenbank und Anhänge und meldet
danach alle ab. In der Webkonsole dasselbe:

```bash
docker compose exec app python -m app.ops restore apply /backups/<archiv>.tar \
  --replace --confirm '<Name der Organisation>'
```

Die Einzelheiten stehen in [`SICHERUNG.md`](SICHERUNG.md) („Einspielen in eine
laufende Installation“, „In der Verwaltung“).

**Auf einem neuen VPS** (oder wenn die App nicht mehr startet) wird in eine **leere**
Datenbank eingespielt; die Schritte unten leeren sie. Die Einzelheiten und alle Meldungen stehen in [`SICHERUNG.md`](SICHERUNG.md)
(„Wiederherstellen“). In der Webkonsole, `<projekt>` ist der Projektname,
`<archiv>` der Dateiname der Sicherung (z. B. `herd-20261116T023000Z-1.0.2`):

1. **Auf einem neuen VPS:** zuerst den Stack wie oben in Schritt 1 bereitstellen (ohne
   Werte). Dann von deinem Rechner aus beide Dateien der Sicherung ins Volume kopieren
   und sie dem Benutzer der App (10001) geben:

   ```bash
   scp herd-sicherungen/<archiv>.tar herd-sicherungen/<archiv>.manifest.json \
     'root@<VPS-IP>:/var/lib/docker/volumes/<projekt>_backups/_data/'
   ```

   ```bash
   chown 10001:10001 /var/lib/docker/volumes/<projekt>_backups/_data/herd-*
   ```

   **Auf demselben VPS** liegen die Archive schon dort; dann vorher noch den jetzigen
   Stand sichern, als Weg zurück:
   `docker compose exec backup python -m app.ops backup run`.

2. App und Sicherung anhalten (die Datenbank läuft weiter):

   ```bash
   cd /docker/<projekt>
   docker compose stop app backup
   ```

3. **Nur auf einem neuen VPS:** den aufbewahrten Schlüssel zurückspielen. Der Befehl
   fragt nach ihm; einfügen und Enter drücken (die Eingabe bleibt unsichtbar):

   ```bash
   docker compose run --rm --no-deps init set-secret-key
   ```

   Er antwortet mit `HERD_SECRET_KEY written (key id …)`. Ein Schlüssel kürzer als 32
   Zeichen oder mit Leerzeichen wird abgelehnt, und nichts ändert sich.

4. Prüfen. Erwartet wird jetzt genau eine Meldung, `restore.target_not_empty` (die
   Datenbank ist noch nicht leer). Steht dort auch `restore.secret_key_mismatch`, passt
   der Schlüssel nicht: Schritt 3 mit dem richtigen Schlüssel wiederholen.

   ```bash
   docker compose run --rm --no-deps -v <projekt>_backups:/backups \
     --entrypoint "python -m app.ops" app restore check /backups/<archiv>.tar
   ```

   Wichtig ist `<projekt>_backups` vor dem Doppelpunkt, mit dem Projektnamen davor.
   Mit nur `backups` hängt Docker ein neues, leeres Volume ein, und die Prüfung meldet
   `archive.format_unknown`.

5. Datenbank leeren, noch einmal prüfen (jetzt: `ok`), dann einspielen:

   ```bash
   docker compose exec db psql -U herd -d postgres \
     -c 'DROP DATABASE herd WITH (FORCE)' -c 'CREATE DATABASE herd OWNER herd'
   docker compose run --rm --no-deps -v <projekt>_backups:/backups \
     --entrypoint "python -m app.ops" app restore check /backups/<archiv>.tar
   docker compose run --rm --no-deps -v <projekt>_backups:/backups \
     --entrypoint "python -m app.ops" app restore apply /backups/<archiv>.tar
   ```

6. Wieder starten: `docker compose up -d` (oder im Docker Manager neu bereitstellen).
   Alle melden sich neu an, mit ihren Passwörtern aus der Sicherung.

Spiele nur Archive ein, die aus deiner eigenen Installation stammen: Ein Archiv läuft
beim Einspielen als Skript mit der Datenbankrolle der App, und in diesem Stack ist das
der Superuser aus `POSTGRES_USER` ([Was ein Archiv ausführen darf](SICHERUNG.md#was-ein-archiv-ausführen-darf)).
Ein Dump mit mehr als dem Schema der App lehnt die Prüfung ab
(`archive.dump_foreign`).

Scheitert das Einspielen (`failed <code>`), bleibt die Datenbank leer. Dann mit einer
anderen Sicherung ab Schritt 4 wiederholen (auf demselben VPS z. B. mit der aus
Schritt 1).

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

Meldungen von `init`. Bei Exit 2 bricht die Bereitstellung ab. Docker hat `app`, `db`
und `backup` dann schon angehalten, und sie bleiben gestoppt, bis der Wert in der
`.env` korrigiert und erneut bereitgestellt ist. Die Daten bleiben erhalten. Was
`init` gemeldet hat, zeigt `docker compose logs init`.

| Meldung | Bedeutung, Abhilfe |
|---|---|
| `DOMAIN must be a bare host name …` | In `DOMAIN` steht eine Adresse statt eines Namens (`https://…`, `/` am Ende, Port, Leerzeichen). Nur den Hostnamen eintragen. Bei Umlauten nennt die Meldung die `xn--`-Form, die stattdessen hineingehört. |
| `DOMAIN must be written in lower case …` | Großbuchstaben im Namen. Klein schreiben, wie die Meldung es vorschlägt; sonst verbindet die Live-Bearbeitung nie. |
| `DOMAIN must be a full name with a dot …` | Ein Name ohne Punkt (z. B. `localhost`). Den vollen Namen eintragen, z. B. `srvNNNNNN.hstgr.cloud`. |
| `DOMAIN must be a name, not an IP address …` | Für eine IP-Adresse gibt es kein Zertifikat. Den Hostnamen des VPS oder die eigene Domain eintragen. |
| `ADMIN_PASSWORD is set but ADMIN_EMAIL is empty` | Beide zusammen setzen (oder beide leer lassen). |
| `ADMIN_EMAIL must be an e-mail address …` | Tippfehler in der Adresse. |
| `ADMIN_PASSWORD must be 10 to 200 characters long` | Längeres Passwort wählen. |
| `ADMIN_PASSWORD is easy to guess (auth.password_common)` | Das Passwort steht auf einer Liste geleakter Passwörter: ein anderes wählen. |
| `ADMIN_PASSWORD is easy to guess (auth.password_context)` | Es enthält ein Wort aus der E-Mail-Adresse oder dem Produktnamen: ein anderes wählen. |
| `… is empty: the volume is broken` (Exit 1) | Eine Geheimnis-Datei im Volume ist leer. Aus einer Kopie zurückholen; ein neues Datenbankpasswort würde die App aus ihrer Datenbank aussperren. |
| `/secrets/secret_key: Permission denied. The stack's secret files must be files of user 10001 …` (Exit 1) | Die Schlüsseldatei wurde von Hand (als root) ins Volume gelegt. Mit `docker compose run --rm --no-deps init set-secret-key` neu schreiben (siehe [Wiederherstellen](#wiederherstellen)), dann neu bereitstellen. |

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
  Stand das Passwort ohne Anführungszeichen in der `.env`, wurde es womöglich
  abgeschnitten: siehe „Ausgesperrt, gleich nach der Installation?“ in Schritt 4.
- **Live-Bearbeitung verbindet nicht:** `DOMAIN` muss genau der Name sein, unter dem
  die App im Browser geöffnet wird (klein geschrieben).
- **Die App ist nach einer Änderung der `.env` weg:** `docker compose ps -a` zeigt
  `init` mit Exit 2 und die anderen gestoppt. `docker compose logs init` nennt den
  Wert; korrigieren und neu bereitstellen.

## Grenzen

- Ein zweites Exemplar dieses Stacks auf demselben VPS bräuchte andere Namen für den
  Traefik-Router (`herd-app` ist fest); dafür die Referenz unter `deploy/compose/`
  nehmen.
- Anhänge liegen im Volume `app-data`; einen S3-Speicher (`HERD_STORAGE=s3`,
  [`SICHERUNG.md`](SICHERUNG.md), „Anhänge in S3“) bietet dieser Stack nicht an: Sein
  Schlüssel wäre ein Wert in der `.env`, und der Dienst `backup` hat keinen Weg nach
  draußen. Dafür die Referenz unter `deploy/compose/` (`compose.s3.yml`) oder das
  Chart nehmen.
- Die Schutzschichten aus M9b sind mit ihren Standardwerten an und lassen sich in diesem
  Stack nicht einstellen: Sitzungen enden nach 24 Stunden ohne Nutzung
  (`HERD_SESSION_IDLE_HOURS`), je Person höchstens 120 Schreibvorgänge und 30 Uploads
  je Minute (`HERD_WRITE_RATE_PER_MINUTE`, `HERD_UPLOAD_RATE_PER_MINUTE`). Ohne
  Gegenstück bleiben: der Virenscan (`HERD_CLAMAV_ADDRESS`), TLS zur Datenbank
  (`HERD_DATABASE_SSLMODE`; die Datenbank liegt hier im internen Netz des Projekts) und
  getrennte Datenbankrollen (`HERD_MIGRATE_DATABASE_URL`). Wer sie braucht, nimmt die
  Referenz unter `deploy/compose/` oder das Chart (README, Betriebshinweise).
- Sehr große Uploads (bis 25 MB je Anhang, 100 MB je Import) über eine langsame
  Leitung können an Zeitgrenzen von Hostingers Traefik scheitern; dessen Einstellungen
  gehören zu `/docker/traefik`, nicht zu diesem Stack.
- Die Compose-Datei ist für Web-Editoren schlicht gehalten (keine Tabs, Anker oder
  verschachtelten Variablen); `backend/tests/test_hostinger_compose.py` prüft das und
  die übrigen Regeln, die CI startet den Stack (`deploy/scripts/hostinger-smoke.sh`).
