# M9 Produktion — Umsetzungsplan

> **Für ausführende Agenten:** Arbeite nach den Superpowers-Skills (subagent-driven-development bzw. executing-plans, TDD, verification-before-completion). Jede Aufgabe: fehlschlagender Test zuerst → kleinste Umsetzung → Tests grün → ruff/mypy sauber → Doku, wenn sich Verhalten ändert → Commit. `CLAUDE.md` gilt ohne Ausnahme. Jede Aufgabe läuft in einem eigenen Worktree mit eigener Testdatenbank (`createdb herd_m9_<task>`, `HERD_TEST_DATABASE_URL`).

**Ziel:** Das System wird betriebsfest: Sicherung und Wiederherstellung des ganzen Datenstands (Kommandozeile, Zeitplan, Offsite, Verwaltung), Anmeldung über OIDC mit Google als fertigem Anbieter und optionaler Selbstregistrierung, ein vollständiges Helm-Chart mit HPA und Alarmen, gehärtete Live-Bearbeitung (Tokens statt Cookie, mehrere Collab-Instanzen), S3 für Anhänge, Lasttest, gemessene Ressourcen und eine Sicherheitsprüfung nach ASVS L2.

**Abnahme (Spezifikation 14):** Steckbrief vollständig; Restore in der CI grün. Weil die CI auf GitHub derzeit keine Jobs startet (kontoseitig), gilt hier: Die Wiederherstellungsprobe läuft lokal gegen Postgres 16 (Port 5433) grün und ist in `docs/demo/m9.md` protokolliert; derselbe Ablauf steht als CI-Job bereit und wird grün, sobald die CI läuft.

**Tech Stack:** wie M8. Neu: `pyjwt[crypto]` (MIT, heute schon transitiv) als direkte Abhängigkeit für ID-Tokens; im Image `postgresql-client-17` (Debian, PostgreSQL-Lizenz) und `restic` (BSD-2-Clause, Binärdatei mit Prüfsumme wie `tini`). Kein Redis/Valkey, kein boto, kein MinIO (Entscheidungen 8, 17, 18). Vor dem Bauen die aktuelle Dokumentation lesen (Context7 bzw. Herstellerseiten, soweit erreichbar): PyJWT, Google OpenID Connect, restic, `pg_dump`/`pg_restore` 17, Kubernetes `autoscaling/v2`, ASVS 5.0.

**Spezifikation:** `docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md`, Zeile M9 in Abschnitt 14 mit Jans Ergänzungen vom 13. und 14.11., 5.1, 9 (Anhänge, Live-Bearbeitung), 12.4 bis 12.7, R14 aus Review M2.

---

## Was schon da ist (Abgleich)

- Anmeldung mit Passwort (argon2id), Sitzung als Cookie (nur SHA-256 gespeichert), Ratenbegrenzung in Postgres, `/auth/me` mit `permissions` (`modules/auth`, `core/security.py`, `core/ratelimit.py`). `app_user.password_hash` darf leer sein.
- OAuth-Client mit PKCE, `state` in Postgres, Egress-Regeln, Stub über https (`modules/oauth`, `tests/support/oauth_stub.py`, `e2e/global-setup.mjs`). Daran lehnt sich OIDC an, ohne Code zu teilen, der Konnektoren betrifft.
- Geheimnisse `env:`/`enc:` mit Fernet/HKDF und Rotation (`core/secrets.py`, `SecretUnavailable`).
- Dateiablage `core/storage.py` (nur `LocalStorage`, Schlüssel `attachments/<org_id>/<sha256>`, inhaltsadressiert); ungenutzte Dateien löscht `wiki/attachments._drop_unused` sofort nach dem Commit.
- Export je Bereich als Markdown-Zip (M2, `wiki/export.py`) — Jans Ergänzung „dazu der Export je Bereich“ ist damit gebaut; M9 verweist nur darauf.
- Collab: Relay `web/collab_proxy.py` reicht das Sitzungs-Cookie an den Collab-Prozess weiter; die interne API (`wiki/collab_router.py`, `collab_service.py`) nimmt Sitzungs-IDs an (R14). Eine Instanz, `Recreate`.
- Chart: Deployments api/worker/collab, Migrations-Job, Ingress, NetworkPolicy, ServiceMonitor, PrometheusRule mit `promtool`-Tests, PVC; **kein** HPA, kein PDB, kein Backup-CronJob, kein S3. Compose: `compose.yml`, `compose.nodes.yml`, `smoke.sh`, `load.sh`.
- Fälligkeits-Schleife `app/worker/due.py` mit Aufbewahrung für Termine, Ereignisse und `mcp_call` (90 Tage); Outbox-Aufbewahrung im Verteiler; abgelaufene Sitzungen beim Login.
- Deadlock/Serialisierung (40P01/40001) antwortet schon 409 `conflict.retry` (`core/db_errors.py`): der M4b-Vermerk ist erledigt.

## Entscheidungen dieses Plans

