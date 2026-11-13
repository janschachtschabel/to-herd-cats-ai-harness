# to-herd-cats-ai — Design-Spezifikation

Stand: 12. Nov. 2026 · Status: **freigegeben von Jan am 12.11.2026** (F1–F3 mit den Empfehlungen) · Lizenz des Projekts: Apache-2.0
Vorarbeiten: [Konzeptabgleich](2026-11-12-konzept-abgleich-design.md), Ideenskizze vom 12.11.2026, Jans Antworten vom 12.11.2026.
Repos, aus denen Code übernommen werden darf: `janschachtschabel/to-herd-cats-ai` (im Folgenden **ai-1**) und `janschachtschabel/to-herd-cats-ai-2` (**ai-2**).

Dieses Dokument sagt, *was* gebaut wird und *welche* Entscheidungen feststehen. Die Umsetzungspläne unter `docs/superpowers/plans/` sagen, *in welcher Reihenfolge* und *mit welchen Tests*.

---

## 1. Absicht

Ein selbst betriebenes Arbeitssystem für Teams, in dem **Menschen und KI-Agenten dieselbe Art von Teammitglied** sind. Gemeinsames Wissen liegt in einem Wiki, gemeinsame Arbeit in Tickets und gemeinsame Kommunikation in Kanälen im Slack-Stil. Alle drei hängen an **Bereichen** mit einem einzigen Rechtemodell. Agenten werden wie Kolleginnen eingesetzt: Man weist ihnen Tickets zu, erwähnt sie im Kanal oder plant ihre Arbeit. Ihre Grenzen setzt der Code, nicht der Prompt.

Der Neustart im Repo `to-herd-cats-ai-harness` ist gewollt. Die beiden Vorgänger kannten kein vollwertiges Ticketsystem und kein Nachrichtensystem, und Jan möchte einen sauberen Start. Code aus ai-1 und ai-2 wird übernommen, wo seine Qualität stimmt und es die Arbeit beschleunigt (Abschnitt 13).

### Ziele

1. Ein Team kann **ohne KI** produktiv arbeiten: Wiki, Suche, Tickets, Kanäle. Die KI ist eine Erweiterung, keine Voraussetzung, und lässt sich je Person abschalten.
2. Ein Agent kann auf Ticket, Erwähnung, Zeitplan oder Ereignis hin mehrschrittig arbeiten. Er sieht dabei nie mehr als die Person, für die er arbeitet, und richtet nichts an, was sich nicht zurückdrehen oder vorher freigeben lässt.
3. Admins richten die KI-Anbindung zentral ein und weisen sie zu. Verbrauch, Kosten und sicherheitsrelevante Aktionen werden zentral mitgeschrieben.
4. Der Betrieb erfolgt in einem Container mit Postgres oder skaliert im Cluster mit demselben Image. Logging, Tracing, Proben, Metriken und Helm folgen dem Betriebsleitfaden (Abschnitt 11).

### Nicht-Ziele (v1)

- Kein Ersatz für E-Mail. Externe Kanäle (E-Mail, Slack, Teams, Matrix) kommen später als Adapter.
- Keine Ausführung von beliebigem Code oder Shell durch Agenten im App-Prozess.
- Mehrere Organisationen sind in der Oberfläche nicht vorgesehen. `org_id` steht trotzdem auf jeder Tabelle, siehe Entscheidung E9.
- Keine mobile App. Die Weboberfläche ist responsiv.
- Keine eigenen Workflow-Engines (Kestra o. Ä.). Abläufe sind Agenten-Läufe.

### Anti-Ziele (wäre ein Fehlschlag, auch wenn es technisch läuft)

- Ein Agent liest oder schreibt etwas, das sein Auftraggeber nicht dürfte.
- Kanäle versinken in System- und Ticketmeldungen.
- Ein Modul hat eine eigene Rechteprüfung neben der zentralen.
- Ein Feld, eine Tabelle oder ein Dienst existiert „für später“ und wird von keinem getesteten Code gelesen. Diese Regel stammt aus ADR 0001 von ai-1.

---

## 2. Feste Entscheidungen

Mit **[Jan]** markierte Entscheidungen hat Jan getroffen. Mit **[Claude]** markierte sind meine Wahl mit Begründung; Jan kann sie korrigieren.

| # | Entscheidung | Quelle |
|---|---|---|
| E1 | Neustart im Repo `to-herd-cats-ai-harness`; Code aus ai-1/ai-2 nur nach Prüfung übernommen | [Jan] |
| E2 | Lizenz Apache-2.0; Laufzeitabhängigkeiten nur mit MIT-, MIT-0-, BSD-2-Clause-, BSD-3-Clause-, 0BSD-, Apache-2.0-, ISC-, PostgreSQL-, PSF-2.0-, Python-2.0-, MPL-2.0- (unverändert genutzt), Unlicense-, CC0-1.0-, BlueOak-1.0.0- oder OFL-1.1-Lizenz (Schriften); die schwachen Copyleft- und Public-Domain-Lizenzen sind mit einer Apache-2.0-Verteilung vereinbar. Die CI prüft das. Keine AGPL-Bausteine, keine Tiptap-Pro-Erweiterungen | [Jan], Abhängigkeitsregel [Claude], erweitert in M1 (transitive Abhängigkeiten wie certifi, typing_extensions, Schriften) |
| E3 | Kanäle und Direktnachrichten im Slack-Stil, dazu Threads an Tickets und Seiten. **Kein separates Postfach**: System und Agenten schreiben ins Nachrichtensystem. System- und Ticketmeldungen sind sichtbar von normaler Kommunikation getrennt (Abschnitt 6) | [Jan] |
| E4 | Admins sehen alles. Andere sehen private Inhalte nicht. Gemeinsames gehört in Wissens- oder Teambereiche | [Jan] |
| E5 | KI zentral: Admins richten Verbindungen ein und weisen sie Personen oder Gruppen zu, dazu eine Standardzuordnung. Personen ohne KI sind möglich. Keine persönlichen Schlüssel. Verbrauch wird zentral erfasst | [Jan] |
| E6 | Standardanbieter ist OpenAI mit freier Basis-URL und freier Modellwahl, Standardmodell `gpt-6-luna`. Die b-api ist eine optionale Verbindungsart | [Jan] |
| E7 | Externe Agenten (Claude Code, OpenAI Codex) kommen später (Meilenstein 8) | [Jan] |
| E8 | Backend in Python 3.13 mit FastAPI, SQLAlchemy 2 (async) und Alembic. Frontend in React 19 mit TypeScript, Vite, Tailwind 4, shadcn/ui, TanStack Router/Query und i18next | [Claude]: beide Vorgänger, ADR 0004 von ai-1 |
| E9 | Nur PostgreSQL (≥ 16, mit pgvector). `org_id` auf jeder Tabelle, eine Organisation je Installation | [Claude]: ai-1 Regel 1 und 2 |
| E10 | Agenten-Schleife mit **Pydantic AI**, dauerhafte Ausführung, Zeitpläne und Warteschlangen mit **DBOS** auf Postgres. Beide werden nur in `app/runtime/` importiert | [Claude]: ai-1 ADR 0003, Wiederanlauf dort live geprüft. LangGraph ist ausgeschlossen, weil der erste Versuch davon weggegangen ist |
| E11 | Live-Bearbeitung mit Tiptap 3, Yjs und **Hocuspocus** (Node) als Prozess im selben Image. Markdown ist kanonisch; Yjs ist der Zustand einer Live-Sitzung mit **Generationen** | [Claude]: in ai-2 erprobt |
| E12 | Live-Zustellung an Browser über **Server-Sent Events**, verteilt über Postgres `LISTEN/NOTIFY` | [Claude]: Senden läuft über REST, Empfangen reicht in eine Richtung; SSE funktioniert durch jeden HTTP-Proxy, und ai-1 nutzt es schon |
| E13 | **Ein Image** mit den Rollen `api`, `worker` und `collab` über `HERD_ROLE` und Standard `all`. Zwei Ports: öffentlich 8080 (API, SPA, SSE, `/collab`) und intern 9090 (`/health`, `/ready`, `/metrics`, interne Collab-Schnittstelle) | [Claude]: Skizze und Betriebsleitfaden |
| E14 | Dienst-ID überall `to-herd-cats-ai`: Logs (`service`), `OTEL_SERVICE_NAME`, Image, Helm-Chart | [Claude]: Betriebsleitfaden |

