# to-herd-cats-ai: nächste Freigabe (noch nicht veröffentlicht)

Diese Notiz sammelt, was nach dem Stand von [`RELEASE-1.0.0.md`](RELEASE-1.0.0.md)
(Code-Stand `b8f7ce4`, Alembic-Revision `9e4b6d2f8a17`) dazugekommen ist: M9b Tasks 12
bis 16 und 18, die Nacharbeiten an der Hostinger-Installation (Task 19) und die
Fix-Wellen nach den Reviews. Sie richtet sich an alle, die einen Build von 1.0.0
betreiben und auf den neuen Stand gehen.

**Noch keine Freigabe.** Der Tag `v1.0.0` ist nie veröffentlicht worden, und Jan hat
entschieden, dass der Freigabe-Tag erst kommt, wenn die ganze App fertig ist. Bis
dahin gilt:

- `pyproject.toml`, Chart-`version` und `appVersion` stehen weiter auf **1.0.0**;
  `backend/alembic/RELEASED` nennt weiter `9e4b6d2f8a17`. Erst beim Tag wird
  `RELEASED` auf den dann aktuellen Head gesetzt (`release.yml` prüft das).
- Es gibt noch **kein veröffentlichtes Image** unter `ghcr.io/<owner>/to-herd-cats-ai`
  und kein Chart unter `oci://ghcr.io/<owner>/charts`. Die Hostinger-Datei
  (`docker-compose.yml`, `HERD_IMAGE_TAG=1.0`) kann deshalb erst nach der ersten
  veröffentlichten Freigabe ein Image laden; bis dahin baut man das Image selbst
  (`docker build`, README „Schnellstart mit Docker Compose“).
- Auch `RELEASE-1.0.0.md` ist nicht endgültig; beide Notizen werden zur Freigabe
  zusammengeführt.
- Auf dem Arbeitszweig liegt außerdem der Anfang von M10 (Kalender, Tasks 1 und 2,
  [`KALENDER.md`](KALENDER.md)). Er ist hier nur bei den Migrationen erwähnt und wird
  beschrieben, wenn M10 fertig ist.

## Was neu ist