1. **Zwei Teile, M9a vor M9b.** M9a ist das Minimum für „freigabefähig“: Sicherung und Wiederherstellung über die Kommandozeile mit Probe, automatische Sicherung mit Aufbewahrung, Offsite und Alarm, OIDC mit Google und Selbstregistrierung samt Oberfläche, Collab-Tokens (R14), volles Chart, Härtung der Altlasten, ASVS-Prüfung, Lasttest, Abschluss (Tasks 1 bis 11). M9b vervollständigt Jans Ergänzungen und die Skalierung: Wartungsmodus und Einspielen in eine laufende Installation, Sicherung in der Verwaltung, S3, Collab Stufe 2, bedingt TOTP (Tasks 12 bis 17). Ein Tag `vX.Y.Z` veröffentlicht Image und Chart; er wird nur auf Jans Wort gesetzt (Frage J1).
2. **Sicherung mit `pg_dump -Fc`/`pg_restore`, kein eigener logischer Export.** Gründe: Der Dump gibt Schema und Daten vollständig wieder (Trigger wie `work_item.status_changed_at`, erzeugte Spalten wie `search_tsv`, Fremdschlüssel-Zyklen, Indizes), aus einem konsistenten Snapshot und mit erprobtem Werkzeug. Ein eigener Export per `COPY` müsste pg_dump nachbauen: Beim Laden feuern Trigger und überschreiben Werte, Fremdschlüssel verlangen eine Reihenfolge oder Superuser-Rechte, erzeugte Spalten sind nicht ladbar. Die Bindung an den Code leistet das Manifest (Alembic-Revision, Version). Das Image bringt `postgresql-client-17` mit; unterstützt sind Server ab 16 (E9). Regeln beim Einspielen: Hauptversion des Zielservers ≥ der des Quellservers, `pg_restore` ≥ `pg_dump` des Archivs, sonst Abbruch mit Code. Geladen wird mit `--no-owner --no-privileges` (verwaltete Datenbanken), `--single-transaction --exit-on-error` (ganz oder gar nicht).
3. **Archivformat 1.** Eine unkomprimierte tar-Datei `herd-<UTC JJJJMMTTThhmmssZ>-<Version>.tar` (Rechte 0600, Verzeichnis 0700) mit `herd/FORMAT` (`1`), `herd/db.dump`, `herd/files/<Speicherschlüssel>` und zuletzt `herd/manifest.json`; daneben `<Name>.manifest.json` mit derselben Manifestkopie und `archive_sha256`. Das Manifest enthält nur Kennzahlen, nie Inhalte: Format, App-Version, Alembic-Revision, Erstellzeit, Serverhauptversion, `pg_dump`-Version, Speicherart (`local`/`s3`), Zeilen je Tabelle, Dateien (Anzahl, Bytes), SHA-256 und Größe je Mitglied, Schlüsselkennung (Entscheidung 5), Anzahl `enc:`-Werte je Spalte, Namen der `env:`-Verweise. Unkomprimiert, weil der Dump schon komprimiert ist und Anhänge meist auch, und weil restic so über Archive hinweg dedupliziert.
4. **Konsistenz von Datenbank und Dateien.** Die Sicherung öffnet eine `REPEATABLE READ`-Transaktion, exportiert ihren Snapshot (`pg_export_snapshot()`), lässt `pg_dump --snapshot=<id>` darauf laufen und liest im selben Snapshot Zeilenzahlen und die Speicherschlüssel aller Anhänge; genau diese Dateien kommen ins Archiv. Damit eine Datei nicht zwischen Snapshot und Kopie verschwindet, löscht `_drop_unused` nicht mehr sofort, sondern schreibt einen Grabstein (`storage_tombstone`, in derselben Transaktion wie das Löschen der Zeile); die Fälligkeits-Schleife löscht nach 48 Stunden, wenn die Datei dann noch unbenutzt ist (Sperre wie heute). Eine Sicherung, die länger als 48 Stunden braucht, ist nicht vorgesehen (Doku).
5. **Geheimnisse.** Das Archiv enthält `enc:`- und `env:`-Werte unverändert. Das Manifest nennt die **Schlüsselkennung** von `HERD_SECRET_KEY` (die ersten 16 Hex-Zeichen von HKDF-SHA256 mit `info=b"herd-key-id"`), nie den Schlüssel. Beim Einspielen muss `HERD_SECRET_KEY` oder `HERD_SECRET_KEY_PREVIOUS` des Ziels dieselbe Kennung haben, sonst bricht die Prüfung mit `restore.secret_key_mismatch` ab (bzw. `restore.secret_key_missing` ohne Schlüssel, wenn das Archiv `enc:`-Werte hat). Mit `--without-secrets` läuft es trotzdem: Die `enc:`-Werte bleiben unlesbar, KI-Verbindungen, Konnektoren, MCP-Server und OIDC-Anbieter melden dann ihren vorhandenen Fehler „Geheimnis nicht verfügbar“ (`SecretUnavailable`), bis ein Admin den Wert neu einträgt; die Prüfung listet die betroffenen Spalten mit Anzahl. Fehlende Umgebungsvariablen zu `env:`-Verweisen meldet die Prüfung als Warnung.
6. **Wiederherstellung per Kommandozeile nur in eine leere Installation (M9a).** Leer heißt: keine Tabelle im Schema `public` und in der Dateiablage kein Schlüssel des Archivs mit anderem Inhalt (inhaltsadressiert: gleicher Schlüssel = gleicher Inhalt, geprüft über SHA-256). Abgelehnt werden: falsche Prüfsumme, unbekanntes Format, eine Alembic-Revision, die der Code nicht kennt (`restore.archive_newer`), Versionsregeln aus 2, Schlüssel aus 5. Eine ältere bekannte Revision wird eingespielt und dann mit `alembic upgrade head` angehoben. Danach in einer Transaktion: alle Sitzungen, OAuth- und OIDC-Abläufe und Collab-Berechtigungen gelöscht (Spezifikation 12.6: nach dem Restore ist jede Sitzung ungültig), `backup_run`-Zeilen im Zustand `running` auf `interrupted`, ein Audit-Eintrag `backup.restored` (Akteur `system`, Archivname, Revisionen). Wiederherstellung und Migration nehmen dieselbe Advisory-Sperre (`herd.schema`), sodass ein startender `all`-Prozess nicht dazwischen migriert. Einspielen in eine laufende Installation ist M9b (Entscheidung 9).
7. **Automatische Sicherung.** Zeitplan `HERD_BACKUP_SCHEDULE` (Cron, UTC, Standard `30 2 * * *`), Ziel `HERD_BACKUP_DIR` (Volume, Standard `/backups`). Compose: Dienst `backup` mit demselben Image (`python -m app.ops backup schedule`, Zeit aus `core/clock.py`, kein Sleep in Tests). Helm: CronJob mit `concurrencyPolicy: Forbid` (`python -m app.ops backup run`). Ein Lauf: Archiv schreiben → zurücklesen und prüfen → erst dann `ok` → Aufbewahrung → Offsite. Aufbewahrung nach Großvater-Vater-Sohn: die letzten `HERD_BACKUP_KEEP_DAILY` (7) Tage, `…_WEEKLY` (4) Wochen und `…_MONTHLY` (6) Monate, je Zeitraum das neueste gelungene Archiv, und immer das neueste gelungene; misslungene Archive werden sofort entfernt und zählen nie; ohne gelungenes neues Archiv wird nichts gelöscht.
8. **Offsite mit restic** (Spezifikation 12.6, ai-2). Eingeschaltet, wenn `HERD_BACKUP_OFFSITE_REPOSITORY` gesetzt ist; Passwort `HERD_BACKUP_OFFSITE_PASSWORD` (Geheimnis). Die Zugangsdaten des Speichers (`AWS_*`, `B2_*`, `AZURE_*`, `GOOGLE_*`, `RESTIC_*` außer Repository und Passwort) gehen aus einem eigenen Secret bzw. `backup.env` **nur** an den restic-Kindprozess; dessen Umgebung wird ausdrücklich gebaut, nichts anderes aus der App-Umgebung. Ablauf: `restic backup` des Archivs und seines Manifests, `restic forget --prune` mit der Regel aus 7, monatlich `restic check --read-data-subset=5%`. restic verschlüsselt clientseitig; die Archive im Volume sind unverschlüsselt (Doku: Volume schützen).
9. **Wartungsmodus und Einspielen in eine laufende Installation (M9b).** Tabelle `maintenance` (eine Zeile je Organisation, `active`, `reason` als Enum `restore`, `started_at`, `version`). Solange sie aktiv ist, antwortet die API auf alles außer `/health`, `/ready`, `/metrics`, `GET /api/maintenance` und der SPA mit 503 `maintenance.active` und `Retry-After: 30` (vorübergehend, daher 503); jeder Prozess hält den Zustand als Cache, aufgefrischt über `NOTIFY herd_maintenance` und spätestens alle 5 s. Worker-Schleifen (Outbox, Läufe, Fälligkeiten) pausieren; Collab-Verbindungen schließen mit 4503. Einspielen: Sicherheitsarchiv des jetzigen Stands → Wartung an → 10 s Auslauf → **eine** `psql --single-transaction`-Sitzung mit `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, dem Ausgabe-SQL von `pg_restore -f -` und `UPDATE maintenance SET active = true` im eingespielten Stand → `alembic upgrade head` → Schritte aus 6 → Wartung aus. Scheitert die Transaktion, bleibt der alte Stand vollständig. Nur mit `backup.manage`, mit Eingabe des Organisationsnamens als Bestätigung.
10. **Recht `backup.manage` nur für `owner`**, nicht für `admin`. Ein Archiv enthält Direktnachrichten, die Admins nur über die protokollierte Einsicht sehen (5.5); ein Archiv herunterzuladen wäre eine Masseneinsicht ohne Protokoll. Jedes Anlegen, Herunterladen, Prüfen und Einspielen steht im Audit (ohne Inhalte). Die Kommandozeile handelt als `system` mit `via=cli`.
11. **Zustand der Sicherungen in der Datenbank:** `backup_run` (org_id, `trigger` `schedule|cli|admin|pre_restore`, `state` `running|ok|failed|interrupted`, Start, Ende, Archivname, Bytes, `archive_sha256`, `error_code`, `offsite_state` `off|ok|failed`). Ein kurzlebiger CronJob ist nicht abfragbar; deshalb liest der Worker (wie die Gauges der Fälligkeits-Schleife) aus der Tabelle: `herd_backup_last_success_timestamp_seconds`, `herd_backup_last_failure_timestamp_seconds`, `herd_backup_last_bytes`, `herd_backup_offsite_last_success_timestamp_seconds`. Alarme: `HerdBackupTooOld` (letzte gelungene Sicherung älter als `backup.alertAfterHours`, Standard 26), `HerdBackupFailing` (letzter Fehlschlag jünger als letzter Erfolg), `HerdOffsiteBackupFailing`, `HerdBackupNeverRan` (Metrik 0 nach 26 h Laufzeit des Workers).
12. **OIDC allgemein, Google als Vorlage.** Autorisierungscode mit PKCE (S256), `state` und `nonce` in Postgres (`oidc_flow`, 10 Minuten), dazu ein HttpOnly-Cookie `herd_oidc` (SameSite=Lax, Pfad `/api/auth/oidc`) mit einem Bindungswert, dessen Hash am Ablauf steht (gegen Login-CSRF). Anbieter in `oidc_provider` (Verwaltung mit `user.manage`, `version`/409), Client-Secret als `enc:`/`env:` (`env:HERD_OIDC_<NAME>`). Discovery, Token-Endpunkt und JWKS nur über `core/egress.py` (https, öffentliche Adressen, private nur über `HERD_OIDC_ALLOWED_HOSTS`), JWKS am Anbieter gespeichert, bei unbekannter `kid` höchstens einmal je Minute neu geholt. ID-Token-Prüfung mit PyJWT: Algorithmen nur RS256/ES256 (nie `none`/HS*), `iss` exakt, `aud` enthält die Client-ID, `azp` bei mehreren Zielgruppen, `exp`/`iat`/`nbf` mit 60 s Spielraum, `nonce`. Kein Userinfo-Aufruf; die Claims kommen aus dem ID-Token. Rückruf `{HERD_PUBLIC_URL}/api/auth/oidc/{key}/callback`; ohne `HERD_PUBLIC_URL` lässt sich kein Anbieter einschalten (`oidc.public_url_missing`).
13. **Verknüpfen.** Erst über `user_identity (provider_id, subject)`. Sonst mit einem bestehenden aktiven Konto derselben E-Mail nur, wenn `email_verified` wahr ist **und** der Anbieter für diese Adresse maßgeblich ist: Google, wenn die Adresse auf `@gmail.com` endet oder `hd` gleich ihrer Domain ist; ein allgemeiner Anbieter nur mit dem Schalter `trust_email` (Standard aus). Sonst `oidc.link_refused` mit Hinweis, sich erst mit Passwort anzumelden und im Profil zu verknüpfen. Deaktivierte Konten: abgelehnt wie unbekannt. Verknüpfen steht im Audit; Admins sehen und lösen Verknüpfungen (`user.manage`), Personen die eigenen.
14. **Selbstregistrierung** je Anbieter: Schalter `allow_signup` (Standard aus), wirksam nur mit nicht leerer Liste `allowed_domains` (klein geschrieben, ohne Punkt am Ende, exakt, keine Subdomains). Geprüft wird die Domain der bestätigten E-Mail; bei Google muss für eine Nicht-gmail-Domain zusätzlich `hd` gleich dieser Domain sein (`gmail.com` geht nur, wenn ausdrücklich gelistet). Das neue Konto: `member`, aktiv, ohne Passwort, Sprache `de`, **persönliche KI-Zuordnung „keine KI“** (Frage J2), keine Bereiche außer dem eigenen und den offenen nach den Regeln aus 5.3. Audit `user.self_registered`.
15. **Google-Vorlage** (aus Googles OpenID-Connect-Dokumentation; hier ohne Netz nicht prüfbar, beim Bauen gegenprüfen und sonst so belassen und markieren): Issuer `https://accounts.google.com`, als `iss` auch `accounts.google.com`; Scopes `openid email profile`; zusätzlich `prompt=select_account` und, wenn genau eine Domain erlaubt ist, `hd=<Domain>` (nur Vorauswahl; erzwungen wird über den Claim). Der Admin trägt nur Client-ID, Secret, Selbstregistrierung und Domains ein.
16. **Collab mit kurzlebigen Berechtigungen statt Cookie (R14).** Das Relay prüft wie bisher und erzeugt dann eine Berechtigung `herd_cg_<256 Bit>` (gespeichert nur als SHA-256 in `collab_grant`: Sitzung, Person, Seite, Generation, Ablauf 10 Minuten, bei jeder Prüfung alle 5 s verlängert), die es dem Collab-Prozess als `Authorization: Bearer` schickt; das Cookie verlässt die API nicht mehr. Die interne API nimmt Laden, Speichern und Prüfen nur noch mit Berechtigungen an, die zu genau dieser Seite und Generation gehören; eine unbekannte Berechtigung beendet keine Generation. Ein kompromittierter Collab-Prozess erreicht damit nur Seiten, die gerade offen sind, und keine Sitzung. Keine Übergangsschicht für ältere Collab-Prozesse: Es gibt noch keine Freigabe.
17. **Collab Stufe 2 ohne Redis: Seitenbindung in Postgres** (Abweichung von 12.4, [Claude]). Mehrere Collab-Instanzen melden sich über die interne API an (`collab_instance`: Adresse aus `HERD_COLLAB_ADVERTISE_URL`, Herzschlag alle 5 s, `draining`). Das Relay leitet alle Verbindungen einer Seite an ihre Besitzerin (`collab_page_owner`: Instanz, `epoch`, Ablauf 30 s, verlängert durch die Prüfung alle 5 s); ohne gültige Besitzerin wählt es die am wenigsten belastete lebende Instanz und erhöht `epoch` atomar. Speichern und Prüfen nennen Instanz und `epoch`; wer nicht Besitzerin ist, bekommt 409 `collab.not_owner` und schließt mit 4409 (Browser verbindet neu). Warum nicht die Hocuspocus-Redis-Erweiterung: Die Speicherlogik dieses Projekts (Generationen, Zurücklesen, Rechte je beteiligter Sitzung, Zusammenfassen von Versionen) hängt daran, dass eine Instanz alle Bearbeitenden einer Seite kennt; mit Redis kämen fremde Änderungen ohne Sitzung an, und es gäbe einen zweiten zustandsbehafteten Dienst. Die Bindung behält die bewährte Logik, braucht keinen neuen Dienst und schützt über `epoch` vor zwei schreibenden Instanzen.
18. **S3 für Anhänge (M9b)** mit einem kleinen eigenen Client auf `httpx` (SigV4, Pfad-Stil, `x-amz-content-sha256` = bekannter SHA-256 des Anhangs; PUT, GET gestreamt, HEAD, DELETE, ListObjectsV2), kein boto (Größe, Abhängigkeiten). Einstellungen `HERD_STORAGE` (`local`|`s3`), `HERD_S3_ENDPOINT`, `HERD_S3_REGION`, `HERD_S3_BUCKET`, `HERD_S3_ACCESS_KEY_ID`, `HERD_S3_SECRET_ACCESS_KEY` (Geheimnis), `HERD_S3_PREFIX`. Der Endpunkt ist Betreibereinstellung (vertrauenswürdig wie die Datenbank-URL): eigener Client ohne Umgebungs-Proxy, nicht über die SSRF-Sperre. Für Compose und CI **SeaweedFS** (Apache-2.0) statt des in 12.5 genannten MinIO (AGPL, E2). Umzug lokal → S3: `python -m app.ops storage copy --to s3` (idempotent je Schlüssel).
19. **Helm vollständig:** `autoscaling/v2`-HPA für api und worker (Standard aus; CPU-Ziel 70 %, Grenzen aus der Messung), PDB für api, worker und collab ab zwei Replikas, Backup-CronJob mit eigener PVC (Standard an), OIDC-, Backup-, Offsite-, S3- und Collab-Werte, neue Alarme. Kein PgBouncer in M9: Mit den Standardgrenzen (api ≤ 6, worker ≤ 3) bleibt der Verbindungsbedarf nach Messung unter 100; der Steckbrief nennt die Rechnung, `HERD_DB_PGBOUNCER` aus 12.4 entsteht erst mit einem Leser.
20. **Lasttest-Referenz:** 200 gleichzeitige Personen (Mischung: Seiten lesen 40 %, Suchen 10 %, Nachrichten schreiben 15 %, SSE offen 100 %, Tickets bewegen 10 %, Board/„meine Tickets“ 15 %, Seiten speichern 10 %) auf 2 API + 1 Worker. Ziele: P95 Lesen ≤ 300 ms, Schreiben ≤ 500 ms, Live-Zustellung P95 ≤ 2 s, keine 5xx. Gemessen ohne Docker als Prozesse (wie M3 bis M8); verfehlt ein Ziel, nennt der Steckbrief Engpass und Folgeaufgabe, ohne stillen Umbau.
21. **ASVS 5.0.0, Stufe 2** (die aktuelle Fassung; 12 nennt keine Version). Jede Anforderung bekommt in `docs/SICHERHEIT.md` Status (erfüllt / nicht anwendbar / Lücke) und Beleg (Code oder Test). Kleine Lücken (≤ ½ Tag) behebt Task 9 selbst, größere werden Fragen an Jan. Bekannt vorab: ASVS L2 verlangt Mehr-Faktor-Anmeldung (laut V6, hier nicht nachprüfbar); über OIDC leistet sie der Anbieter, lokale Passwortkonten haben keine (Frage J3, Task 16 bedingt).
22. **Migrationen ab der ersten Freigabe:** `backend/alembic/RELEASED` nennt die Revision der letzten Freigabe (bis zum ersten Tag leer). `scripts/check_migrations.py` lehnt in jeder späteren Revision `drop_table`, `drop_column`, `drop_index`, `drop_constraint`, `alter_column(type_=…)`, Umbenennungen und `op.execute` mit `DROP`/`RENAME` ab, außer die Revision erklärt `contract_of = "<frühere Revision>"`, und diese liegt vor `RELEASED`. Die Ausnahme der Lauf-Spuren-Migration (M6, nicht nur erweiternd) ist damit abgeschlossen: Sie liegt vor der ersten Freigabe. Ebenso entfallen jetzt, vor der ersten Freigabe, `event_outbox.attempts` und `next_attempt_at` (M4-Vermerk, kein Leser mehr).
23. **Getragene Punkte, je entschieden:** b-api-Anmeldung → Frage J4, bis dahin in `docs/KI.md` als „Anmeldeart ungeprüft“ markiert (die Verbindungsart ist optional). Lesestand-Endpunkt (M3 N9) → Task 8. Ein NOTIFY je Schreibvorgang (M3 N17) → bleibt; `one_notify` und die Faltung gleicher NOTIFYs je Transaktion begrenzen es, Task 10 misst die Schreibgrenze und trägt sie in den Steckbrief. Aufbewahrung von `mcp_call` (gebaut, 90 Tage) und aller anderen Tabellen → Katalog in Task 8. `propose_new_page` nach einem gelesenen Entwurf → Task 8 öffnet es für den Bereich des Entwurfs. Lauf-Spuren-Migration → Entscheidung 22. UUIDv7 als Lesestand (M3 N13), Schritt über die Sperrfrist hinaus (M6), Abbrechen ohne kurze Sperrgrenze (M6) → bekannte Grenzen, dokumentiert; die unter Last instabilen Abbruch-Wettlauf-Tests (M7) macht Task 8 stabil. Dritte schmale Prüfung G1/G2 aus M8 → Task 0 (Reviewer) vor M9.