---

## 3. Lösungswege (Approaches)

Drei Wege wurden betrachtet:

| Weg | Inhalt | Für | Gegen |
|---|---|---|---|
| **A: ai-1 weiterbauen** | ai-1 ins neue Repo kopieren und Nachrichten und Tickets ergänzen | schnellster Weg zu Funktionen | Jan will bewusst neu anfangen; ai-1 hat Postfach und Tickets in einer Form, die nicht zu E3 passt; seine Frontend-Struktur (Chat-Seite mit assistant-ui) passt nicht zum Slack-Modell |
| **B: Neustart mit gezielter Übernahme** (gewählt) | neues Gerüst nach dieser Spezifikation; aus ai-1/ai-2 werden einzelne, geprüfte Module übernommen (Abschnitt 13) | sauberes Datenmodell für Nachrichten und Tickets von Anfang an; bewährte Teile (Rechte, Secrets, SSRF, Speicher, Laufzeit-Adapter, Yjs-Muster) bleiben erhalten | mehr Arbeit als A in den ersten zwei Meilensteinen |
| **C: Neustart ohne Übernahme** | alles neu | keine Altlasten | verschenkt geprüften Code; widerspricht Jans Angebot |

---

## 4. Architektur

### 4.1 Bausteine

```
Browser (React-SPA) ──HTTPS──► :8080  api      (FastAPI: REST, SSE, /mcp, statische SPA, /collab-WS-Weiterleitung)
                                       │
Externe KI-Clients ──HTTPS──► :8080  /mcp     (gleiche Service-Schicht, Token-Rechte)
                                       │
                               collab (Node, Hocuspocus) ◄─ interne Aufrufe ─► api :9090/internal/*
                                       │
                               worker (DBOS: Agenten-Läufe, Zeitpläne, Outbox-Verteiler, Indexierung, Konvertierung)
                                       │
                               PostgreSQL (Daten, Volltext, pgvector, DBOS-Zustand, Yjs-Stände, Sitzungen, Outbox)
                               Dateiablage (Volume oder S3-kompatibel)
```

- **Service-Schicht**: Jede fachliche Aktion ist eine Methode eines `*Service` in `app/modules/<domain>/service.py`. Router, Agenten-Werkzeuge, MCP-Endpunkt und interne Collab-Schnittstelle rufen ausschließlich Services auf (Prinzip 3 der Skizze).
- **Schichten** nach ai-1: `router → service → repository`. SQL steht nur in Repositories, Regeln nur in Services.
- **Rollen**: Bei `HERD_ROLE=all` startet ein Python-Startprogramm API und Worker im selben Prozessverbund und den Collab-Prozess (Node) als Kindprozess, der auf `127.0.0.1:1234` lauscht. Die API leitet `/collab` per WebSocket dorthin weiter. Im Cluster laufen `api`, `worker` und `collab` als eigene Deployments; auch dort leitet die API `/collab` an `collab` weiter. *Geändert in M2: Ursprünglich leitete der Ingress `/collab` direkt an `collab`. Die API prüft aber vor dem Weiterleiten Origin, Sitzungs-Cookie, Sichtbarkeit, `page.edit` und die Generation mit demselben Code wie die REST-API; so bleibt `collab` ein interner Dienst ohne eigenen Zugang von außen (NetworkPolicy: nur API-Pods), und der Ingress braucht keine eigene Pfadregel. Den Collab-Prozess startet `all` nur, wenn `HERD_INTERNAL_TOKEN` gesetzt ist; der Worker kommt mit M3.*
- **Migrationen**: Bei `HERD_ROLE=all` laufen sie beim Start automatisch. Im Cluster läuft ein einmaliger Job (`HERD_ROLE=migrate`, Helm-Hook), und `/ready` meldet „nicht bereit“, solange die Datenbank keine oder eine ältere, dem Code bekannte Revision hat. Steht sie auf einer Revision, die der Code nicht kennt (eine neuere Version hat vorab migriert), bleibt der Pod bereit. Deshalb müssen Migrationen mit der vorherigen Version verträglich sein: erst erweitern, frühestens eine Version später zurückbauen (expand/contract). *Geändert in M1, Task 14: Mit der strengen Regel „Revision = Head“ wurden die alten Pods bei jedem Upgrade mit Migration sofort nicht bereit, also ein Ausfall pro Upgrade.*

### 4.2 Die eine Rechteprüfung

```python
async def can(actor: Actor, action: Action, space_id: UUID | None) -> bool
def visible_space_ids_sql(actor: Actor) -> Select   # für Filter in Listen und Suche
```

`Actor` ist der handelnde Principal samt Kontext: Mensch, Agent im Auftrag einer Person, Agent im eigenen Auftrag (Zeitplan) oder Token (MCP).

`Action` ist ein Enum aus dem Rechtekatalog (Abschnitt 5.3).

Listen und Suche filtern in SQL über `visible_space_ids_sql`, nie erst im Ergebnis.

### 4.3 Ereignisse (Outbox)

Jede Service-Methode, die etwas ändert, schreibt **in derselben Transaktion** einen Eintrag in `event_outbox` mit `id`, `type`, `actor`, `space_id`, `subject_type`, `subject_id`, `payload`, `caused_by_run_id` und `depth`.

Ein Verteiler im Worker (DBOS-Workflow) holt Einträge mit `FOR UPDATE SKIP LOCKED` und verteilt sie an:

- Systemnachrichten in Objekt-Threads,
- Benachrichtigungen,
- Agenten-Auslöser,
- Suchindex,
- Live-Zustellung (`NOTIFY`).

*Geändert in M3: Bis M6 ist der Verteiler kein DBOS-Workflow, sondern eine einfache Schleife in der Rolle `worker` (in `all` enthalten): Stapel mit `FOR NO KEY UPDATE SKIP LOCKED`, je Handler ein Zustellnachweis in derselben Transaktion wie seine Wirkung, Wiederholung mit wachsender Wartezeit, mindestens einmal zugestellt, Handler idempotent. DBOS kommt mit seinem ersten echten Leser, den dauerhaften Agenten-Läufen (M6) und Zeitplänen (M7); Plan M3, Entscheidung 1.*

Das Audit-Protokoll wird **synchron** in derselben Transaktion geschrieben und nicht über die Outbox.

Schutz vor Schleifen:

- Ein Ereignis, das ein Agent verursacht hat, löst diesen Agenten nie aus.
- `depth` steigt bei jedem Agenten-Lauf, der aus einem Ereignis entsteht. Ab `depth > 3` werden keine Agenten mehr ausgelöst.
- Ereignis-Auslöser haben eine Ruhezeit (Standard 60 s), in der gleiche Ereignisse zusammengefasst werden.

---

## 5. Identität, Bereiche und Rechte

### 5.1 Principals

- **Mensch** (`user`): lokales Konto mit argon2id-Passwort. OIDC ist optional (Meilenstein 9) und wird über Subject oder bestätigte E-Mail verknüpft.
- **Agent** (`agent`): Profil (Abschnitt 8) mit einer verantwortlichen Person.
- **Gruppe** (`group`): Menschen und Agenten; kann Mitglied von Bereichen sein.

Urheberschaft wird überall als `(principal_type, principal_id)` gespeichert, zum Beispiel bei `created_by`, Versionen und Nachrichten.

### 5.2 Systemrollen

| Systemrolle | Bedeutung |
|---|---|
| `owner` | wie Admin; es gibt mindestens einen |
| `admin` | sieht und verwaltet alles (E4) |
| `member` | normale Person |
| `guest` | sieht nur Bereiche mit ausdrücklicher Mitgliedschaft, nie offene Bereiche; darf keine Bereiche anlegen und keine Agenten auslösen |

Dazu kommen **Funktionsrechte**, die über Gruppen ergänzt werden können. Rechte addieren sich nur; es gibt keine Rechte, die etwas abziehen. Unabhängig davon steht `ai.use` (Abschnitt 7) als eigenes Feld an der Person.

### 5.3 Bereiche