- **Wartungsmodus und Einspielen in eine laufende Installation (Task 12):**
  `python -m app.ops restore apply ARCHIV --replace --confirm "<Name der Organisation>"`
  sichert zuerst den jetzigen Stand (Sicherheitsarchiv, Auslöser `pre_restore`),
  schaltet die Wartung ein (API und `/mcp` antworten 503 `maintenance.active` mit
  `Retry-After: 30`, der Worker pausiert, Live-Bearbeitung schließt mit 4503), tauscht
  die Datenbank in einer Transaktion, migriert und meldet alle ab. Scheitert der Tausch,
  bleibt der alte Stand ganz. `python -m app.ops maintenance status|off` ist der Ausweg
  nach einem Abbruch ([`SICHERUNG.md`](SICHERUNG.md#einspielen-in-eine-laufende-installation-wartungsmodus)).
- **Sicherung in der Verwaltung (Task 13):** Verwaltung → Sicherung, nur für Inhaber
  (`backup.manage`): Läufe live, „Jetzt sichern“ (der Worker sichert), Archive
  herunter- und hochladen (bis `HERD_BACKUP_UPLOAD_MAX_BYTES`), „Prüfen“ gegen die
  Installation und „Einspielen …“ mit Bestätigung durch den Namen der Organisation;
  danach zeigt jede offene Seite die Wartungsseite und dann die Anmeldung
  ([`SICHERUNG.md`](SICHERUNG.md#in-der-verwaltung)).
- **Anhänge in S3 (Task 14):** `HERD_STORAGE=s3` mit eigenem S3-Client (SigV4, kein
  SDK, durch die Egress-Prüfung), Sicherung und Wiederherstellung über den Speicher,
  `python -m app.ops storage copy --to s3|local` und `storage check`; Compose
  `compose.s3.yml` (SeaweedFS), Chart `s3.*` ([`SICHERUNG.md`](SICHERUNG.md#anhänge-in-s3)).
- **Mehrere Collab-Instanzen (Task 15):** jede Seite in PostgreSQL an genau eine
  Instanz gebunden (`collab_instance`, `collab_page_owner` mit `epoch`), ohne Redis;
  SIGTERM speichert, gibt frei und schickt die Browser auf eine andere Instanz. Chart
  `collab.replicas` (ab 2 mit RollingUpdate und PDB), Compose `compose.nodes.yml` mit
  `collab-a` und `collab-b` ([`WIKI.md`](WIKI.md#mehrere-collab-instanzen-seit-m9b)).
- **Zweiter Faktor mit TOTP (Task 16):** freiwillig für jedes Konto mit Passwort, im
  Profil mit QR-Code und zehn Wiederherstellungscodes; Anmeldung in zwei Schritten (auch
  nach OIDC), Zurücksetzen durch Admins, ein Code beim Anlegen von Zugangstoken
  ([`ANMELDUNG.md`](ANMELDUNG.md#zweiter-faktor-totp)).
- **ASVS-Lücken J7 bis J14 (Task 18):** Inaktivitätsgrenze der Sitzung, eigene
  Sitzungen im Profil („Angemeldete Geräte“), erneute Anmeldung vor dem Verknüpfen
  eines Anbieters, Schreibgrenze je Person und Minute, optionaler Virenscan (clamd),
  TLS zur Datenbank, wechselbares internes Token, Rückruf je OAuth-App mit Prüfung von
  `iss`, optional getrennte Datenbankrollen. ASVS 5.0 L2 jetzt 196 erfüllt, 53 nicht
  anwendbar, 4 Lücken als dokumentierte Abweichungen ([`SICHERHEIT.md`](SICHERHEIT.md)).
- **Aus den Reviews (Fix-Wellen):** Das Einspielen nimmt aus einem Archiv nur, was zu
  unserem Schema gehört (`archive.dump_foreign`), nutzt den `\restrict`-Schutz von
  `pg_restore`/`psql` und erkennt einen gebrochenen Tausch (`restore.swap_broken`,
  `restore.swap_unknown`); zwei gleichzeitige Anfragen „Jetzt sichern“ oder
  „Einspielen“ starten nur eine (409 `backup.busy`); ein startender Prozess gilt bis zu
  seinem ersten Lesen als in Wartung; die TOTP-Sperre (unten); Collab misst die
  Lebendigkeit an der Uhr der Datenbank; ein Tab ohne Eingabe hält die Sitzung nicht
  mehr am Leben; die Schreibgrenze ist je Route entschieden, mit einem Test über alle
  schreibenden Routen; Skill-Importe werden mitgescannt; die Laufzeitrolle darf
  `alembic_version` nur lesen; der Beweis vor dem Verknüpfen über einen Anbieter
  verlangt eine frische Anmeldung (`prompt=login`, `max_age=600`, `auth_time`).
- **Hostinger-Stack:** `app` hängt jetzt auch das Volume `backups` ein (für
  Verwaltung → Sicherung) und kennt `HERD_BACKUP_UPLOAD_MAX_BYTES`
  ([`HOSTINGER.md`](HOSTINGER.md)).

## Einstellungen

Neu (alle optional, mit Standard; in beiden Compose-Dateien und im Chart, soweit nicht
anders gesagt):

| Einstellung | Standard | Wofür | Chart |
|---|---|---|---|
| `HERD_SESSION_IDLE_HOURS` | `24` (`0` = aus) | Sitzung endet nach so vielen Stunden ohne Nutzung | `api.sessionIdleHours` |
| `HERD_WRITE_RATE_PER_MINUTE` | `120` | Schreibaktionen je Person bzw. Agent und Minute, darüber 429 `rate.limited` | `writeLimit.perMinute` |
| `HERD_UPLOAD_RATE_PER_MINUTE` | `30` | Uploads (Anhänge, Importe) je Person und Minute | `writeLimit.uploadsPerMinute` |
| `HERD_CLAMAV_ADDRESS` | leer (aus) | `host:port` eines clamd; dann werden Anhänge und Importe vorher gescannt (fail closed) | `virusScan.clamavAddress`, `virusScan.egress` |
| `HERD_DATABASE_SSLMODE` | leer | `disable` … `verify-full`, gewinnt über `sslmode` in der URL; gilt für die App, LISTEN und die pg-Werkzeuge | `database.sslMode` |
| `HERD_DATABASE_SSLROOTCERT` | leer | CA-Datei für `verify-ca`/`verify-full` (ohne: bei `verify-full` die CAs des Systems; `verify-ca` ohne sie ist ein Startfehler) | `database.caSecret` |
| `HERD_INTERNAL_TOKEN_PREVIOUS` (`_FILE`) | leer | das alte interne Token während eines Wechsels (nur die API) | Schlüssel `previous` im Token-Secret |
| `HERD_MIGRATE_DATABASE_URL`, `HERD_MIGRATE_DATABASE_PASSWORD` (`_FILE`) | leer | Migrationsrolle (besitzt das Schema; Migration, `python -m app.ops`) | `database.migrate.url`, `database.migrate.existingSecret` |
| `HERD_DATABASE_RUNTIME_ROLE` | leer | Laufzeitrolle, bekommt nach jeder Migration die Datenrechte; Pflicht zusammen mit `HERD_MIGRATE_DATABASE_URL` | `database.migrate.runtimeRole` |
| `HERD_STORAGE` | `local` | `local` oder `s3` | `s3.enabled` |
| `HERD_S3_ENDPOINT`, `HERD_S3_REGION` (`us-east-1`), `HERD_S3_BUCKET`, `HERD_S3_PREFIX`, `HERD_S3_ACCESS_KEY_ID`, `HERD_S3_SECRET_ACCESS_KEY` (`_FILE`) | – | der S3-Speicher | `s3.endpoint`, `s3.region`, `s3.bucket`, `s3.prefix`, `s3.existingSecret` |
| `HERD_COLLAB_ADVERTISE_URL` | – | Adresse, unter der die API einen Collab-Prozess erreicht (`ws://host:port`); **Pflicht für jeden Collab-Prozess**, in Rolle `all` und im Chart gesetzt | aus der Pod-IP |
| `HERD_BACKUP_UPLOAD_MAX_BYTES` | `2147483648` | größtes Archiv, das ein Inhaber hochlädt (nur API) | `backup.uploadMaxBytes` |

Der Hostinger-Stack reicht von diesen nur `HERD_BACKUP_UPLOAD_MAX_BYTES` durch; dort
gelten für die übrigen die Standards ([`HOSTINGER.md`](HOSTINGER.md#grenzen)).

**Entfernt: `HERD_COLLAB_URL`.** Die API wählt die Collab-Instanz jetzt je Seite aus
den angemeldeten Instanzen; die Einstellung hat keinen Leser mehr und wird ignoriert.
Wer Collab-Prozesse selbst startet (eigenes Compose, eigene Manifeste), setzt bei
jedem `HERD_COLLAB_ADVERTISE_URL`; ohne sie endet der Prozess mit Exit-Status 2. Meldet
sich keine Instanz an, schließt das Relay mit 4502 `collab.unavailable`.

## Hinweise zum Update

Vorher sichern (README, „Update einer Installation“), dann:

- **Migrationen:** zehn neue Revisionen nach `9e4b6d2f8a17`, alle erweiternd (neue
  Tabellen, neue Spalten mit Standard): `a3c5e7f9b2d4` Wartung, `c4d8e1f7a2b9` TOTP,
  `daa60bc7c565` Collab-Instanzen, `e1f4a7c2b9d3`, `f2a5b8c3d6e9`, `a6c9d2e5f8b1`
  Sitzungen (letzte Nutzung, Gerät und Anmeldezeit, erneute Anmeldung), `b7d0e3f6a9c2`
  Aussteller der OAuth-Apps, `e4b6c8d0f2a3` TOTP-Sperre, `c8e1f4a7b0d3` frische
  Anbieter-Anmeldung, `b1c4e7a90d23` Kalender (M10). Eine einzige ersetzt eine
  Bedingung: `e4b6c8d0f2a3` erweitert die erlaubten Gründe einer Benachrichtigung um
  `totp_locked` (`contract_of` `7c2e9a4f1b86`; der alte Code schreibt weiter nur
  erlaubte Werte). Ein 1.0.0-Prozess läuft also gegen die neue Datenbank weiter, bis er
  ersetzt ist (`check_migrations.py` mit `RELEASED=9e4b6d2f8a17`). Nicht auf 1.0.0
  zurückgehen, sobald jemand TOTP eingeschaltet hat: 1.0.0 kennt die TOTP-Tabellen
  nicht und meldet diese Personen nur mit dem Passwort an.
- **Kürzere Sitzungen.** Eine Sitzung endet jetzt auch nach 24 Stunden ohne Nutzung
  (vorher nur nach 7 Tagen). Wer das nicht will: `HERD_SESSION_IDLE_HOURS=0`.
- **Schreibgrenze.** Mehr als 120 Schreibaktionen einer Person in einer Minute
  (30 Uploads) beantwortet die API mit 429 `rate.limited` und `Retry-After`. Eigene
  Skripte, die in Massen schreiben, warten den `Retry-After` ab (wie `demo_api` und
  `loadsetup`). Agenten und `/mcp` zählen wie Personen.
- **Anmeldung mit 202.** Für eine Person mit TOTP antwortet `POST /api/auth/login` mit
  202 `{second_factor: "totp"}` und öffnet noch keine Sitzung; der zweite Schritt ist
  `POST /api/auth/login/second-factor`. Skripte, die sich als Person anmelden, nehmen
  ein Konto ohne TOTP oder ein Zugangstoken.
- **TOTP-Sperre.** 10 falsche Codes innerhalb von 24 Stunden sperren den zweiten
  Faktor der Person für eine Stunde (429 `auth.second_factor_locked`, auch für einen
  richtigen Code; Audit `user.totp_locked`, Hinweis in der Aktivität der Person). Ein
  Admin hebt die Sperre mit „Zwei-Faktor zurücksetzen“ auf.
- **OAuth-Apps: neue Rückrufadresse eintragen.** Jede OAuth-App (Konnektoren, M8) hat
  jetzt ihre eigene Rückrufadresse `<HERD_PUBLIC_URL>/api/ai/oauth/<id>/callback`; ihre
  Karte in der Verwaltung zeigt sie (`callback_url`). Sie muss beim Anbieter (GitHub,
  GitLab …) eingetragen werden. Die alte gemeinsame Adresse `/api/ai/oauth/callback`
  beendet nur noch Abläufe, die mit ihr begonnen haben; neue Verbindungen scheitern,
  bis die neue Adresse eingetragen ist. Apps, die vor dem Update angelegt wurden, haben
  **keinen Aussteller** (`issuer`): Ein gesendetes `iss` wird dann nicht verglichen,
  bis ein Admin die App bearbeitet und den Aussteller einträgt (die Erkennung über
  Discovery schlägt ihn vor) ([`MCP.md`](MCP.md)).
- **Verknüpfen eines Anbieters** verlangt jetzt das Passwort oder eine frische
  Anmeldung über einen schon verknüpften Anbieter (403 `auth.reauth_required` sonst).
- **Eigene Collab-Prozesse:** `HERD_COLLAB_URL` entfernen, `HERD_COLLAB_ADVERTISE_URL`
  setzen (oben). Rolle `all`, Compose und das Chart erledigen das selbst. Während des
  Rollouts bedient die API einen Collab-Prozess von 1.0.0 nur, solange keine neue
  Instanz die Seite besitzt; Browser sehen kurz „Getrennt – neuer Versuch …“.
- **Sicherung in der Verwaltung braucht das Sicherungsverzeichnis in API und Worker.**
  Compose und der Hostinger-Stack hängen das Volume `backups` jetzt ein. Im Chart nur,
  wenn sich die PVC teilen lässt (`backup.persistence.accessModes: [ReadWriteMany]`
  oder `backup.persistence.existingClaim`); die ReadWriteOnce-PVC aus 1.0 bleibt dem
  CronJob, die Seite zeigt dann keine Archive und „Jetzt sichern“ endet mit
  `backup.io` (Umstellen: [`SICHERUNG.md`](SICHERUNG.md#in-der-verwaltung)). Ein Proxy
  vor der App muss Uploads bis `HERD_BACKUP_UPLOAD_MAX_BYTES` durchlassen.
- **Werkzeuge für das Einspielen im Betrieb:** `pg_restore` und `psql` mindestens
  **16.10 bzw. 17.6** (18 ab .0), sonst lehnt `--replace` mit `restore.tools_too_old`
  ab (erst diese Versionen kennen `\restrict`). Das Image bringt `postgresql-client-17`
  aus Debian mit; prüfen muss das nur, wer mit eigenen Werkzeugen einspielt
  (Entwicklungsrechner, eigenes Image). Die Datenbankrolle, die einspielt, muss das
  Schema `public` löschen dürfen.
- **Getrennte Datenbankrollen (optional):** Mit `HERD_MIGRATE_DATABASE_URL` und
  `HERD_DATABASE_RUNTIME_ROLE` lehnt die Verwaltung das Einspielen ab
  (`restore.not_schema_owner`): Die App hat dann nur die Laufzeitrolle. Eingespielt
  wird mit der Migrationsrolle auf der Kommandozeile (Backup-Dienst bzw. ‑Job);
  „Jetzt sichern“ geht weiter ([`SICHERUNG.md`](SICHERUNG.md#getrennte-datenbankrollen-seit-m9b-optional)).
- **Virenscan:** Mit `HERD_CLAMAV_ADDRESS` werden Uploads abgelehnt, solange clamd
  nicht antwortet (503 `attachment.scan_unavailable`); ein Fund ist 422
  `attachment.rejected_by_scan`. Hochgeladene Sicherungsarchive werden nicht gescannt.
- **Internes Token wechseln** geht jetzt ohne Ausfall über
  `HERD_INTERNAL_TOKEN_PREVIOUS` ([`WIKI.md`](WIKI.md#internes-token-wechseln)).
- **Archive aus 1.0.0** lassen sich einspielen, auch in eine laufende Installation;
  die Migration hebt sie an.

## Bekannte Grenzen

- Noch nicht enthalten aus M5: Embeddings, hybride Suche, Docling (M5 Tasks 8 bis 11).
- Nicht ausgeführt in dieser Umgebung (kein Docker, kein Cluster): `smoke.sh` mit
  `SMOKE_NODES=1` und `SMOKE_S3=1`, die Abläufe zum Einspielen in Compose und
  Kubernetes, Collab-Instanzen als eigene Pods, getrennte Rollen in einem echten
  Deployment. Diese Prüfungen stehen in der CI.
- Hochgeladene Archive löscht die Oberfläche nicht, und die Aufbewahrung räumt sie
  nicht auf (nur im Verzeichnis löschen).
- Mit mehreren API-Pods läuft „Einspielen“ in dem Pod, der die Anfrage annahm; wird er
  vor der Wartung beendet, ist der Versuch verloren (nichts halb getan, noch einmal
  starten).
- Eine Collab-Adresse aus einer IPv6-Pod-IP bildet das Chart nicht (eckige Klammern).
- Die vier übrigen ASVS-Lücken sind dokumentierte Abweichungen: V5.4.3 ohne
  eingestellten Scanner, V6.3.3 (TOTP ist freiwillig, J3), V12.3.3 und V12.3.4 (TLS
  zwischen API und Collab-Prozess; Mesh mit mTLS oder NetworkPolicy als
  Betriebsvoraussetzung).
- Gemessen und nicht gemessen: [`STECKBRIEF.md`](STECKBRIEF.md).