## Fragen an Jan (nur was seine Ziele ändert)

- **J1** Wann wird getaggt (erste Freigabe), nach M9a oder nach M9b, und mit welcher Version? Vorschlag: nach M9a als `v1.0.0`.
- **J2** „Neue Konten ohne KI-Zuordnung“: wörtlich keine eigene Zuordnung (dann gilt die Standardzuordnung der Organisation, und Selbstregistrierte hätten sofort KI) oder ausdrücklich „keine KI“, bis ein Admin sie freigibt? Gebaut wird die zweite Lesart (Kosten und Datenabfluss nur nach Entscheidung); eine Zeile in `oidc/admission.py`, falls Jan die erste will.
- **J3** ASVS L2 verlangt MFA. Option A: TOTP für lokale Konten (Pflicht für Owner/Admin, freiwillig für andere; Task 16). Option B: MFA nur über den OIDC-Anbieter, lokale Konten als dokumentierte Abweichung. Empfehlung A.
- **J4** Wie meldet sich die b-api an (Bearer oder eigener Kopf)? Bis zur Antwort gilt Bearer, markiert als ungeprüft.
- **J5** Ansprechperson und Vertretung für den Steckbrief (Pflichtfeld nach 12.7, ohne sie ist er nicht „vollständig“).
- **J6** Aus M8 offen: Admin-Einsicht zeigt markierte DM-Texte nicht; Neustart einer DM; Rückfragen in geteilten Orten unter der persönlichen Marke abgelehnt. Bestätigen oder ändern.

## Global Constraints