| Art | Sichtbar für | Zweck |
|---|---|---|
| `open` | alle `member` mit der Rolle `viewer` (lesen und in Kanälen schreiben), dazu Mitglieder je Rolle; Gäste nur bei ausdrücklicher Mitgliedschaft | Wissensbereiche, z. B. „Handbuch“. Bei der Einrichtung entsteht der offene Bereich „Allgemein“; sein Kanal `#allgemein` kommt in M3 |
| `team` | nur Mitglieder; für andere weder in Navigation noch in Suche | Teams und Projekte |
| `personal` | genau eine Person, automatisch je Person angelegt | eigene Notizen, Entwürfe, private Agenten |

Admins sehen alle drei Arten (E4). Wer kein Admin ist, sieht fremde `personal`- und `team`-Bereiche nicht, auch nicht deren Existenz.

**Bereichsrollen**:

| Rolle | Darf |
|---|---|
| `viewer` (Leser) | lesen, in Kanälen und Threads schreiben, reagieren |
| `editor` (Autor) | zusätzlich Seiten und Tickets anlegen und bearbeiten, eigene Seiten veröffentlichen |
| `moderator` | zusätzlich alle Seiten veröffentlichen, in den Papierkorb legen und wiederherstellen; Vorschläge annehmen oder ablehnen; Tickets zuweisen; Kanäle verwalten |
| `admin` (Verwalter) | zusätzlich Mitglieder, Einstellungen und KI-Richtlinie des Bereichs |

Die wirksame Rolle ist das Maximum aus direkter Mitgliedschaft und Gruppenmitgliedschaften.

**Rechtekatalog**:

- Bereichsbezogen: `space.read`, `space.manage`, `page.create`, `page.edit`, `page.publish`, `page.trash`, `page.moderate`, `ticket.read`, `ticket.create`, `ticket.edit`, `ticket.assign`, `channel.post`, `channel.manage`.
- Systemweit: `space.create`, `user.manage`, `group.manage`, `ai.manage`, `agent.manage`, `agent.create_personal`, `connector.manage`, `skill.manage`, `audit.read`, `mcp.use`, `directory.read` (Personen und Gruppen nach Namen suchen, nie nach E-Mail, um sie Bereichen hinzuzufügen; alle außer Gästen; zeigt nur Typ, ID und Name aktiver Personen und Gruppen).

### 5.4 Rechte von Agenten

Ein Agent hat eigene Bereichsmitgliedschaften wie ein Mensch. **Wirksam** ist die Schnittmenge aus:

1. der Bereichsrolle des Agenten,
2. den Rechten des Auslösers (Person, Token oder bei Zeitplänen die verantwortliche Person),
3. der Werkzeugfreigabe am Agenten (`allow`, `confirm`, `block`),
4. der Autonomiestufe (Abschnitt 8.2),
5. der KI-Sperre der Seite oder Datei (`no_ai`),
6. der KI-Richtlinie des Bereichs (Abschnitt 7.3).

Die Prüfung läuft **vor jedem Werkzeugaufruf** und **beim Fortsetzen nach einer Freigabe** erneut. Wurden Rechte entzogen, endet der Lauf mit `stop_reason=rights_revoked`. Dieses Muster stammt aus ai-2.

**Wer zählt als Auslöser?** [Claude]

| Auslöser | Rechte und Abrechnung |
|---|---|
| Erwähnung oder Direktnachricht | die schreibende Person |
| Ticketzuweisung | die zuweisende Person |
| Übergabe von Agent zu Agent per Ticket | die **ursprüngliche** Person der Kette; sie wird als `origin_user_id` am Lauf weitergegeben |
| Zeitplan, Heartbeat, Ereignis | die verantwortliche Person des Agenten |

Freigaben gehen an diese Person. Fehlt sie, gehen sie an die verantwortliche Person. Ist die verantwortliche Person deaktiviert, starten keine Läufe.

### 5.6 Publikumsregel: Was ein Agent ausgeben darf [Claude, siehe F3]

Die Schnittmenge in 5.4 schützt das **Lesen**. Ein Agent schreibt aber in Gespräche mit eigenem Publikum. Damit dort nichts durchsickert, wird der Lesebereich eines Laufs zusätzlich auf das **Publikum des Ausgabeorts** begrenzt:

- **Kanal, Ticket oder Seiten-Thread in Bereich S:** Der Lauf liest nur S und `open`-Bereiche. Ist S ein `open`-Bereich, liest er nur `open`-Bereiche.
- **Direktnachricht:** Der Lauf liest nur Bereiche, die **alle** Teilnehmenden sehen. Das sind höchstens 9 Personen, die Schnittmenge ist also billig zu berechnen.
- **Persönlicher Bereich oder Direktnachricht allein mit dem Agenten:** Es gelten die vollen Rechte der Person (∩ Agent).
- **Zeitplan oder Ereignis:** Das Publikum ergibt sich aus dem Zustellort des Auslösers (`deliver_to`).

Umgesetzt wird das als Feld `read_scope` am `Actor` eines Laufs, das `can()` und `visible_space_ids_sql` zusätzlich anwenden. Das Feld kommt in M5/M6. Der Rechtekern aus M1 nimmt es als optionalen Filter auf, ohne Umbau.

### 5.5 Gesehen von Admins

Admins können jeden Bereich öffnen (E4). Das Öffnen eines `personal`- oder `team`-Bereichs, in dem der Admin kein Mitglied ist, wird im Audit vermerkt.

**Direktnachrichten** sind keinem Bereich zugeordnet. Admins sehen sie nur über eine ausdrückliche, begründete und protokollierte „Einsicht“ in der Verwaltung, nicht in der normalen Navigation. Das ist meine Lesart von E4 mit Blick auf Datenschutz; Jan kann sie ändern (Frage F1).

---

## 6. Nachrichten

### 6.1 Modell

Es gibt ein einziges Nachrichtenmodell.

- **`conversation`** mit `kind`:
  - `channel`: gehört zu einem Bereich; die Zielgruppe sind die Mitglieder des Bereichs.
  - `dm`: 2 bis 9 Teilnehmende, Menschen und Agenten.
  - `thread_ticket` und `thread_page`: genau ein Gespräch je Ticket bzw. je Seite, mit den Rechten des Bereichs.
- **`message`** mit:
  - `conversation_id`,
  - `parent_id` für Antworten in einem Thread (eine Ebene),
  - `author` (Principal oder `system`),
  - `kind`: `human`, `agent` oder `system`,
  - `body_md`,
  - `card` (JSON für strukturierte Karten: Freigabe, Laufergebnis, Ticketänderung),
  - `run_id`, `edited_at`, `deleted_at`.
- **`message_mention`** und **`reaction`**.
- **`conversation_read`** mit dem Lesestand je Person und Gespräch.
- **`notification`**: Empfänger, Grund (`mention`, `reply`, `assignment`, `approval`, `run_result`, `review_request`, `due`), Verweis auf eine Nachricht oder ein Objekt, `read_at`, `done_at`.

### 6.2 Übersichtlichkeit (Trennung von System und Gespräch)

- **Kanäle und Direktnachrichten** enthalten nur Nachrichten der Arten `human` und `agent`. Agenten-Nachrichten tragen ein „KI“-Kennzeichen und den Link zum Lauf.
- **Systemmeldungen** (`system`) entstehen nur in Ticket- und Seiten-Threads. Dort stehen sie als kompakte, graue Zeitleisten-Einträge zwischen den Kommentaren, ähnlich wie bei GitHub. Sie lassen sich per Schalter ausblenden.
- **„Aktivität“** ist die persönliche Ansicht, die das Postfach ersetzt. Sie hat drei Reiter:
  - „Für mich“: Erwähnungen, Antworten und Zuweisungen,
  - „Freigaben“: Agenten warten auf eine Entscheidung,
  - „Abläufe“: Ergebnisse geplanter Läufe und Systemhinweise.

  Jeder Eintrag führt in sein Gespräch. Freigaben lassen sich direkt in der Karte erteilen.
- Ein Kanal kann ein Ticket **verlinken**. Dann erscheint eine einzelne, sich aktualisierende Karte statt vieler Einzelmeldungen.

Skizze der Seitenleiste:

```
┌──────────────────────┐
│ 🔔 Aktivität     (3) │
│ 🔍 Suche             │
│ ── Kanäle ────────── │
│ # allgemein          │
│ # team-dienste       │
│ ── Direkt ────────── │
│ ● Mia (KI)           │
│ ● Jan, Lea           │
│ ── Bereiche ──────── │
│ 📚 Handbuch          │
│ 👥 Team Dienste      │
│ 🔒 Mein Bereich      │
│ ── Arbeit ────────── │
│ ☑ Tickets            │
│ 🤖 Team & Agenten    │
└──────────────────────┘
```

