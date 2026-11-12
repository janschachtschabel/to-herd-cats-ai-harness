# to-herd-cats-ai: Konzept, abgeglichen mit den Vorgängern und fünf Ideenquellen

Stand 12. Nov. 2026 · Grundlage: Ideenskizze „to-herd-cats-ai: ausgebautes Konzept“ (12. Nov. 2026)
Status: **Entwurf zur Diskussion**, noch nicht freigegeben. Es wird nichts implementiert, bevor Jan dieses Dokument freigibt (Superpowers-Ablauf: brainstorming → Design-Freigabe → writing-plans).

## 0. Kurzfassung

1. **Die Skizze erfindet zu großen Teilen neu, was in `to-herd-cats-ai` schon gebaut ist.** Dort laufen Meilensteine M0 bis M5: Bereiche mit Rollen, Agenten als Principals, Wiki mit Versionen, Vorschläge mit Moderation, Werkzeugrechte `allow | confirm | block` mit Freigaben, dauerhafte Läufe, Arbeitszeiten (Cron, Ereignisse), Tagesbudget, Tickets mit Agentenzuweisung und Postfach. Das sind etwa 8.000 Zeilen Python, 16.000 Zeilen TypeScript, 31 Testdateien und 18 Migrationen, alles mit acht ADRs begründet.
2. **An zwei Stellen weicht die Skizze von dem ab, was dort bewusst entschieden wurde.** Die erste ist LangGraph statt Pydantic AI + DBOS als Agenten-Schleife: ADR 0001/0003 sind nach dem ersten Versuch *weg* von LangGraph gegangen. Die zweite ist die Live-Bearbeitung mit Yjs, die dort auf später verschoben war. Für das Wiki hat `to-herd-cats-ai-2` Yjs/Hocuspocus inzwischen erfolgreich gebaut und liefert die wichtigste Lektion dazu (siehe 3.3).
3. **Neu und wertvoll an der Skizze** sind die Teamnachrichten (Kanäle, @-Erwähnungen), die Modellrichtlinie je Bereich („nur lokal“), das System als eigener MCP-Server, die Autonomiestufen als verständliche Einstellung, die Regel „Agent setzt nie selbst auf Erledigt“, die Dateikonvertierung und der Betrieb ohne Internet.
4. **Wiki.js 3 ist seit 1. Nov. 2026 erschienen**, mit Echtzeit-Bearbeitung, Freigabe-Workflows und eingebautem MCP-Server. Die Vergleichstabelle der Skizze ist damit veraltet. An der Empfehlung „Eigenbau“ ändert das wenig, aber einige Ideen lohnen die Übernahme (Abschnitt 2).
5. **Die wichtigste offene Frage ist nicht technisch:** Wird `to-herd-cats-ai` weitergebaut, oder entsteht im neuen Repo `to-herd-cats-ai-harness` ein dritter Anlauf? (Abschnitt 5, Frage 1)

## 1. Was die Vorgänger schon entschieden haben

### 1.1 Die beiden Repos in einem Satz

| Repo | Stand | Stack | Charakter |
|---|---|---|---|
| `to-herd-cats-ai` | 10. Sept. 2026, M0–M5 umgesetzt | Python 3.13, FastAPI, SQLAlchemy, **Pydantic AI + DBOS**, Postgres 16 + pgvector; React 19, shadcn/ui, assistant-ui, Tiptap 3 | Architektonisch fast deckungsgleich mit der Skizze, sauber begründet (8 ADRs, „Verfassung“ in CLAUDE.md) |
| `to-herd-cats-ai-2` | 10. Sept. 2026, „Pilot v0.8“ | TypeScript, Next.js/vinext, **SQLite/D1**, Drizzle, eigener TS-Agentenloop; Tiptap + **Yjs + Hocuspocus** | Parallelentwurf, betrieblich sehr gründlich (Backups mit Restic, Audits, Lasttests), aber eine Instanz je Datenvolume, kein Postgres |