- Alles aus `CLAUDE.md`, besonders: `org_id` und Org-Scope, Schichten, ≤ ~300 Zeilen je Datei, jedes Feld mit getestetem Leser, Paginierung, `version`/409, i18n `de`/`en`, nur erweiternde Migrationen (eine je Scheibe, ein Head), neue `HERD_`-Einstellungen in **beiden** Compose-Dateien, im Chart (Werte, Schema, Chart-Regel) und in der Doku.
- Keine Inhalte in Logs, Metriken, Outbox, NOTIFY oder Audit — auch nicht aus Sicherung, Wiederherstellung, OIDC-Claims (nur Anbieter-Schlüssel, Codes, Anzahlen; E-Mail nie im Log) oder restic-Ausgaben (nur Exit-Code und Kennzahlen).
- Datenbank-Passwort, Geheimschlüssel, restic-Passwort, S3-Schlüssel, Client-Secrets nie in Argumentlisten (`ps`), URLs, Logs oder Fehlermeldungen; Kindprozesse bekommen `PGPASSWORD` bzw. ihre Variablen nur in einer ausdrücklich gebauten Umgebung.
- Tests erreichen nie das Netz: OIDC-Stub (`tests/support/oidc_stub.py`), S3-Stub (`tests/support/s3_stub.py`), ein falsches `restic` auf `PATH` (`tests/support/fake_restic.py`); echtes restic und SeaweedFS nur in der CI.
- Wiederholbare Zeit: alles Planende liest `core/clock.py`; Tests nutzen `SettableClock`.
- `config.py` hat 233 Zeilen: Neue Einstellungen kommen in Teilklassen (`core/config_ops.py`, `core/config_auth.py`), zu denen `Settings` erbt; `get_settings()` bleibt die eine Quelle.
- **Was hier läuft und was nur in der CI:** Hier gibt es kein Docker, kein helm, kubeconform und promtool, und der Proxy sperrt manche Hosts (GitHub-Releases, get.helm.sh). Jede Aufgabe nennt ihre lokale Prüfung; „fertig“ hängt nie an der CI. Lokale Ersatzprüfungen: `jsonschema` gegen `values.schema.json` (Werte-Dateien), `bash -n` für Skripte, `yaml.safe_load` für Workflows und Templates ohne Go-Ausdrücke, ein Python-Abgleich der Alarme mit den Metriken im Code, die Wiederherstellungsprobe gegen Postgres 16 auf Port 5433.

## Review Focus

1. **Ein Archiv, das nicht passt:** neuere Revision, anderer Schlüssel, manipuliertes oder abgeschnittenes Mitglied, fremde Datei im Ziel, nicht leere Datenbank, älterer Zielserver — jedes Mal Abbruch mit Code, und am Ziel hat sich nichts geändert (Task 2: `test_a_refused_restore_leaves_the_target_untouched` je Fall parametrisiert).
2. **Sicherung während geschrieben wird:** Hochladen und Löschen von Anhängen während der Sicherung — das eingespielte Archiv hat zu jeder Anhang-Zeile ihre Datei (Task 1: `test_a_backup_during_uploads_and_deletes_is_self_consistent`).
3. **OIDC-Übernahme von Konten:** unbestätigte E-Mail, fremde Google-Adresse ohne `hd`, Groß-/Kleinschreibung, Subdomain und Punkt am Ende einer erlaubten Domain, wiederverwendeter `state`/Code/`nonce`, `iss`/`aud`-Verwechslung, `alg=none`, Rückruf ohne Bindungs-Cookie (Task 4: `test_admission_matrix` und `test_callback_refuses_*`).
4. **Einspielen im Betrieb:** Anfragen und laufende Agenten-Läufe während des Tauschs, Sitzungen danach, eine scheiternde Transaktion lässt den alten Stand ganz (Task 12: `test_a_failed_replace_keeps_the_old_state`, `test_requests_during_maintenance_answer_503`).
5. **Collab:** ein Prozess mit fremder oder abgelaufener Berechtigung erreicht keine andere Seite (Task 6); zwei Instanzen, die dieselbe Seite speichern wollen — die mit veralteter `epoch` wird abgewiesen, kein Inhalt geht verloren (Task 15: `test_a_stale_owner_cannot_save`).

---

## Aufgaben

### Task 0: Schmale Prüfung G1/G2 aus M8 (Reviewer, kein Implementierer)

Die in M8 offene dritte, schmale Prüfung der persönlichen Marke (G1 gespeichert und dem Inhalt folgend, G2 Freigabe statt Ablehnung) auf dem aktuellen Stand. Befunde gehen als Fix-Welle vor Task 8; Fragen J6 an Jan. Läuft hier vollständig (Backend- und e2e-Tests der Agenten).

### Task 1: Archiv und Sicherung über die Kommandozeile (M9a)

**Ziel:** `python -m app.ops backup create|verify|list` schreibt und prüft Archive nach Entscheidungen 2 bis 5 und 11; Dateilöschung mit Grabstein.

**Dateien:** neu `backend/app/ops/{__init__,__main__,archive,manifest,pgtools,snapshot,backup,cli_backup}.py`, `backend/app/modules/backups/{models,repository,metrics}.py`, `backend/app/core/storage_tombstones.py` (+ Repository), `backend/app/core/config_ops.py`; geändert `core/config.py` (Teilklassen), `core/secrets.py` (`key_id`), `core/storage.py` (`exists`), `wiki/attachments.py` (`_drop_unused` → Grabstein), `worker/due.py` (Grabsteine abarbeiten), Migration `m9_backup_run_and_tombstones`, `Dockerfile` (`postgresql-client-17`).

**Schnittstellen (Produces):**
- `core/secrets.key_id(material: str) -> str`; `current_key_ids() -> tuple[str | None, str | None]` (aktuell, vorherig).
- `ops/manifest.py`: `@dataclass(frozen=True) Manifest` mit den Feldern aus Entscheidung 3; `Manifest.to_json() -> bytes`, `Manifest.from_json(data: bytes) -> Manifest` (unbekannte Felder → `ManifestInvalid`).
- `ops/archive.py`: `ArchiveWriter(path: Path)` mit `add_file(name: str, source: Path)`, `add_stream(name: str, size: int, chunks: AsyncIterator[bytes])`, `finish(manifest: Manifest) -> str` (SHA-256 des Archivs, schreibt Sidecar); `verify_archive(path: Path) -> list[str]` (Problemcodes, leer = gut: `archive.checksum`, `archive.member_missing`, `archive.member_checksum`, `archive.format_unknown`, `archive.truncated`).
- `ops/pgtools.py`: `child_env(settings) -> dict[str, str]`; `async server_major(conn) -> int`; `client_major(tool: str) -> int`; `async dump(settings, snapshot_id: str, out: Path) -> None`.
- `ops/backup.py`: `async create_backup(settings: Settings, *, trigger: BackupTrigger, clock: Clock) -> BackupOutcome(run_id, archive: Path | None, state, error_code)`.
- `modules/backups/models.BackupRun` (Felder aus Entscheidung 11), `BackupTrigger`, `BackupState`.

**Tests zuerst** (`backend/tests/test_backup_archive.py`, `test_backup_create.py`, `test_storage_tombstones.py`; brauchen `pg_dump`, lokal 16, CI-Runner 16/17):
- `test_manifest_round_trips_and_refuses_unknown_fields`
- `test_verify_finds_a_changed_byte_a_missing_member_and_a_truncated_tail` (je ein Problemcode)
- `test_create_backup_writes_dump_files_and_manifest` — Manifest nennt Revision = Head, Zeilen je Tabelle = `count(*)`, jede Anhang-Datei mit SHA-256 = Schlüsselende, Rechte 0600.
- `test_a_backup_during_uploads_and_deletes_is_self_consistent` — während `pg_dump` läuft (ein Haken in `dump` wartet auf ein Ereignis), wird ein Anhang hochgeladen und einer gelöscht; das Archiv enthält genau die Dateien des Snapshots.
- `test_deleting_an_attachment_leaves_the_file_for_48_hours` und `test_the_due_loop_removes_a_file_after_the_grace_unless_reused` (`SettableClock`).
- `test_key_id_is_stable_and_never_the_key`; `test_no_password_in_argv` (die Argumentliste von `pg_dump` enthält weder Passwort noch URL mit Passwort).
- `test_failed_dump_marks_the_run_failed_and_leaves_no_archive`.

**Abnahme:** Archiv einer Demo-Datenbank entsteht, `verify` leer, `backup_run` `ok`; Gates grün. **Hier:** alles. **Nur CI:** Image-Build mit `postgresql-client-17`.
**Commits:** `ops: write and verify backup archives`, `wiki: delete unused files after a grace period`.

Geändert in M9: Zwei Migrationen statt einer (`m9_storage_tombstone` mit dem Commit der Grabsteine, `m9_backup_run` mit dem der Archive; je Scheibe eine). Die Kommandozeile hat einen Verteiler `ops/cli.py` (`run(argv, settings, clock)`, testbar ohne Prozess); `backup list` liest `backup_run` und ist damit der Leser aller Felder. `modules/backups/metrics.py` (Gauges) und `HERD_BACKUP_DIR` in Compose und Chart kommen mit Task 3, wo Dienst, Volume und CronJob entstehen; Task 1 legt die Einstellung in `core/config_ops.py` an und dokumentiert sie in `docs/SICHERUNG.md`. Zusätzliche Codes: `archive.exists` (ein Archiv gleichen Namens wird nie überschrieben), ein Mitglied, das nicht im Manifest steht, zählt als `archive.member_checksum`. Die CLI-Sicherung steht im Audit als `backup.created` mit Akteur `system` (`actor_id` = Null-UUID) und `via` = Auslöser. Der CI-Job `backend` installiert `postgresql-client-17` (der Dienst ist PostgreSQL 17, das `pg_dump` 16 des Runners lehnte ihn ab).