### 6.3 Agenten im Nachrichtensystem

- `@agent` in einem Kanal oder Thread startet einen Lauf, sofern die schreibende Person `ai.use` hat. Die Antwort landet als Thread-Antwort auf die erwähnende Nachricht.
- Eine Direktnachricht mit einem Agenten ist der „Chat mit dem Agenten“. Jede Nachricht startet einen Lauf mit dem bisherigen Gesprächsverlauf als Kontext. Der Verlauf wird nach Zeichen begrenzt; das Muster `history_window` stammt aus ai-1.
- Während des Laufs zeigt eine Fortschrittskarte die Schritte live über SSE. Die Antwort erscheint als fertige Nachricht. Token-Streaming kommt später; die b-api bricht Streams ohnehin nach 30 s ab.
- Pro Gespräch läuft höchstens ein Agentenlauf zugleich. Die Sperre ist ein Postgres Advisory Lock (ai-1).

### 6.4 Live-Zustellung

`GET /api/stream` (SSE) liefert je Sitzung die Ereignisse `message.created|updated|deleted`, `notification.created`, `run.progress` und `presence` (nur Lesestand).

Fan-out: Der Service schreibt, ein Trigger oder der Verteiler ruft `NOTIFY herd_live, '<json mit ids>'`, jeder API-Knoten lauscht und filtert je Verbindung nach Rechten. Die Nutzlast enthält nur IDs; der Client lädt Inhalte nach. So verlassen keine Daten die Rechteprüfung.

---

## 7. KI-Anbindung, Zuordnung und Verbrauch

### 7.1 Verbindungen (nur Admins, `ai.manage`)

| Feld | Bedeutung |
|---|---|
| `kind` | `openai` (Standard), `openai_compatible`, `b_api`, `local` |
| `base_url` | frei; Standard `https://api.openai.com/v1` |
| `secret_ref` | `enc:`/`env:` wie in ai-1, nie im Klartext und nie im Log |
| `models` | ermittelt über `/models` oder von Hand eingetragen; Standardmodell `gpt-6-luna` |
| `param_family` | `max_completion_tokens` (GPT-5/6) oder `max_tokens` (ältere und offene Modelle) |
| `extra_body` | JSON, das jedem Aufruf beigefügt wird, z. B. `reasoning_effort: "none"` für Tool-Calling mit `gpt-6-luna` |
| `supports_tools` | ja/nein |
| `data_location` | `local`, `eu` oder `external`; wird von der Bereichsrichtlinie (7.3) ausgewertet |
| `max_concurrency`, `requests_per_minute` | Grenzen je Verbindung |
| `purpose` | `chat`, `embedding` oder beides |

Bei **b-api**-Verbindungen wird im Feld `model` ein **Routenname** statt eines Modellnamens geschickt. Antworten mit Status 401, 402, 403 oder 429 führen zu `stop_reason=provider_refused` mit einem verständlichen Grund, ohne Wiederholung. Streaming ist bei b-api-Verbindungen aus.

### 7.2 Zuordnung

- Für die Organisation gibt es eine **Standardzuordnung** (Chat-Verbindung und Modell) und eine **Embedding-Verbindung**. Die Embedding-Verbindung ist organisationsweit, weil der Index einheitlich sein muss.

**Embedding lokal und fest** [Jan, 12.11.2026]: Das Embedding läuft standardmäßig mit einem **lokalen Modell im Worker**. Es ist damit unabhängig von API-Anbietern und von Wechseln des Chat-Modells, und es verlassen keine Inhalte das System. Eine externe Embedding-Verbindung bleibt als Option. Das Modell muss Deutsch können, besser mehrsprachig sein. Die Modellwahl ist offen und wird in der M5-Planung mit einem Vergleich entschieden. Kandidaten:

| Kandidat | Art | Erwartung |
|---|---|---|
| `multilingual-e5-small` | Transformer, 384 Dimensionen | gute Qualität, mäßige CPU-Last |
| `paraphrase-multilingual-MiniLM-L12-v2` | Transformer, 384 Dimensionen | ähnlich, älter |
| `JanSchachtschabel/m2v-qwen3-4b-256-edu` | statisches Modell (Model2Vec), 256 Dimensionen | um ein Vielfaches schneller, ohne Torch nutzbar, eventuell weniger feinfühlig; könnte im Verbund mit der Volltextsuche reichen |

Der Vergleich in M5 misst auf deutschen Wiki- und Ticket-Texten die Trefferqualität der **Hybridsuche** (Recall@10, MRR), nicht des Embeddings allein. Dazu kommen Durchsatz auf CPU, RAM-Bedarf und Größe (das Modell kommt über ein Volume, nicht ins Image). Mit einem lokalen Modell hat die Embedding-Verbindung `data_location=local`, sodass auch `restricted`-Bereiche indexiert werden.
- `ai_assignment` gilt je Gruppe oder je Person, überschreibt den Standard und kann auf Personenebene „keine KI“ setzen. Vorrang hat Person vor Gruppe vor Standard.
- `ai.use` ergibt sich aus der Zuordnung. Personen ohne KI sehen keine KI-Funktionen: Sie können keine Agenten erwähnen, keine Direktnachrichten an Agenten schreiben, keine Tickets an Agenten zuweisen und keine Agenten verwalten. Agenten-Beiträge anderer lesen sie normal.
- Agenten haben ihre **eigene** Verbindung und ihr eigenes Modell, beides vom Admin gewählt. Der Verbrauch wird trotzdem der auslösenden Person, dem Agenten und dem Bereich zugerechnet.

### 7.3 KI-Richtlinie je Bereich

`ai_policy` hat die Werte:

- `any`: Standard.
- `restricted`: Nur Verbindungen mit `data_location ∈ allowed_locations` dürfen Inhalte des Bereichs erhalten.
- `none`: Agenten sehen den Bereich nicht. Es entstehen keine Embeddings; die Suche nutzt nur den Volltext.

Embeddings eines `restricted`-Bereichs entstehen nur, wenn `data_location` der Embedding-Verbindung erlaubt ist. Sonst wird der Bereich nur im Volltext gesucht. [Claude]

Die Schleife markiert jeden Lauf mit der strengsten Richtlinie aller bisher gelesenen Inhalte. Vor jedem Modellaufruf prüft sie, ob die Verbindung des Agenten diese Richtlinie erfüllt. Ist das nicht der Fall, endet der Lauf mit `stop_reason=policy_blocked`. Inhalte gelangen also nie an eine unzulässige Verbindung.

### 7.4 Verbrauch und Budgets

`usage_record` wird je Modellaufruf und je Embedding-Stapel geschrieben, mit org, Person, Agent, Lauf, Bereich, Verbindung, Modell, Tokens (ein, aus, gecacht), Kosten (sofern ein Preis hinterlegt ist) und Dauer.

Budgets:

- Tageslimit in Tokens oder Euro je Person, je Agent und für die Organisation,
- Schritte und Laufzeit je Lauf (Agentenprofil).

Die Prüfung erfolgt vor jedem Modellaufruf. Die Verwaltungsansicht zeigt Verbrauch je Person, Agent, Bereich und Tag.

---

## 8. Agenten

### 8.1 Profil

| Feld | Inhalt |
|---|---|
| Identität | Name, Avatar, Rollenbezeichnung, Kurzvorstellung (für Kolleginnen), Persönlichkeit |
| Anweisungen | Systemanweisung (Markdown) |
| Modell | Verbindung und Modell, optional ein Ersatzmodell |
| Bereiche | Mitgliedschaften wie bei Menschen |
| Werkzeuge | Liste von Freigaben `{tool, policy: allow|confirm|block}` |
| Skills | zugeordnete Skills |
| Autonomiestufe | 1 bis 4 (8.2) |
| Grenzen | max. Schritte (Standard 25), max. Laufzeit (Standard 10 min), Tagesbudget |
| Verantwortlich | Person; erhält Freigabeanfragen und Fehler |
| Gedächtnis | eine Seite **je Bereich**, in dem der Agent arbeitet (8.5) |
| Art | `builtin`; `external` folgt in Meilenstein 8 |
| Status | `draft`, `active`, `paused` |

