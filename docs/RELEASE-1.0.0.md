# to-herd-cats-ai 1.0.0

Die erste Freigabe. Image `ghcr.io/<owner>/to-herd-cats-ai:1.0.0` (und `:1.0`), Chart
`oci://ghcr.io/<owner>/charts/to-herd-cats-ai` Version 1.0.0. Die Alembic-Revision der
Freigabe ist `9e4b6d2f8a17` (`backend/alembic/RELEASED`): Ab jetzt sind Migrationen
nur erweiternd, zurückgebaut wird frühestens eine Freigabe später (README,
„Freigaben und Updates“).

## Was 1.0.0 enthält

- **Grundlage (M1):** Anmeldung, Personen, Gruppen, Bereiche (offen, Team, persönlich),
  Rollen, die eine Rechteprüfung, Audit, Verwaltung; Image, Compose, Helm-Chart, CI.
- **Wiki (M2):** Seitenbaum, Markdown-Editor und gemeinsames Live-Bearbeiten, Versionen,
  Papierkorb, Tags, Anhänge, Volltextsuche, Import und Export als Markdown-ZIP
  ([`WIKI.md`](WIKI.md)).
- **Nachrichten (M3):** Kanäle, Direktnachrichten, Threads, Erwähnungen, Reaktionen,
  Lesestand, Seiten-Threads, Benachrichtigungen, Aktivität, Suche, Live-Zustellung über
  SSE auch über mehrere API-Knoten ([`NACHRICHTEN.md`](NACHRICHTEN.md)).
- **Aufgaben (M4, M4b):** Tickets `HC-<n>` mit Epics, Storys, Tasks und Bugs, Status je
  Bereich, Board, Epic-Übersicht, Sprints, Backlog, „Mein Board“ und die Tagesansicht
  ([`TICKETS.md`](TICKETS.md)).
- **KI-Grundlage (M5 Tasks 1 bis 7):** KI-Verbindungen (OpenAI-Protokoll, Schlüssel als
  `env:`/`enc:`, SSRF-Sperre, optionaler Egress-Proxy), Modellzuordnung, Verbrauch,
  KI-Richtlinie je Bereich und die Sperre `no_ai` ([`KI.md`](KI.md)).
- **Agenten als Mitarbeiter (M6):** Stufen 1 bis 3, Werkzeugkatalog mit Freigaben je
  Agent, Auslöser, Freigaben und Rückfragen, Laufjournal, Seiten- und Skill-Vorschläge,
  Skills, Gedächtnisseiten, persönliche Agenten ([`AGENTEN.md`](AGENTEN.md)).
- **Automatisierung (M7):** einmalige, wiederkehrende, Heartbeat- und Ereignis-Regeln,
  Protokoll, Pausieren und Übernehmen, Budgets je Organisation, Person und Agent,
  Prüfintervall des Wikis ([`AGENTEN.md`](AGENTEN.md)).
- **Öffnung über MCP (M8):** Zugangstokens, der Endpunkt `/mcp` für Claude Code, Codex
  und andere, externe Agenten, externe MCP-Server mit Freigabe je Werkzeug,
  Konnektoren (Bearer, Header, OAuth mit PKCE), Katalog ([`MCP.md`](MCP.md)).
- **Produktion, erster Teil (M9a):**
  - Sicherung und Wiederherstellung über die Kommandozeile, automatische Sicherung mit
    Aufbewahrung, Offsite mit restic, Alarme, geprobte Wiederherstellung
    ([`SICHERUNG.md`](SICHERUNG.md));
  - Anmeldung über OIDC (Google-Vorlage und allgemeine Anbieter), Verknüpfen,
    Selbstregistrierung mit Freigabe durch einen Admin ([`ANMELDUNG.md`](ANMELDUNG.md));
  - kurzlebige Berechtigungen für den Collab-Prozess statt des Sitzungs-Cookies;
  - volles Helm-Chart mit Autoskalierung, PodDisruptionBudgets, NetworkPolicy und
    Alarmen;
  - Aufbewahrungskatalog, die Migrationsregel ab dieser Freigabe;
  - Sicherheitsprüfung nach ASVS 5.0 L2 ([`SICHERHEIT.md`](SICHERHEIT.md));
  - Lasttest und gemessene Ressourcen ([`STECKBRIEF.md`](STECKBRIEF.md)).
