# Sicherung und Wiederherstellung

Stand: M9 Task 1 (Archiv und Sicherung über die Kommandozeile). Wiederherstellung,
Zeitplan, Aufbewahrung und Offsite folgen in den nächsten Aufgaben von M9.

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