`agent.manage` (Admin) legt Agenten für die Organisation an. `agent.create_personal` erlaubt Personen mit `ai.use`, Agenten anzulegen, die nur im eigenen persönlichen Bereich Mitglied sein dürfen.

### 8.2 Autonomiestufen

Eine Stufe ist eine **Voreinstellung** der Werkzeugfreigaben. Einzelne Werkzeuge lassen sich danach nur verschärfen; Admin-Overlays können ebenfalls nur verschärfen.

| Stufe | Name | Bedeutung |
|---|---|---|
| 1 | Nur lesen | Suche, Lesen, Antworten in Nachrichten |
| 2 | Vorschlagen (Standard) | dazu Vorschläge für Seiten und Skills, Kommentare an Tickets, Ticketstatus bis „Zur Prüfung“ |
| 3 | Schreiben intern | dazu direkte Seiten- und Ticketänderungen in Bereichen mit `agent_write_policy=direct` |
| 4 | Nach außen handeln | dazu externe Werkzeuge mit Schreibwirkung; als kritisch markierte Aufrufe brauchen immer eine Freigabe |

Eine Stufe über 2 darf nur vergeben, wer jeden Bereich des Agenten verwaltet, oder ein Admin.

### 8.3 Lauf

1. **Auslöser** (8.4) legt `run` an (`queued`) → DBOS-Workflow `run_agent(run_id)`.
2. **Kontext**: Anweisungen, Persönlichkeit, Name und Kurzbeschreibung der Skills (Volltext erst über das Werkzeug `load_skill`), Gedächtnisseite (gekürzt auf 4.000 Zeichen), Auftrag, Gesprächsverlauf.
3. **Schleife** mit Pydantic AI. Jeder Werkzeugaufruf geht durch die Service-Schicht.
   - Bei `confirm` entsteht eine **Freigabe**, die an den **Fingerabdruck** von Werkzeug, Argumenten und betroffener Objektversion gebunden ist. Der Lauf wartet mit `DBOS.recv` (Standard-Zeitlimit 72 h). Eine Freigabe für einen veränderten Inhalt gilt nicht.
4. Jede Werkzeugantwort wird als **nicht vertrauenswürdige Daten** gerahmt (ai-1 `untrusted.py`), gekürzt im Prompt und vollständig im Protokoll.
5. **Ende** mit `stop_reason`:
   - `completed`, `max_steps`, `deadline`, `budget`, `no_progress` (dritter identischer Aufruf),
   - `cancelled`, `rights_revoked`, `policy_blocked`, `provider_refused`, `error`.
6. **Ergebnis** an den Auslöser: Thread-Antwort, Ticket-Kommentar, Vorschlag oder Aktivität. Das vollständige Protokoll liegt in `run_event` und ist in der **Laufansicht** Schritt für Schritt einsehbar, mit Kosten und Abbruchknopf.

Abbruch: `run_cancel_request` ist ein eigener Datensatz. Er wird vor jedem Schritt und transaktional vor dem Abschluss geprüft (ai-2).

### 8.4 Auslöser

| Art | Beispiel |
|---|---|
| Erwähnung oder Direktnachricht | `@Mia fasse den Thread zusammen` |
| Ticketzuweisung | Ticket wird Mia zugewiesen |
| Einmalig | „am 1.12. um 8 Uhr“ |
| Wiederkehrend | Cron mit IANA-Zeitzone |
| Heartbeat | alle 30 min in aktiven Stunden mit einer Checkliste; das Ergebnis `HEARTBEAT_OK` wird protokolliert, aber nicht zugestellt |
| Ereignis | Seite veröffentlicht, Ticket mit Tag angelegt, Datei hochgeladen, Seite veraltet |

Wiederkehrende Auslöser überspringen einen Termin, solange der vorige Lauf noch arbeitet; das wird vermerkt. Die Aufgabenverwaltung zeigt je Auslöser den nächsten Termin, den letzten Lauf und dessen Ergebnis und erlaubt es, den Auslöser zu pausieren.

### 8.5 Gedächtnis und Lernen

- **Gedächtnisseiten**: Je Agent und Bereich gibt es eine normale, versionierte Wiki-Seite unter `/_agenten/<agent>/gedaechtnis`. Sie hat die Rechte dieses Bereichs. In einen Lauf werden nur die Gedächtnisseiten der Bereiche geladen, die sein Lesebereich (5.6) erlaubt, zusammen höchstens 4.000 Zeichen. So trägt das Gedächtnis kein Wissen aus einem Team-Bereich in einen anderen. Der Agent ändert die Seite über `update_memory(space)`. Das ist auch auf Stufe 2 direkt erlaubt; Menschen können sie korrigieren. [Claude]
- **Laufarchiv**: Frühere Läufe des Agenten sind über das Werkzeug `search_past_runs` durchsuchbar, aber nicht automatisch im Kontext.
- **Skill-Vorschläge**: Ein Agent kann mit `propose_skill` einen neuen Skill oder eine Änderung vorschlagen. Der Vorschlag läuft durch dieselbe Moderation wie Seitenvorschläge.

### 8.6 Eingebaute Werkzeuge

| Gruppe | Werkzeuge |
|---|---|
| Wiki | `search`, `read_page`, `list_tree`, `propose_page_change`, `propose_new_page`, `update_page` (nur Stufe 3, zweistufig mit Diff), `list_versions` |
| Tickets | `search_tickets`, `read_ticket`, `create_ticket`, `comment_ticket`, `set_ticket_status` (höchstens Kategorie `review`), `assign_ticket` (an Menschen oder Agenten = Übergabe mit Begründung), `link_ticket_page` |
| Nachrichten | `post_message` (nur in Gespräche, in denen der Agent Mitglied ist), `read_conversation` |
| Gedächtnis und Skills | `update_memory`, `search_past_runs`, `load_skill`, `propose_skill` |
| Virtuell | `ask_user` (Rückfrage als Karte, Lauf wartet), `submit_result` |

Agenten löschen nie. Delegation an andere Agenten erfolgt in v1 **nur über Ticketzuweisung**.

---

## 9. Wiki

- **Seite**: `space_id`, `parent_id`, `title`, `slug`, `path` (materialisiert, eindeutig je Bereich), `content_md` (kanonisch), `status` (`draft`, `published`), `tags`, `no_ai`, `version`, `trashed_at`, `review_due_at`, Urheber als Principal, `search_tsv`.
- **Version**: bei jedem gespeicherten Stand; Versionen derselben Person innerhalb einer Live-Sitzung werden über 60 s zusammengefasst. Versionen entstehen auch vor jedem Agenten-Schreibzugriff und bei Wiederherstellung (als neue Version). Jede Version hat `source` (`human`, `agent`, `import`, `restore`), einen Änderungstext, ein **KI-Kennzeichen** bei Agenten und `run_id`. *Geändert in M2: Live-Speicherungen haben die Quelle `collab`. Zusammengefasst wird je Live-Sitzung statt je Person: eine Version je Speicherung, solange die letzte Version aus derselben Live-Sitzung stammt, jünger als 60 s ist und von einer der Personen dieser Speicherung; sonst eine neue Version unter der ersten dieser Personen. Eine Version je Person und Speicherung hätte mit fortlaufenden Versionsnummern bei zwei Bearbeitenden jede Speicherung zu zwei Versionen gemacht. KI-Kennzeichen und `run_id` kommen mit den Agenten (M5/M6).* *Geändert in M2 (Review R16): Versionsgeschichte, Vergleich, Benennen und Wiederherstellen brauchen `page.edit`; Leser sehen nur den aktuellen veröffentlichten Stand, nie Entwurfsstände oder deren Autoren.*
- **Live-Bearbeitung**: Hocuspocus authentifiziert über `POST :9090/internal/collab/auth`. Die API prüft dabei `page.edit` und prüft bei jeder Nachricht erneut; zurückgegeben wird ein Kurzzeit-Token. *Geändert in M2: Kein Kurzzeit-Token und keine Prüfung je Nachricht. Die Anmeldung liefert die Sitzungs-ID und die Generation; der Collab-Prozess prüft alle 5 s (`POST /internal/collab/pages/{id}/check`) und bei jeder Speicherung Generation und Rechte jeder beteiligten Sitzung. Eine API-Anfrage je Nachricht wäre bei 20 Änderungen je Sekunde zu teuer gewesen; über die Sitzung statt die Person verliert auch eine abgemeldete oder abgelaufene Sitzung ihre Verbindung. Wer das Recht verliert, wird mit 4403 getrennt; hatte er ungespeicherte Änderungen, endet die Generation, damit kein anderer Browser sie wieder einspielt.* Gespeichert wird über `PUT :9090/internal/collab/pages/{id}` mit Yjs-Zustand und Markdown; das Markdown erzeugt der Collab-Prozess mit Tiptap und Markdown-Serializer. Gespeichert wird **nur über diesen Service-Aufruf**.
- **Generationen**: Diese Ereignisse erhöhen `page.collab_generation` und schließen alle offenen Live-Verbindungen der Seite:
  - Speichern im Markdown-Modus,
  - Wiederherstellen,
  - Agenten-Schreibzugriff,
  - Verschieben,
  - Ändern der KI-Sperre,
  - Papierkorb.

  Alte Yjs-Stände werden abgelehnt. *Ergänzt in M2: auch Wiederherstellen aus dem Papierkorb und ungespeicherte Änderungen einer Person, die das Schreibrecht verloren hat. Eine Titeländerung allein beendet die Sitzung nicht. Agenten-Schreibzugriff und KI-Sperre kommen mit M5/M6.*