### Task 2: Wiederherstellung über die Kommandozeile und Probe (M9a)

**Ziel:** `python -m app.ops restore check <archiv>` und `restore apply <archiv> [--without-secrets]` nach Entscheidungen 5 und 6; Probe als Skript, lokal und als CI-Job.

**Dateien:** neu `backend/app/ops/{restore,restore_checks,restore_after,cli_restore,schema_lock}.py`, `backend/scripts/compare_databases.py`, `deploy/scripts/restore-rehearsal.sh`; geändert `core/migrations.py` (Advisory-Sperre `herd.schema`), `.github/workflows/ci.yml` (Job `restore`: Dienst `pgvector/pgvector:pg17`, `postgresql-client-17` aus apt.postgresql.org, Skript).

**Schnittstellen:**
- Consumes: Task 1 (`verify_archive`, `Manifest`, `pgtools`, `key_id`).
- `ops/restore_checks.py`: `async check_restore(settings, archive: Path) -> RestoreCheck(problems: list[str], warnings: list[str], manifest: Manifest)`; Codes `restore.archive_newer`, `restore.target_not_empty`, `restore.file_conflict`, `restore.server_too_old`, `restore.tools_too_old`, `restore.secret_key_mismatch`, `restore.secret_key_missing`, dazu die Archivcodes aus Task 1; Warnungen `restore.env_missing:<NAME>`, `restore.secrets_unreadable:<tabelle.spalte>=<n>`.
- `ops/restore.py`: `async restore_into_empty(settings, archive: Path, *, without_secrets: bool, clock: Clock) -> RestoreReport(revision_from, revision_to, tables: dict[str,int], files: int)`.
- `ops/restore_after.py`: `async finish_restore(session, *, archive_name: str, clock: Clock) -> None` (Sitzungen, OAuth/OIDC-Abläufe, Collab-Berechtigungen löschen; `running` → `interrupted`; Audit `backup.restored`). Gelöscht wird nach der Liste `CLEARED_AFTER_RESTORE` (Tabellennamen); Task 2 trägt ein, was bei seinem Merge besteht, Tasks 4 und 6 ergänzen `oidc_flow` bzw. `collab_grant`, falls sie später landen; ein Test prüft, dass jede Tabelle der Liste existiert.

**Tests zuerst** (`test_restore_checks.py`, `test_restore_apply.py`; zweite Datenbank per `createdb`, Fixture räumt auf):
- `test_a_refused_restore_leaves_the_target_untouched[<code>]` für jeden Code oben (Zieldatenbank und -ablage danach unverändert).
- `test_restore_into_an_empty_database_brings_every_row_and_file_back` — Zeilen je Tabelle wie im Manifest, Dateien mit gleichem SHA-256.
- `test_an_older_archive_is_migrated_to_head` (Archiv mit `alembic downgrade -1` erzeugt, danach Head).
- `test_sessions_are_gone_after_restore_and_login_works`; `test_running_backup_rows_become_interrupted`.
- `test_without_secrets_restores_and_connections_report_secret_unavailable`.
- `test_restore_and_migrate_exclude_each_other` (zweiter Teilnehmer wartet auf die Sperre).

**Probe** `deploy/scripts/restore-rehearsal.sh`: Datenbank A anlegen, App (Rolle `all`) starten, `demo_seed` mit Anhang, `backup create`; Datenbank B und leere Ablage, `restore check` (leer), `restore apply`; App auf B starten, `/ready`, Anmeldung mit dem Demo-Admin klappt, das alte Cookie von A nicht; `compare_databases.py A B` (Zeilen je Tabelle ohne Sitzungstabellen) und Anhang-Download mit gleichem SHA-256; manipuliertes Archiv → `restore check` scheitert mit `archive.member_checksum`; Aufräumen. Exit 0 nur, wenn alles stimmt.

**Abnahme:** Probe lokal grün, Ausgabe in `docs/demo/m9.md`. **Hier:** alles gegen PG16. **Nur CI:** Job `restore` gegen PG17 und Client 17 (`bash -n` und `yaml.safe_load` der Workflow-Datei hier).
**Commits:** `ops: restore an archive into an empty installation`, `ci: rehearse a restore`.

Geändert in M9: `finish_restore` bekommt zusätzlich `revision_from`/`revision_to` (für das Audit). Die Probe hält A nach der Sicherung an und vergleicht A und B, bevor B startet: Die Anmeldung an B ändert `app_user` und `rate_limit_hit`, und ein laufendes A könnte nach dem Snapshot noch schreiben; `compare_databases.py` vergleicht außer Zeilen auch eine Prüfsumme des Inhalts je Tabelle und lässt Sitzungen, Abläufe, Audit-Log und `backup_run` aus. Ein Speicherschlüssel im Archiv, den die Ablage nicht zulässt, ist `archive.format_unknown`. Die Sperre `herd.schema` nimmt alembics `env.py` je Migrationstransaktion (`core/migrations.lock_schema`), die Wiederherstellung auf Sitzungsebene für ihre ganze Dauer (`ops/schema_lock.py`).

### Task 3: Automatische Sicherung, Aufbewahrung, Offsite, Alarm (M9a)

**Ziel:** Entscheidungen 7, 8 und 11 in Code, Compose und Chart.

**Dateien:** neu `backend/app/ops/{retention,offsite,schedule,cli_run}.py`, `backend/tests/support/fake_restic.py`, `backend/scripts/check_alert_metrics.py`; geändert `modules/backups/metrics.py` (Gauges im Worker), `worker/main.py`, `deploy/compose/{compose.yml,compose.nodes.yml,backup.env.example,smoke.sh}`, Chart (`templates/cronjob-backup.yaml`, `pvc-backups.yaml`, Werte/Schema `backup.*`, `files/prometheus-rules.yaml`, `tests/rules-test.yaml`, `scripts/check-chart-rules.sh`), `Dockerfile` (restic mit Prüfsumme je Architektur).

**Schnittstellen:**
- `ops/retention.py`: `@dataclass KeepRule(daily: int, weekly: int, monthly: int)`; `keep_set(archives: Sequence[ArchiveInfo], now: datetime, rule: KeepRule) -> set[str]` (rein, ohne Ein-/Ausgabe).
- `ops/offsite.py`: `async push_offsite(settings, archive: Path, rule: KeepRule, clock: Clock) -> OffsiteState`; `restic_env(settings, passthrough: Mapping[str, str]) -> dict[str, str]`.
- `ops/schedule.py`: `async run_schedule(settings, clock: Clock, *, stop: asyncio.Event) -> None` (nächster Termin mit `cronsim`, ruft `backup run`).
- Einstellungen: `HERD_BACKUP_DIR`, `HERD_BACKUP_SCHEDULE`, `HERD_BACKUP_KEEP_DAILY`, `…_WEEKLY`, `…_MONTHLY`, `HERD_BACKUP_OFFSITE_REPOSITORY`, `HERD_BACKUP_OFFSITE_PASSWORD`.

**Tests zuerst:**
- `test_keep_set_grandfather_father_son` (Tabelle von 120 Tagen täglicher Archive → genau 7 + 4 + 6 ohne Doppelte, plus das neueste); `test_failed_archives_never_count_and_nothing_is_deleted_without_a_new_good_one`.
- `test_schedule_fires_at_the_cron_term_without_sleeping` (`SettableClock`).
- `test_offsite_passes_only_its_own_environment` (falsches restic schreibt seine Umgebung und Argumente in eine Datei: kein `HERD_DATABASE_PASSWORD`, kein `HERD_SECRET_KEY`, Passwort nicht in Argumenten); `test_offsite_failure_marks_offsite_failed_but_keeps_the_backup_ok`.
- `test_backup_gauges_come_from_backup_run` (Worker-Metriken).
- `scripts/check_alert_metrics.py` + `test_every_alert_names_metrics_the_code_exports` (lokaler Ersatz für promtool: jede Metrik in einem `expr` existiert in einer Registry des Codes; jeder Alarm hat einen Fall in `rules-test.yaml`).
- `rules-test.yaml`: `HerdBackupTooOld`, `HerdBackupFailing`, `HerdOffsiteBackupFailing`, `HerdBackupNeverRan` feuern und schweigen je einmal.

**Abnahme:** Compose-Dienst `backup` und CronJob beschrieben und lokal statisch geprüft. **Hier:** Python-Tests, `check_alert_metrics.py`, `bash -n` der Skripte, `jsonschema` der Werte. **Nur CI:** `promtool test rules`, `helm lint`, `kubeconform`, Image mit restic, `smoke.sh` (Sicherung im Compose-Dienst, Wiederherstellung in eine zweite Datenbank), echtes restic gegen ein lokales Dateisystem-Repository.
**Commits:** `ops: back up on a schedule with retention and restic`, `deploy: add the backup service, cron job and alerts`.

Geändert in M9: `keep_set(archives, rule)` ohne `now` (die Stufen zählen vom neuesten guten Archiv aus, eine Uhr braucht es nicht). Die Stufen sind kaskadierend: die letzten 7 Tage, dann ältere Wochen, die noch kein behaltenes Archiv haben, dann ältere Monate ebenso; 120 Tage tägliche Archive können keine 6 älteren Monate tragen, der Test nimmt 240 Tage. `offsite_state` (`off|ok|failed`) an `backup_run` kommt in einer eigenen Migration (`m9_backup_offsite`). `backup run` endet mit 1, wenn die Sicherung oder Offsite scheitert (CronJob `backoffLimit: 0` meldet es), die Zeile bleibt `ok`. Zusätzliche Gauges `herd_backup_offsite_last_failure_timestamp_seconds` und `herd_backup_alert_after_seconds` (aus `HERD_BACKUP_ALERT_AFTER_HOURS`, Vorgabe 26), damit die Regeldatei statisch bleibt und der Schwellenwert eine Einstellung ist. `backup schedule` ist der Dienst in Compose (`run_schedule` mit Tick, Termin streng nach der Uhrzeit).