Hinter beiden steht der erste Versuch `to-herd-cats` (FastAPI + LangGraph + Angular). Dessen Lehren hat ADR 0001 in `to-herd-cats-ai` festgehalten.

### 1.2 Abgleich Punkt für Punkt

| Thema | Skizze | `to-herd-cats-ai` | `to-herd-cats-ai-2` | Empfehlung |
|---|---|---|---|---|
| Datenbank | nur Postgres | nur Postgres (Regel 1) | SQLite/D1 | Postgres, wie Skizze und ai-1 |
| Backend | Python/FastAPI (Tendenz) | Python/FastAPI | TypeScript | Python |
| Agenten-Schleife | LangGraph + Postgres-Checkpointer | **Pydantic AI + DBOS** (Wiederanlauf nach getötetem Worker live geprüft) | eigener TS-Loop ohne Checkpoint | **Pydantic AI + DBOS beibehalten**. Der Wechsel zurück zu LangGraph bräuchte einen neuen Grund; die Skizze nennt keinen. Die „schmale eigene Schnittstelle“ der Skizze existiert dort schon (nur `runtime/` importiert die Bibliotheken). |
| Warteschlange/Zeitplan | eigene PG-Queue mit Zeilensperre | DBOS-Queue für Läufe, Trigger per `SKIP LOCKED` | SQLite-Queue mit Leases | DBOS + `SKIP LOCKED`, wie in ai-1 |
| Frontend | Angular oder React offen | React (ADR 0004) | React | React |
| Wiki-Speicher | Yjs-Dokument, Markdown abgeleitet | **Markdown kanonisch**, Yjs „später“ | Markdown kanonisch + Yjs-Live-Sitzung mit „Generationen“ | Markdown kanonisch, Yjs als Live-Sitzungszustand (3.3) |
| Bereichsrollen | Leser, Autor, Verwalter | viewer, editor, **moderator**, admin | Lesen, Bearbeiten, Moderation, Admin | **vier Rollen**: Moderation wird für die Prüfung von Agentenvorschlägen gebraucht |
| Sichtbarkeit | offen, teamintern, privat; Admins sehen Privates nicht | `private` / `org`; **Admins sehen alles** | persönliche Profile/Chats auch vor Admins privat | Frage an Jan (5, Frage 3) |
| KI-Sperre je Seite | fehlt | `no-ai`-Tag (weicher zweiter Schutz) | „KI-Freigabe“ je Seite und Datei | **übernehmen** |
| Agentenrechte | Schnittmenge Agent ∩ Auslöser | Agentenbereiche ∩ Sicht des Nutzers | zusätzlich: Rechte bei jedem Schritt und beim Fortsetzen **neu prüfen**, Lauf bricht bei geändertem Profil ab | Schnittmenge **plus Neuprüfung** je Schritt |
| Werkzeugrechte | Autonomiestufen 1–4 | `allow / confirm / block` je Werkzeug, Overlays verschärfen nur | nur lesende MCP-Werkzeuge | **beides**: Stufen als Voreinstellung, Werkzeugrecht als Feineinstellung (3.4) |
| Agent schreibt ins Wiki | Vorschlag oder direkt je Bereich | `agent_write_policy` propose/direct, direkt nur zweistufig mit Fingerabdruck | nur Ergebnis, Übernahme manuell | wie ai-1 |
| Ereignisse | ein Ereignisprotokoll | Domain-Events, eigene Schreibvorgänge wecken niemanden | **Outbox** atomar mit Änderung, Event-ID gegen Doppelverarbeitung, Kettenlimit | Outbox + Schleifenschutz (3.5) |
| Heartbeat | fehlt | Heartbeat mit `HEARTBEAT_OK`, aktive Stunden | „fortlaufend“ mit Mindestpause | **übernehmen** als fünfte Auslöserart |
| Abbruchgründe | „Grenze überschritten“ | benannte `stop_reason` (max_steps, deadline, token_budget, no_progress …) | dto., plus Stillstandserkennung (3. identischer Aufruf) | übernehmen |
| Werkzeugantworten | „gelten als Daten“ | Untrusted-Rahmung jeder Werkzeugantwort | dto. | übernehmen, im Code statt nur im Prompt |
| LLM-Verbindungen | nur Admin | Admin (Org) | **persönliche** Verbindungen je Nutzer plus gemeinsame | Frage an Jan (5, Frage 4) |
| Dateien | Docling-Konvertierung | Anhänge, keine Konvertierung | „Wissensspeicher“ mit KI-Freigabe je Datei, PDF/DOCX-Text | Skizze + KI-Freigabe je Datei |
| Papierkorb | fehlt | Soft-Delete für Seiten/Tickets | Papierkorb mit Wiederherstellen | übernehmen |
| Mandanten | offen | `org_id` auf jeder Tabelle, eine Org je Installation | ein Workspace je Instanz | wie ai-1 |
| Migrationen | beim Start automatisch | Einzelinstanz: ja; **Cluster: einmaliger Job vor dem Rollout**, App verweigert Dienst bei altem Schema | beim Start mit Prüfsummen | wie ai-1 |
| Backup | Dump + Dateiablage | `backup.sh`/`restore.sh`, Restore live geprobt | Restic, verschlüsselt, S3/SFTP, Restore-Test in CI | ai-1 als Basis, Restic-Variante aus ai-2 als Option |
| Lizenz | offen | Apache-2.0, nur permissive Abhängigkeiten | Apache-2.0 | Apache-2.0 (5, Frage 5) |