- **Vorschläge**: `page_proposal` mit Diff, Annehmen oder Ablehnen durch `moderator`. Beim Annehmen wird geprüft, ob die Basisversion noch aktuell ist; ist sie es nicht, gibt es einen Drei-Wege-Diff im Dialog. Vorschläge von Menschen sind je Bereich einschaltbar (`human_review`).
- **Papierkorb** statt Löschen; endgültiges Löschen nur durch Admins.
- **Veraltete Seiten**: Je Bereich gibt es eine Frist (`review_interval_days`). Ist sie abgelaufen, entsteht das Ereignis `page.review_due`, das eine Aktivität beim Moderator oder einen Agenten-Auslöser erzeugt.
- **Anhänge**: über `core/storage.py` (lokal oder S3; in M2 nur lokal unter `HERD_DATA_DIR`, S3 mit M9). Sie werden nur über eine geprüfte Route ausgeliefert. Rasterbilder werden inline angezeigt, alles andere als Download mit `nosniff`. SVG und HTML sind nicht erlaubt.
- **Import und Export**: Markdown-Zip in beide Richtungen; jede Seite ist als `.md` exportierbar.

---

## 10. Tickets

- **`work_item`**:
  - `space_id`, `number` (je Organisation fortlaufend, z. B. `HC-42`),
  - `kind` (`epic`, `story`, `task`, `bug`), `parent_id`,
  - `title`, `description_md`, `status_id`, `priority` (`low`, `normal`, `high`, `urgent`),
  - `assignee` (Principal), `reporter` (Principal), `due_at`, `tags`, `version`, `search_tsv`.
  - Verknüpfungen zu Seiten (`work_item_page`).
- **Status-Workflow je Bereich**: Status mit Name, Reihenfolge und **Kategorie** (`open`, `active`, `review`, `done`, `cancelled`). Standardstatus: Neu, In Arbeit, Zur Prüfung, Erledigt, Verworfen. Die Logik richtet sich nur nach Kategorien. Agenten können keinen Status der Kategorie `done` oder `cancelled` setzen.
- **Kommentare** sind Nachrichten im Ticket-Thread (`thread_ticket`). Änderungen am Ticket erzeugen dort Systemmeldungen (6.2).
- **Ansichten**: Board je Bereich, Liste (bereichsübergreifend, gefiltert nach sichtbaren Bereichen), Epic-Übersicht, „Meine Tickets“.
- **Agentenzuweisung**: Abnahmekriterien sind ein Pflichtabschnitt der Beschreibung, wenn ein Agent zugewiesen wird. Der Agent meldet sein Ergebnis als Kommentar und setzt den Status auf „Zur Prüfung“. Der Verbrauch wird zusätzlich je Ticket summiert.

*Geändert in M4: Die Fälligkeit ist ein Datum, `due_on` (DATE) statt `due_at`, ohne Uhrzeit und Zeitzone. Das Präfix des Schlüssels ist fest `HC` (ein einstellbares Präfix kommt, wenn es jemand braucht). Die Verknüpfungstabelle heißt `ticket_page_link`. Es gibt keine Handsortierung: In einer Board-Spalte gilt Priorität absteigend, Fälligkeit aufsteigend (ohne Datum zuletzt), Nummer. Plan M4, Entscheidungen 1, 7 und 8; Bedienung in `docs/TICKETS.md`.*

### Tags

Es gibt einen gemeinsamen Tag-Vorrat (`tag`: Name, Farbe, `space_id` oder systemweit) für Seiten, Tickets, Skills und Agenten. Tags dienen als Suchfilter und als Auslöser.

---

## 11. Suche, Dateien, Skills, Konnektoren, MCP

- **Suche**: Die Tabelle `search_chunk` hat `source_type`, `source_id`, `space_id`, `tags`, `no_ai`, `text`, `tsv` (`german` und `simple` kombiniert) und `embedding vector(n)`. Die Hybridsuche verbindet Volltext und Vektorsuche per Reciprocal Rank Fusion. Die Rechte werden in derselben Abfrage gefiltert. Ohne Embedding-Verbindung gibt es nur Volltextsuche. Ein Modellwechsel startet eine Neuindexierung als Hintergrundauftrag mit Fortschrittsanzeige. Vor der Ausgabe wird geprüft, ob die Quellversion noch aktuell ist (Befund R01 aus ai-2).
- **Dateien**: Hochgeladene PDF-, Office- und HTML-Dateien wandelt ein Worker-Auftrag mit **Docling** in Markdown um. Original und Markdown bleiben erhalten, und je Datei gibt es eine KI-Sperre.
- **Skills**: SKILL.md-Format (agentskills.io), versioniert, je Bereich geteilt, Import und Export.
- **MCP-Server als Werkzeugquelle**: nur über Streamable HTTP. Die Werkzeugliste wird beim Anlegen eingelesen, und jedes Werkzeug wird einzeln freigegeben. Jeder Aufruf geht durch die SSRF-Sperre (ai-1). stdio ist ausgeschlossen.
- **Konnektoren**: gespeicherte Zugänge (API-Schlüssel, OAuth). Das Geheimnis wird serverseitig eingesetzt und ist nie im Prompt.
- **System als MCP-Server** (`/mcp`): stellt die eingebauten Werkzeuge bereit. Zugriff über persönliche Tokens mit Umfang (Bereiche, nur lesen oder schreiben) und dem Recht `mcp.use`. Ein Token hat höchstens die Rechte seiner Person, und Schreibvorgänge tragen das KI-Kennzeichen.

---

## 12. Betrieb (nach dem Betriebsleitfaden, ohne b-api-/edu-sharing-Spezifika)

### 12.1 API

- OpenAPI wird aus dem Code erzeugt (`/api/openapi.json`, `/api/docs`), mit `info.title` und `info.description` für Endnutzende. Sie enthält nur öffentliche Pfade.
- Fehler haben die Form `{"error": {"code", "message", "trace_id"}}`.
  - 4xx bei Fehlern des Aufrufers, 5xx nur bei eigenen Fehlern.
  - Dauerhafte Fehler nie als 503.
  - 409 bei Versionskonflikten.
- Länger als 30 s wird nie synchron gearbeitet: Läufe, Indexierung und Konvertierung sind Aufträge mit ID und Status.

### 12.2 Logging und Tracing

- JSON-Logs nach stdout mit `timestamp`, `level`, `service=to-herd-cats-ai`, `trace_id`, `span_id`, `message`, `org_id`, `actor` (Typ und ID) und `run_id`.
- `HERD_LOG_FORMAT=text` schaltet für die Entwicklung auf Klartext um, `HERD_LOG_LEVEL` steuert die Stufe.
- Das Uvicorn-Access-Log ist aus. Stattdessen gibt es eine eigene Zeile je Anfrage mit Methode, Pfad-Template, Status, Dauer und `trace_id`, **ohne Header**.
- OpenTelemetry für FastAPI, httpx, SQLAlchemy und Pydantic AI. Der Propagator ist über `OTEL_PROPAGATORS` einstellbar (Standard `tracecontext,baggage`, wahlweise `b3`). `x-client-trace-id` wird übernommen und weitergegeben. Der Export ist nur aktiv, wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist.
- Nie geloggt werden Schlüssel, Header-Werte, Passwörter und Nachrichteninhalte. Prompt-Inhalte stehen nur im Laufprotokoll in der Datenbank und nie im Log.