### Task 4: OIDC-Kern mit Google-Vorlage und Stub (M9a)

**Ziel:** Entscheidungen 12 bis 15 im Backend.

**Dateien:** neu `backend/app/modules/oidc/{models,repository,protocol,id_token,admission,flow,service,providers,router,schemas,metrics}.py`, `backend/app/core/config_auth.py`, `backend/tests/support/oidc_stub.py`, `tests/factories_oidc.py`; geändert `auth/service.py` (Sitzung öffnen als gemeinsame Methode `open_session(user, now) -> str`), `core/permissions.py` (keine neue Aktion: `user.manage`), `ops/restore_after.py` (`oidc_flow`), `pyproject.toml` (`pyjwt[crypto]`), Migration `m9_oidc`.

**Schnittstellen:**
- Modelle: `OidcProvider(org_id, key, name, kind google|generic, issuer, client_id, client_secret_ref, scopes, trust_email, allow_signup, allowed_domains, enabled, jwks, jwks_fetched_at, version)`, `OidcFlow(org_id, provider_id, state_hash, nonce, verifier, binding_hash, expires_at)`, `UserIdentity(org_id, user_id, provider_id, subject, created_at, last_login_at)` mit eindeutig `(provider_id, subject)`.
- `id_token.verify_id_token(raw: str, *, jwks: Mapping, issuers: frozenset[str], client_id: str, nonce: str, now: datetime) -> IdClaims(sub, email, email_verified, hd, name, locale)`; Fehler `IdTokenInvalid(reason: str)` (`signature`, `alg`, `iss`, `aud`, `azp`, `expired`, `not_yet_valid`, `nonce`, `kid_unknown`).
- `admission.decide(rules: ProviderRules, claims: IdClaims, by_subject: uuid.UUID | None, by_email: ExistingUser | None) -> Admission` mit `Login(user_id) | Link(user_id) | Signup(email, name) | Refuse(code)`; Codes `oidc.link_refused`, `oidc.signup_closed`, `oidc.domain_not_allowed`, `oidc.email_unverified`, `oidc.account_inactive`.
- Routen: `GET /api/auth/providers` (öffentlich: `key`, `name`, `kind`); `GET /api/auth/oidc/{key}/start` (302); `GET /api/auth/oidc/{key}/callback` (302 auf `/` bzw. `/login?error=<code>`); Verwaltung `GET|POST /api/admin/oidc-providers`, `GET|PATCH|DELETE /api/admin/oidc-providers/{id}` (`version`, Secret nur schreibbar), `POST …/{id}/check` (Discovery-Test); `GET /api/auth/me/identities`, `DELETE /api/auth/me/identities/{id}` (nicht die letzte Anmeldemöglichkeit eines Kontos ohne Passwort: 409 `oidc.last_identity`), `GET|DELETE /api/users/{id}/identities[/…]` (`user.manage`).
- Einstellungen: `HERD_OIDC_ALLOWED_HOSTS`, `HERD_OIDC_RATE_PER_MINUTE` (Start und Rückruf je Adresse, Standard 30).
- Metrik `herd_oidc_logins_total{outcome}` (Codes, keine Namen); Alarm `HerdOidcFailing` (Anteil Fehler wegen Anbieter > 50 % über 15 min).

**Tests zuerst** (`test_oidc_id_token.py`, `test_oidc_admission.py`, `test_oidc_flow.py`, `test_oidc_admin.py`; Stub in-process mit TLS wie der OAuth-Stub, steuerbar: falsche `aud`/`iss`, abgelaufen, `alg=none`, HS256 mit öffentlichem Schlüssel, falsche `nonce`, `email_verified=false`, `hd` fehlt/abweichend, Schlüsselwechsel):
- `test_verify_id_token_refuses[<reason>]` für jeden Grund; `test_a_new_kid_refetches_jwks_at_most_once_a_minute`.
- `test_admission_matrix` — Tabelle über (Subjekt bekannt, E-Mail-Konto vorhanden, bestätigt, Google gmail/hd/ohne, `trust_email`, `allow_signup`, Domains inkl. `Example.COM`, `sub.example.com`, `example.com.`) → erwartetes Ergebnis.
- `test_callback_refuses_without_the_binding_cookie`, `…_a_reused_state`, `…_an_expired_flow`, `…_a_flow_of_another_provider`.
- `test_signup_creates_a_member_without_password_and_without_ai` (`ai.use` fehlt trotz Standardzuordnung; Audit `user.self_registered`).
- `test_google_preset_sends_hd_only_with_exactly_one_domain_and_accepts_both_issuers`.
- `test_discovery_and_jwks_go_through_the_egress_guard` (private Adresse ohne Freigabe → `oidc.provider_unreachable`).
- `test_no_email_or_claims_in_logs` (caplog über einen ganzen Ablauf).
- `test_provider_admin_needs_user_manage_and_version` (404 ohne Recht, 409 bei alter Version, Secret nie in Antworten).

**Abnahme:** Anmeldung und Selbstregistrierung gegen den Stub, alle Ablehnungsfälle mit Code. **Hier:** alles. **Nur CI:** nichts zusätzlich. Gegen echtes Google nicht prüfbar (markiert in `docs/ANMELDUNG.md`).
**Commits:** `auth: add OIDC providers with a Google preset`, `auth: sign up through OIDC within allowed domains`.

### Task 5: Oberfläche Anmeldung und Browsertests (M9a)

**Ziel:** Anmeldeseite mit Knöpfen je Anbieter und Fehlertexten aus `?error=`, Verwaltung → Anmeldung (Anbieter anlegen, Google-Vorlage mit nur Client-ID, Secret, Selbstregistrierung, Domains; Prüfen; Rückruf-Adresse zum Kopieren), Profil → Verknüpfte Konten, Personenverwaltung zeigt Verknüpfungen. Sichtbarkeit nur aus `permissions` (`user.manage`).

**Dateien:** `frontend/src/features/auth/{OidcButtons.tsx,…}`, `frontend/src/features/admin/oidc/*`, `frontend/src/features/profile/identities/*`, `queries.ts` je Feature, Locales `de`/`en`, Routen in `adminRoutes.tsx`; `e2e/tests/oidc.spec.mjs`, `e2e/oidc-helpers.mjs`, `e2e/global-setup.mjs` (OIDC-Stub als Prozess über https, Port +7, `HERD_OIDC_ALLOWED_HOSTS=localhost`).

**Tests zuerst:** vitest `OidcButtons.test.tsx` (kein Anbieter → keine Knöpfe; Fehlercode → Text), `OidcProviderForm.test.tsx` (Secret-Feld leer bei Bearbeitung, Domains Pflicht bei Selbstregistrierung, 409 zeigt Neuladen); e2e: Anmeldung über den Stub mit verknüpftem Konto; Selbstregistrierung mit erlaubter Domain landet als Mitglied ohne KI-Funktionen; fremde Domain sieht den Fehlertext.

**Abnahme:** `npm run lint/typecheck/test/build`, `check-i18n`, `check:api`, e2e `oidc` grün. **Hier:** alles (Chromium vorhanden wie in M8).
**Commit:** `web: sign in with OIDC providers and manage them`.

### Task 6: Collab mit kurzlebigen Berechtigungen (R14, M9a)

**Ziel:** Entscheidung 16.

**Dateien:** neu `backend/app/modules/wiki/{collab_grants,collab_grant_repository}.py`, Migration `m9_collab_grant`; geändert `web/collab_proxy.py` (kein Cookie mehr, `Authorization: Bearer herd_cg_…`), `wiki/collab_router.py`, `collab_schemas.py`, `collab_service.py` (Berechtigungen statt Sitzungs-IDs; ggf. Aufteilung wegen 300 Zeilen), `collab/{server.mjs,api.mjs,checks.mjs,admission.mjs}`, `collab`-Tests, `ops/restore_after.py`.

**Schnittstellen:**
- `collab_grants.mint(session, *, session_id, user_id, page_id, generation, now) -> str`; `resolve(session, token, *, page_id, generation, now) -> GrantRef | None`; `renew(session, tokens, now) -> None`.
- Interne API: `POST /internal/collab/auth {grant}` → Person, `session_ref` (undurchsichtige ID für die Grenzen je Sitzung), Generation; `GET /pages/{id}` mit Kopf `X-Herd-Grant`; `PUT /pages/{id}` mit `editor_grants`; `POST /pages/{id}/check` mit `grants`, `unsaved_grants` → `revoked_grants`, `ended_grants`.

**Tests zuerst:** `test_collab_grants.py`: `test_a_grant_works_only_for_its_page_and_generation`, `test_an_unknown_grant_ends_no_generation` (R14 Kern), `test_a_grant_expires_after_ten_minutes_without_a_check`, `test_logout_keeps_the_grant_for_saving_within_the_hour` (Verhalten aus M2 R2 bleibt), `test_the_relay_sends_no_cookie_upstream`; collab `node --test`: Grenzen je Sitzung über `session_ref`. Bestehende Live-Tests (Backend, collab-Integration, e2e `live-*`) bleiben grün.

**Abnahme:** Gates; `collab npm test` und `npm run test:integration`; e2e `live-*`. **Hier:** alles.
**Commit:** `wiki: hand the collab process page-bound grants instead of the session cookie`.