### 1.3 Was aus `to-herd-cats-ai-2` besonders lohnt

- **Wiki-Zusammenarbeit**: funktionierende Tiptap/Yjs/Hocuspocus-Integration mit Rechteprüfung bei jeder Nachricht, „Generationen“ (Markdown-Speichern beendet die Live-Sitzung, alte CRDT-Stände können nichts überschreiben), Versionen je Person und 60-s-Fenster zusammengefasst, Grenzen je Dokument (3 MB Yjs, 80.000 Zeichen).
- **Laufabbruch** als eigener Datensatz, der nicht vom Fortschritt überschrieben werden kann, und eine transaktionale Prüfung vor dem Abschluss.
- **Freigaben sind an den Inhalt gebunden**: „Eine alte Freigabe autorisiert keinen veränderten Inhalt“ (P3).
- **Betrieb**: verschlüsselte Offsite-Backups, Restore nur in ein neues Volume, alte Sitzungen danach ungültig; i18n-Schlüsselprüfung in CI; Container ohne globale Paketmanager.

## 2. Ideen aus anderer Software

| Quelle | Was sie ist | Übernehmen | Nicht übernehmen |
|---|---|---|---|
| **Multica** | Open-Source-Board, auf dem man Issues an Coding-Agenten zuweist wie an Kollegen (Go + Next.js + Postgres) | Agenten erscheinen auf dem Board und in Kommentaren wie Menschen; Arbeit landet immer „zur Prüfung“; **Squads**: gemischtes Team mit einem Leiter, der Arbeit verteilt; **Autopilots** (Cron); Token-Verbrauch je Lauf, Agent *und Ticket*; **externe Laufzeiten**: ein lokaler Daemon startet Claude Code/Codex auf eigener Hardware | Eigene Lizenz (Apache-Text mit Zusatzbedingungen), also keinen Code übernehmen; Fokus auf Code-Repos |
| **Open WebUI** | Chat-Oberfläche mit RBAC, Wissensbasen, Werkzeugen | Gruppenrechte additiv; Trennung „Rechtegruppen“ vs. „Teilungsgruppen“; Standardmodell je Gruppe; Hinweis: nie Master-Schlüssel eines Gateways für Nutzerverkehr | Rechte pro Objekt (ACL je Modell/Wissensbasis); die Skizze vergibt Rechte bewusst nur am Bereich |
| **Wiki.js 3** (seit 1.11.2026) | Neuschreibung, nur Postgres 17/18, Visual-Editor speichert Markdown, Echtzeit-Bearbeitung, MCP-Server | **„KI“-Kennzeichen** an Agenten-Änderungen in der Historie; **Prüfung durch eine Gruppe** (Vorschläge auch für Menschen, nicht nur Agenten); **Regeln für veraltete Seiten** („seit 12 Monaten unverändert → prüfen“), ideal als Agentenaufgabe; MCP-Zugang als eigenes Recht (`use:mcp`), Token handelt mit den Rechten seines Besitzers | Wiki.js als Wiki-Kern: zweites Rechtemodell bleibt das Gegenargument. Als **Import- und Konnektor-Quelle** sinnvoll (Jans `mcp-wiki-js-ai` existiert) |
| **OpenClaw** | Persönlicher Agent mit Gateway, Kanälen, Skills, Gedächtnis | Läufe **je Sitzung serialisiert** (ai-1: Advisory Lock je Thread); nur Name und Beschreibung der Skills im Prompt; **zweistufiges Gedächtnis**: kuratierte `MEMORY`-Seite wird injiziert, Tagesnotizen werden nur durchsucht; Zeichenbudgets je Kontextdatei; Fremdinhalte mit festen Markern umschlossen; Konfiguration streng schema-validiert | Shell-Werkzeug mit Standard „volle Ausführung ohne Rückfrage“; Einzelnutzer-Vertrauensmodell |
| **Hermes Agent** | Selbstlernender Agent von Nous Research | **Lernschleife**: Agent schlägt nach gelöster Aufgabe einen Skill vor (bei uns als *Vorschlag*, den ein Mensch annimmt); **Erinnerung über frühere Läufe** per Volltextsuche; Bots mit eigenem Gedächtnis, die sich im Gruppenchat per @ ansprechen; Heartbeat/Cron mit Zustellung an Kanäle | Ausführung von Code und Terminal-Backends im selben Prozess; Hermes als Laufzeit (ADR 0003, Option D: Einzelbetreiber-Design) |