### 12.3 Ports, Proben, Metriken

- Port 8080 ist öffentlich.
- Port 9090 ist intern:
  - `/health`: Liveness, ohne Datenbank.
  - `/ready`: Datenbank erreichbar, Schema auf dem Head dieses Codes oder neuer (siehe 4.1, Migrationen), DBOS gestartet (beim Worker).
  - `/metrics`: Prometheus.
  - `/internal/*`: nur mit `HERD_INTERNAL_TOKEN`.
- **Metriken**:
  - HTTP-Dauer und -Status,
  - Datenbank-Pool,
  - Länge der Outbox,
  - Läufe nach Status,
  - wartende Freigaben,
  - Tokens und Kosten je Verbindung,
  - LLM-Fehler nach Status,
  - SSE-Verbindungen,
  - Collab-Verbindungen,
  - Dauer der Indexierung.
- Bei mehreren Uvicorn-Workern gilt `PROMETHEUS_MULTIPROC_DIR`.

### 12.4 Zustand und Skalierung

- Die Prozesse sind zustandslos. Sitzungen, Ratenlimits (Postgres-basiert, ai-1), Sperren, Warteschlangen, Zeitpläne und Yjs-Stände liegen in Postgres; Dateien liegen auf einem Volume oder in S3.
- Zeitpläne laufen im Cluster genau einmal (DBOS bzw. `SKIP LOCKED`).
- **Collab im Cluster**:
  - Stufe 1: eine einzelne Collab-Instanz (Replica 1, `Recreate`).
  - Stufe 2: Hocuspocus-Redis-Erweiterung mit Valkey, optional im Chart.
- Ab etwa 10 Replikas sitzt PgBouncer im Transaktionsmodus davor (`HERD_DB_PGBOUNCER=true`).

### 12.5 Image und Helm

- Ein Multi-Stage-Image mit `python:3.13-slim` als Basis, Node-Laufzeit nur für `collab` und der SPA als statischen Dateien.
- Das Image läuft nicht als root, mit nur lesbarem Dateisystem; beschreibbar ist nur `/tmp` (`emptyDir`). Keine Modelle im Image, auch Docling-Modelle nicht: Diese kommen über ein Volume oder einen Init-Container.
- Der Prozess ist PID 1 (oder `tini`). Er fängt SIGTERM ab und erlaubt einen geordneten Abschluss. Der Worker schließt den laufenden Schritt ab, und DBOS setzt nach dem Neustart fort.
- Das Datenbank-Passwort steht nie in `HERD_DATABASE_URL`, sondern in `HERD_DATABASE_PASSWORD` oder `HERD_DATABASE_PASSWORD_FILE` (beides zugleich ist ein Startfehler). Die Konfiguration setzt es maskiert in die URL ein; Alembic nutzt dieselbe URL. Eine URL mit Passwort funktioniert weiter (Tests, lokale Entwicklung).
- `deploy/compose/` ist die Referenz mit `db`, `app` (`all`) und optional `minio`, `backup` und `otel-collector`.
- **Helm-Chart**:
  - Pfad `deploy/helm/to-herd-cats-ai/`, `version` = `appVersion` = Version des Dienstes; ein CI-Test hält sie gleich.
  - Deployments für `api`, `worker` und `collab`, ein Migrations-Job, Ingress (alles an `api`, auch `/collab`; *geändert in M2*, siehe 4.1), HPA (api, worker).
  - NetworkPolicy, ServiceMonitor, PrometheusRule mit `promtool`-Tests und Backup-CronJob.
  - `postgresql.enabled` und `s3` sind abschaltbar und auf externe Dienste umstellbar.
  - Pod Security „restricted“.
- **CI**: Lint, Typen, Tests (Postgres-Service), Abhängigkeitsprüfung, `helm lint --strict`, `helm template | kubeconform`. Bei Tags `vX.Y.Z` werden das Image (`:X.Y.Z`, `:X.Y`) und das Chart als OCI veröffentlicht. Basis-Images sind per Digest festgelegt, Renovate hält sie aktuell.

### 12.6 Sicherung

- `pg_dump -Fc` der App-Datenbank und der DBOS-Datenbank, dazu ein Spiegel der Dateiablage.
- Restore nur in eine leere Datenbank; danach werden alle Sitzungen ungültig (ai-2). Die Wiederherstellung wird in der CI geprobt.
- Optional: verschlüsselte Offsite-Sicherung mit Restic (ai-2).

### 12.7 Steckbrief

`docs/STECKBRIEF.md` enthält Kurzbeschreibung, Funktionen mit Laufzeit (P50/P90) und Kosten, Abhängigkeiten, Clusterfähigkeit, Zeitpläne, gemessene Ressourcen mit Request- und Limit-Empfehlung, Image-Größe, Ansprechperson und Vertretung. Er wird ab Meilenstein 1 gepflegt und bei jedem Meilenstein aktualisiert.

---

## 13. Übernahme aus den Vorgängern

Regel: Übernommen wird nur, was **gelesen, getestet und an diese Spezifikation angepasst** ist. Je Übernahme gibt es einen eigenen Commit mit dem Hinweis `ported from ai-1@<sha>:<pfad>`.

| Ziel | Quelle | Anpassung |
|---|---|---|
| `core/config.py`, `core/db.py`, `core/errors.py` | ai-1 `backend/app/core/` | Fehlerobjekt um `trace_id` ergänzen; Präfix `HERD_` bleibt |
| `core/secrets.py` (SecretRef) | ai-1 | Schlüsselableitung mit HKDF statt nacktem SHA-256 |
| `core/security.py`, Login und Sitzungen, Ratenlimit | ai-1 `core/security.py`, `core/ratelimit.py`, `modules/auth` | unverändert im Kern |
| `core/permissions.py`, `core/principal.py` | ai-1 | um Gruppen als Principal, Gast, Bereichsart `personal`/`team` und neue Rechte erweitern |
| `core/ssrf.py`, `core/storage.py`, `core/slug.py` | ai-1 | unverändert |
| Testgerüst (`conftest.py`: echtes Postgres, Rollback je Test) | ai-1 `backend/tests/conftest.py` | unverändert |
| Wiki: Seitenbaum, Versionen, Verschieben, Volltext, Import/Export | ai-1 `modules/wiki` | an `space.kind`, Papierkorb, Generationen und KI-Kennzeichen anpassen |
| Collab: Hocuspocus-Server, Rechteprüfung je Nachricht, Generationen, Markdown-Konvertierung | ai-2 `runtime/collaboration.mjs`, `editor/` | Speicherung über die interne API statt SQLite |
| Laufzeit: `agent_factory`, `durable`, `untrusted`, `history_window`, Toolsets, zweistufige Schreibvorgänge | ai-1 `backend/app/runtime/` | Stop-Gründe, Richtlinienprüfung und Neuprüfung der Rechte ergänzen |
| Vorschläge mit Diff | ai-1 `modules/proposals` | um Skill-Vorschläge erweitern |
| Zeitpläne und Ereignis-Auslöser | ai-1 `modules/schedules` | an die Outbox anbinden; Heartbeat ergänzen |
| Abbruch-Semantik, inhaltsgebundene Freigaben | ai-2 `lib/runs.ts`, Doku AGENTEN.md | in Python neu umsetzen |
| Backup und Restore | ai-1 `infra/backup/`, ai-2 `scripts/offsite-backup.mjs` | Compose-Dienst und Helm-CronJob |
| Frontend-Gerüst, shadcn-Bausteine, i18n-Prüfung | ai-1 `frontend/src/components/ui`, ai-2 `scripts/check-i18n.mjs` | neue Navigation nach 6.2 |

**Nicht** übernommen wird:

- das Postfach (`inbox`) aus ai-1, ersetzt durch Aktivität und Benachrichtigungen,
- die Chat-Threads mit assistant-ui als eigene Seite, ersetzt durch Direktnachrichten mit Agenten,
- die Ticket-Kommentartabelle aus ai-1, ersetzt durch den Ticket-Thread,
- die SQLite- und D1-Schicht aus ai-2.

