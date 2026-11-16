# Sicherung und Wiederherstellung

Stand: M9a (Archiv und Sicherung über die Kommandozeile, Wiederherstellung in eine leere
Installation mit Probe, Zeitplan, Aufbewahrung, Offsite mit restic, Alarme, Aufbewahrung
je Tabelle) und aus M9b der Wartungsmodus mit dem Einspielen in eine **laufende**
Installation über die Kommandozeile. Die Sicherung in der Verwaltung folgt in M9b.

**Kurz für den Betrieb:**

1. Die Sicherung läuft von selbst: jede Nacht um 02:30 UTC (Compose-Dienst `backup`,
   im Chart der CronJob). Prüfen: `python -m app.ops backup list` (unten).
2. `HERD_SECRET_KEY` und, mit Offsite, das restic-Passwort **getrennt** von den
   Archiven aufbewahren (Passwortsafe). Ohne den Schlüssel bleiben gespeicherte
   KI-Schlüssel und Client-Secrets nach einer Wiederherstellung unlesbar.
3. Für eine Kopie außer Haus `HERD_BACKUP_OFFSITE_REPOSITORY` und
   `HERD_BACKUP_OFFSITE_PASSWORD` setzen (restic, verschlüsselt).
4. Alarme `HerdBackupTooOld`, `HerdBackupFailing` und `HerdOffsiteBackupFailing`
   beobachten (Prometheus, Chart).