*Geändert in M9 (Task 6) [Claude, 15.11.2026]:*
- `collab_grant` speichert keine Person: Sie folgt aus der Sitzung, eine eigene Spalte hätte keinen Leser (Regel 5). `mint(session, *, org_id, session_id, page_id, generation, now)`; `renew(session, grants, *, now)` nimmt die gefundenen `GrantRef`s; dazu `bound(...)` (gefunden für genau Seite und Generation). Der Schritt nach dem Einspielen (Task 2) leert `collab_grant` über `CLEARED_AFTER_RESTORE` in `ops/restore_after.py` (vor `user_session`); eine eigene Funktion dafür braucht es nicht.
- Eine Berechtigung wird **nicht mit ihrer Sitzung gelöscht**, sondern verliert mit ihr jede Wirkung (`session_id` → NULL, `ON DELETE SET NULL`) und wird eine Stunde nach ihrem Ablauf beim Ausstellen neuer Berechtigungen aufgeräumt. Grund: Würde sie mitgelöscht, wäre die Berechtigung einer widerrufenen Sitzung unbekannt; eine unbekannte darf keine Generation beenden, und ungespeicherte Änderungen der widerrufenen Person blieben dann im Dokument, ohne dass jemand sie speichern oder verwerfen könnte. So beendet nur eine Berechtigung, die für genau diese Seite und Generation ausgestellt wurde, eine Generation.
- `POST /internal/collab/auth` nimmt außer `grant` auch `page_id` und `generation` (die Bindung wird schon bei der Aufnahme geprüft). Prüfen antwortet `revoked_grants` und `ended_grants`, keine `revoked_user_ids` mehr (jede Verbindung hat ihre eigene Berechtigung); Fehler nennen keine Berechtigungen (403 `collab.editors_revoked` ohne Details), ungültige Berechtigungen sind 401 `collab.grant_invalid`.
- Die Grenzen je Anmeldung zählt der Collab-Prozess erst nach der Aufnahme über `session_ref` (vorher beim Upgrade über den Hash des Cookies). `HERD_SESSION_COOKIE_NAME` geht nicht mehr an den Collab-Prozess.

### Task 7: Volles Helm-Chart (M9a)

**Ziel:** Entscheidung 19 und alle neuen Einstellungen der Tasks 1 bis 6 im Chart; Compose vollständig.

**Dateien:** `templates/{hpa-api,hpa-worker,pdb}.yaml`, Werte/Schema für `api.autoscaling`, `worker.autoscaling`, `podDisruptionBudget`, `oidc.*` (`allowedHosts`, `existingSecret` für `HERD_OIDC_*`-Secrets), `backup.*` (aus Task 3), `collab.*`; `ci/production-values.yaml` und neues `ci/full-values.yaml` (alles an); `scripts/check-chart-rules.sh` (HPA nur mit gesetzten Grenzen, `replicas` entfällt bei HPA, PDB nur ab zwei Replikas, CronJob ohne KI-Secret außer `HERD_SECRET_KEY`, keine Geheimnisse als Werte); neu `deploy/helm/scripts/check_values.py` (lokal: jede `ci/*-values.yaml` und `values.yaml` gegen `values.schema.json` mit `jsonschema`, jede `@param` in `values.yaml` hat einen Schemaeintrag und umgekehrt); README-Abschnitt Helm; NOTES.txt.

**Tests zuerst:** `check_values.py` als Test (`backend/tests/test_chart_values.py` ruft es auf) mit einer absichtlich falschen Werte-Datei als Gegenprobe; neue Fälle in `check-chart-rules.sh`.

**Abnahme:** **Hier:** `check_values.py`, `bash -n` aller Skripte, `check-chart-version.sh`. **Nur CI:** `helm lint --strict` (alle Werte-Dateien), `helm template | kubeconform -strict`, `check-chart-rules.sh`, `promtool`.
**Commit:** `deploy: autoscale api and worker and complete the chart`.

### Task 8: Härtung und getragene Punkte (M9a)

**Ziel:** Entscheidungen 22 und 23, je ein Commit.

1. **Aufbewahrungskatalog:** `app/core/retention.py` mit `RETENTION: Mapping[str, Retention]` (`keep` mit Begründung, `upkeep` mit Tagen und Ort, `self` mit Verweis auf den Code, der aufräumt). Neu im Upkeep der Fälligkeits-Schleife: abgelaufene Sitzungen (nicht nur beim Login), abgelaufene `oidc_flow`/`oauth_flow`, `collab_grant`, `rate_limit_hit`, `ai_rate_window`, erledigte Grabsteine; Benachrichtigungen bleiben (Inhalt der Person), Audit, `usage_record`, `run`/`run_event` bleiben (Nachweis; Löschung ist Betreiberentscheidung, `docs/SICHERUNG.md`). Test `test_every_table_has_a_retention_rule` (gegen `Base.metadata`) und je neuer Regel ein Test mit `SettableClock`. Commit `ops: keep a retention rule for every table`.
2. **Migrationsregel:** `backend/alembic/RELEASED` (leer), `scripts/check_migrations.py`, Test mit Beispielrevisionen (erlaubt/abgelehnt/`contract_of`); in CI-Job `backend`. Neue Migration `m9_drop_outbox_attempts` entfernt `event_outbox.attempts`/`next_attempt_at` (vor `RELEASED` erlaubt). Commit `alembic: check that released migrations only expand`.
3. **Lesestand-Endpunkt:** `GET /api/conversations/{id}/read` → `{last_read_message_id, last_read_at}` (404 wie unbekannt); die Markierung „Neu“ im Frontend nutzt ihn statt der Zählung. Tests Backend + vitest. Commit `messaging: expose the read position`.
4. **`propose_new_page` nach gelesenem Entwurf:** erlaubt, wenn der Vorschlag in einen Bereich mit Entwurfsmarke geht (sichtbar nur mit `page.edit` dort), abgelehnt für jeden anderen Bereich. Test `test_propose_new_page_after_a_draft_read_stays_in_the_draft_space`. Commit `agents: let a draft-marked run propose new pages in that space`.
5. **Abbruch-Wettlauf-Tests:** mit systematic-debugging die Instabilität unter Last finden (409 dann Teardown-Deadlock) und beheben; 20 Durchläufe unter paralleler Last grün. Commit nach Befund.
6. Dokumentiert als bekannte Grenzen (`docs/AGENTEN.md`, `docs/NACHRICHTEN.md`): N13, Schritt über die Sperrfrist, Abbrechen ohne kurze Sperrgrenze; b-api „ungeprüft“ (`docs/KI.md`).

**Abnahme:** volle Backend-Suite, vitest. **Hier:** alles.

### Task 9: Sicherheitsprüfung ASVS 5.0 L2 (M9a)

**Ziel:** Entscheidung 21. `docs/SICHERHEIT.md` mit einer Zeile je L1/L2-Anforderung (Kapitel, Nummer, Status, Beleg), Sicherheitshinweise des Steckbriefs dorthin verschoben und verlinkt. Prüfungen, die als Test bleiben: `test_security_headers_on_every_public_route` (CSP, `nosniff`, `frame-ancestors`, HSTS hinter https), `test_cookies_are_httponly_samesite_and_secure_in_production`, `test_production_start_refuses_unsafe_settings` (z. B. `HERD_COOKIE_SECURE=false` mit https-`HERD_PUBLIC_URL`), `test_error_bodies_never_echo_input`. Gefundene kleine Lücken: Test zuerst, beheben, je ein Commit `security: …`. Größere Lücken → Fragen an Jan in der Abschlussmeldung; MFA siehe J3.

**Abnahme:** jede L2-Anforderung hat einen Status; keine Lücke ohne Eintrag. **Hier:** alles.
**Commit:** `docs: check the system against ASVS 5.0 level 2` (+ Fix-Commits).

### Task 10: Lasttest und gemessene Ressourcen (M9a)

**Ziel:** Entscheidung 20; der Steckbrief wird vollständig (12.7).

**Dateien:** `deploy/compose/loadgen.py` (Szenario-Mischung, SSE-Verzögerung, Zielauswertung; ggf. Aufteilung), neu `deploy/scripts/measure-processes.sh` (RSS/CPU je Rolle aus `/proc`, ohne Docker), `docs/STECKBRIEF.md` (Ressourcen, Request/Limit, HPA-Grenzen, Verbindungsrechnung aus 19, Sicherungs- und Wiederherstellungsdauer mit Archivgröße für 10.000 Seiten und 1 GiB Anhänge, Schreibgrenze durch NOTIFY, „Nicht gemessen“ bereinigt).

**Tests zuerst:** `test_loadgen_report.py` (Auswertung: Perzentile, Zielvergleich, Fehlerzählung aus einer festen Messreihe).

**Abnahme:** Messung mit Ergebnis gegen die Ziele im Steckbrief; Chart-Standardwerte für Requests/Limits aus der Messung. **Hier:** Messung als Prozesse. **Nur CI/Betrieb:** `load.sh` mit `docker stats`.
**Commit:** `deploy: measure 200 people and size the chart from it`.

### Task 11: Abschluss M9a