## 3. Das geschärfte Konzept: Änderungen an der Skizze

Die fünf Prinzipien der Skizze bleiben. Ein sechstes kommt dazu:

> **6. Jede Wirkung ist gebunden und prüfbar.** Eine Freigabe gilt für genau den Inhalt, den ein Mensch gesehen hat (Fingerabdruck). Ein Lauf prüft Rechte bei jedem Schritt neu. Jede Änderung trägt den auslösenden Lauf.

### 3.1 Architektur

- Modularer Monolith wie in der Skizze. Rollen im Image: `api`, `worker`, `collab` (Hocuspocus, Node). Standard: alle in einem Prozessverbund; im Cluster wählt eine Umgebungsvariable die Rolle.
- **Agenten-Schleife: Pydantic AI + DBOS** statt LangGraph (Begründung in 1.2). Freigaben sind `DBOS.recv` mit Zeitlimit, Läufe überstehen Neustarts, Zeitpläne laufen genau einmal im Cluster. Beide Bibliotheken werden nur in `runtime/` importiert.
- **Collab-Server** authentifiziert jede Verbindung über die API (`darf(principal, "page.edit", bereich)`) und prüft bei jeder Nachricht neu (Muster aus ai-2).
- Migrationen: Einzelinstanz automatisch beim Start; im Cluster ein einmaliger Job, die App startet nicht mit veraltetem Schema.

### 3.2 Rollen, Rechte, Bereiche