- **Installation auf einem Hostinger-VPS:** `docker-compose.yml` im Hauptordner für den
  Docker Manager („Compose from URL“), erster Start ohne Variablen, Geheimnisse erzeugt
  ein Init-Dienst, HTTPS über Hostingers Traefik ([`HOSTINGER.md`](HOSTINGER.md)).

## Hinweise zum Update

Wer schon einen Stand vor 1.0.0 betreibt: vorher sichern (README, „Update einer
Installation“), dann:

- **Einmal abgemeldet.** Über https heißen die Cookies jetzt `__Host-herd_session` und
  `__Host-herd_oidc`. Das alte Cookie zählt nicht mehr: Wer angemeldet war, meldet sich
  nach dem Update einmal neu an. Laufende Live-Bearbeitungen verbinden sich danach neu;
  das Update also nicht mitten in der Arbeitszeit einspielen. API und Collab-Prozess
  gehören zur selben Version (ein älterer Collab-Prozess lehnt die neue API ab).
- **`max_connections` der Datenbank prüfen.** Jeder API- und Worker-Pod hält bis zu 16
  Verbindungen. Mit den Standardgrenzen der Autoscaler (API 6, Worker 3) sind das in
  der Spitze rund 150 mit Sicherung und Migration; PostgreSQL hat ab Werk 100. Eine
  externe Datenbank auf mindestens 160 setzen oder `maxReplicas` senken. Das
  mitgelieferte PostgreSQL des Charts startet mit `postgresql.maxConnections` (200),
  und das Chart rendert nicht, wenn die Grenzen darüber lägen (README,
  „Autoskalierung und Datenbankverbindungen“).
- **Selbstregistrierung nur über vertrauenswürdige Anbieter.** Ein allgemeiner
  OIDC-Anbieter legt Konten nur an, wenn bei ihm „E-Mail vertrauen“ (`trust_email`)
  eingeschaltet ist; sonst endet die Anmeldung mit `oidc.signup_closed`. Jedes selbst
  registrierte Konto wartet deaktiviert, bis ein Admin es freigibt; ohne Freigabe kommt
  niemand ins System ([`ANMELDUNG.md`](ANMELDUNG.md#selbstregistrierung-und-freigabe)).
- **`HERD_BOOTSTRAP_ADMIN_PASSWORD` muss die Passwortprüfungen bestehen** (10 bis 200
  Zeichen, keines der häufigsten Passwörter, nicht aus Produkt, Organisation oder
  Adresse ableitbar). Sonst bricht der allererste Start mit `bootstrap refused` und
  Exit-Status 4 ab, ohne etwas anzulegen. Eine bestehende Installation (es gibt schon
  Personen) prüft den Wert nicht mehr.
- **Sicherung und Wiederherstellung:** Eine Wiederherstellung hält die Sicherungssperre
  und wird abgelehnt (`restore.backup_running`), solange eine Sicherung läuft; den
  Sicherungsdienst bzw. CronJob vorher anhalten, wie in
  [`SICHERUNG.md`](SICHERUNG.md) beschrieben.

## Bekannte Grenzen

- **Noch nicht enthalten aus M5:** Embeddings, hybride Suche und die Umwandlung von
  Dokumenten mit Docling (M5 Tasks 8 bis 11). Die Suche ist Volltextsuche.
- **M9b folgt:** Wartungsmodus und Einspielen in eine laufende Installation (bis dahin
  nur in eine leere), Sicherung und Wiederherstellung in der Verwaltung (bis dahin nur
  über die Kommandozeile), S3 für Anhänge (mehr als ein API-Pod braucht bis dahin eine
  Anhänge-PVC mit ReadWriteMany), Collab Stufe 2 (bis dahin genau eine
  Collab-Instanz), TOTP als zweiter Faktor für lokale Konten und die übrigen
  ASVS-Lücken J7 bis J14 ([`SICHERHEIT.md`](SICHERHEIT.md)).
- **CI noch nicht auf GitHub gelaufen.** Alle Prüfungen der CI (Backend, Frontend,
  Collab, Browser-Tests, Chart, Image, Smoke-Test, Wiederherstellungsprobe) liefen für
  diese Freigabe lokal; die Workflows selbst laufen erst mit dem ersten Push auf
  GitHub. „Restore in der CI grün“ (Abnahme M9) steht damit noch aus, die Probe ist
  lokal protokolliert ([`demo/m9.md`](demo/m9.md)).
- **Lasttest:** Die Ziele sind bei 48 Anfragen/s klar erfüllt, bei 95 Anfragen/s an der
  Grenze ([`STECKBRIEF.md`](STECKBRIEF.md)).