5. Wiederherstellen: am einfachsten **im laufenden Betrieb** mit
   `restore apply ARCHIV --replace --confirm "<Name der Organisation>"`
   ([unten](#einspielen-in-eine-laufende-installation-wartungsmodus)): zuerst ein
   Sicherheitsarchiv des jetzigen Stands, dazwischen der Wartungsmodus. Auf einer neuen
   Maschine in eine **leere** Datenbank (Ablauf für [Compose](#ablauf-in-compose) und
   [Kubernetes](#ablauf-in-kubernetes)). Einmal im Jahr proben.

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
mit Aufbewahrung und Offsite; von Hand mit Auslöser `cli`, der CronJob im Chart ruft
`backup run --scheduled` und hält `schedule` fest) und `python -m app.ops backup
schedule` (läuft dauerhaft und ruft `run` zu jedem Termin, Auslöser `schedule`, der
Compose-Dienst `backup`).

Exit-Status 0 bei Erfolg, 1 bei einem Fehler, 2 bei falschem Aufruf. Die
Kommandozeile handelt als `system`: Eine gelungene Sicherung steht im Audit-Log als
`backup.created` (Archivname, Bytes, `via` = Auslöser).

Vor allem anderen prüft ein Lauf die Datenbank und ob schon eine Sicherung läuft; dann
endet er ohne Zeile in `backup_run`, mit Exit-Status 1 und einem Code (nie mit einem
Traceback):

| Code | Bedeutung |
|---|---|
| `backup.database_unavailable` | die Datenbank ist nicht erreichbar |
| `backup.no_schema` | die Datenbank ist nicht migriert |
| `backup.no_organization` | die Datenbank hat noch keine Organisation |
| `backup.schema_behind` | die Datenbank steht auf einer älteren Revision als der Code: erst migrieren |
| `backup.schema_ahead` | die Datenbank steht auf einer Revision, die der Code nicht kennt (eine neuere Version hat migriert): mit dem Image dieser Version sichern |
| `backup.already_running` | eine andere Sicherung (oder eine Wiederherstellung) läuft gerade (sie hält die Advisory-Sperre `herd.backup` auf einer eigenen Verbindung, solange sie läuft) |

Die Sperre gilt für die Sitzung der Verbindung, nicht für eine Transaktion: Die
Verbindung steht während der Sicherung im Zustand `idle`, nie `idle in transaction`. Ein
`idle_in_transaction_session_timeout` des Servers oder der Rolle (bei verwalteten
PostgreSQL-Diensten üblich) beendet sie also nicht. Geht die Verbindung trotzdem
verloren (Server neu gestartet, Netz), ist die Sperre mit ihr weg; die Sicherung läuft
zu Ende, meldet im Log `backup.lock_release_failed` (Code `backup.lock_lost`) und
behält ihr Ergebnis: Aufräumen und Offsite laufen wie nach jeder gelungenen Sicherung.

Zeilen, die noch `running` sind, während niemand die Sperre hält, gehören zu Sicherungen,
deren Prozess starb (etwa vom Zeitlimit des CronJobs, 6 Stunden, beendet): Die nächste
Sicherung und die Fälligkeits-Schleife des Workers (einmal je Minute) setzen sie auf
`interrupted` mit Code `backup.interrupted` (Endzeit = Zeitpunkt des Markierens); das
zählt als misslungene Sicherung (`HerdBackupFailing`). Eine Wiederherstellung setzt die
Zeilen, die im Archiv noch liefen (darunter die Sicherung, die das Archiv schrieb), auf
`interrupted` mit `backup.in_restored_archive`; die zählen nicht als Fehler. Das sind
nur Zeilen, die spätestens in der Sekunde des Archivs (`created_at` im Manifest)
begonnen haben; eine spätere `running`-Zeile bleibt, wie sie ist. Die
Ablehnungen oben (`backup.already_running`, `backup.schema_*`,
`backup.database_unavailable`) schreiben keine Zeile: sie meldet nur `HerdBackupTooOld`,
sobald die letzte gelungene zu alt ist (und der Exit-Status 1 des Jobs).

Die versteckten Dateien einer gestorbenen Sicherung (`.herd-*.part`: Archiv,
Begleitdatei und Dump, bis zu einem ganzen Archiv groß) entfernt die nächste Sicherung,
während sie die Sperre hält (Log `backup.leftovers_removed` mit der Anzahl); andere
Dateien im Verzeichnis rührt sie nicht an.

Ein Lauf schreibt zuerst eine Zeile `backup_run` (`running`), dann den Dump in eine
versteckte Arbeitsdatei neben dem Archiv (`.<archiv>.db.dump.part`, Modus 0600, auf dem
Sicherungs-Volume, nie in `/tmp`) und Dump und Dateien in eine versteckte `.part`-Datei,
die erst am Ende umbenannt wird; die Arbeitsdatei ist danach weg. Auf dem Volume braucht
eine Sicherung also kurz Platz für den Dump zweimal plus die Anhänge. Danach liest er das
Archiv vollständig zurück und prüft es. Erst dann ist der Lauf `ok`. Scheitert etwas,
wird alles Geschriebene entfernt und der Lauf mit einem Code `failed`:

| Code | Bedeutung |
|---|---|
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
Sicherung `restic backup` von Archiv und Begleitdatei (Host und Tag `herd`), dann
`restic forget --group-by host,tags --prune --keep-last=1
--keep-daily/--keep-weekly/--keep-monthly` mit denselben Zahlen über alle Stände des
Repositorys und am Ersten jedes Monats `restic check --read-data-subset=5%`. restic zählt
die Zeiträume überlappend (die 4 Wochen schließen die 7 Tage ein, die 6 Monate die
Wochen): offsite reicht deshalb **weniger weit zurück** als das Volume, mit den
Standardwerten 15 Stände bis rund 5 Monate statt 17 bis rund 6½ Monate. Wer offsite
länger braucht, setzt die Zahlen höher (sie gelten für beide). Ein noch nicht
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

## Aufbewahrung je Tabelle

Jede Tabelle hat eine Regel im Katalog `backend/app/core/retention.py`; ein Test
(`tests/test_retention.py::test_every_table_has_a_retention_rule`) schlägt fehl, sobald
eine neue Tabelle keine hat. Drei Arten:

- **Bleibt** (`Keep`, mit Begründung): Inhalte der Organisation (Seiten, Nachrichten,
  Tickets, Skills, Anhänge), Einstellungen (Verbindungen, Agenten, Aufgaben, Anbieter,
  Konnektoren, Server) und alles, was mit seinem Elternteil geht (Versionen, Erwähnungen,
  Reaktionen, Mitgliedschaften). Benachrichtigungen bleiben auch: „gelesen“ und
  „erledigt“ sind Zustände, gelöscht wird eine nur mit ihrer Nachricht, ihrem Gespräch,
  ihrem Vorschlag oder ihrem Konto (die Tabelle wächst also mit der Nutzung). Personen
  werden deaktiviert, nicht gelöscht; nur ein abgelehntes, nie aktives selbst
  registriertes Konto wird gelöscht ([`ANMELDUNG.md`](ANMELDUNG.md)). Nachweise bleiben ebenfalls: `audit_log`, `usage_record`, `run`/`run_event`
  (mit Rückfragen, Freigaben, Abbrüchen), `dm_inspection`, `backup_run` (eine Zeile je
  Sicherung). Sie zu löschen ist eine Entscheidung des Betreibers (Aufbewahrungspflichten,
  Datenschutz), nicht des Codes; wer kürzen will, löscht mit SQL in einem Wartungsfenster
  und sichert vorher.
- **Fälligkeits-Schleife** (`Upkeep`, mit Frist): `automation_event` (7 Tage nach seinem
  Termin), `automation_firing` und `mcp_call` (90 Tage), `storage_tombstone` (48 h, dann
  die Datei, wenn sie unbenutzt ist), und die abgelaufenen Zeilen: `user_session`
  (1 h nach Ende), `oauth_flow` und `oidc_flow` (bei Ablauf), `collab_grant` (1 h nach
  Ablauf), `rate_limit_hit` (60 s), `ai_rate_window` (1 h).
- **Räumt selbst auf** (`Cleans`): die Outbox (`event_outbox` 7 Tage nach der
  Zustellung, mit `event_delivery`; gescheiterte Ereignisse bleiben für den Betreiber,
  `herd_outbox_failed`) und `event_lane` (sobald der Handler das Ereignis hatte).

## Überwachung

Jeder Worker liest die Sicherungsläufe alle 10 s aus `backup_run` (ein kurzlebiger Job
lässt sich nicht abfragen) und meldet:

| Metrik | Bedeutung |
|---|---|
| `herd_backup_last_success_timestamp_seconds` | Ende der letzten gelungenen Sicherung (0: noch keine) |
| `herd_backup_last_failure_timestamp_seconds` | Ende der letzten misslungenen (`failed`, oder `interrupted` mit `backup.interrupted`) |
| `herd_backup_last_bytes` | Größe des letzten gelungenen Archivs |
| `herd_backup_offsite_last_success_timestamp_seconds` | letzte gelungene Sicherung, die das restic-Repository erreichte |
| `herd_backup_offsite_last_failure_timestamp_seconds` | letzte gelungene Sicherung, deren Offsite-Schritt scheiterte |
| `herd_backup_alert_after_seconds` | `HERD_BACKUP_ALERT_AFTER_HOURS` in Sekunden |

Alarme (`files/prometheus-rules.yaml` des Charts, `metrics.prometheusRule.enabled`;
geprüft mit `promtool test rules` und `scripts/check_alert_metrics.py`):

| Alarm | Wann | Stufe |
|---|---|---|
| `HerdBackupTooOld` | die letzte gelungene Sicherung ist älter als `HERD_BACKUP_ALERT_AFTER_HOURS` (`backup.alertAfterHours`, 26), 10 Minuten lang | critical |
| `HerdBackupFailing` | die letzte Sicherung scheiterte (jünger als die letzte gelungene); weg mit der nächsten gelungenen | warning |
| `HerdOffsiteBackupFailing` | die letzte gelungene Sicherung erreichte das restic-Repository nicht | warning |
| `HerdBackupNeverRan` | 26 Stunden lang keine gelungene Sicherung, seit ein Worker die Metrik meldet (Job fehlt, Zeitplan feuert nicht) | critical |

## Betrieb: Compose und Helm

**Compose** (`deploy/compose/compose.yml`, auch mit `compose.nodes.yml`): der Dienst
`backup` (dasselbe Image, `python -m app.ops backup schedule`) sichert nach
`HERD_BACKUP_SCHEDULE` in das Volume `backups` (`/backups`), liest die Anhänge
schreibgeschützt und öffnet keinen Port. `HERD_SECRET_KEY` kommt aus `ai.env` (nur für die
Schlüsselkennung im Archiv), Repository, Passwort und Speicherzugang für restic aus
`backup.env` (Vorlage `backup.env.example`). Von Hand:
`docker compose exec backup python -m app.ops backup run` (oder `list`, `verify`).
`/tmp` des Dienstes ist ein tmpfs (Arbeitsspeicher) mit 1 GiB Obergrenze: dort liegt nur
der Cache von restic, der Dump geht ins Volume `backups`.
`smoke.sh` sichert im Dienst, spielt das Archiv in eine zweite Datenbank ein und kopiert
eine Sicherung mit dem echten restic in ein Repository im Container.

**Helm**: ein CronJob `<release>-backup` (Standard an, `backup.enabled`) mit
`backup.schedule` (Zeitzone Etc/UTC), `concurrencyPolicy: Forbid`, `backoffLimit: 0`
(ein Fehlschlag wird nicht wiederholt, `HerdBackupFailing` meldet ihn) und höchstens 6
Stunden Laufzeit, auf einer eigenen PVC `<release>-backups` (bleibt beim Deinstallieren;
`backup.persistence.*`). Die Anhänge-PVC wird schreibgeschützt eingehängt: Legt das
Chart sie mit ReadWriteOnce an, setzt es eine Pod-Affinität des Job-Pods zum Knoten
eines API-Pods (dort ist der Claim eingehängt); ReadWriteOncePod lässt sich nicht teilen
und wird mit `backup.enabled` abgelehnt; ein eigener Claim (`persistence.existingClaim`)
sollte ReadWriteMany sein, sonst muss der Job anders auf den richtigen Knoten kommen. Offsite: `backup.offsite.existingSecret` nennt ein Secret mit
`HERD_BACKUP_OFFSITE_REPOSITORY`, `HERD_BACKUP_OFFSITE_PASSWORD` und den
Speicherzugangsdaten; es erreicht nur den Backup-Job, von `ai.existingSecret` bekommt er
allein `HERD_SECRET_KEY`. Mit `networkPolicy.enabled` darf der Job nur DNS, die Datenbank
und `backup.offsite.egress` erreichen. Der Worker bekommt `HERD_BACKUP_ALERT_AFTER_HOURS`
aus `backup.alertAfterHours`. `/tmp` des Job-Pods (emptyDir, nur der Cache von restic)
ist auf `backup.tmpSizeLimit` (2Gi) begrenzt; der Dump liegt während der Sicherung neben
dem Archiv auf der PVC `<release>-backups`, die also neben den behaltenen Archiven Platz
für einen Dump mehr braucht. Das Image bringt restic 0.19.1 mit, aus den Quellen
gebaut (Quellarchiv mit der Prüfsumme aus den `SHA256SUMS` der Veröffentlichung, Go
1.27.4, Module mit Sicherheitskorrekturen aus `deploy/restic/go.mod` und `go.sum`;
siehe `Dockerfile`), weil die veröffentlichten Binärdateien mit älterem Go gebaut sind.

## Einspielen in eine laufende Installation (Wartungsmodus)

Ersetzt den ganzen Stand einer **laufenden** Installation durch ein Archiv, ohne die App
anzuhalten. Mit den `HERD_*`-Einstellungen der Installation (Datenbank,
`HERD_DATA_DIR`, `HERD_SECRET_KEY`, `HERD_BACKUP_DIR`):

```bash
python -m app.ops restore check ARCHIV         # erwartet: restore.target_not_empty, sonst nichts
python -m app.ops restore apply ARCHIV --replace --confirm "<Name der Organisation>" [--without-secrets]
python -m app.ops maintenance status           # "off" oder "on restore since <Zeit>"
python -m app.ops maintenance off              # nur nach einem Abbruch (unten)
```

`--confirm` verlangt den Namen der Organisation der **laufenden** Installation, genau
(Groß- und Kleinschreibung zählen): ein Schutz gegen das Einspielen in die falsche
Installation. Es ist der Name aus `HERD_BOOTSTRAP_ORG_NAME` beim ersten Start (Standard
„Meine Organisation“); angemeldet zeigt ihn `/api/auth/me` im Browser (`org.name`). Ohne
`--confirm` endet der Befehl mit `restore.confirm_missing`.

**Was geschieht** (alles unter der Advisory-Sperre `herd.schema`, keine Migration und
keine zweite Wiederherstellung dazwischen):

1. die Prüfungen aus [`restore check`](#wiederherstellen-in-eine-leere-installation)
   außer „leer“, dazu der Name;
2. ein **Sicherheitsarchiv** des jetzigen Stands nach `HERD_BACKUP_DIR` (eine normale
   Sicherung mit Auslöser `pre_restore`, sie zählt für Aufbewahrung und Alarme wie jede
   andere); misslingt es, geht nichts weiter. Danach hält der Befehl die Sperre
   `herd.backup`: keine andere Sicherung liest die Datenbank, während sie getauscht wird;
3. **Wartungsmodus an** (Audit `maintenance.started`); 10 Sekunden Auslauf, in denen
   jeder Prozess davon erfährt (sofort über `NOTIFY herd_maintenance`, spätestens nach
   5 Sekunden) und laufende Anfragen enden;
4. die Dateien des Archivs, die noch nicht in der Ablage liegen, dann die Datenbank in
   **einer** Transaktion (`psql`): `DROP SCHEMA public CASCADE`, `CREATE SCHEMA public`,
   der Dump des Archivs (aus `pg_restore --file=-`, ohne Zwischendatei), der
   Wartungsmodus im eingespielten Stand, `COMMIT`. Das `COMMIT` geht erst hinaus, wenn
   `pg_restore` fehlerfrei durch ist; bei jedem Fehler wird `psql` beendet, bevor es ein
   `COMMIT` liest, und die Transaktion rollt zurück;
5. `alembic upgrade head` (ein älteres Archiv wird angehoben), dann wie bei der
   leeren Installation: alle Sitzungen, offenen Anmeldeabläufe und
   Live-Berechtigungen gelöscht, Audit `backup.restored` (mit `replaced`,
   `safety_archive` und `via: cli`); das Sicherheitsarchiv steht danach auch in der
   eingespielten Installation in `backup list`; Dateien, die nur der alte Stand
   brauchte, bekommen einen Grabstein und verschwinden nach 48 Stunden, wenn nichts
   sie wieder braucht;
6. **Wartungsmodus aus** (Audit `maintenance.ended`).

Die Ausgabe nennt Revisionen, Tabellen, Dateien und das Sicherheitsarchiv:
`replaced by <archiv>: revision … -> …, 70 tables, 3 files; safety archive herd-….tar`.
Die Dauer ist die einer Sicherung plus die eines Einspielens plus 10 Sekunden (Messung
mit 10.000 Seiten und 1 GiB Anhängen: Sicherung 10–11 s, Einspielen 8–9 s,
[`STECKBRIEF.md`](STECKBRIEF.md)).

**Was Personen merken:** Im Wartungsmodus antwortet die API auf alles mit 503
`maintenance.active` und `Retry-After: 30`, außer `GET /api/maintenance` (sagt, seit wann
und warum) und den Dateien der Oberfläche; `/health`, `/ready` und `/metrics` auf dem
internen Port bleiben erreichbar. Live-Verbindungen (`/api/stream`) enden und verbinden
sich neu (dann 503); die Live-Bearbeitung schließt mit 4503 und speichert nichts mehr
(was in den letzten Sekunden getippt wurde, gehört zum Stand, der ersetzt wird). Danach
ist jede Person abgemeldet und meldet sich neu an. Ein Zugang über `/mcp` antwortet
ebenfalls 503; Zugangstoken bleiben gültig, wenn das Archiv sie enthält.

**Was der Worker tut:** Die Schleifen pausieren (keine Ereignisse, keine Fälligkeiten,
keine Aufräumarbeiten); Agenten-Läufe, die gerade laufen, werden wie bei einem Stopp
abgebrochen und nach der Wartung aus ihrem Journal fortgesetzt, sofern das Archiv sie
enthält. Ein pausierter Worker bleibt `ready` (kein `HerdWorkerStalled`).

**Voraussetzungen:** `psql` und `pg_restore` im `PATH` (im Image enthalten); die
Datenbankrolle der App muss das Schema `public` löschen dürfen (Besitzerin der Datenbank
oder des Schemas; bei verwalteten Datenbanken prüfen); auf dem Sicherungs-Volume Platz
für ein weiteres Archiv. Eine Transaktion, die irgendwo offen hängt, hält das
`DROP SCHEMA` höchstens 60 Sekunden auf (`lock_timeout`), dann scheitert der Tausch.

Abgelehnt wird (am Ziel ändert sich nichts) mit den Codes der Prüfung und:

| Code | Bedeutung |
|---|---|
| `restore.confirm_missing` | `--replace` ohne `--confirm` |
| `restore.confirm_mismatch` | der Name stimmt nicht (oder die Datenbank hat keine Organisation: dann in eine leere Installation einspielen) |
| `restore.safety_backup_failed:<code>` | das Sicherheitsarchiv misslang, `<code>` aus der Tabelle der Sicherung oben (`backup.schema_behind`: erst migrieren) |
| `backup.already_running` | eine Sicherung begann gerade; noch einmal versuchen |

Scheitert der Tausch (`failed <code>`), ist der **alte Stand vollständig** da: die eben
geschriebenen Dateien sind entfernt, der Wartungsmodus ist aus, das Audit hat
`backup.restore_failed` (Archiv, Code). Das Sicherheitsarchiv bleibt `ok` in
`backup list`. Codes: `restore.swap_failed` (ein SQL-Fehler im Tausch, etwa fehlende
Rechte für `DROP SCHEMA` oder die Sperrfrist), `restore.pg_restore_failed`,
`restore.tool_missing`, `archive.member_checksum`, `restore.failed` (etwas anderes).

**Abbruch nach dem Tausch** (`failed restore.finish_failed`, selten: etwa die Migration
oder die Verbindung brach ab): Die Datenbank hat schon den Stand des Archivs, der
Wartungsmodus bleibt **an** (die App bedient niemanden mit halb fertigem Stand). Ursache
im Log beheben, die Datenbank migrieren, falls nötig (`HERD_ROLE=migrate`, im Chart der
Migrations-Job), und denselben Befehl noch einmal ausführen: Er nimmt ein neues
Sicherheitsarchiv und läuft ganz durch. `maintenance off` nur, wer bewusst ohne
erneutes Einspielen weitermacht (die Sitzungen aus dem Archiv gelten dann noch). Endet der
Befehl selbst mitten im Tausch (Prozess beendet), rollt die Datenbank zurück; der
Wartungsmodus bleibt an, bis `maintenance off` oder ein neuer Versuch ihn beendet.

Das Recht `backup.manage` (Sicherungen und Einspielen in der Verwaltung, M9b) hat nur die
Rolle `owner`, nicht `admin`: Ein Archiv enthält Direktnachrichten, die Admins nur über
die protokollierte Einsicht lesen. Die Kommandozeile handelt als `system` (`via=cli`).

### Im laufenden Betrieb mit Compose

Nicht in dieser Umgebung ausgeführt (kein Docker); die Befehle folgen `compose.yml`. Die
App läuft weiter; eingespielt wird aus einem Einmal-Container des App-Dienstes (der
Dienst `backup` hängt die Anhänge nur lesend ein):

```bash
docker compose exec backup python -m app.ops backup list   # das Archiv wählen
docker compose run --rm --no-deps -v backups:/backups --entrypoint "python -m app.ops" \
  app restore check /backups/<archiv>.tar          # erwartet: restore.target_not_empty
docker compose run --rm --no-deps -v backups:/backups --entrypoint "python -m app.ops" \
  app restore apply /backups/<archiv>.tar --replace --confirm "Meine Organisation"
```

Mit `compose.nodes.yml` genauso; alle Knoten gehen gemeinsam in den Wartungsmodus.

### Im laufenden Betrieb mit Kubernetes

Nicht in einem Cluster ausgeführt. Einen Job aus dem CronJob ableiten wie in Schritt 4
[unten](#ablauf-in-kubernetes), aber mit `command` `["/usr/bin/tini", "--", "python",
"-m", "app.ops", "restore", "apply", "/backups/<archiv>.tar", "--replace", "--confirm",
"<Name der Organisation>"]`; beim Volume und beim Einhängen `data` jedes
`readOnly: true` entfernen, den `affinity`-Block **behalten** (die API-Pods laufen, und
eine ReadWriteOnce-PVC der Anhänge verlangt denselben Knoten). Die App nicht anhalten
und den CronJob nicht aussetzen (das Einspielen hält die Sperre `herd.backup`; ein
CronJob, der gerade dann startet, endet mit `backup.already_running`).

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
Eine laufende Installation ersetzt `--replace`
([unten](#einspielen-in-eine-laufende-installation-wartungsmodus)).

Abgelehnt wird mit einem Code; am Ziel ändert sich dann nichts:

| Code | Bedeutung |
|---|---|
| `archive.*` | das Archiv selbst passt nicht (siehe `verify` oben) |
| `restore.archive_newer` | das Archiv hat eine Alembic-Revision, die dieser Code nicht kennt (neuere Version): erst die passende oder neuere App-Version einsetzen |
| `restore.target_not_empty` | die Zieldatenbank hat schon Tabellen |
| `restore.backup_running` | am Ziel läuft gerade eine Sicherung (sie hält die Sperre `herd.backup`): sie stoppen bzw. den CronJob aussetzen, dann erneut |
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
ein startender App-Prozess in Rolle `all` wartet also, statt dazwischen zu migrieren)
und der Sicherungssperre `herd.backup` (bis zum Ende startet keine Sicherung, eine
gestartete endet mit `backup.already_running`, und die Fälligkeits-Schleife markiert
nichts):

1. die Prüfungen oben;
2. die Dateien des Archivs in die Ablage (je Datei beim Schreiben gegen das Manifest
   geprüft; schon vorhandene mit gleichem Inhalt bleiben);
3. die Datenbank mit `pg_restore --no-owner --no-privileges --single-transaction
   --exit-on-error` (ganz oder gar nicht; scheitert es, werden die eben geschriebenen
   Dateien wieder entfernt); der Dump geht aus dem Archiv direkt in `pg_restore`
   (Standardeingabe), ohne Zwischendatei;
4. `alembic upgrade head`, wenn das Archiv eine ältere bekannte Revision hat;
5. in einer Transaktion: alle Sitzungen und offenen OAuth-Abläufe gelöscht (nach einer
   Wiederherstellung ist jede Anmeldung ungültig), Sicherungsläufe im Zustand `running`
   werden `interrupted` (`backup.in_restored_archive`, kein Fehler für den Alarm), ein Audit-Eintrag `backup.restored` (`system`, Archivname,
   Revisionen).

Danach die App normal starten. `restore apply` gibt Revisionen, Tabellen und Dateien
aus; scheitert ein Schritt, endet es mit `failed <code>` (`restore.pg_restore_failed`,
`restore.tool_missing`, `archive.member_checksum`; hat sich das Archiv nach den
Prüfungen geändert: `archive.truncated`, `archive.member_missing`,
`archive.unreadable`). Die Datenbank bleibt dann leer, eben geschriebene Dateien werden
wieder entfernt.

Was Schritt 5 leert, steht in `CLEARED_AFTER_RESTORE` (`backend/app/ops/restore_after.py`):
`collab_grant`, `oidc_flow`, `user_session`, `oauth_flow`. Jede Person meldet sich also
neu an, offene Anmeldungen bei einem OIDC-Anbieter oder OAuth-Server beginnen neu, und
offene Live-Bearbeitungen verbinden sich neu.

### Ohne den Schlüssel

Das Archiv hat `enc:`-Werte in diesen Spalten (das Manifest zählt sie je Spalte):
`ai_connection.secret_ref` (KI-Verbindungen), `connector.secret_ref` und
`connector.refresh_token_ref` (Konnektoren der MCP-Server), `oauth_client.client_secret_ref`
(OAuth-Clients), `oidc_provider.client_secret_ref` (Anmeldeanbieter). Ohne passenden
`HERD_SECRET_KEY` lehnt `restore check` mit `restore.secret_key_mismatch` bzw.
`restore.secret_key_missing` ab und listet
`restore.secrets_unreadable:<tabelle.spalte>=<Anzahl>`. Mit `--without-secrets` spielt
`restore apply` trotzdem ein; dann gilt:

- alle übrigen Daten (Seiten, Nachrichten, Tickets, Anhänge, Personen, Rechte) sind
  vollständig da, die Anmeldung mit Passwort geht;
- KI-Verbindungen, Konnektoren, OAuth-Clients und Anmeldeanbieter mit gespeichertem
  Secret melden „Geheimnis nicht verfügbar“ (`SecretUnavailable`): Läufe der Agenten
  über diese Verbindungen scheitern, die Anmeldung über diese Anbieter geht nicht;
- ein Admin trägt jedes Secret in der Verwaltung neu ein (KI-Verbindung, Konnektor,
  OAuth-Client, Anbieter unter Verwaltung → Anmeldung); persönliche Konnektoren
  verbinden die Personen neu;
- `env:`-Verweise sind davon nicht betroffen, sie brauchen nur die Variable am Ziel
  (`restore.env_missing:<NAME>` warnt, wenn sie fehlt).

Ein neuer Schlüssel am Ziel ist dann richtig: `HERD_SECRET_KEY` neu setzen, die Secrets
neu eintragen; `HERD_SECRET_KEY_PREVIOUS` braucht es nicht.

### Ablauf in Compose

Die Befehle folgen `compose.yml`; dieselben Schritte für den Hostinger-Stack (mit dessen
Volume- und Projektnamen) stehen in [`HOSTINGER.md`](HOSTINGER.md#wiederherstellen) und
wurden dort mit Docker durchgespielt. Im Verzeichnis `deploy/compose`, mit derselben
`.env` und `ai.env` (gleicher `HERD_SECRET_KEY`) wie die gesicherte Installation.

Das Sicherungs-Volume heißt **`to-herd-cats-ai_backups`** (Projektname `to-herd-cats-ai`
aus `compose.yml`, mit `-p <name>` entsprechend `<name>_backups`; `docker volume ls`
zeigt es). Bei `docker compose run -v` muss genau dieser Name vor dem Doppelpunkt
stehen: Ein bloßes `backups` hängt ein neues, leeres Volume ein, und die Prüfung meldet
`archive.format_unknown`.

Erst prüfen, dann sichern, erst danach etwas löschen: Lehnt die Prüfung ab
(`restore.secret_key_mismatch`, `restore.tools_too_old`, `archive.*`), ist noch nichts
verloren.

```bash
docker compose exec backup python -m app.ops backup list   # das Archiv wählen (Name)
docker compose exec backup python -m app.ops backup verify /backups/<archiv>.tar
# Prüfen, solange die alte Datenbank noch da ist: ein Einmal-Container des App-Dienstes
# mit dem Sicherungs-Volume. Erwartet wird genau ein Problem, restore.target_not_empty
# (die Datenbank ist ja noch voll); jedes andere zuerst beheben.
docker compose run --rm --no-deps -v to-herd-cats-ai_backups:/backups \
  --entrypoint "python -m app.ops" app restore check /backups/<archiv>.tar
# Ein Weg zurück: der jetzige Stand als eigene Sicherung (bleibt im Volume)
docker compose exec backup python -m app.ops backup run
docker compose stop app backup             # mit compose.nodes.yml: api-a api-b worker collab backup
# Datenbank leeren (das Volume bleibt; nur die Datenbank herd wird neu angelegt)
docker compose exec db psql -U herd -d postgres \
  -c 'DROP DATABASE herd WITH (FORCE)' -c 'CREATE DATABASE herd OWNER herd'
# noch einmal prüfen (jetzt: ok), dann einspielen
docker compose run --rm --no-deps -v to-herd-cats-ai_backups:/backups \
  --entrypoint "python -m app.ops" app restore check /backups/<archiv>.tar
docker compose run --rm --no-deps -v to-herd-cats-ai_backups:/backups \
  --entrypoint "python -m app.ops" app restore apply /backups/<archiv>.tar
docker compose up -d --wait                # die App startet auf dem eingespielten Stand
```

Scheitert das Einspielen trotzdem (`failed <code>`), bleibt die Datenbank leer
(`pg_restore` läuft in einer Transaktion): mit der eben gemachten Sicherung zurück auf
den alten Stand (dieselben Schritte ab „Datenbank leeren“, mit ihrem Archiv).

Der App-Dienst hat die Anhänge (`app-data`) beschreibbar eingehängt und liest
`HERD_SECRET_KEY` aus `ai.env`; der Dienst `backup` hängt sie nur lesend ein und taugt
deshalb nicht zum Einspielen. Kommt das Archiv aus der Offsite-Kopie, zuerst mit restic
zurückholen (`restic -r <Repository> restore latest --tag herd --target /tmp/r`, Passwort
aus `RESTIC_PASSWORD`/`--password-file`) und die `.tar`-Datei samt `.manifest.json` ins
Volume `to-herd-cats-ai_backups` kopieren (`docker compose cp <datei> backup:/backups/`).

Auf eine **neue Maschine**: `.env`, `ai.env` (Schlüssel!) und `backup.env` mitnehmen,
`docker compose up -d db` (nur die Datenbank, sie ist dann leer), das Archiv samt
`.manifest.json` ins Volume `to-herd-cats-ai_backups` kopieren, dann ab „prüfen, dann
einspielen“ wie oben. Nicht `docker compose up` vor dem Einspielen: der App-Dienst
(Rolle `all`) migriert beim Start, die Datenbank ist dann nicht mehr leer
(`restore.target_not_empty`).

### Ablauf in Kubernetes

Nicht in einem Cluster ausgeführt; die Namen folgen dem Chart (`<f>` ist der
vollständige Name, etwa `herd-to-herd-cats-ai`). Mit dem Release, dessen Image zur
Revision des Archivs passt oder neuer ist:

1. Prüfen und sichern, solange die App noch läuft (der Job-Pod braucht wegen der
   Pod-Affinität einen laufenden API-Pod): einen Job aus dem CronJob mit `command`
   `["/usr/bin/tini", "--", "python", "-m", "app.ops", "restore", "check",
   "/backups/<archiv>.tar"]` ableiten (wie in Schritt 4, aber Affinität und
   `readOnly` bleiben) und sein Log lesen: erwartet wird genau
   `restore.target_not_empty`, jedes andere Problem zuerst beheben. Dann den jetzigen
   Stand als Weg zurück sichern und abwarten:
   ```bash
   kubectl create job <f>-backup-before-restore --from=cronjob/<f>-backup
   kubectl wait --for=condition=complete --timeout=6h job/<f>-backup-before-restore
   ```
2. Die App anhalten (mit Autoscaler genügt `scale` auch: ein HPA skaliert nicht von 0)
   und die nächtliche Sicherung aussetzen:
   ```bash
   kubectl scale deployment/<f>-api deployment/<f>-worker deployment/<f>-collab --replicas=0
   kubectl patch cronjob/<f>-backup -p '{"spec":{"suspend":true}}'
   ```
3. Die Datenbank leeren. Mitgeliefertes PostgreSQL:
   `kubectl exec <f>-postgresql-0 -- psql -U herd -d postgres -c 'DROP DATABASE herd WITH (FORCE)' -c 'CREATE DATABASE herd'`;
   eine externe Datenbank leert ihr Betrieb (neu anlegen, Besitzer die Rolle aus
   `database.url`).
4. Einen Job aus dem CronJob ableiten, der einspielt statt sichert:
   ```bash
   kubectl create job <f>-restore --from=cronjob/<f>-backup --dry-run=client -o yaml > restore.yaml
   ```
   In `restore.yaml`: `command` auf `["/usr/bin/tini", "--", "python", "-m", "app.ops",
   "restore", "apply", "/backups/<archiv>.tar"]` setzen (zuerst gern mit `"check"`),
   beim Volume und beim Einhängen `data` jedes `readOnly: true` entfernen (das Einspielen
   schreibt die Anhänge) und einen `affinity`-Block löschen (er bindet den Job an einen
   API-Pod, und es läuft keiner). `HERD_SECRET_KEY` bekommt der Job wie der CronJob aus
   `ai.existingSecret`; ohne passenden Schlüssel `"--without-secrets"` anhängen (oben).
   Dann `kubectl apply -f restore.yaml` und `kubectl logs -f job/<f>-restore`.
5. Die App wieder starten: `helm upgrade` mit denselben Werten (setzt die Replikas und
   lässt den Migrations-Job laufen; die Datenbank steht nach dem Einspielen auf dem
   Head) oder `kubectl scale` auf die vorigen Zahlen; den CronJob mit
   `{"spec":{"suspend":false}}` wieder einschalten und `kubectl delete job <f>-restore`.

Das Archiv liegt auf der PVC `<f>-backups`. Eines von außen (Offsite, andere
Installation) kommt mit einem Hilfs-Pod, der diese PVC einhängt, und `kubectl cp` dorthin
(Archiv und `.manifest.json`).

## Ergänzung: Export je Bereich

Unabhängig von der Sicherung exportiert jede Person mit Leserecht einen Bereich als
Markdown-ZIP (Kopf des Bereichs → „Import/Export“, [`WIKI.md`](WIKI.md)): alle Seiten
als `.md` mit Anhängen, wieder importierbar in einen Bereich derselben oder einer
anderen Installation. Das ist kein Ersatz für die Sicherung: Nachrichten, Tickets,
Versionen, Rechte, Agenten und Einstellungen fehlen darin. Es taugt für einzelne
Bereiche, für die Weitergabe von Wissen und als lesbare Kopie ohne die App.

### Probe

`deploy/scripts/restore-rehearsal.sh` spielt den ganzen Weg durch: Installation A mit
Demodaten und Anhang, Sicherung während A läuft, Einspielen in eine leere Datenbank B,
Vergleich aller Tabellen (`scripts/compare_databases.py`: Zeilen und Prüfsumme des
Inhalts), Anmeldung an B, das alte Cookie von A gilt nicht, der Anhang hat dieselbe
Prüfsumme; dann wird das laufende B (mit einer neuen Seite) durch dasselbe Archiv
ersetzt (`--replace`): B antwortet dazwischen 503, danach ist Bs Sitzung ungültig, die
neue Seite weg, der Anhang da und das Sicherheitsarchiv gelistet; zuletzt wird ein
manipuliertes Archiv abgelehnt. Ohne Docker, gegen einen
PostgreSQL-Server über `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD` (Standard
`localhost:5433`, `herd`); Ausgabe der letzten Probe in
[`demo/m9.md`](demo/m9.md). In der CI läuft sie als Job `restore` gegen PostgreSQL 17.