- **Vier Bereichsrollen**: Leser, Autor, Moderator, Verwalter. Moderator nimmt Vorschläge an (von Agenten und, optional je Bereich, von Menschen).
- **Zwei Schutzebenen**: harte Rechte am Bereich und eine **KI-Sperre je Seite/Datei** (Tag `kein-ki`), die eine Seite für alle Agenten unsichtbar macht, auch wenn der Bereich lesbar ist.
- Effektives Agentenrecht = Agentenrolle im Bereich ∩ Rechte des Auslösers ∩ Werkzeugfreigabe ∩ Autonomiestufe ∩ KI-Sperre. Prüfung **vor jedem Werkzeugaufruf und beim Fortsetzen** nach einer Freigabe.
- Gast als Systemrolle von Anfang an im Datenmodell: sieht nur Bereiche mit expliziter Mitgliedschaft, nie „offene“ Bereiche, keine Agenten anlegen. Die Oberfläche dafür kommt später.

### 3.3 Wiki

- **Markdown ist kanonisch** für Versionen, Suche, Agenten und Export. Yjs ist der Zustand einer *Live-Sitzung*.
- **Generationen** (aus ai-2): Markdown-Speichern, Wiederherstellen, Agenten-Schreibzugriff, Verschieben und Ändern der KI-Sperre beenden die laufende Yjs-Generation. Offene Editoren laden neu, alte CRDT-Stände können nichts überschreiben. Das löst den Konflikt „Agent schreibt, während Menschen live tippen“ ohne serverseitiges Yjs-Mergen in Python.
  - *Alternative für später*: Agentenänderungen als Yjs-Transaktion über den Collab-Server einspielen. Das wäre eleganter, ist aber deutlich aufwendiger.
- Versionen: automatisch nach Pause, zusammengefasst je Person und Sitzung (60 s), vor jedem Agenten-Schreibzugriff, manuell benannt. Agentenversionen tragen ein **KI-Kennzeichen** und den Link zum Lauf.
- **Papierkorb** statt Löschen; Agenten können nie löschen.
- **Veraltete Seiten**: je Bereich eine Frist; abgelaufene Seiten erscheinen im Eingang der Moderation oder werden einem Agenten als Prüfaufgabe gegeben.

### 3.4 Agenten

- **Autonomiestufen** (Skizze) sind eine Voreinstellung, die die Werkzeugrechte `allow / confirm / block` befüllt. Wer mehr Feinheit braucht, ändert einzelne Werkzeuge; Overlays von Admins können nur verschärfen.
- **Stop-Gründe** werden am Lauf gespeichert und angezeigt: `ziel_erreicht`, `max_schritte`, `zeitlimit`, `budget`, `kein_fortschritt` (dritter identischer Aufruf), `abgebrochen`, `rechte_entzogen`, `fehler`.
- **Gedächtnis** in zwei Stufen (OpenClaw/Hermes): eine kuratierte Notizseite je Agent (versioniert, von Menschen korrigierbar, mit Zeichenbudget, wird injiziert) plus durchsuchbares Laufarchiv (nicht injiziert, per Suchwerkzeug abrufbar).
- **Lernschleife**: Ein Agent kann nach einer Aufgabe einen neuen Skill oder eine Skill-Änderung *vorschlagen*. Der Vorschlag läuft durch dieselbe Moderation wie Wiki-Vorschläge.
- **Tickets**: Der Agent setzt höchstens „Zur Prüfung“. Verbrauch wird zusätzlich je Ticket summiert.
- **Auslöser**: direkt, Zuweisung, einmalig, wiederkehrend, Ereignis **und Heartbeat** (periodische Checkliste in aktiven Stunden; Ergebnis `HEARTBEAT_OK` wird protokolliert, aber nicht zugestellt).
- **Externe Laufzeit** (Idee aus Multica, für Stufe 7): Ein Agentenprofil kann statt der eingebauten Schleife einen externen Client nutzen (Claude Code, Codex), der über den MCP-Endpunkt mit einem Token dieses Agenten arbeitet. Rechte, Tickets und Audit bleiben dieselben.

### 3.5 Ereignisse

- Jede Änderung schreibt **in derselben Transaktion** einen Outbox-Eintrag. Ein Dispatcher verteilt an Changelog, Benachrichtigungen, Audit und Agenten-Auslöser.
- Schleifenschutz: Die eigene Änderung eines Agenten weckt ihn nicht; Ketten Agent → Ereignis → Agent haben eine maximale Tiefe (Vorschlag: 3); Ereignis-Auslöser haben eine Ruhezeit (Debounce).

