# Sicherung und Wiederherstellung

Stand: M9 Tasks 1 bis 3 (Archiv und Sicherung über die Kommandozeile, Wiederherstellung
in eine leere Installation mit Probe, Zeitplan, Aufbewahrung, Offsite mit restic und
Alarme).

## Was gesichert wird

Ein Archiv enthält den **ganzen Datenstand** der Installation: die Datenbank als
`pg_dump -Fc` (Schema und Daten, mit Triggern, Indizes und erzeugten Spalten) und
alle Dateien, auf die eine Anhang-Zeile zeigt. Beides stammt aus **einem**
Datenbank-Snapshot: Die Sicherung öffnet eine `REPEATABLE READ`-Transaktion, exportiert
ihren Snapshot, lässt `pg_dump --snapshot` darauf laufen und liest im selben Snapshot
die Zeilenzahlen und die Speicherschlüssel der Anhänge. Genau diese Dateien kommen ins
Archiv; was während der Sicherung hochgeladen wird, gehört nicht dazu, was gelöscht
wird, schon (die Datei bleibt 48 Stunden liegen, siehe
[`WIKI.md`](WIKI.md#versionen-papierkorb-tags-anhänge-suche)). Eine Sicherung, die
länger als 48 Stunden braucht, ist nicht vorgesehen.

## Archivformat 1

Eine unkomprimierte tar-Datei `herd-<UTC JJJJMMTTThhmmssZ>-<Version>.tar` (Rechte
0600; ein neu angelegtes Verzeichnis 0700), Mitglieder in dieser Reihenfolge:

| Mitglied | Inhalt |
|---|---|
| `herd/FORMAT` | `1` |
| `herd/db.dump` | `pg_dump -Fc` (in sich komprimiert) |
| `herd/files/<Speicherschlüssel>` | je gespeicherte Datei, z. B. `attachments/<org_id>/<sha256>` |
| `herd/manifest.json` | das Manifest (zuletzt) |

Daneben liegt `<Name>.manifest.json`: dasselbe Manifest plus `archive_sha256`, die
Prüfsumme der ganzen tar-Datei. Das Manifest enthält nur Kennzahlen, nie Inhalte:
Format, App-Version, Alembic-Revision, Erstellzeit (UTC), Hauptversion des Servers,
Version von `pg_dump`, Speicherart (`local`), Zeilen je Tabelle, Dateien (Anzahl,
Bytes), SHA-256 und Größe je Mitglied, die **Schlüsselkennung** von `HERD_SECRET_KEY`,
die Anzahl der `enc:`-Werte je Geheimnis-Spalte (jede Textspalte `*_ref`) und die
Namen der `env:`-Verweise.

Unkomprimiert, weil der Dump schon komprimiert ist und Anhänge meist auch, und weil ein
deduplizierendes Offsite-Werkzeug (restic) so über Archive hinweg spart.

## Geheimnisse und Schlüssel

Das Archiv enthält die gespeicherten Geheimnisse **unverändert**: `enc:`-Werte
(verschlüsselt mit `HERD_SECRET_KEY`) und `env:`-Verweise (nur Namen). Der Schlüssel
selbst steht nirgends im Archiv; das Manifest nennt nur seine Kennung (die ersten 16
Hex-Zeichen von HKDF-SHA256 mit `info="herd-key-id"`). Wer ein Archiv einspielen will,
braucht denselben `HERD_SECRET_KEY` (oder ihn als `HERD_SECRET_KEY_PREVIOUS`):
**Bewahren Sie den Schlüssel getrennt vom Archiv auf.**

Die Archive selbst sind **nicht verschlüsselt** und enthalten alle Inhalte, auch
Direktnachrichten. Schützen Sie das Sicherungs-Volume wie die Datenbank (Zugriff nur
für den Betrieb, verschlüsselter Datenträger).

## Kommandozeile

Im Image (oder im Entwicklungs-Checkout unter `backend/` mit `uv run`), mit denselben
`HERD_*`-Einstellungen wie die App (Datenbank, `HERD_DATA_DIR`, `HERD_SECRET_KEY`):

```bash
python -m app.ops backup create [--dir DIR]   # schreibt ein Archiv, gibt seinen Pfad aus
python -m app.ops backup verify ARCHIV        # "ok" oder je Zeile ein Problemcode
python -m app.ops backup list [--limit N]     # die Sicherungen aus backup_run, neueste zuerst
```

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `HERD_BACKUP_DIR` | `/backups` | Zielverzeichnis der Archive (ein eigenes Volume) |

Weitere Befehle für den Zeitplan (unten): `python -m app.ops backup run` (eine Sicherung
mit Aufbewahrung und Offsite, der CronJob im Chart) und `python -m app.ops backup
schedule` (läuft dauerhaft und ruft `run` zu jedem Termin, der Compose-Dienst `backup`).

Exit-Status 0 bei Erfolg, 1 bei einem Fehler, 2 bei falschem Aufruf. Die
Kommandozeile handelt als `system`: Eine gelungene Sicherung steht im Audit-Log als
`backup.created` (Archivname, Bytes, `via=cli`).

Ein Lauf schreibt zuerst eine Zeile `backup_run` (`running`), dann Dump und Dateien in
eine versteckte `.part`-Datei, die erst am Ende umbenannt wird; danach liest er das
Archiv vollständig zurück und prüft es. Erst dann ist der Lauf `ok`. Scheitert etwas,
wird alles Geschriebene entfernt und der Lauf mit einem Code `failed`:

| Code | Bedeutung |
|---|---|
| `backup.no_organization` | die Datenbank hat noch keine Organisation |
| `backup.no_schema` | die Datenbank ist nicht migriert |
| `backup.tool_missing` | `pg_dump` fehlt im `PATH` |
| `backup.tools_too_old` | `pg_dump` ist älter als der Server (Hauptversion) |
| `backup.dump_failed` | `pg_dump` endete mit einem Fehler (Verbindung, Rechte) |
| `backup.file_missing` | eine Datei des Snapshots fehlt in der Ablage |
| `backup.io` | Schreiben scheiterte (Platz, Rechte, Name schon vergeben) |
| `backup.verify_failed` | das zurückgelesene Archiv passt nicht |
| `backup.failed` | etwas anderes |

`pg_dump` bekommt das Datenbank-Passwort nur über `PGPASSWORD` in einer eigens
gebauten Umgebung (nie als Argument oder in einer URL); seine Ausgaben werden nicht
protokolliert.

`verify` meldet: `archive.checksum` (die Prüfsumme der Begleitdatei passt nicht),
`archive.format_unknown`, `archive.member_missing`, `archive.member_checksum` (ein
Mitglied weicht vom Manifest ab oder steht nicht darin), `archive.truncated`. Ohne
Begleitdatei (ein einzeln kopiertes Archiv) prüft es die Mitglieder gegen das innere
Manifest.

**Werkzeuge:** Das Image bringt `postgresql-client-17` mit; unterstützt sind Server ab
PostgreSQL 16. `pg_dump` muss mindestens die Hauptversion des Servers haben.

## Zeitplan, Aufbewahrung, Offsite

Ein Lauf (`backup run`): Archiv schreiben → zurücklesen und prüfen → erst dann `ok` →
Aufbewahrung im Volume → Offsite mit restic. Eine misslungene Sicherung löscht nichts.
Exit-Status 0 nur, wenn Sicherung und (falls eingeschaltet) Offsite gelangen; die Zeile
in `backup_run` sagt, welcher Teil scheiterte (`state`, `offsite_state` `off|ok|failed`).

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `HERD_BACKUP_SCHEDULE` | `30 2 * * *` | Termine von `backup schedule` (Cron, fünf Felder, UTC); im Chart hat der CronJob `backup.schedule` |
| `HERD_BACKUP_KEEP_DAILY` | `7` | so viele Tage: je Tag das neueste Archiv |
| `HERD_BACKUP_KEEP_WEEKLY` | `4` | danach so viele ISO-Wochen: je Woche das neueste |
| `HERD_BACKUP_KEEP_MONTHLY` | `6` | danach so viele Monate: je Monat das neueste |
| `HERD_BACKUP_OFFSITE_REPOSITORY` | leer (aus) | restic-Repository, z. B. `s3:https://s3.example/bucket/herd`, `b2:bucket:herd`, `sftp:backup@host:/srv/herd` |
| `HERD_BACKUP_OFFSITE_PASSWORD` | – | Passwort des restic-Repositorys (Geheimnis; Pflicht mit Repository) |
| `HERD_BACKUP_ALERT_AFTER_HOURS` | `26` | ab diesem Alter der letzten gelungenen Sicherung feuert `HerdBackupTooOld` (der Worker meldet den Wert als Metrik) |

**Aufbewahrung** (Großvater-Vater-Sohn, UTC): das neueste gelungene Archiv bleibt immer;
dazu das neueste je Tag für die letzten 7 Tage mit Archiv, davor das neueste je
ISO-Woche für 4 weitere Wochen, davor das neueste je Monat für 6 weitere Monate (mit den
Standardwerten 17 Archive). Archive ohne lesbare Begleitdatei (von Hand abgelegt) rührt
die Aufbewahrung nicht an.

**Offsite** (eingeschaltet mit `HERD_BACKUP_OFFSITE_REPOSITORY`): nach jeder gelungenen
Sicherung `restic backup` von Archiv und Begleitdatei (Tag `herd`), dann `restic forget
--prune --keep-last=1 --keep-daily/--keep-weekly/--keep-monthly` mit denselben Zahlen
(restic zählt Zeiträume überlappend, offsite bleibt also mindestens so viel wie im
Volume) und am Ersten jedes Monats `restic check --read-data-subset=5%`. Ein noch nicht
angelegtes Repository legt der erste Lauf an (`restic init`). restic verschlüsselt auf
dem Client mit dem Repository-Passwort: **ohne dieses Passwort ist die Offsite-Kopie
wertlos**, es gehört wie `HERD_SECRET_KEY` getrennt verwahrt.

restic bekommt eine eigens gebaute Umgebung: `PATH`, `HOME`, Repository und Passwort aus
den Einstellungen und aus der Umgebung des Sicherungsprozesses **nur** die Variablen des
Speichers (`AWS_*`, `B2_*`, `AZURE_*`, `GOOGLE_*`, `OS_*`, `ST_*` und `RESTIC_*` außer
Repository und Passwort, z. B. `RESTIC_COMPRESSION`). Datenbank-Passwort, Geheimschlüssel
und KI-Schlüssel erreichen restic nie; das Passwort steht nie in einer Argumentliste.
Ausgaben von restic werden nicht protokolliert, nur Schritt und Exit-Status
(`backup.offsite_failed`).

## Überwachung

Jeder Worker liest die Sicherungsläufe alle 10 s aus `backup_run` (ein kurzlebiger Job
lässt sich nicht abfragen) und meldet:

| Metrik | Bedeutung |
|---|---|
| `herd_backup_last_success_timestamp_seconds` | Ende der letzten gelungenen Sicherung (0: noch keine) |
| `herd_backup_last_failure_timestamp_seconds` | Ende der letzten misslungenen |
| `herd_backup_last_bytes` | Größe des letzten gelungenen Archivs |
| `herd_backup_offsite_last_success_timestamp_seconds` | letzte gelungene Sicherung, die das restic-Repository erreichte |
| `herd_backup_offsite_last_failure_timestamp_seconds` | letzte gelungene Sicherung, deren Offsite-Schritt scheiterte |
| `herd_backup_alert_after_seconds` | `HERD_BACKUP_ALERT_AFTER_HOURS` in Sekunden |

## Wiederherstellen (in eine leere Installation)

Eingespielt wird über die Kommandozeile, mit den `HERD_*`-Einstellungen der
**Ziel**-Installation (Datenbank, `HERD_DATA_DIR`, `HERD_SECRET_KEY`):

```bash
python -m app.ops restore check ARCHIV                       # "ok" oder Problemcodes, dazu Warnungen
python -m app.ops restore apply ARCHIV [--without-secrets]   # nur in eine leere Installation
```

**Leer** heißt: keine Tabelle im Schema `public` (eine frisch angelegte Datenbank, noch
nicht migriert, kein App-Prozess hat sie gestartet) und in der Ablage kein Schlüssel des
Archivs mit anderem Inhalt (gleicher Schlüssel = gleicher Inhalt, geprüft über SHA-256).
Einspielen in eine laufende Installation folgt in M9b.

Abgelehnt wird mit einem Code; am Ziel ändert sich dann nichts:

| Code | Bedeutung |
|---|---|
| `archive.*` | das Archiv selbst passt nicht (siehe `verify` oben) |
| `restore.archive_newer` | das Archiv hat eine Alembic-Revision, die dieser Code nicht kennt (neuere Version): erst die passende oder neuere App-Version einsetzen |
| `restore.target_not_empty` | die Zieldatenbank hat schon Tabellen |
| `restore.file_conflict` | ein Schlüssel des Archivs liegt in der Ablage mit anderem Inhalt |
| `restore.server_too_old` | der Zielserver hat eine kleinere Hauptversion als der Quellserver |
| `restore.tools_too_old` | `pg_restore` ist älter als das `pg_dump` des Archivs (oder fehlt) |
| `restore.secret_key_mismatch` | das Archiv hat `enc:`-Werte, und weder `HERD_SECRET_KEY` noch `HERD_SECRET_KEY_PREVIOUS` hat die Kennung aus dem Manifest |
| `restore.secret_key_missing` | dasselbe, ohne jeden Schlüssel am Ziel |

Warnungen halten nicht auf: `restore.env_missing:<NAME>` (eine Umgebungsvariable zu
einem `env:`-Verweis fehlt am Ziel) und, bei einem Schlüsselproblem,
`restore.secrets_unreadable:<tabelle.spalte>=<Anzahl>`.

**Ohne passenden Schlüssel** spielt `--without-secrets` trotzdem ein: Die `enc:`-Werte
bleiben unlesbar. KI-Verbindungen, Konnektoren und OAuth-Clients melden dann „Geheimnis
nicht verfügbar“, bis ein Admin den Wert neu einträgt.

Der Ablauf, unter der Advisory-Sperre `herd.schema` (dieselbe nimmt jede Migration;
ein startender App-Prozess in Rolle `all` wartet also, statt dazwischen zu migrieren):

1. die Prüfungen oben;
2. die Dateien des Archivs in die Ablage (je Datei beim Schreiben gegen das Manifest
   geprüft; schon vorhandene mit gleichem Inhalt bleiben);
3. die Datenbank mit `pg_restore --no-owner --no-privileges --single-transaction
   --exit-on-error` (ganz oder gar nicht; scheitert es, werden die eben geschriebenen
   Dateien wieder entfernt);
4. `alembic upgrade head`, wenn das Archiv eine ältere bekannte Revision hat;
5. in einer Transaktion: alle Sitzungen und offenen OAuth-Abläufe gelöscht (nach einer
   Wiederherstellung ist jede Anmeldung ungültig), Sicherungsläufe im Zustand `running`
   werden `interrupted`, ein Audit-Eintrag `backup.restored` (`system`, Archivname,
   Revisionen).

Danach die App normal starten. `restore apply` gibt Revisionen, Tabellen und Dateien
aus; scheitert ein Schritt, endet es mit `failed <code>` (`restore.pg_restore_failed`,
`restore.tool_missing`, `archive.member_checksum`).

### Probe

`deploy/scripts/restore-rehearsal.sh` spielt den ganzen Weg durch: Installation A mit
Demodaten und Anhang, Sicherung während A läuft, Einspielen in eine leere Datenbank B,
Vergleich aller Tabellen (`scripts/compare_databases.py`: Zeilen und Prüfsumme des
Inhalts), Anmeldung an B, das alte Cookie von A gilt nicht, der Anhang hat dieselbe
Prüfsumme, ein manipuliertes Archiv wird abgelehnt. Ohne Docker, gegen einen
PostgreSQL-Server über `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD` (Standard
`localhost:5433`, `herd`); Ausgabe der letzten Probe in
[`demo/m9.md`](demo/m9.md). In der CI läuft sie als Job `restore` gegen PostgreSQL 17.