---

## 14. Meilensteine

Jeder Meilenstein endet mit etwas, das ein Team sofort nutzen kann, mit Tests, einem Demo-Skript und einem aktualisierten Steckbrief. Für jeden Meilenstein entsteht ein eigener Umsetzungsplan, sobald der vorige fertig ist. So arbeitet der Plan mit dem echten Code und nicht mit Annahmen.

| M | Ergebnis | Abnahme |
|---|---|---|
| **M1 Fundament** | Gerüst, Image, Compose, CI, Helm-Grundgerüst; Logging, Tracing, Ports und Proben; Anmeldung, Personen, Gruppen, Bereiche (open/team/personal), Rollen, `can()`, Audit; Oberflächen-Gerüst mit Navigation und Verwaltung. Outbox und Worker kommen in M3, Tags in M2, jeweils mit ihrem ersten Leser | Zwei Personen in verschiedenen Team-Bereichen sehen gegenseitig weder Inhalte noch Existenz, auch nicht per direkter ID; Admins sehen beides; `docker compose up` startet alles; das Helm-Chart besteht `kubeconform` |
| **M2 Wiki** | Seitenbaum, Markdown-Editor, Live-Bearbeitung mit Generationen, Versionen und Wiederherstellung, Papierkorb, Anhänge, Volltextsuche, Import/Export, Tags (systemweit und je Bereich, mit Verwaltung und Filter im Seitenbaum). *Geändert in M2: Tags gehören hierher (siehe M1); die Volltextsuche liegt als Spalte `page.search_tsv` an der Seite, die Tabelle `search_chunk` aus 11 kommt mit der Hybridsuche (M5); `/collab` läuft über die API (4.1); Anhänge nur lokal, S3 mit M9. Verschieben im Baum per Dialog statt per Ziehen.* | Zwei Browser bearbeiten gleichzeitig; das Speichern im Markdown-Modus beendet die Live-Sitzung sauber; die Suche findet nur Sichtbares. Erfüllt am 13.11.2026, siehe `docs/demo/m2.md` |
| **M3 Nachrichten** | Kanäle, Direktnachrichten, Threads, Erwähnungen, Reaktionen, Lesestand, Aktivität, SSE-Zustellung über mehrere API-Knoten | Eine Nachricht auf Knoten A erscheint live auf Knoten B; eine Erwähnung erzeugt eine Aktivität |
| **M4 Tickets** | Arbeitspakete mit Hierarchie, Status-Workflow je Bereich, Board und Liste, Ticket-Threads mit Systemmeldungen, Seitenverknüpfung, Tags | Kanäle bleiben frei von Ticketmeldungen; Systemmeldungen lassen sich im Thread ausblenden. Erfüllt am 13.11.2026, siehe `docs/demo/m4.md` |
| **M5 KI-Grundlage** | Verbindungen (openai, kompatibel, b-api, lokal), Zuordnung und `ai.use`, Verbrauchserfassung, KI-Richtlinie je Bereich, Embeddings und Hybridsuche, Docling-Konvertierung, Direktnachricht mit einem Agenten auf Stufe 1 | Personen ohne KI sehen keine KI-Funktion; ein `restricted`-Bereich erreicht nie eine `external`-Verbindung (Test) |
| **M6 Agenten als Mitarbeiter** | Profile, Werkzeuge und Autonomiestufen, Skills, Vorschläge, Freigaben mit Fingerabdruck, Erwähnungen, Ticketzuweisung, Laufansicht, Gedächtnis, Abbruch | Ein Agent bearbeitet ein Ticket bis „Zur Prüfung“; eine Freigabe für einen geänderten Inhalt wird abgelehnt; ein Lauf übersteht den Neustart des Workers |
| **M7 Automatisierung** | einmalige, wiederkehrende und Heartbeat-Auslöser, Ereignis-Auslöser mit Ruhezeit und Tiefenlimit, Budgets, Aufgabenverwaltung, veraltete Seiten | Ein Zeitplan läuft bei drei Worker-Replikas genau einmal; eine Agentenkette stoppt bei Tiefe 3 |
| **M8 Öffnung** | eigener MCP-Endpunkt mit Tokens, externe MCP-Server als Werkzeuge, Konnektoren, **externe Agenten** (Claude Code, Codex über MCP mit Agenten-Token und Ticket-Abholung) | Claude Code liest über `/mcp` nur Bereiche seines Tokens; ein externer Agent schließt ein Ticket bis „Zur Prüfung“ ab |
| **M9 Produktion** | OIDC, volles Helm-Chart mit HPA und Alarmen, Collab Stufe 2, Offsite-Backup, geprobte Wiederherstellung, Lasttest, gemessene Ressourcen, Sicherheitsprüfung (ASVS L2). *Ergänzt in M2 (Review R14): Die Weitergabe des Sitzungs-Cookies an den Collab-Prozess wird durch kurzlebige, an Seite und Generation gebundene Tokens ersetzt; die interne API nimmt Speichern dann nur noch für solche Tokens an.* | Steckbrief vollständig; Restore in der CI grün |
| **M10 Kalender** [Jan, 13.11.2026] | Voller Kalender für Person, Team (Bereich) und Organisation: Termine mit Einladungen, Serientermine, Verfügbarkeit, Abgleich mit Google Kalender und CalDAV, iCal-Abo; zeigt auch Fälligkeiten, Sprints und Agenten-Zeitpläne. Eigener Plan nach M9 | Ein Serientermin mit Einladung erscheint bei allen Eingeladenen und im abonnierten externen Kalender; ein Termin eines Team-Bereichs ist für Außenstehende unsichtbar |

M1 und M2 zusammen sind das kleinste sinnvolle Produkt (Wiki mit Rechten). Mit M3 und M4 ist das System ohne KI vollständig nutzbar.

---

## 15. Was dem Bauenden überlassen bleibt

- Konkrete Bibliotheken innerhalb der gesetzten Grenzen, z. B. `structlog` oder `python-json-logger`, Diff-Bibliothek, Cron-Parser.
- Gestaltung der Oberfläche innerhalb von shadcn/ui, WCAG 2.2 AA, Hell- und Dunkelmodus und vollständig selbst gehosteten Assets.
- Tabellen- und Indexdetails, solange jede Liste paginiert ist und jeder konkurrierende Schreibzugriff `version` mit 409 nutzt.

## 16. Offene Fragen an Jan

- **F1**: Sollen Admins Direktnachrichten in der normalen Oberfläche sehen, oder nur über die protokollierte „Einsicht“ (5.5)? Mein Vorschlag ist die Einsicht, wegen Datenschutz und Betriebsrat.
- **F4** (für M5): Welches lokale Embedding-Modell? Entscheidung gemeinsam nach dem Vergleich der drei Kandidaten (7.2).
- **F2**: Wie heißt das Produkt in der Oberfläche? Ich verwende bis auf Weiteres „Herd“, die Dienst-ID ist `to-herd-cats-ai`.
- **F3**: Ist die Publikumsregel (5.6) so richtig? Sie verhindert, dass ein Agent Wissen aus einem Team-Bereich in einen offenen Kanal trägt. Der Preis: Ein Agent, der in `#allgemein` erwähnt wird, nutzt dort nur offenes Wissen, auch wenn die fragende Person mehr sehen darf. Wer mehr will, fragt den Agenten per Direktnachricht oder im Team-Kanal.

### Entscheidungen aus dem Gegenlesen (Builder-Check)

Ein unabhängiger Prüfer hat die Spezifikation gelesen. Folgende Punkte habe ich daraufhin selbst entschieden; sie sind oben eingearbeitet und mit [Claude] markiert:

- Wer bei Zuweisung, Übergabe und Ereignis als Auslöser zählt (5.4).
- Die Publikumsregel (5.6, bestätigen über F3).
- Gedächtnis je Bereich statt im persönlichen Bereich (8.5).
- Offene Bereiche geben Mitgliedern die Rolle `viewer`; bei der Einrichtung entsteht der Bereich „Allgemein“ (5.3).
- Embeddings für `restricted`-Bereiche nur bei passender Embedding-Verbindung (7.3).
- Umfang der Planung: Meilenstein 1 im Detail, die übrigen Meilensteine als Abschnitt 14 mit je eigenem Plan, sobald der Vorgänger fertig ist.