### 3.6 Nachrichten

Die Skizze plant Kanäle, Direktnachrichten und Threads. Beide Vorgänger haben das bewusst kleiner gehalten (Postfach + Threads an Objekten, „kein Messenger-Ersatz“). Das ist eine Umfangsentscheidung für Jan (5, Frage 2). Unabhängig davon gilt: **ein** Nachrichtenmodell mit Anker (Kanal, Ticket, Seite, Agentenchat), @-Erwähnung startet bei Agenten einen Lauf, Zustellung live über WebSocket bzw. SSE mit Postgres `LISTEN/NOTIFY`.

### 3.7 KI-Anbindung und Suche

Wie in der Skizze, ergänzt um:
- Ratenlimit und Nebenläufigkeit **je Verbindung** (ai-1 ADR 0007).
- Modellrichtlinie je Bereich wird in der Schleife *vor* jedem Modellaufruf erzwungen: Treffer aus einem „nur lokal“-Bereich machen den Rest des Laufs „nur lokal“.
- Bei der Hybridsuche Quellversionen vor der Ausgabe erneut prüfen (Befund R01 aus ai-2: Text kann sich während des Embedding-Aufrufs ändern).

### 3.8 Ausbaustufen (angepasst)

Wenn auf `to-herd-cats-ai` aufgebaut wird, verschieben sich die Stufen der Skizze so:

| Skizze | Stand in ai-1 | Was fehlt noch |
|---|---|---|
| 1 Fundament | erledigt | Gastrolle, Outbox, Tags systemweit |
| 2 Wiki | erledigt ohne Live-Bearbeitung | Yjs/Hocuspocus mit Generationen, KI-Kennzeichen, Papierkorb, veraltete Seiten |
| 3 Tickets und Nachrichten | Tickets erledigt; Nachrichten nur als Agentenchat und Postfach | Kanäle/@-Erwähnungen (falls gewollt), Personen zuweisen in der UI |
| 4 KI-Grundlage | Verbindungen und Chat erledigt | Embeddings und Hybridsuche, Dateikonvertierung |
| 5 Agenten als Mitarbeiter | weitgehend erledigt | Autonomiestufen-Voreinstellung, Gedächtnis, Skill-Vorschläge, Stop-Gründe in der UI |
| 6 Automatisierung | weitgehend erledigt | Heartbeat-Unterdrückung, Webhooks, Budget je Agent und Bereich |
| 7 Öffnung und Skalierung | offen | MCP-Endpunkt, MCP-Server als Werkzeuge, Konnektoren, externe Laufzeit, Helm, lokaler Modus |

## 4. Empfehlungen zu den offenen Entscheidungen der Skizze

| Entscheidung | Empfehlung | Begründung |
|---|---|---|
| Backend-Sprache | **Python** mit Hocuspocus als Node-Prozess im selben Image | Beide Python-Gründe der Skizze stimmen; ai-1 ist schon Python; Hocuspocus ist in ai-2 und im edu-sharing-Editor erprobt. Eine reine Python-Variante (pycrdt-websocket) spart Node, ist aber weniger erprobt. |
| Agenten-Schleife (neu) | **Pydantic AI + DBOS**, nicht LangGraph | Entscheidung aus ADR 0003, in ai-1 umgesetzt und mit Wiederanlauf geprüft; spart Checkpointer-Plumbing und eigenen Scheduler |
| Frontend | **React** | Beide Vorgänger nutzen React; Tiptap, assistant-ui und shadcn sind React-first (ADR 0004) |
| Übernahme aus den Entwürfen | **ai-1 als Codebasis**, aus ai-2 Wiki-Zusammenarbeit, Abbruch-Semantik, inhaltsgebundene Freigaben, Backup-Variante | siehe 1.2 und 1.3; endgültig nur nach Frage 1 |
| Delegation zwischen Agenten | **zuerst nur über Tickets**, später ein Werkzeug `delegieren` mit Eltern-/Kind-Lauf | Tickets sind sichtbar, rechtegeprüft und prüfbar; direkte Delegation braucht Tiefenlimit und Rechte-Schnittmenge über die Kette, das ist Stufe 7 |
| Gastzugang | **im Datenmodell jetzt, Oberfläche später** | kostet wenig, weil jede Abfrage schon über die sichtbaren Bereiche filtert |
| Mandantenfähigkeit | **eine Organisation je Installation**, `org_id` überall | so in ai-1 umgesetzt; mehrere Organisationen werden später ein Schalter, kein Umbau |
| Lizenz | **Apache-2.0**, nur permissive Abhängigkeiten | beide Repos sind schon Apache-2.0; Docmost (AGPL), Multica (Zusatzbedingungen) und Tiptap-Pro-Erweiterungen meiden |