`docs/SICHERUNG.md` (Sicherung, Zeitplan, Aufbewahrung, Offsite, Wiederherstellung in Compose und Kubernetes mit vollständigem Ablauf, Schlüssel, was ohne Schlüssel geschieht, Export je Bereich als Markdown-Zip als Ergänzung), `docs/ANMELDUNG.md` (OIDC, Google einrichten Schritt für Schritt, Selbstregistrierung, Verknüpfen, Fehlercodes), README (Betriebshinweise, Freigabehinweise mit Migrationsregel), `CLAUDE.md` (Stand, neue Module, Befehle `python -m app.ops …`, Probe), Spezifikation (12.4, 12.5, 12.6, 5.1, 14 mit Abweichungen und Belegen), `docs/demo/m9.md` (ausgeführt und protokolliert: Wiederherstellungsprobe, Anmeldung über den Stub mit Selbstregistrierung, Alarm-Regeltest, Collab ohne Cookie), Demo-Daten (`demo_seed`: OIDC-Anbieter gegen den Stub nur mit `--oidc-stub`, eine Sicherung über die CLI ist kein API-Weg, daher nicht im Seed). Volle Gates aller Pakete. Danach **Modul-Review M9a** mit Fix-Welle; erst dann „freigabefähig“ (J1).

### Task 12: Wartungsmodus und Einspielen in eine laufende Installation (M9b)

**Ziel:** Entscheidung 9 im Backend und in der CLI (`restore apply --replace --confirm "<Organisationsname>"`).

**Dateien:** neu `backend/app/modules/maintenance/{models,repository,service,middleware,cache}.py`, `backend/app/ops/replace.py`, Migration `m9_maintenance`; geändert `app/web/public.py` (Middleware), `worker/{dispatcher,runs,due}.py` (Pause), `collab_service.check` (Wartung → schließen), `core/access.py`/`permissions.py` (`backup.manage`, nur `owner`).

**Tests zuerst:** `test_requests_during_maintenance_answer_503` (mit `Retry-After`, Ausnahmen erreichbar), `test_workers_pause_in_maintenance`, `test_a_failed_replace_keeps_the_old_state` (SQL-Fehler mitten im Einspielen → alter Stand, Wartung aus, `backup_run` `failed`), `test_replace_takes_a_safety_archive_first`, `test_replace_signs_everyone_out_and_audits`, `test_backup_manage_is_owner_only` (Admin bekommt 404 wie unbekannt), `test_maintenance_cache_follows_notify_and_polls`.

**Abnahme:** Gates. **Hier:** alles.
**Commit:** `ops: replace a running installation from an archive in maintenance`.

### Task 13: Sicherung in der Verwaltung (M9b)

**Ziel:** Verwaltung → Sicherung (nur mit `backup.manage`): Liste der `backup_run` (paginiert), „Jetzt sichern“ (Auftrag im Worker, Status live über `backup.changed`), Herunterladen (gestreamt, Audit), Hochladen eines Archivs bis `HERD_BACKUP_UPLOAD_MAX_BYTES` (Standard 2 GiB, in `HERD_BACKUP_DIR`) oder Auswahl eines vorhandenen, „Prüfen“ (zeigt Manifest gegen Installation: Versionen, Revision, Schlüssel passt, Zeilen- und Dateizahlen, Warnungen), „Einspielen“ (Bestätigung mit Organisationsnamen, danach Wartungsseite, Abmeldung). Hinweis auf den Export je Bereich.

**Dateien:** `backend/app/modules/backups/{service,router,schemas,jobs}.py`, Worker-Auftrag (`backup_job` als Zustand in `backup_run` mit `trigger=admin`), `frontend/src/features/backup/*`, Wartungsseite in `features/shared`, Locales, `e2e/tests/backup.spec.mjs`.

**Tests zuerst:** Backend `test_backup_routes_are_owner_only_and_paginated`, `test_download_streams_and_audits`, `test_upload_is_bounded_and_checked`; vitest Prüfansicht (Schlüssel passt nicht → Einspielen gesperrt mit Text); e2e: Sicherung anlegen, in der Liste sehen, Prüfung eines manipulierten Archivs zeigt den Fehler.

**Abnahme:** Gates, e2e `backup`. **Hier:** alles.
**Commits:** `backups: start, list, download and check archives in the administration`, `web: add the backup administration`.

### Task 14: S3-Ablage (M9b)

**Ziel:** Entscheidung 18; Sicherung und Wiederherstellung mit S3.

**Dateien:** neu `backend/app/core/{s3_client,s3_signing,storage_s3}.py`, `backend/tests/support/s3_stub.py` (prüft SigV4), `backend/app/ops/storage_copy.py`; geändert `core/storage.py` (`get_storage` nach `HERD_STORAGE`), `ops/backup.py`/`restore.py` (Dateien über `Storage`), `deploy/compose/compose.s3.yml` (SeaweedFS), Chart `s3.*` (Secret-Name statt Werte), Doku.

**Tests zuerst:** `test_sigv4_matches_the_aws_examples` (veröffentlichte Testvektoren von AWS als feste Werte), `test_s3_storage_put_open_delete_exists` (Stub), `test_a_wrong_signature_is_refused_by_the_stub` (Gegenprobe), `test_backup_and_restore_with_s3`, `test_storage_copy_is_idempotent`, `test_no_s3_secret_in_logs_or_errors`.

**Abnahme:** **Hier:** alles gegen den Stub. **Nur CI:** `smoke.sh` mit `compose.s3.yml` (SeaweedFS).
**Commit:** `storage: keep attachments in S3-compatible storage`.

### Task 15: Collab Stufe 2 — Seitenbindung (M9b)

**Ziel:** Entscheidung 17.

**Dateien:** neu `backend/app/modules/wiki/{collab_instances,collab_owner_repository}.py`, Migration `m9_collab_instances` (`collab_instance` ohne `org_id` als Infrastrukturtabelle, ausdrücklich so entschieden; `collab_page_owner` mit `org_id`); geändert `web/collab_proxy.py` (Wahl der Instanz), `collab_router.py` (`POST /internal/collab/instances`, Instanz und `epoch` in Speichern/Prüfen), `collab/server.mjs` (Anmeldung, Herzschlag, `draining` bei SIGTERM: speichern, Bindungen freigeben, mit 4503 schließen), `launch.py` (Rolle `all`: eine Instanz mit `127.0.0.1`), Chart (`collab.replicas`, `RollingUpdate` ab 2, PDB, `HERD_COLLAB_ADVERTISE_URL` aus der Pod-IP über die Downward-API), Compose-Knoten-Datei (zwei Collab-Container), `docs/WIKI.md`.

**Tests zuerst:** `test_all_connections_of_a_page_go_to_its_owner`, `test_an_expired_owner_is_replaced_and_epoch_rises`, `test_a_stale_owner_cannot_save` (409 `collab.not_owner`, Inhalt der neuen Besitzerin bleibt), `test_a_draining_instance_gets_no_new_pages`; collab-Integration mit zwei Prozessen: zwei Browser derselben Seite landen auf derselben Instanz; Instanz beenden → Wiederverbinden auf der anderen ohne Verlust gespeicherter Änderungen.

**Abnahme:** Gates, collab-Integration, e2e `live-*` (eine Instanz) grün; Messung mit zwei Instanzen (40 Bearbeitende auf 8 Seiten) im Steckbrief. **Hier:** alles. **Nur CI:** Compose mit zwei Collab-Containern.
**Commit:** `collab: bind each page to one of several collab instances`.

### Task 16: TOTP für lokale Konten (M9b, nur bei J3 = A)

Zweiter Faktor mit TOTP (RFC 6238, eigener Code auf `hmac`, keine Abhängigkeit), Wiederherstellungscodes (gehasht), Pflicht für `owner`/`admin` nach Übergangsfrist, Anmeldung zweistufig mit Ratenbegrenzung, Zurücksetzen durch Admins mit Audit, Oberfläche. Tests mit RFC-Testvektoren und `SettableClock`. Ohne Jans Zustimmung entfällt die Aufgabe, und `docs/SICHERHEIT.md` vermerkt die Abweichung.

### Task 17: Abschluss M9b

Doku (`docs/SICHERUNG.md` Einspielen im Betrieb, S3, `docs/WIKI.md` Stufe 2), Steckbrief (S3, zwei Collab-Instanzen), Spezifikation (12.4 Abweichung Seitenbindung, 12.5 SeaweedFS statt MinIO, 14 Zeile M9 mit Belegen), `CLAUDE.md`, `docs/demo/m9.md` ergänzt (Einspielen in der Verwaltung, Wechsel der Collab-Instanz), Modul-Review M9b mit Fix-Welle.

## Reihenfolge und Parallelität

Task 0 zuerst (Reviewer), seine Fix-Welle vor Task 8.

**M9a:** 1 → 2 → 3. Daneben von Anfang an 4 → 5 und 6. Task 7 nach 3, 4 und 6 (sammelt deren Einstellungen). Task 8 nach Task 0s Fix-Welle und nach 1 (Grabsteine im Katalog), 9 nach 4 bis 6, 10 nach 6 und 7. Task 11 zum Schluss, dann Modul-Review M9a. Höchstens drei Implementierer zugleich; gemeinsame Dateien (`core/config.py`, `worker/due.py`, `ops/restore_after.py`, Chart-Werte, Compose) ändert je Welle nur ein Task, die anderen tragen ihre Zeilen in ihrem Bericht nach.

**M9b** (nach dem Review von M9a): 12 → 13; daneben 14 und 15; 16 nur nach J3; 17 zum Schluss, dann Modul-Review M9b.

**Minimum für „freigabefähig“:** Tasks 0 bis 11 und die Fix-Welle des Reviews M9a. Ohne M9b fehlt Jans Wunsch „in der Verwaltung auslösbar“ (Export und Import gehen dann nur über die Kommandozeile), S3 (mehrere API-Pods brauchen ReadWriteMany) und mehr als eine Collab-Instanz.