## 5. Fragen, die nur Jan beantworten kann

In der Reihenfolge ihrer Wirkung:

1. **Weiterbauen oder Neuanfang?** `to-herd-cats-ai` deckt etwa vier der sieben Stufen schon ab. Wofür ist das neue Repo `to-herd-cats-ai-harness` („AI harness with knowledge-base“) gedacht: als neues Zuhause für den Code von ai-1, als bewusster Neuanfang, oder als etwas anderes, etwa eine reine Agenten-Laufzeit neben dem Cockpit? Was hat an ai-1 oder ai-2 nicht gereicht, sodass ein dritter Anlauf nötig ist?
2. **Wie viel Kommunikation?** Echte Teamkanäle und Direktnachrichten (ein kleines Slack im System), oder Postfach plus Threads an Tickets, Seiten und Agenten, wie beide Vorgänger es entschieden haben?
3. **Private Bereiche vor Admins verbergen?** Die Skizze will, dass Admins privaten Inhalt nicht sehen; ai-1 lässt Admins alles sehen. Verbergen erhöht das Vertrauen, macht aber Wiederherstellung nach Austritt, Rechtsauskünfte und Missbrauchsprüfung schwerer.
4. **Persönliche KI-Schlüssel?** ai-2 erlaubt jedem Nutzer eigene LLM-Verbindungen; die Skizze nur den Admin. Persönliche Schlüssel erleichtern das Ausprobieren, unterlaufen aber Modellrichtlinien und Budgets je Bereich.
5. **Offen veröffentlichen?** Beide Repos tragen Apache-2.0. Ist eine öffentliche Veröffentlichung geplant? Das entscheidet, wie streng Abhängigkeiten geprüft werden müssen.
6. **Externe Laufzeiten (Multica-Idee)?** Sollen Claude Code oder Codex später als „Mitarbeiter“ auf Tickets arbeiten können, oder bleiben Agenten auf die eingebaute Schleife beschränkt?

## 6. Quellen

- `janschachtschabel/to-herd-cats-ai` (README, CLAUDE.md, docs/CONCEPT.md, docs/ROADMAP.md, ADR 0001–0008, Design-Spec 2026-09-02)
- `janschachtschabel/to-herd-cats-ai-2` (README, docs/PROJEKTPLAN.md, WEITERENTWICKLUNG-0.2.md, OPEN_SOURCE.md, AGENTEN.md, WIKI-BACKUP.md, audits/2026-09-09-review.md)
- Multica: https://github.com/multica-ai/multica
- Open WebUI RBAC: https://docs.openwebui.com/features/authentication-access/rbac
- Wiki.js 3: https://blog.elest.io/wiki-js-3-what-changed-and-how-to-migrate-from-2-x/ (Angaben aus einem Blogbeitrag, nicht selbst getestet)
- OpenClaw: https://clawdocs.org/architecture/overview
- Hermes Agent: https://hermes-agent.nousresearch.com/docs
