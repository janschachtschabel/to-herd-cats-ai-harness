# MCP: das System als MCP-Server und als MCP-Client

Seit M8 öffnet sich das System in beide Richtungen (Plan
`docs/superpowers/plans/2026-11-15-m8-oeffnung.md`):

- **Nach außen, als MCP-Server:** Externe KI-Clients wie Claude Code und Codex lesen und
  arbeiten über den Endpunkt `/mcp` mit einem [Zugangstoken](#zugangstoken), nie mit
  mehr Rechten als die Person und nur in den Bereichen des Tokens
  ([Der Endpunkt `/mcp`](#der-endpunkt-mcp)). [Externe Agenten](#externe-agenten) sind
  Teammitglieder, die von außen mit einem Agenten-Token Tickets abholen und bis „Zur
  Prüfung“ bringen.
- **Nach innen, als MCP-Client:** Die eigenen Agenten rufen Werkzeuge
  [externer MCP-Server](#externe-mcp-server) auf, jedes einzeln freigegeben, mit
  gespeicherten Zugängen ([Konnektoren](#konnektoren), auch
  [OAuth](#oauth-konnektoren)) und Vorlagen aus dem [Katalog](#katalog) (GitHub,
  GitLab, eigene).

Betrieb (Reverse-Proxy, Einstellungen, Grenzen, Metriken und Alarme) steht unter
[Betrieb](#betrieb), was ein externer Client sehen kann und was nicht unter
[Sicherheit](#sicherheit-was-ein-externer-client-sieht). Bedienung der Agenten:
[`AGENTEN.md`](AGENTEN.md), KI-Verbindungen und Richtlinie: [`KI.md`](KI.md), Tickets:
[`TICKETS.md`](TICKETS.md).

## Zugangstoken

Externe KI-Clients (Claude Code, Codex) melden sich am Endpunkt `/mcp` mit einem
**persönlichen Zugangstoken** an. Ein Token handelt als seine Person, nie mit mehr
Rechten als sie, und nur in seinem Umfang.

### Wer Token haben darf: `mcp.use`

- Das Recht `mcp.use` wird nie an der Person gespeichert. Es gilt für **jede aktive
  Person außer Gästen**, solange der **MCP-Schalter der Organisation** an ist
  (Standard: aus), **außer wer ausdrücklich keine KI hat**: Steht in der persönlichen
  KI-Zuweisung einer Person „keine KI“ (`no_ai`), hat sie auch kein `mcp.use`, denn ein
  externer Client ist eine KI, die Daten der Organisation liest. Ein Modell braucht
  `mcp.use` dagegen nicht: Wem gar keine Zuweisung gilt (kein Standard, keine Gruppe),
  der behält `mcp.use`. Wird „keine KI“ gesetzt, antworten die Token der Person sofort
  401; wird es wieder entfernt, gelten sie wieder.
- Den Schalter stellen Personen mit `ai.manage` in der KI-Verwaltung
  (`PUT /api/ai/mcp`). Jede Änderung steht im Audit (`mcp.settings_set`, mit altem und
  neuem Wert), und jede aktive Person bekommt `access.changed`, damit ihr Client
  `mcp.use` neu lädt.
- Ohne `mcp.use` ist von der Funktion nichts zu sehen: Die eigenen Token-Routen
  antworten 404 `token.not_found` wie für eine unbekannte ID, und jedes Token der
  Person antwortet am Endpunkt 401 wie ein unbekanntes. Schaltet die Organisation
  wieder ein, gelten die nicht widerrufenen, nicht abgelaufenen Token wieder.
- `/api/auth/me` nennt `mcp.use` unter `permissions`; die Oberfläche entscheidet nur
  danach.

### Datenort des Endpunkts

Ein externer Client zählt für die KI-Richtlinie eines Bereichs wie eine Verbindung mit
`data_location = external`: Über ein Token ist nur lesbar, was eine solche Verbindung
lesen dürfte. Bereiche mit Richtlinie `none`, Bereiche mit `restricted` ohne
`external` und alles mit KI-Sperre (`no_ai`) sind für das Token nicht vorhanden.
Laufen die Clients im Haus, stellt die Verwaltung den Datenort organisationsweit auf
`eu` oder `local` (dieselbe Einstellung, mit Audit). **Entwürfe** sind über ein Token
nie lesbar, auch nicht für Bearbeitende des Bereichs.

### Anlegen, Anzeigen, Widerrufen

- `POST /api/tokens` mit `name` (bis 80 Zeichen), `mode` (`read` oder `write`),
  `expires_in_days` (Pflicht, 1 bis 365) und optional `space_ids` (1 bis 50 Bereiche,
  die die Person jetzt lesen darf, sonst 422 `token.space_invalid`, gleich für
  unbekannte und unsichtbare Bereiche). Ohne `space_ids` gilt „alle meine Bereiche“:
  alle Bereiche, die die Person lesen darf, ohne die persönlichen Bereiche anderer
  (auch für Admins).
- Die Antwort enthält in `secret` den **Klartext des Tokens, genau dieses eine Mal**
  (Präfix `herd_pat_`, danach 256 Bit Zufall). Gespeichert wird nur der SHA-256-Hash;
  ein verlorenes Token lässt sich nicht wieder anzeigen, nur widerrufen und neu
  anlegen.
- `GET /api/tokens` (seitenweise, neueste zuerst): die eigenen Token mit Name, Art,
  Modus, Umfang, Ablauf, letzter Nutzung (auf die Minute, höchstens einmal je Minute
  geschrieben) und Widerruf. Nie mit Hash oder Klartext.
- `DELETE /api/tokens/{id}`: widerruft ein eigenes Token (204, auch wenn es schon
  widerrufen war; im Audit nur einmal). Fremde Token antworten wie unbekannte
  (404 `token.not_found`).

### Verwaltung

Personen mit `ai.manage` (alle anderen: 404 `ai.not_found`):

- `GET /api/ai/mcp`, `PUT /api/ai/mcp` (`enabled`, `data_location`, `version`;
  409 `mcp.settings_version_conflict` bei veralteter Version).
- `GET /api/ai/mcp/tokens` (seitenweise): alle Token der Organisation, nur Metadaten
  und wem sie gehören.
- `DELETE /api/ai/mcp/tokens/{id}`: widerruft jedes Token der Organisation (Audit
  `access_token.revoked` mit der Person, der es gehört). Beides geht auch bei
  ausgeschaltetem Schalter.

### In der Oberfläche

- **Eigene Token:** Benutzermenü → „Zugangstoken“ (`/profile/tokens`, auch verlinkt im
  Profil), nur mit `mcp.use`. Anlegen mit Name, „Nur lesen“ oder „Lesen und
  schreiben“, allen oder ausgewählten Bereichen und der Gültigkeit in Tagen. Danach
  zeigt ein Dialog den Klartext genau einmal, mit Kopierknopf, Warnung und den
  Befehlen für Claude Code und Codex (mit der Adresse dieser Installation und
  `$HERD_TOKEN`). Je Token: Zustand (aktiv, abgelaufen, widerrufen), letzte Nutzung,
  „Aufrufe“ (die letzten Werkzeugaufrufe mit Ergebnis und Dauer) und „Widerrufen“
  (mit Rückfrage).
- **Verwaltung:** Administration → KI → „MCP-Zugang“ (`/admin/ai/mcp`, nur mit
  `ai.manage`): der Schalter, der Datenort der Clients (Speichern mit der gelesenen
  Version; bei 409 bleibt die Auswahl stehen und lässt sich neu speichern) und alle
  Token der Organisation mit ihrer Person oder ihrem Agenten, Aufrufen und Widerrufen.
- Was über ein Token geschrieben wurde (Nachrichten, Kommentare, Einträge der
  Ticket- und Seitenverläufe, Vorschläge, Seitenversionen), trägt das KI-Kennzeichen und
  „über Token „Name““; eine Seitenversion aus `/mcp` heißt „Über MCP“.

### Rechte eines Tokens

Bei **jedem Aufruf** wird das Token neu aufgelöst, nichts wird zwischengespeichert:

- Lesbar ist die Schnittmenge aus den **Rechten der Person** (wie sie jetzt sind:
  Rolle, Gruppen, Mitgliedschaften), dem **Umfang des Tokens** und dem, was die
  **KI-Richtlinie** für den Datenort des Endpunkts erlaubt. Wird der Person ein
  Bereich entzogen, ist er für das Token sofort weg.
- Ein `read`-Token schreibt nirgends. Ein `write`-Token schreibt höchstens in den
  Bereichen seines Umfangs und nur, was die Person dort selbst darf (die Werkzeuge
  dafür: [Der Endpunkt `/mcp`](#der-endpunkt-mcp)).
- Ist die Person nicht mehr aktiv, wird sie Gast, bekommt sie „keine KI“ oder ist der
  Schalter aus, antwortet das Token 401.

### Sicherheit

- Das Token geht nur im Kopf `Authorization: Bearer <token>`, nie in der URL.
- Klartext und Hash stehen nie in Logs, Audit, Outbox, Fehlermeldungen oder URLs
  (Test `test_token_secrecy.py`). Das Audit nennt Art, Modus, Größe des Umfangs und
  Ablauf (`access_token.created`) bzw. den Widerruf (`access_token.revoked`).
- Unbekannt, widerrufen, abgelaufen, Person inaktiv oder ohne `mcp.use`: überall
  dieselbe Antwort 401 `token.invalid`, auf demselben Weg (eine Suche nach dem Hash,
  dann eine Entscheidung), damit die Antwort nichts verrät.
- **Ratenbegrenzung je Token** in PostgreSQL, gemeinsam für alle API-Knoten:
  `HERD_MCP_RATE_PER_MINUTE` Aufrufe je Minute (Standard 120, 1 bis 10.000); darüber
  429 `mcp.rate_limited` mit `Retry-After`.

Die Einstellungen stehen unter [Betrieb](#einstellungen). Im Code:
`backend/app/modules/tokens/resolve.py` löst ein Token bei jedem Aufruf zum Akteur der
Person mit Umfang, Modus, Token-Name und Datenort auf; `backend/app/modules/tokens/reach.py`
sagt in SQL, was ein solcher Akteur lesen darf.

## Der Endpunkt `/mcp`

Externe KI-Clients (Claude Code, Codex und jeder andere MCP-Client) lesen und arbeiten
über `https://<Installation>/mcp` mit einem Zugangstoken (Plan M8, Tasks 2 und 3). Der
Endpunkt spricht MCP über **Streamable HTTP, zustandslos**: jede Anfrage ist ein
`POST` mit einer JSON-RPC-Nachricht und bekommt genau eine JSON-Antwort. Es gibt keine
Sitzungen (`Mcp-Session-Id`), keine Server-Streams (`GET` und `DELETE` antworten 405)
und nur **Werkzeuge** (`tools`), keine `resources`, `prompts` oder `sampling`. Jeder
API-Knoten kann jede Anfrage beantworten; im Prozess bleibt nichts zurück. Clients mit
dem Handshake (`initialize`, Protokoll 2025) und Clients des zustandslosen Protokolls
(2026-07-28, `server/discover`) werden beide bedient.

### Einen Client verbinden

Zuerst unter den persönlichen Einstellungen („Zugangstoken“) ein Token anlegen
(`read` zum Lesen, `write` zum Arbeiten; am besten nur mit den nötigen Bereichen und
kurzer Laufzeit) und den Klartext in eine Umgebungsvariable legen, etwa `HERD_TOKEN`.
Das Token gehört nie in eine Datei, die eingecheckt wird, und nie in eine URL. Die
Syntax unten ist geprüft am 15.11.2026 an der Dokumentation von Claude Code
(code.claude.com/docs/en/mcp) und am Quelltext von Codex (`codex-rs`: `mcp_cmd.rs`,
`config/src/mcp_types.rs`); ein Lauf der beiden Clients gegen eine Installation war
von hier aus nicht möglich.

**Claude Code**, als Befehl (Transport `http` ist Streamable HTTP):

```bash
claude mcp add --transport http herd https://herd.example.com/mcp \
  --header "Authorization: Bearer $HERD_TOKEN"
```

Die Shell setzt dabei den Klartext ein, und Claude Code speichert ihn in seiner
Konfiguration (Geltung `local` oder `user`: in `~/.claude.json`). Wer das nicht will,
trägt den Server in die `.mcp.json` des Projekts ein; Claude Code setzt
`${HERD_TOKEN}` erst beim Verbinden aus der Umgebung ein, die Datei enthält das Token
also nie:

```json
{
  "mcpServers": {
    "herd": {
      "type": "http",
      "url": "https://herd.example.com/mcp",
      "headers": { "Authorization": "Bearer ${HERD_TOKEN}" }
    }
  }
}
```

Ob die Verbindung steht, zeigt `/mcp` in Claude Code (ein ungültiges Token erscheint
als fehlgeschlagene Verbindung mit 401). Der Name der Variable ist frei, nur nicht einer
der Zugangsdaten, die Claude Code für entfernte Server bewusst leer lässt (etwa
`ANTHROPIC_API_KEY`, `HTTPS_PROXY`, `NPM_TOKEN`).

**Codex**, in `~/.codex/config.toml` (Codex liest das Token bei jeder Anfrage aus der
Umgebung und sendet es als `Authorization: Bearer`; mit `bearer_token_env_var`
versucht es keine OAuth-Anmeldung):

```toml
[mcp_servers.herd]
url = "https://herd.example.com/mcp"
bearer_token_env_var = "HERD_TOKEN"
```

oder als Befehl `codex mcp add herd --url https://herd.example.com/mcp
--bearer-token-env-var HERD_TOKEN`.

Andere Clients: Streamable HTTP, `POST` an `/mcp`, Kopf `Authorization: Bearer
<token>`, kein `Origin`. Was zwischen Client und API steht, beschreibt
[Reverse-Proxy und Ingress](#reverse-proxy-und-ingress).

### Werkzeuge

Es sind die Werkzeuge des Katalogs der Agenten (`agents/toolbox/catalog.py`), mit
denselben Beschreibungen und Argumenten, keine zweite Liste. Angeboten werden nur die,
die ohne Lauf funktionieren.

Mit jedem Token (lesend):

| Werkzeug | Was es tut |
|---|---|
| `search` | Volltextsuche in Seiten und Tickets |
| `read_page` | eine Seite (Markdown) nach ID |
| `read_ticket` | ein Ticket nach Schlüssel (`HC-12`) |
| `list_tree` | ohne `space_id` die lesbaren Bereiche, mit `space_id` dessen Seitenbaum |
| `list_versions` | die Versionen einer Seite (ohne Inhalt; braucht wie für Personen `page.edit`, also ein `write`-Token) |
| `search_tickets` | Tickets nach Text und Filtern |

Zusätzlich mit einem `write`-Token:

| Werkzeug | Was es tut |
|---|---|
| `create_ticket` | ein Ticket in einem Bereich anlegen |
| `comment_ticket` | ein Ticket kommentieren (eine Nachricht im Ticket-Thread) |
| `set_ticket_status` | den Status setzen, höchstens bis zur Kategorie „Prüfung“; „erledigt“ und „abgebrochen“ setzen Personen |
| `link_ticket_page` | eine Seite mit einem Ticket verknüpfen |
| `propose_page_change`, `propose_new_page` | einen Seitenvorschlag machen; eine moderierende Person entscheidet |
| `update_page` | eine Seite direkt ändern, nur in Bereichen mit `agent_write_policy = direct` (sonst kommt der Hinweis, einen Vorschlag zu machen); in zwei Schritten: erst Diff und Prüfwert, dann mit demselben Inhalt und dem Prüfwert speichern |
| `post_message` | eine Nachricht in einen Kanal eines Bereichs des Tokens |

Nicht über `/mcp`: Werkzeuge, die einen Lauf brauchen (Rückfrage, Ergebnis, Gedächtnis,
Skills, frühere Läufe, das Gespräch des Laufs), Werkzeuge mit Freigabe und
`assign_ticket` (eine Übergabe startet Läufe von Agenten). Ein unbekannter
Werkzeugname ist ein Protokollfehler (`-32602`).

### Was ein Token liest und schreibt

- Lesbar ist, was Abschnitt [Rechte eines Tokens](#rechte-eines-tokens) und
  [Datenort](#datenort-des-endpunkts) sagen: Rechte der Person ∩ Umfang ∩
  KI-Richtlinie für den Datenort des Endpunkts, nie Entwürfe, nie etwas mit KI-Sperre.
  Was das Token nicht lesen darf, antwortet **genau wie eine unbekannte ID**
  („Nothing found (or not readable).“), auch in der Suche und in Listen.
- Geschrieben wird nur mit `write`-Token, nur in den Bereichen des Umfangs und nur, was
  die Person dort selbst darf (ein `write`-Token einer lesenden Person schreibt nichts).
- Was ein Token schreibt, gehört **seiner Person** und trägt das **KI-Kennzeichen**:
  den Namen des Tokens in `via_token` an der Nachricht, am Ticket, am Seitenvorschlag
  und an der Seitenversion (Quelle `mcp`; auch wenn ein Vorschlag angenommen wird).
  Vorschläge und Versionen mit `via_token` haben `ai: true`. Nachrichten über ein Token
  erwähnen niemanden und starten keinen Lauf eines Agenten.
- Auch die **Systemeinträge der Zeitleiste**, die ein Aufruf auslöst (Ticket angelegt,
  Status geändert, Seite verknüpft, Seitenvorschlag gemacht), tragen den Namen des
  Tokens in `via_token`. Die Ereignisse der Outbox nennen dafür nur die ID des Tokens
  (`token_id` in der Nutzlast, gesetzt um jeden Werkzeugaufruf herum,
  `outbox.through_token`); den Namen liest der Handler beim Schreiben des Eintrags.
- Eine Ablehnung (nicht gefunden, nicht erlaubt, Status „erledigt“) und ein Konflikt
  mit einer zwischenzeitlichen Änderung („Changed meanwhile (…): read it again.“) sind
  **Werkzeugfehler** (`isError: true`); das Werkzeug hat dann nichts geschrieben.
  Ungültige Argumente nennen nur die Felder, nie ihre Werte. Ein unerwarteter Fehler
  ist „The call failed. Try again later.“, ohne Einzelheiten; was der Aufruf schon
  geschrieben hatte, ist zurückgenommen.
- Jeder Aufruf eines schreibenden Werkzeugs steht im **Audit** (`mcp.write_call` am
  Token, mit Werkzeug und Ergebnisart, nie mit Inhalt).

### Schutz des Endpunkts

- **Kein Browser**: Eine Anfrage mit `Origin`-Kopf wird abgelehnt (403
  `mcp.origin_refused`), gültiges Token oder nicht (Schutz vor DNS-Rebinding und vor
  Seiten mit einem eingefügten Token). Es gibt keine CORS-Köpfe. Ein Sitzungs-Cookie
  öffnet `/mcp` nicht.
- **Token**: nur `Authorization: Bearer`; jede Art von ungültigem Token antwortet 401
  `token.invalid` mit `WWW-Authenticate: Bearer realm="to-herd-cats-ai",
  error="invalid_token"`. Ratenbegrenzung je Token wie oben (429 `mcp.rate_limited`,
  `Retry-After`); jede HTTP-Anfrage zählt.
- **Größen**: Anfragen höchstens `HERD_MAX_BODY_BYTES` (413), Antworten höchstens
  1 MiB, der Text eines Werkzeugergebnisses höchstens 100.000 Zeichen (dahinter
  gekürzt, mit Hinweis).
- **Fehlerform**: Ablehnungen vor dem MCP-Teil (403, 401, 405, 429) kommen als
  JSON-RPC-Fehler ohne `id`, mit dem üblichen Fehler (`code`, `message`, `trace_id`)
  in `error.data`; Fehler im MCP-Teil als JSON-RPC-Fehler des SDK, ohne interne
  Einzelheiten.

### Nutzung je Token

Jeder Werkzeugaufruf wird gezählt (`mcp_call`: Token, Werkzeug, Ergebnisart `ok`,
`refused`, `invalid` oder `failed`, Dauer, Zeit; nur IDs, nie Argumente oder
Ergebnisse) und in der Metrik `herd_mcp_calls_total{tool, outcome}`. Die Zeilen
bleiben 90 Tage: die Fälligkeits-Schleife des Workers löscht ältere einmal je Minute in
Stapeln von höchstens 1.000 (`MCP_CALL_RETENTION` in `app/worker/due.py`, Index auf
`created_at`; siehe [`AGENTEN.md`](AGENTEN.md#aufbewahrung)). Ein widerrufenes Token
behält seine Zeilen bis dahin.

- `GET /api/tokens/{id}/calls` (seitenweise, neueste zuerst): die Aufrufe eines eigenen
  Tokens (`mcp.use`; fremde Token 404 `token.not_found`).
- `GET /api/ai/mcp/tokens/{id}/calls`: dasselbe für jedes Token der Organisation
  (`ai.manage`; sonst 404 `ai.not_found`).

Logzeilen `mcp.tool_call` nennen Person, Werkzeug, Ergebnisart und Dauer; das Token
selbst, Argumente und Ergebnisse stehen in keiner Logzeile (Test
`test_mcp_endpoint_usage.py`).

### Aufbau

- `backend/app/mcp/endpoint.py`: die Route (`Origin`, Token, Methode, Fehlerform);
  `backend/app/mcp/server.py`: je Anfrage ein `Server` des SDK (Low-Level, nur
  `tools/list` und `tools/call`) mit einem zustandslosen Sitzungsmanager, die Antwort
  gesammelt und als eine Antwort gesendet, nachdem die Transaktion der Anfrage steht.
  Nur `backend/app/mcp/` importiert das SDK.
- `backend/app/modules/mcp_tools/`: welche Werkzeuge (`exposed.py`), ein Aufruf
  (`service.py`: Argumente prüfen, Savepoint, `mcp_call`, Audit), der Schreibkontext
  des Tokens (`context.py`) und die Nutzung (`usage.py`). Lesende Werkzeuge nehmen
  einen `CallContext`, schreibende einen `WriteContext`, den Läufe (`ToolContext`) und
  Token (`TokenContext`) gleich bedienen; mypy hält die Werkzeuge von `/mcp` von
  allem fern, was einen Lauf braucht.
- Tests: `tests/test_mcp_endpoint.py`, `test_mcp_read_tools.py`,
  `test_mcp_write_tools.py`, `test_mcp_endpoint_usage.py`, `test_mcp_offered_tools.py`
  (ein echter Client des SDK über ASGI gegen die App).

## Externe Agenten

Ein externer Agent (Plan M8, Entscheidungen 11 und 12; Bedienung:
[`AGENTEN.md`](AGENTEN.md#externe-agenten-seit-m8)) arbeitet von außen über `/mcp`, mit
einem **Agenten-Token** statt eines persönlichen. Zum Beispiel ein Claude Code oder
Codex, das ein Team als Mitarbeiter betreibt: Er holt sich Tickets ab, arbeitet sie ab
und bringt sie bis „Zur Prüfung“.

### Agenten-Token ausstellen

Personen, die den Agenten verwalten (`agent.manage`; alle anderen 404
`agent.not_found` wie für einen unbekannten Agenten):

- `POST /api/agents/{id}/tokens` mit denselben Feldern wie ein persönliches Token
  (`name`, `mode`, `expires_in_days`, optional `space_ids`). Die Antwort enthält den
  Klartext in `secret`, **genau einmal**, mit dem Präfix `herd_agt_`.
  - Nur für externe Agenten (422 `token.agent_not_external`).
  - Nur solange die verantwortliche Person `mcp.use` hat (Schalter an, aktiv, kein
    Gast, nicht „keine KI“; sonst 422 `token.responsible_without_mcp`).
  - `space_ids`: nur Bereiche, die der Agent lesen darf (Mitgliedschaft oder offener
    Bereich), sonst 422 `token.space_invalid`. Ohne: alle diese Bereiche.
- `GET /api/agents/{id}/tokens` (seitenweise, neueste zuerst; nur Metadaten, mit
  `agent_id`), `DELETE /api/agents/{id}/tokens/{token_id}` (Widerruf, 204, idempotent;
  das Token eines anderen Agenten antwortet 404 `token.not_found`),
  `GET /api/agents/{id}/tokens/{token_id}/calls` (die Aufrufe des Tokens: die Aktivität
  des Agenten über `/mcp`).
- Das Token gehört in der Datenbank der **verantwortlichen Person** (`user_id`) und
  nennt den Agenten (`agent_id`, Art `agent`). In der eigenen Token-Liste der Person
  erscheint es nicht; die Verwaltung (`GET /api/ai/mcp/tokens`) zeigt es mit `agent`
  (ID und Name) und widerruft es wie jedes Token.
- Audit: `access_token.created` (mit `agent_id`, Art, Modus, Umfang, Ablauf) und
  `access_token.revoked` (mit `agent_id`), nie Hash oder Klartext.

### Rechte eines Agenten-Tokens

Bei jedem Aufruf neu aufgelöst, wie bei persönlichen Token:

- Lesbar und beschreibbar ist die Schnittmenge aus den **Mitgliedschaften des Agenten**
  (seine Rolle je Bereich; in offenen Bereichen liest er), den **Rechten der
  verantwortlichen Person**, dem **Umfang des Tokens** und der **KI-Richtlinie** für
  den Datenort des Endpunkts; nie Entwürfe. Nimmt man dem Agenten oder der Person
  einen Bereich, ist er sofort weg.
- **Höchstens Stufe 2**, und nur bis zur Stufe des Agenten: Ein `write`-Token eines
  Agenten auf Stufe 2 bekommt die lesenden Werkzeuge, `list_my_tickets`,
  `claim_ticket`, `create_ticket`, `comment_ticket`, `set_ticket_status`,
  `link_ticket_page`, `propose_page_change` und `propose_new_page`; nie `update_page`
  oder `post_message` (Stufe 3). Auf Stufe 1 oder mit einem `read`-Token nur die
  lesenden Werkzeuge und `list_my_tickets`. Werkzeugfreigaben des Agenten
  (`agent_tool`) schränken weiter ein: Angeboten wird nur, was `allow` bleibt.
- Der Agent **ruht** (das Token antwortet 401 `token.invalid`, wie ein unbekanntes),
  solange er nicht aktiv ist (pausiert oder Entwurf), seine verantwortliche Person
  kein `mcp.use` hat (inaktiv, Gast, „keine KI“, Schalter aus) oder eine andere Person
  für ihn verantwortlich ist. Ein Wechsel der Verantwortung **widerruft** alle seine
  Token (Audit `agent.updated` mit `tokens_revoked`), sodass sie auch dann nicht wieder
  gelten, wenn die Verantwortung zurückgeht (Review M8 1, Befund 9); man stellt neue
  aus.
- Was das Token schreibt, ist **des Agenten** (`author`/`reporter` vom Typ `agent`,
  Nachrichten der Art `agent`), mit dem Namen des Tokens in `via_token`, auch in den
  Systemeinträgen der Zeitleiste. Seine Nachrichten erwähnen niemanden und starten
  keinen Lauf.

### Ticket-Abholung

Nur mit einem Agenten-Token:

| Werkzeug | Was es tut |
|---|---|
| `list_my_tickets` | die Tickets, die dem Agenten zugewiesen und nicht erledigt oder verworfen sind, zuletzt geänderte zuerst, je mit Schlüssel, Status und `version` (höchstens 50) |
| `claim_ticket` | ein nicht zugewiesenes Ticket (oder ein schon eigenes) übernehmen: es wird dem Agenten zugewiesen und wechselt aus einem offenen Status in den ersten Status der Kategorie „in Arbeit“ des Bereichs; mit der gelesenen `version` (ohne: die aktuelle). Ein Ticket einer anderen Person oder eines anderen Agenten, eines zur Prüfung, erledigt oder verworfen wird abgelehnt |

- Von zwei Agenten, die dasselbe Ticket zugleich übernehmen, bekommt es einer; der
  andere bekommt einen Werkzeugfehler („Changed meanwhile (ticket.version_conflict)“
  oder „Assigned to someone else“). Die Zeile des Tickets ist dabei gesperrt
  (`tickets/claiming.py`).
- Übernehmen kann der Agent nur in Bereichen, in denen er (und seine Person) Tickets
  bearbeiten darf (`ticket.edit`; Mitglied mindestens als `editor`).
- Danach wie bei internen Agenten: kommentieren, den Status höchstens bis zur Kategorie
  „Zur Prüfung“ setzen (`set_ticket_status`; „erledigt“ und „verworfen“ setzt ein
  Mensch), Seitenvorschläge.
- Einem externen Agenten zugewiesene, noch offene Tickets tragen in der API
  `awaiting_pickup: true` („wartet auf Abholung“). Die Zuweisung startet keinen Lauf und
  schreibt keinen Hinweis in die Ticket-Diskussion.
- In der Oberfläche: Administration → Agenten → „Externen Agenten anlegen“ (Name,
  Kurzvorstellung, verantwortliche Person, Status, Stufe 1 oder 2; kein Modell). Die
  Seite des Agenten zeigt nur, was für ihn zählt: Stufe bis 2, „Werkzeuge über MCP“
  (nur „Erlaubt“ oder „Gesperrt“) und „Token des Agenten“ (anlegen mit Klartext einmal
  und `$HERD_AGENT_TOKEN`, Aufrufe, widerrufen); keine Läufe, Skills oder Aufgaben.
  Tickets, die auf Abholung warten, tragen „Wartet auf Abholung“ in Liste, Board und
  Ticket; Personen- und Erwähnungsauswahl markieren einen externen Agenten mit „extern“.

### Einrichten in Claude Code und Codex

Wie für ein persönliches Token ([Einen Client verbinden](#einen-client-verbinden)), nur
mit dem Agenten-Token in der Umgebung des Rechners oder der Pipeline, auf dem der Agent
läuft:

```bash
claude mcp add --transport http herd https://herd.example.com/mcp \
  --header "Authorization: Bearer $HERD_AGENT_TOKEN"
```

Für Codex `bearer_token_env_var = "HERD_AGENT_TOKEN"`. Ein sinnvoller Auftrag an den
Agenten: „Rufe `list_my_tickets` auf, übernimm das erste Ticket mit `claim_ticket`,
arbeite es ab, kommentiere das Ergebnis und setze es auf ‚Zur Prüfung‘.“

## Konnektoren

Ein Konnektor ist ein gespeicherter Zugang zu einem externen Dienst (Plan M8,
Entscheidung 9). Das Geheimnis wird nur serverseitig beim Aufruf eingesetzt; es steht
nie in einer Antwort, im Prompt, in Werkzeugargumenten, im Laufprotokoll, im Audit oder
im Log.

- **Geteilt** (`/api/ai/connectors`, Recht `ai.manage`): gehört der Organisation, z. B.
  ein Bot-Token für GitHub. Wer `ai.manage` nicht hat, bekommt 404 `ai.not_found`.
- **Persönlich** (`/api/ai/my-connectors`, Recht `ai.use`, „Meine Verbindungen“):
  gehört genau einer Person und handelt in ihrem Namen. Nur diese Person sieht, ändert
  und löscht ihn; für alle anderen, Admins eingeschlossen, ist er 404
  `connector.not_found` wie eine unbekannte ID. Ohne `ai.use` antwortet die Liste
  404 `ai.not_found`.
- **Anmeldearten** (`auth_kind`): `bearer` sendet `Authorization: Bearer <Geheimnis>`;
  `header` sendet das Geheimnis als Wert des Kopfes `header_name` (etwa
  `PRIVATE-TOKEN` bei GitLab). Köpfe, die der HTTP-Client oder das MCP-Protokoll
  selbst setzen (`Host`, `Content-Type`, `Accept`, `Mcp-Session-Id`,
  `Mcp-Protocol-Version`, `Proxy-*`, `Sec-*` u. a.), sind nicht erlaubt. Der Wert ist
  sichtbares ASCII ohne Leerzeichen (wie bei KI-Schlüsseln, `core/secrets.py`).
  `oauth` holt das Token beim Verbinden selbst (siehe „OAuth-Konnektoren“).
- **Geheimnis**: `{"value": "…"}` wird als `enc:` unter `HERD_SECRET_KEY` gespeichert;
  ein geteilter Konnektor darf stattdessen eine Umgebungsvariable nennen
  (`{"env": "HERD_AI_…"}`, dieselben Regeln wie bei KI-Verbindungen). Persönliche
  Konnektoren sind nur `enc:` (422 `connector.env_not_allowed`): eine Person kann die
  Umgebung des Servers nicht benennen. Antworten zeigen nur `has_secret` und
  `secret_kind` (`enc`/`env`); ein `PATCH` mit `secret` ersetzt es.
- **Schreiben** nennt die gelesene `version` (409 `connector.version_conflict`); Namen
  sind je Eigentümer eindeutig, ohne Groß-/Kleinschreibung (409
  `connector.name_taken`).
- **Audit**: `connector.created`, `connector.updated`, `connector.deleted` mit der ID,
  dem Geltungsbereich, der Anmeldeart, den Namen geänderter Felder und beim Geheimnis
  nur seiner Art, nie mit Werten.
- **Schlüsselwechsel**: `scripts/rotate_secrets.py` schlüsselt die `enc:`-Werte aller
  Konnektoren mit um (siehe [`KI.md`](KI.md#schlüssel)).
- **Persönlicher Zugang zu einem Server**: Ein persönlicher Konnektor kann beim Anlegen
  einen externen MCP-Server nennen (`mcp_server_id`), der mit dem Zugang jeder Person
  arbeitet; je Person und Server einer (409 `connector.server_taken`), andere Server
  422 `connector.server_invalid`. `GET /api/ai/my-mcp-servers` (`ai.use`) listet diese
  Server mit `url` (wohin der eigene Zugang geht) und `connected`. Wird der Server
  gelöscht, gehen die daran gebundenen persönlichen Konnektoren mit; ihre OAuth-Token
  werden nach dem Commit beim Anbieter widerrufen (Review M8 1, Befund 8), und das
  Audit `mcp_server.deleted` nennt ihre Zahl (`personal_connectors_disconnected`).
- **Wohin ein Geheimnis geht**: Jeder Konnektor nennt `server_urls`, die Adressen der
  Server, an die sein Geheimnis geht (ein geteilter: jeder Server, der ihn nennt; ein
  persönlicher: sein Server). Ein Geheimnis geht nur dorthin, wofür es hinterlegt wurde
  (Review M8 1, Befund 4): Bekommt ein Server einen **neuen Ursprung** (Schema, Host oder
  Port; ein anderer Pfad zählt nicht, denn derselbe Ursprung ist derselbe Empfänger, der
  das Geheimnis schon hat), werden in derselben Transaktion alle persönlichen
  Konnektoren dieses Servers getrennt: gelöscht, OAuth-Token nach dem Commit beim
  bisherigen Anbieter widerrufen. Die Personen sehen unter „Meine Verbindungen“ „Nicht
  verbunden“ mit der neuen Adresse und verbinden sich bewusst neu. Ein geteilter
  Konnektor wird vom Server gelöst (`connector_scope` `none`), außer die Änderung sagt
  `keep_shared_connector: true` oder nennt mit ihr einen anderen geteilten Konnektor.
  Audit `mcp_server.updated` mit `moved` (`personal_connectors_disconnected`,
  `shared_connector_detached`).
- **In Gebrauch**: Ein geteilter Konnektor, den ein Server nennt, wird nicht gelöscht
  (409 `connector.in_use`).

## OAuth-Konnektoren

Ein Konnektor der Art `oauth` holt sein Zugangstoken über OAuth 2 (Autorisierungscode
mit PKCE, OAuth 2.1, RFC 7636) bei einem Autorisierungsserver und erneuert es selbst
(Plan M8, Task 8). Geltung wie bei jedem Konnektor: geteilt (der Admin verbindet ihn
einmal, etwa mit einem Bot-Konto) oder persönlich (jede Person verbindet ihren eigenen,
er handelt in ihrem Namen).

### OAuth-Clients

Die Registrierung der Organisation beim Anbieter (eine GitHub-OAuth-App, eine
GitLab-Anwendung) heißt **OAuth-Client**; Verwaltung unter `/api/ai/oauth-clients`
mit `ai.manage` (sonst 404 `ai.not_found`): `GET`/`POST`, `GET`/`PATCH`/`DELETE
…/{id}` (`DELETE ?version=`).

- **Felder**: `name` (je Organisation eindeutig, 409 `oauth_client.name_taken`),
  `authorization_endpoint`, `token_endpoint`, optional `revocation_endpoint` (RFC
  7009), `client_id`, `client_secret` (schreibend: `{"value": …}` → `enc:`, `{"env":
  "HERD_AI_…"}` oder `null` für einen öffentlichen Client, der nur mit PKCE arbeitet),
  `token_auth` (`client_secret_post`, Standard, oder `client_secret_basic`: wie das
  Geheimnis zum Token-Endpunkt geht), `scopes` (leerzeichengetrennt), optional
  `resource` (RFC 8707: die Adresse des MCP-Servers, für den die Token gelten; MCP
  verlangt sie in Autorisierungs- und Token-Anfrage). Antworten zeigen nur
  `has_client_secret` und `client_secret_kind`.
- Die Adressen gehen durch dieselben Regeln wie die eines MCP-Servers (https, keine
  Zugangsdaten, Query oder Fragment, keine private oder Metadaten-Adresse als Literal;
  422 `oauth_client.url_not_allowed`); private Hosts nur, wenn
  `HERD_MCP_ALLOWED_HOSTS` sie nennt (ein GitLab im Firmennetz ist sein eigener
  Autorisierungsserver). Aufgerufen wird der Anbieter nur über den geschützten Ausgang.
- Schreiben nennt die `version` (409 `oauth_client.version_conflict`). Ein Client, den
  ein Konnektor oder ein Server nennt, wird nicht gelöscht (409 `oauth_client.in_use`).
- **Neue Endpunkte trennen** (Review M8 1, Befund 4): Ändert sich
  `authorization_endpoint`, `token_endpoint` oder `revocation_endpoint` (jede Änderung
  der Adresse; an Token- und Widerrufsadresse gehen Token), wird jeder Konnektor über
  diesen Client getrennt, bevor die neuen Adressen gelten: persönliche werden beim
  bisherigen Anbieter widerrufen und gelöscht, geteilte verlieren ihre Token (ebenfalls
  widerrufen), außer `keep_shared_connectors: true`.
- Audit `oauth_client.created`, `.updated` (Feldnamen, beim Geheimnis nur seine Art,
  bei neuen Endpunkten `moved` mit den Zahlen getrennter Konnektoren), `.deleted`; nie
  Werte.
- **Beim Anbieter registrieren**: Jede OAuth-App hat eine eigene Rückleitungsadresse
  (Callback-URL), `<HERD_PUBLIC_URL>/api/ai/oauth/<id>/callback` (seit M9b; `id` ist
  die der App hier, nicht die Client-ID beim Anbieter). Die Antwort nennt sie als
  `callback_url`, die Karte der App zeigt sie; sie wird beim Anbieter genau so
  eingetragen (bei GitHub und GitLab geht das auch nach dem Anlegen). **Nach dem Update
  auf M9b**: Für jede bestehende OAuth-App die neue Adresse beim Anbieter eintragen;
  bestehende Verbindungen laufen weiter (das Erneuern braucht keine Rückleitung), nur
  neues Verbinden braucht sie.
- **Aussteller** (`issuer`, optional) und `issuer_in_response`: Der Aussteller des
  Autorisierungsservers (RFC 8414); schickt der Server in seiner Antwort `iss` mit
  (RFC 9207), muss es genau dieser sein. `issuer_in_response: true` (aus den
  Metadaten, `authorization_response_iss_parameter_supported`) heißt, der Server
  schickt `iss` immer; eine Antwort ohne gilt dann als fremd. Ohne Aussteller (422
  `oauth_client.issuer_required` mit `issuer_in_response`) wird ein gesendetes `iss`
  nicht verglichen; dann schützt allein die eigene Rückleitungsadresse.
- **Ermitteln** (`POST /api/ai/oauth-clients/discover` mit `{"url": "<MCP-Server>"}`):
  schlägt die Felder vor, wie die MCP-Autorisierung (Stand 2025-11-25) es vorsieht:
  Zuerst wird der Server ohne Token gefragt; nennt seine 401-Antwort in
  `WWW-Authenticate` `resource_metadata` (RFC 9728), gilt diese Adresse und ihr
  `scope`. Sonst die Well-known-Adressen (`/.well-known/oauth-protected-resource/<Pfad>`,
  dann an der Wurzel). Das `resource` der Metadaten muss die Adresse des Servers sein
  (sonst `resource_mismatch`); vom ersten Autorisierungsserver werden die Metadaten
  gelesen (RFC 8414, OpenID Discovery, mit den Pfadvarianten). `pkce` sagt, ob der
  Server S256 ankündigt (gesendet wird S256 immer), `registration`, ob er dynamische
  Registrierung anbietet (genutzt wird sie nicht: der Client wird von Hand
  registriert). Gespeichert wird nichts; jede Anfrage über den geschützten Ausgang,
  Antworten höchstens 64 KiB. `status`: `ok`, `blocked`, `timeout`, `unreachable`,
  `no_metadata`, `resource_mismatch`, `no_authorization_server`, `invalid_metadata`.

### Konnektor anlegen, verbinden, trennen

- **Anlegen**: `{"name", "auth_kind": "oauth", "oauth_client_id"}` ohne `secret` (ein
  unbekannter Client: 422 `connector.oauth_client_invalid`). Bis er verbunden ist, ist
  `has_secret` `false`. Ein OAuth-Konnektor bleibt einer, und kein anderer wird es (422
  `connector.oauth_fixed`); ein Geheimnis lässt sich ihm nicht geben.
- **Verbinden**: `POST /api/ai/connectors/{id}/authorize` bzw.
  `/api/ai/my-connectors/{id}/authorize` (wer den Konnektor verwalten darf) antwortet
  `{"authorization_url"}`; die Oberfläche schickt den Browser dorthin. Die Adresse
  trägt `response_type=code`, `client_id`, `redirect_uri`, `state`, die
  S256-`code_challenge`, `scope` und `resource`, nie das Client-Geheimnis.
- **Rückkehr**: Der Anbieter schickt den Browser an
  `GET /api/ai/oauth/<id>/callback`, die Rückleitungsadresse seiner App. Ein Ablauf
  wird nur an der Adresse beendet, mit der er begann (sonst `invalid`, der Ablauf ist
  verbraucht, nichts wird eingelöst), und `iss` muss passen (sonst `issuer_mismatch`,
  ebenso). Der Code wird eingelöst (mit Prüfwert, derselben Rückleitungsadresse und `resource`),
  die Token als `enc:` gespeichert, die Version des Konnektors erhöht, Audit
  `connector.connected` (Geltung, ob ein Erneuerungstoken kam). Danach geht der
  Browser auf die Seite `/ai/oauth/done?status=…` (mit `connector` und `scope`, wenn
  bekannt); `status` ist `connected`, `denied` (abgelehnt beim Anbieter), `failed`
  (Fehler des Anbieters oder beim Einlösen), `invalid` (unbekannter, benutzter,
  abgelaufener oder fremder `state`, falsche Rückleitungsadresse, Konnektor weg,
  Rechte weg) oder `issuer_mismatch` (`iss` nicht der Aussteller der App, oder es
  fehlt, obwohl der Server es zugesagt hat). Was der Anbieter sagt, steht nie in
  dieser Adresse.
- **Trennen**: `POST …/{id}/disconnect` mit `{"version"}` löscht die Token (Audit
  `connector.disconnected`) und widerruft sie nach dem Commit beim Anbieter (RFC 7009,
  erst das Erneuerungstoken, dann das Zugangstoken), sofern der Client einen
  `revocation_endpoint` hat; ohne einen (GitHub-OAuth-Apps haben keinen) bleibt der
  Widerruf in den Einstellungen des Kontos beim Anbieter. Das Löschen eines
  verbundenen Konnektors widerruft ebenso.

### `state`, PKCE und Rückleitungsadresse

- `state` (256 Bit) und Prüfwert entstehen beim Start und liegen in Postgres
  (`oauth_flow`), nicht im Prozess: vom `state` nur der SHA-256, der Prüfwert als
  `enc:`; dazu die Anmeldesitzung, die Rückleitungsadresse und ein Ablauf (10
  Minuten). Die Rückkehr gilt nur in **derselben Anmeldesitzung**; die Zeile wird in
  der Anweisung gelöscht, die sie findet, also genau **einmal** eingelöst. Eine
  Rückkehr aus einer anderen Sitzung verbraucht sie nicht. Abgemeldete Sitzungen
  nehmen ihre offenen Abläufe mit.
- Die **Rückleitungsadresse** ist `HERD_PUBLIC_URL` plus `/api/ai/oauth/<id>/callback`
  (je App eine eigene, Schutz gegen Mix-up-Angriffe: die Antwort eines Servers kann
  keinen Ablauf beenden, der mit einem anderen begann), nie aus Kopfzeilen der Anfrage
  (`Host`, `X-Forwarded-Host`). Die gemeinsame Adresse früherer Versionen,
  `/api/ai/oauth/callback`, beendet nur noch Abläufe, die mit ihr begannen (also
  höchstens 10 Minuten nach dem Update). Ohne `HERD_PUBLIC_URL` oder
  mit `http` außer für `localhost`/`127.0.0.1` gibt es kein OAuth (422
  `connector.oauth_unconfigured`).
- Das Sitzungs-Cookie ist `SameSite=Lax`; die Rückkehr ist eine Navigation, es kommt
  also mit. Ohne gültige Sitzung endet sie mit `invalid`.
- **Zweck (M10):** Konnektoren und OAuth-Apps haben einen Zweck, `mcp` (alles hier)
  oder `calendar` (der Zugang einer Person zu ihrem externen Kalender, die Google-App
  des Kalenders). Diese Seiten zeigen und ändern nur `mcp`; ein Kalender-Zugang oder
  eine Kalender-App ist hier in keiner Liste und antwortet wie eine unbekannte ID, und
  ein Kalender-Zugang geht nie an einen MCP-Server (umgekehrt ebenso). Die
  Rückleitungsadresse bleibt die der App; nach der Rückkehr entscheidet der Zweck des
  Konnektors, welches Recht noch einmal geprüft wird (`ai.use` bzw. `calendar.sync`) und
  wohin der Browser geht (`/ai/oauth/done` bzw. `/calendar/accounts`). Namen sind über
  beide Zwecke eindeutig (je Person bzw. Organisation), wie in M8.

### Erneuerung

- Läuft das Zugangstoken in weniger als 60 Sekunden ab, wird es vor dem Aufruf
  erneuert; antwortet der Server mit 401, wird es einmal erneuert und der Aufruf
  wiederholt (beim Aufruf im Lauf wie beim Einlesen der Werkzeuge). Ein zweites 401
  ist die Antwort des Servers (`unauthorized`).
- Die Erneuerung läuft in einer **eigenen Transaktion**, die die Zeile des Konnektors
  sperrt (`FOR UPDATE`, Wartezeit 30 s), bevor sie den Anbieter fragt, und die neuen
  Token festschreibt, bevor sie die Sperre löst. Ein zweiter Worker, der zugleich
  erneuern will, wartet und nimmt dann das neue Token, ohne selbst zu fragen. Das ist
  nötig, weil Anbieter Erneuerungstoken nach einmaligem Gebrauch ungültig machen
  (GitHub, GitLab); ein zweiter Versuch mit dem alten würde scheitern.
- Lehnt der Anbieter das Erneuerungstoken ab (`invalid_grant`), werden die Token
  gelöscht; der Konnektor ist nicht mehr verbunden, ein Aufruf endet mit
  `mcp_tool.not_connected`, bis jemand neu verbindet. Ist der Anbieter nicht
  erreichbar oder antwortet anders falsch, bleiben die Token (Fehler
  `mcp_tool.credential_unavailable`; der nächste Aufruf versucht es wieder). Schickt
  der Anbieter kein neues Erneuerungstoken, gilt das alte weiter.
- Ein Konnektor ohne Token: Aufruf `mcp_tool.not_connected`, Einlesen der
  Werkzeugliste `secret_unavailable`.

### Was nie irgendwo steht

Code, `state`, Prüfwert, Zugangs- und Erneuerungstoken und Client-Geheimnis stehen in
keiner Logzeile, keinem Audit-Eintrag, keinem Outbox-Ereignis, keiner Fehlermeldung,
keiner Adresse, die die App schreibt, und keinem Trace (die Rückkehr-Route erzeugt
keinen Span, weil ein Span die Adresse mit Query aufzeichnet; Test
`test_oauth_secrecy.py`). Fehlerantworten des Anbieters werden verworfen; was schief
ging, ist ein fester Zustand (`invalid_grant`, `rejected`, `blocked`, `timeout`,
`unreachable`, `redirect`, `server_error`, `invalid_response`). Logzeile
`oauth.token_request` mit Konnektor, Art (`authorization_code`, `refresh_token`,
`revocation`), Zustand und Dauer. Hinweis für den Betrieb: Der Code steht in der Query
der Rückkehr und damit im Zugriffsprotokoll eines vorgeschalteten Proxys; er ist nur
einmal und nur mit Prüfwert (und Client-Geheimnis) einlösbar.

### Schlüsselwechsel

`scripts/rotate_secrets.py` schlüsselt auch Zugangs- und Erneuerungstoken,
Client-Geheimnisse und die Prüfwerte offener Abläufe um.

### Persönliche Server mit OAuth

Ein Server mit `connector_scope` `personal` kann `oauth_client_id` nennen (nur dann;
422 `mcp_server.oauth_client_invalid`): den Client, mit dem die Leute ihren eigenen
Konnektor verbinden. `GET /api/ai/my-mcp-servers` nennt ihn je Server
(`oauth_client_id`); die Oberfläche legt damit einen persönlichen Konnektor
`{"auth_kind": "oauth", "oauth_client_id", "mcp_server_id"}` an und startet
`authorize`.

### Tests

Gegen einen eigenen Autorisierungsserver im Testprozess
(`backend/tests/support/oauth_stub.py`, https für `oauth.test`: Code mit PKCE,
Erneuerung mit Rotation, Widerruf, Metadaten nach RFC 8414 und RFC 9728, skriptbar;
als Prozess `python -m tests.support.oauth_stub --port 8099`), nie gegen das Netz.

## Externe MCP-Server

Externe MCP-Server sind eine Werkzeugquelle für die eigenen Agenten (Plan M8,
Entscheidung 7). Verwaltung unter `/api/ai/mcp-servers` mit `ai.manage`; ohne das
Recht 404 `ai.not_found`.

- **Nur Streamable HTTP über https**, nie stdio. Die Adresse wird beim Speichern
  geprüft (kein `http`, keine Zugangsdaten, keine Query, kein Fragment, keine private,
  Loopback-, Link-Local- oder Metadaten-Adresse als Literal; 422
  `mcp_server.url_not_allowed`) und bei jeder Verbindung erneut: Der Name wird beim
  Verbindungsaufbau aufgelöst, jede Antwort geprüft und nur die geprüfte Adresse
  gewählt (DNS-Wechsel greift nicht), wie bei KI-Verbindungen
  ([`KI.md`](KI.md#ausgehende-aufrufe-ssrf-sperre)); mit `HERD_AI_EGRESS_PROXY` geht der
  Aufruf durch den Proxy. Private Adressen erreicht ein MCP-Server nur, wenn der
  Betrieb sie freigibt (siehe „Selbst betriebene Server im eigenen Netz“).
  Umleitungen folgt der Client nur innerhalb derselben Herkunft (Schema, Host, Port);
  jede andere endet mit dem Zustand `redirect`.
- **Felder**: Name (je Organisation eindeutig), `url`, `data_location`
  (`local`/`eu`/`external`, wie bei einer Verbindung; die KI-Richtlinie entscheidet
  damit, ob ein Lauf das Werkzeug aufrufen darf), `connector_scope` (`none`, `shared`
  mit `connector_id` eines geteilten Konnektors, `personal`: der Zugang der Person, in
  deren Auftrag aufgerufen wird, optional mit `oauth_client_id`), `enabled`, `version`
  (409 `mcp_server.version_conflict`).
- **Werkzeugliste**: wird beim Anlegen und mit `POST …/{id}/refresh` eingelesen, ohne
  offene Transaktion, mit Zeitlimit (20 s) und Größenlimit (2 MiB); höchstens 500
  Werkzeuge (bei mehr die ersten 500 nach Namen, gleich in welcher Reihenfolge der
  Server sie nennt), Namen nur aus `A-Z a-z 0-9 _ - .` (1–128 Zeichen), Beschreibungen
  gespeichert bis 10.000 Zeichen, Eingabeschemas bis 64 KiB (ein größeres wird nicht
  gespeichert; der Fingerabdruck umfasst es trotzdem ganz). Das Ergebnis ist ein Zustand mit Zahlen
  (`{"status", "new", "changed", "missing"}`), nie die Antwort des Servers. Gelesen wird
  mit dem geteilten Konnektor bzw. bei `personal` mit dem eigenen Konnektor der Admin-
  Person, falls vorhanden. `POST …/{id}/test` verbindet und zählt die Werkzeuge, ohne
  etwas zu speichern.
- **Freigabe je Werkzeug** (`GET …/{id}/tools`, `POST …/tools/{tool_id}/approve`,
  `…/block`, `PATCH …/tools/{tool_id}`, jeweils mit `version`, 409
  `mcp_tool.version_conflict`): Neue Werkzeuge kommen als `pending`. Gespeichert wird
  ein Fingerabdruck (SHA-256 über Name, vollständige Beschreibung und Eingabeschema);
  eine Freigabe merkt sich genau diesen (`approved_fingerprint`). Liest ein Refresh
  einen anderen, wird ein freigegebenes Werkzeug `changed` und ist gesperrt, bis es
  erneut freigegeben wird (kehrt der Server zum freigegebenen Stand zurück, ist es
  wieder `approved`). Solange eine Freigabe steht, merkt sie sich auch die freigegebene
  Beschreibung und das Schema (`approved_description`, `approved_input_schema`): bei
  einem geänderten Werkzeug zeigt die Verwaltung, was sich geändert hat (Beschreibung,
  Eingabeschema), und die freigegebene Fassung neben der neuen (Review M8 1, Befund 14;
  nie in Logs). Für Freigaben von vor dem Update übernimmt die Migration `a6ce005832fd`
  die Fassung nur, wo der Fingerabdruck noch der freigegebene ist; sonst zeigt die
  Verwaltung nur die Fingerabdrücke. Werkzeuge, die der Server nicht mehr nennt, sind `missing` und
  nicht freizugeben (409 `mcp_tool.missing`). Eine Organisation hält höchstens 200
  freigegebene Werkzeuge über alle Server (freigegeben oder seitdem `changed`; 409
  `mcp_tool.approved_limit`, gezählt in SQL, eine Freigabe nach der anderen): die
  Werkzeugliste eines Agenten zeigt jedes davon und hat statt Seiten diese Grenze
  (Review M8 1, Befund 14). Ein gesperrtes Werkzeug gibt seinen Platz frei. Eine neue
  Adresse des Servers zieht alle
  Freigaben zurück; ein neuer Ursprung trennt zudem seine Konnektoren (siehe
  „Konnektoren“, „Wohin ein Geheimnis geht“).
- **Eingabeschema und Modell** (Review M8 1, Befund 2): Jedes Wort eines Schemas ist
  ein Wort des Servers. Ein Modell bekommt deshalb nur die **Struktur** (Typen,
  Feldnamen, Pflichtfelder, Elemente, Verschachtelung, Zahl- und Längengrenzen, gängige
  Formate); was der Server über die Argumente sagt (Beschreibung, Titel, erlaubte
  Werte, Voreinstellung, Beispiele, Muster), geht je Feld auf 300 Zeichen und insgesamt
  auf 2.000 Zeichen gekürzt und gerahmt als
  `<untrusted source="mcp_tool_arguments" server=…>` in die Beschreibung des Werkzeugs.
  Ein Werkzeug, dessen Schema sich so nicht anbieten lässt, hat `schema_problem`:
  `schema_too_large` (über 64 KiB, oder die Struktur über 8.000 Zeichen) oder
  `schema_unsupported` (tiefer als 8 Ebenen) oder `schema_property_names` (ein
  Feldname, auch tief im Schema, der nicht mit einem Buchstaben oder `_` beginnt, andere
  Zeichen als `A-Z a-z 0-9 _` enthält oder länger als 32 Zeichen ist; Review M8 2,
  Befund G4). Es ist nicht freizugeben (409 `mcp_tool.schema_problem`), wird keinem
  Agenten angeboten, und die Verwaltung zeigt den Grund. **Was bleibt:** Feldnamen sind
  das einzige Wort des Servers, das ungerahmt an das Modell geht (es ist der Name des
  Arguments). Die Regel hält sie kurz und schlicht, aber ein Name wie `ignore_rules`
  bleibt ein Wort des Servers. Die Kontrolle dafür ist die Freigabe: Wer ein Werkzeug
  freigibt, sieht sein Schema mit allen Feldnamen.
- **Einstufung** `read`/`write`: Vorschlag `read` nur, wenn der Server das Werkzeug als
  nur lesend kennzeichnet (`readOnlyHint`) **und** die Vorlage des Katalogs `read`
  vorschlägt, sonst `write`. Die Kennzeichnung allein ist eine unverbindliche Angabe
  des Servers (MCP nennt sie so; ein feindlicher Server kennzeichnet ein zerstörendes
  Werkzeug als lesend) und schlägt nichts vor; die Oberfläche zeigt sie als solche
  (Review M8 1, Befund 7). Ein nicht so gekennzeichnetes Werkzeug auf `read` zu setzen,
  verlangt `confirm_loosen: true` (422 `mcp_tool.loosen_unconfirmed`); das Audit
  vermerkt `loosened`. Ein Vorschlag der Vorlage (`suggested_classification`) `write`
  verschärft immer, `read` lockert nie von selbst (siehe „Katalog“).
- **Aufruf** (`backend/app/modules/mcp_servers/calls.py`): nur ein freigegebenes, noch
  gelistetes Werkzeug mit dem freigegebenen Fingerabdruck eines eingeschalteten Servers. Im selben
  Gespräch mit dem Server wird zuerst die Werkzeugliste gelesen; nennt der Server das
  Werkzeug anders als freigegeben, unterbleibt der Aufruf, das Werkzeug wird `changed`
  (bzw. `missing`). Der Zugang wird serverseitig eingesetzt; fehlt bei `personal` der
  Konnektor der Person, ist das ein Fehler `mcp_tool.not_connected`. Zeitlimit 60 s,
  Antworten höchstens 512 KiB (`too_large`). Das Ergebnis ist nicht vertrauenswürdig
  und wird vom Aufrufer gerahmt.
- **Im Lauf eines Agenten** (Plan M8, Entscheidung 8; Einzelheiten in
  [`AGENTEN.md`](AGENTEN.md#externe-werkzeuge-seit-m8)): Ein Agent bekommt ein
  externes Werkzeug nur mit einem Eintrag in seinen Werkzeugfreigaben
  (`PUT /api/agents/{id}/tools`, Name `ext_…`), und nur, solange es brauchbar ist
  (freigegeben, unverändert, gelistet, Server eingeschaltet), und nur, solange die
  Beschreibungen aller seiner externen Werkzeuge zusammen in 100.000 Zeichen je
  Modellaufruf passen (die zuerst gelisteten zuerst; was nicht passt, bleibt bei jedem
  Schritt und jeder Fortsetzung gleich weg und steht in seiner Werkzeugliste als
  `left_out`; Review M8 2, Befund G5). Lesende Werkzeuge sind
  Stufe 2; schreibende Stufe 4 und immer mit Freigabe der fragenden Person
  (Fingerabdruck über Werkzeug, Argumente und die Versionen von Server und Werkzeug:
  ändert sich eins davon vor dem Ausführen, ist die Freigabe veraltet, und nichts wird
  gesendet). In Läufen von Ereignisregeln gilt das ebenso, und dort wartet auch jeder
  Aufruf eines **lesenden** externen Werkzeugs auf die Freigabe der Eigentümerin über
  genau diese Argumente (der Text der auslösenden Person kann sie bestimmen; Review M8
  1, Befund 5). Vor jedem Aufruf entscheidet
  die KI-Richtlinie aller bisher gelesenen Bereiche (und des Bereichs des Ortes) über
  den `data_location` des Servers wie über den einer Verbindung; lässt sie ihn nicht
  zu, wird nicht aufgerufen (`policy_blocked` als Ergebnis). Der Zugang ist der
  geteilte Konnektor oder bei `personal` der eigene der fragenden Person. Ein Ergebnis
  über den **eigenen Konnektor** der fragenden Person markiert den Lauf wie ein
  gelesener Entwurf (`Reads.personal`, im Journal als `read.personal`, sodass auch ein
  fortgesetzter Lauf es weiß): Was er danach anderswo als allein mit ihr
  schreiben will (ein Kanal, ein Ticket, eine Seite, ein Vorschlag, ein Gedächtnis,
  jeder Bereich), wartet auf ihre Freigabe genau dieses Inhalts (Freigabekarte mit
  `personal: true`; im Lauf einer Automation oder Ereignisregel: der Eigentümerin);
  freigegeben ist es nicht mehr markiert (Review M8 2, Befund G2). Die Karte sagt, dass
  er jetzt oder später von anderen gelesen werden kann, und zeigt den Inhalt
  vollständig (Review M8 4, Befund K5), auch beim Schreibwerkzeug eines Servers, den
  sie mit ihrem eigenen Konnektor nutzt: Was es schreibt, verlässt das System
  (Review M8 5, Befund L3); was sich nicht vollständig zeigen lässt (ein Vergleich über
  `HERD_DIFF_MAX_LINES`), wird abgelehnt (`personal_release.too_large`), statt zur
  Freigabe zu stehen (Review M8 3, Befund H5). Ohne Freigabe schreibt er nur in sein
  eigenes Gespräch allein mit ihr (ihre Direktnachricht mit dem Agenten; markiert).
  Jeder andere Ort wartet, auch ihr persönlicher Bereich, ein Bereich, in dem sie heute
  allein ist, und das Gedächtnis des Agenten: Was dort steht, trägt keine Marke
  (Review M8 4, Befunde K1 und K2). In einem Kanal, Thread oder
  einer Direktnachricht mit mehreren bleiben seine Antwort und seine Rückfrage
  zurückgehalten: Er endet statt mit seiner Antwort mit `policy_blocked`
  (`personal_connector`, auch im Hinweis des Gesprächs: `system.stop_detail`). Die
  Marke beginnt also mit dem ersten persönlichen Inhalt im Kontext und endet, wenn
  keiner mehr darin ist. Jedes Ereignis eines markierten Laufs zeigt die Laufansicht
  nur ihr; alle anderen sehen es geschwärzt, den ganzen Lauf (Review M8 3, Befund H1). Sie folgt dem Inhalt: Jede Nachricht eines markierten Laufs ist selbst markiert
  (`personal`), und ein späterer Lauf ist markiert, sobald eine markierte Nachricht in
  sein Verlaufsfenster, ein Treffer eines markierten Laufs aus `search_past_runs` oder
  eine markierte Nachricht aus `read_conversation` in seinen Kontext kommt; das steht
  sofort in seinem Journal. Ohne markierten Inhalt im Kontext beginnt ein Lauf ohne
  Marke (siehe [`AGENTEN.md`](AGENTEN.md)). Von selbst nimmt nichts die Marke ab; mit
  „Neu beginnen“ in ihrer Direktnachricht allein mit dem Agenten setzt die Person einen
  Schnitt, nach dem Läufe dort nichts von davor bekommen: keinen Verlauf, nichts über
  `read_conversation` und keinen Treffer von `search_past_runs` aus früheren Läufen;
  was sie zum Merken freigegeben hat, bleibt (`POST /api/conversations/{id}/fresh-start`;
  Review M8 3, Befund H2; Review M8 4, Befund K3). Ergebnisse über einen geteilten
  Konnektor, Fehler und `external_outcome_unknown` markieren nicht. Trägt der Lauf die Marke, wartet jeder
  Aufruf eines externen Servers, den er nicht mit dem eigenen Konnektor der fragenden
  Person nutzt (geteilter Konnektor oder keiner), auch eines **lesenden** Werkzeugs, auf
  die Freigabe dieser Person über genau diese Argumente (in Läufen von Automationen und
  Ereignisregeln: der Eigentümerin); denn was er sendet, kann tragen, was nur sie lesen
  darf (Review M8 1, Befund 3). Über ihren eigenen Konnektor geht es ohne Freigabe
  weiter; schreibende externe Werkzeuge warten ohnehin immer. Ein Lauf sendet
  höchstens `HERD_MCP_MAX_CALLS_PER_RUN` Aufrufe (Standard 20); der nächste wird nicht
  gesendet (`external_tool_limit`), was zurückgehalten wurde, zählt nicht. Das Ergebnis
  geht gerahmt als `<untrusted source="mcp" server=… tool=…>` und auf 8.000 Zeichen
  gekürzt an das Modell (im Journal vollständig) und gibt nie ein Recht, eine Stufe
  oder eine Freigabe. Es trägt keinen Bereich: Außer der fragenden Person sieht es in
  der Laufansicht niemand. Fehler sind Ergebnisse mit festen Wörtern
  (`external_tool_unavailable`, `external_tool_not_connected`,
  `external_tool_credential_unavailable`, `external_tool_failed: … (<Zustand>)`,
  `external_tool_error` für einen Fehler, den das Werkzeug selbst meldet); der Lauf
  geht weiter. Vor dem Senden steht im Journal `external_outcome_unknown`; geht der
  Worker verloren, wird der Aufruf nicht wiederholt, und das Modell erfährt, dass der
  Ausgang unbekannt ist. Aufrufe werden nicht auditiert; das Journal (`run_event`)
  hält sie mit Argumenten und Ergebnis, nie mit dem Zugang.
- **Was nie ins Log oder Audit geht**: Argumente, Ergebnisse, Beschreibungen,
  Zugänge, Fehlertexte des Servers. Logzeilen `mcp.list_tools` und `mcp.tool_call`
  nennen nur IDs, Zustand, Dauer und Größe; die eigenen Logzeilen des MCP-SDK sind
  abgeschaltet (sie können Antworten zitieren). Audit: `mcp_server.created`,
  `.updated` (Feldnamen), `.deleted`, `.refreshed` (Zustand und Zahlen),
  `mcp_tool.approved`, `.blocked`, `.classified`.
- **Zustände** eines Aufrufs oder Einlesens: `ok`, `blocked` (SSRF-Sperre), `timeout`,
  `unreachable`, `unauthorized`, `forbidden`, `not_found`, `rate_limited`,
  `redirect`, `server_error`, `too_large`, `protocol_error`, `secret_unavailable` (das
  Geheimnis des Konnektors lässt sich nicht auflösen; es wurde nichts gesendet).
- **Selbst betriebene Server im eigenen Netz** (etwa ein GitLab im Firmennetz):
  `HERD_MCP_ALLOWED_HOSTS` nennt die privaten Ziele, kommagetrennt, als exakte
  Hostnamen (ohne Platzhalter und Port; Groß-/Kleinschreibung und ein Punkt am Ende
  zählen nicht) oder als private Netze in CIDR-Form (eine einzelne Adresse zählt als
  ein Host; Netze nur innerhalb von `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`,
  `100.64.0.0/10`, `127.0.0.0/8`, `fc00::/7`, `::1`). Leer (Standard) gilt das oben
  Gesagte: nur öffentliche Adressen. Die Einstellung gibt es nur in der Umgebung, nie
  über die API; ein ungültiger Eintrag verhindert den Start. Ein gelisteter Name darf
  auf private Adressen auflösen; jede Antwort wird trotzdem bei jedem
  Verbindungsaufbau geprüft, Link-Local- und Metadaten-Adressen bleiben immer gesperrt
  (ein gelisteter Name, der plötzlich auf `169.254.169.254` zeigt, wird abgewiesen). Ein
  nicht gelisteter Name, der auf eine private Adresse auflöst, bleibt gesperrt. Ein
  gelistetes Netz erlaubt jede Adresse darin, gleich über welchen Namen (jeder Name,
  der dorthin auflöst, darf gewählt werden; mit https und Zertifikatsprüfung bleibt es
  dann bei einem TLS-Handshake mit einem internen Port); deshalb ist ein exakter
  Hostname die engere Wahl. Es bleibt bei https. Ein gelisteter Host wird direkt
  gewählt, nicht über `HERD_AI_EGRESS_PROXY` (der Proxy ist für draußen gedacht). Das
  entscheidet jede Anfrage nach ihrem eigenen Host, auch beim Erkennen eines
  Autorisierungsservers: ein gelisteter interner Server mit einem öffentlichen
  Autorisierungsserver wird direkt gefragt, der Autorisierungsserver über den Proxy; mit
  `networkPolicy.enabled` im Chart muss `networkPolicy.aiEgress` den Weg zu ihm
  zusätzlich öffnen. Gelesen wird die Einstellung von der API (Werkzeuglisten, Test)
  und vom Worker (Aufrufe in Läufen); Compose `HERD_MCP_ALLOWED_HOSTS`, Chart
  `mcp.allowedHosts` (Liste).
- **Kein Trace-Kontext nach draußen**: das SDK legt den laufenden Trace-Kontext
  (`traceparent`, `tracestate`) in `_meta` jeder Anfrage; der Client nimmt ihn vor dem
  Senden heraus, keine Trace-ID der App erreicht einen externen Server.
- **Tests** laufen gegen einen echten MCP-Server aus dem SDK
  (`backend/tests/support/mcp_stub.py`, https für `mcp.test` auf 127.0.0.1, skriptbar:
  Werkzeugliste, Ergebnisse, Verzögerung, Umleitung, Fehlerstatus, verlangter Kopf),
  nie gegen das Netz. Das SDK (`mcp`) wird nur unter `backend/app/mcp/` importiert
  (`tests/test_mcp_imports.py`).

## Katalog

Der Katalog hält Vorlagen für bekannte MCP-Server (Plan M8, Entscheidung 10). Aus
einer Vorlage legt die Verwaltung einen Server samt dem an, was er braucht; sie trägt
nur den Zugang und seinen Geltungsbereich ein. Freigegeben wird trotzdem jedes
Werkzeug einzeln: Eine Vorlage schlägt nur vor.

### Mitgeliefert: GitHub und GitLab

| Vorlage | Adresse | Anmeldung | geprüft am 2026-11-15 |
|---|---|---|---|
| `github` | `https://api.githubcopilot.com/mcp/` | OAuth (eigene GitHub-App oder OAuth-App; `https://github.com/login/oauth/authorize`, `…/access_token`, Scopes `repo read:org`, PKCE S256) oder persönliches Zugriffstoken als Bearer | Adresse, Anmeldearten, Endpunkte, PKCE aus der Dokumentation von GitHub; der Server war vom Bauort aus nicht erreichbar |
| `gitlab` | `{base_url}/api/v4/mcp`, `base_url` Standard `https://gitlab.com` | OAuth (`{base_url}/oauth/authorize`, `/token`, `/revoke`, Scope `mcp`, PKCE) oder fein granulares persönliches Zugriffstoken als Bearer | Adresse, Scope, Endpunkte, PKCE und Widerruf live an gitlab.com (401 mit `resource_metadata`, RFC 9728/8414) und aus der Dokumentation |

- **GitHub** bietet keine dynamische Client-Registrierung: Für OAuth legt die
  Organisation eine eigene GitHub-App (empfohlen: Token laufen ab und werden erneuert)
  oder OAuth-App an, Callback-URL die der OAuth-App hier
  (`<HERD_PUBLIC_URL>/api/ai/oauth/<id>/callback`, auf ihrer Karte). GitHub
  hat keinen Widerrufs-Endpunkt nach RFC 7009; Zugänge widerruft man bei GitHub in den
  Einstellungen des Kontos. GitHub Enterprise Server hat keinen entfernten MCP-Server.
  Nicht geprüft werden konnte, ob GitHubs Autorisierungsserver den Parameter
  `resource` (RFC 8707, von MCP-Clients verlangt) annimmt oder übergeht, und welche
  Scopes eine OAuth-App mindestens braucht.
- **GitLab** (GitLab.com, Self-Managed, Dedicated; allgemein verfügbar seit 19.5): Für
  OAuth eine Anwendung mit Scope `mcp` anlegen, „Confidential“ abwählen (dann ohne
  Client-Geheimnis, nur PKCE). Klassische, Projekt- und Gruppen-Token lehnt der Server
  ab (403). Für eine eigene Instanz wird beim Anlegen `base_url` angegeben (etwa
  `https://gitlab.example.com`, auch mit Pfad); liegt sie im Firmennetz, muss der
  Betrieb den Host in `HERD_MCP_ALLOWED_HOSTS` freigeben. Nicht geprüft: in welcher
  Kopfzeile der Server ein persönliches Zugriffstoken erwartet (angeboten wird
  Bearer) und ob eine Instanz unter einem Pfad dieselben Pfade darunter bedient.
- Die vorgeschlagenen Einstufungen stammen aus den Werkzeuglisten der Dokumentation
  (Namen und Beschreibungen), nicht aus den Annotationen der Server; der Vorschlag
  `write` gilt für alles, was schreibt, zusammenführt, startet oder Sitzungen anlegt.
  Die Kommentare oben in den Dateien nennen die Quellen und das Ungeprüfte.

### Anlegen aus einer Vorlage

`ai.manage`, ohne das Recht 404 `ai.not_found`:

- `GET /api/ai/mcp-catalog` (seitenweise nach ID) und `GET /api/ai/mcp-catalog/{id}`:
  die Vorlagen, wie sie geladen sind (Name, Beschreibung und Hinweise auf Deutsch und
  Englisch, Adresse bzw. Adressmuster, `base_url` mit Standard, `data_location`,
  erlaubte `connector_scopes`, Anmeldearten mit OAuth-Endpunkten und Scopes, die
  vorgeschlagene Einstufung je Werkzeug, Dokumentation). Eine Vorlage enthält nie eine
  Client-ID oder ein Geheimnis. Unbekannt: 404 `mcp_catalog.not_found`.
- `GET /api/ai/mcp-catalog/problems` (seitenweise): Dateien, die nicht geladen wurden,
  mit Quelle (`shipped`/`operator`), Dateiname und Grund.
- `POST /api/ai/mcp-catalog/{id}/install` (201) mit `connector_scope` und, außer bei
  `none`, `auth_kind`; optional `name` (Standard: Name der Vorlage), `base_url` (nur
  bei Vorlagen mit Adressmuster), `data_location`, `enabled`:
  - `none`: nur der Server.
  - `shared` mit `bearer`/`header`: dazu ein geteilter Konnektor mit `secret`
    (`{"value": …}` verschlüsselt oder `{"env": "HERD_AI_…"}`).
  - `shared` mit `oauth`: dazu ein OAuth-Client aus den Endpunkten der Vorlage mit
    `client_id` (und `client_secret`, wenn vertraulich; `resource` ist die Adresse des
    Servers) und ein geteilter OAuth-Konnektor, der danach verbunden wird
    (`POST /api/ai/connectors/{id}/authorize`).
  - `personal` mit `oauth`: dazu der OAuth-Client, mit dem jede Person ihren eigenen
    Konnektor verbindet (`oauth_client_id` am Server); mit `bearer`/`header` legt jede
    Person ihren Konnektor selbst an.

  Die Antwort nennt den Server (mit `catalog_id` und dem Ergebnis des Einlesens der
  Werkzeuge, `refresh`), `oauth_client_id` und `connector_id`. Alles geschieht in einer
  Transaktion über dieselben Services wie von Hand, mit denselben Regeln und demselben
  Audit (`oauth_client.created`, `connector.created`, `mcp_server.created` mit
  `catalog_id`); scheitert ein Schritt (Name vergeben: 409 `…name_taken`), bleibt
  nichts zurück. Fehler: 422 `mcp_catalog.install_invalid` mit `details.field`
  (`connector_scope` oder `auth_kind`, die die Vorlage nicht anbietet; `base_url` bei
  einer Vorlage ohne Muster), 422 `mcp_catalog.base_url_not_allowed` mit
  `details.reason` (Adresse, die die Ausgangsregeln nicht erlauben, etwa `http` oder
  eine nicht freigegebene private Adresse).
- **Vorschläge**: Liest ein Refresh bei einem Server aus dem Katalog ein Werkzeug zum
  ersten Mal, wird es `write` vorgeschlagen, wenn die Vorlage das sagt, auch wenn der
  Server es als nur lesend kennzeichnet, und `read` nur, wenn beide es sagen. Ein
  Vorschlag `read` für ein nicht so gekennzeichnetes Werkzeug ändert nichts; `read` setzt nur die Verwaltung, mit
  `confirm_loosen`. `GET …/mcp-servers/{id}/tools` nennt je Werkzeug
  `suggested_classification` (oder `null`). Alle Werkzeuge kommen als `pending`.

### Eigene Vorlagen

Eine Vorlage ist eine YAML-Datei (`*.yaml`, `*.yml`, höchstens 256 KiB, UTF-8).
Mitgelieferte liegen unter `backend/app/mcp/catalog/` (eine neue Datei dort braucht
keine Codeänderung); eigene der Installation in `HERD_MCP_CATALOG_DIR` (Compose: das
Verzeichnis im Container, schreibgeschützt eingebunden; Chart:
`mcp.catalogConfigMap`, eine vorhandene ConfigMap, deren Schlüssel die Dateien sind,
eingebunden unter `/etc/herd/mcp-catalog`). Gelesen wird nur von der API; eine neue
oder geänderte Datei gilt ohne Neustart (geprüft an Dateiliste, Größe und
Änderungszeit).

```yaml
id: tracker                  # a-z, 0-9, „-“, bis 40 Zeichen, eindeutig
name: Tracker
description: {de: "Unser Tracker.", en: "Our tracker."}
url: "{base_url}/mcp"        # https; nur {base_url} wird eingesetzt
base_url:                    # nur mit Muster
  default: https://tracker.example.com
  note: {de: "…", en: "…"}
data_location: external      # local | eu | external
connector_scopes: [personal, shared]   # none | personal | shared
auth:
  - kind: oauth              # oauth | bearer | header
    oauth:
      authorization_endpoint: "{base_url}/oauth/authorize"
      token_endpoint: "{base_url}/oauth/token"
      revocation_endpoint: "{base_url}/oauth/revoke"   # optional
      scopes: "mcp"
      resource: true         # Adresse des Servers als RFC-8707-resource senden
      token_auth: client_secret_post   # oder client_secret_basic
    note: {de: "…", en: "…"}
  - kind: header
    header_name: X-Api-Key
tools:                       # Vorschläge, höchstens 500
  search: read
  create_ticket: write
docs: ["https://tracker.example.com/docs/mcp"]
```

- Beim Laden wird jede Datei geprüft (unbekannte Felder, fehlende Pflichtfelder,
  Adressen ohne https, mit Zugangsdaten, Query oder Fragment, andere Platzhalter als
  `{base_url}`, Anmeldeart ohne passenden Geltungsbereich). Eine fehlerhafte Datei
  wird übersprungen, nie ein Startfehler: Sie steht unter
  `GET /api/ai/mcp-catalog/problems` und im Log (`mcp.catalog_problem` mit Quelle,
  Dateiname und Ort und Art des Fehlers, nie dem Inhalt). Eine eigene Vorlage kann
  keine mitgelieferte ersetzen (dieselbe ID: übersprungen, „id … already taken“).
  Versteckte Dateien und andere Endungen werden nicht gelesen, höchstens 100 Dateien
  je Verzeichnis. Die Zahl der übersprungenen Dateien zeigt die Metrik
  `herd_mcp_catalog_problems` (Alarm `HerdMcpCatalogProblems`).
- Im Chart: die Dateien als ConfigMap anlegen und nennen, etwa
  `kubectl create configmap herd-catalog --from-file=tracker.yaml` und
  `--set mcp.catalogConfigMap=herd-catalog`. Eine geänderte ConfigMap kommt mit der
  Verzögerung des Kubelets in den Pods an (ohne Einstellung bis gut eine Minute) und gilt dann
  ohne Neustart.
- Vorab prüfen: `cd backend && uv run python -m scripts.check_mcp_catalog <verzeichnis>`
  nennt jede Vorlage und jedes Problem und endet mit 1, wenn eines da ist. Die CI
  prüft so die mitgelieferten Vorlagen.
- Die Adressen prüfen die Ausgangsregeln erst beim Anlegen (Server und OAuth-Client wie
  von Hand); eine Vorlage für ein internes Ziel braucht dessen Host in
  `HERD_MCP_ALLOWED_HOSTS`.

## Betrieb

### Reverse-Proxy und Ingress

`/mcp` gehört wie `/api` zur API (öffentlicher Port 8080) und braucht keinen eigenen
Dienst, Prozess oder Speicher: Jeder API-Knoten beantwortet jede Anfrage, nichts bleibt
im Prozess (keine Sitzungen, keine Streams). Für den Weg dorthin gilt:

- **Pfad:** `/mcp` unverändert an die API. Das Ingress des Charts leitet mit dem
  Standardpfad `/` (`Prefix`) alles an die API, auch `/mcp`; wer in `ingress.hosts`
  nur einzelne Pfade nennt, nimmt `/mcp` (`Exact` oder `Prefix`) dazu. Hinter einem
  eigenen Proxy dasselbe wie für `/api`.
- **Köpfe:** `Authorization` unverändert durchreichen; keinen `Origin`-Kopf hinzufügen
  (eine Anfrage mit `Origin` lehnt `/mcp` ab, 403 `mcp.origin_refused`). Der Proxy
  darf `Authorization` nicht protokollieren.
- **Pufferung und Zeitlimits:** Jede Anfrage ist ein `POST` mit genau einer
  JSON-Antwort (höchstens 1 MiB), kein Upgrade, kein Server-Stream (`GET` antwortet
  405). Pufferung muss also nicht abgeschaltet werden und schadet nicht; die üblichen
  Zeitlimits der Controller (ingress-nginx: 60 s) reichen weit (gemessen: unter 1 s
  auch unter Last, siehe [Steckbrief](STECKBRIEF.md#mcp-m8)). Ein Größenlimit des
  Proxys für Anfragen muss mindestens `HERD_MAX_BODY_BYTES` (1 MiB) erlauben.
- **TLS:** Clients verbinden sich über https; das Token ist ein Bearer-Token und darf
  nicht über unverschlüsseltes HTTP gehen.
- **Ausgehend** (die eigenen Agenten als Client): API-Pods lesen Werkzeuglisten und
  erneuern OAuth-Token, Worker rufen Werkzeuge in Läufen auf, beide über die
  SSRF-Sperre bzw. `HERD_AI_EGRESS_PROXY`. Mit `networkPolicy.enabled` im Chart muss
  `networkPolicy.aiEgress` die MCP-Server und Autorisierungsserver erlauben (oder den
  Proxy); private Hosts zusätzlich in `HERD_MCP_ALLOWED_HOSTS`.
- **OAuth:** `HERD_PUBLIC_URL` (Chart `publicUrl`, sonst aus dem ersten Ingress-Host)
  muss die Adresse sein, unter der Browser die App öffnen; die Rückleitungsadresse
  jeder OAuth-App, `<HERD_PUBLIC_URL>/api/ai/oauth/<id>/callback`, muss beim Anbieter
  genau so eingetragen sein (nach dem Update auf M9b neu eintragen). Ihr Query enthält den Code: Er steht im Zugriffsprotokoll des Proxys, ist aber
  nur einmal und nur mit Prüfwert einlösbar.

### Einstellungen

| Variable | Standard | wer liest sie | Bedeutung |
|---|---|---|---|
| `HERD_MCP_RATE_PER_MINUTE` | `120` | API | Aufrufe je Zugangstoken und Minute an `/mcp`, 1 bis 10.000, über alle API-Knoten in PostgreSQL gezählt; darüber 429 (Chart `mcp.ratePerMinute`) |
| `HERD_MCP_ALLOWED_HOSTS` | leer | API, Worker | private Hosts externer MCP-Server und Autorisierungsserver: Hostnamen oder private Netze (CIDR), kommagetrennt; nur in der Umgebung, ein ungültiger Eintrag verhindert den Start (Chart `mcp.allowedHosts`; siehe [Externe MCP-Server](#externe-mcp-server)) |
| `HERD_MCP_CATALOG_DIR` | leer | API | Verzeichnis mit eigenen Katalog-Vorlagen (Chart `mcp.catalogConfigMap`, eingebunden unter `/etc/herd/mcp-catalog`; siehe [Katalog](#eigene-vorlagen)) |
| `HERD_MCP_MAX_CALLS_PER_RUN` | `20` | Worker | gesendete Aufrufe externer Werkzeuge je Lauf eines Agenten, 1 bis 500 (Chart `mcp.maxCallsPerRun`) |
| `HERD_PUBLIC_URL` | leer | API | Adresse der App für die OAuth-Rückleitung; ohne sie kein OAuth (422 `connector.oauth_unconfigured`) |
| `HERD_SECRET_KEY` (`_PREVIOUS`) | – | API, Worker | Schlüssel für Konnektor-Geheimnisse, OAuth-Token und Client-Geheimnisse (`enc:`; [`KI.md`](KI.md#schlüssel)) |
| `HERD_AI_EGRESS_PROXY` | – | API, Worker | Proxy für ausgehende Aufrufe nach draußen; gelistete private Hosts gehen direkt |
| `HERD_MAX_BODY_BYTES` | 1 MiB | API | größte Anfrage, auch an `/mcp` (413) |

Ob Personen überhaupt Token haben dürfen und welcher Datenort für `/mcp` gilt, ist
keine Variable, sondern die Einstellung der Organisation in der KI-Verwaltung
(`PUT /api/ai/mcp`, Standard aus). Compose: alle Variablen in beiden Compose-Dateien
(`deploy/compose/README.md`); Chart: Werte unter `mcp.*` mit Schema und Prüfregeln
(`deploy/helm/scripts/check-chart-rules.sh`).

### Grenzen

| Grenze | Wert |
|---|---|
| Aufrufe je Token | `HERD_MCP_RATE_PER_MINUTE` je Minute (Standard 120), jede HTTP-Anfrage zählt |
| Anfrage an `/mcp` | `HERD_MAX_BODY_BYTES` (1 MiB) |
| Antwort von `/mcp` | 1 MiB (500 `mcp.response_too_large`); Text eines Werkzeugergebnisses 100.000 Zeichen |
| Laufzeit eines Tokens | 1 bis 365 Tage, Pflicht |
| Bereiche eines Tokens | 1 bis 50 oder „alle meine“ |
| `list_my_tickets` | 50 Tickets |
| freigegebene externe Werkzeuge | 200 je Organisation (`MAX_APPROVED_TOOLS`) |
| externer Server: Werkzeugliste | 20 s, 2 MiB, 500 Werkzeuge, Beschreibung gespeichert bis 10.000 Zeichen, Eingabeschema bis 64 KiB (dem Modell: Struktur bis 8.000 Zeichen, Worte des Servers gerahmt bis 2.000) |
| externer Server: Aufruf | 60 s (und die Laufzeit des Laufs), Antwort 512 KiB, Ergebnis im Prompt 8.000 Zeichen, Beschreibung im Prompt 1.000 Zeichen |
| externe Werkzeuge je Modellaufruf | Name, Beschreibung und Argumentschema aller externen Werkzeuge eines Agenten zusammen 100.000 Zeichen (`MAX_DEFINITION_CHARS`); was nicht passt, bleibt weg (`left_out`) |
| externe Aufrufe je Lauf | `HERD_MCP_MAX_CALLS_PER_RUN` (Standard 20); externe Aufrufe kosten keine Modell-Tokens und zählen zu keinem Tagesbudget |
| OAuth | Ablauf (`state`) 10 Minuten; Erneuerung 60 s vor Ablauf oder nach einem 401, Sperre der Zeile höchstens 30 s; Antworten des Anbieters 64 KiB |
| Katalog | 100 Dateien je Verzeichnis, 256 KiB je Datei |

### Metriken und Alarme

Auf dem internen Port (`/metrics`, 9090). Labels sind nur Aufzählungswerte und Namen
eingebauter Werkzeuge: nie Token, Token-Namen, Personen, Server-Adressen,
Werkzeugnamen externer Server, Argumente oder Inhalte.

| Metrik | Art | wer | Bedeutung |
|---|---|---|---|
| `herd_mcp_calls_total{tool,outcome}` | Zähler | API | Werkzeugaufrufe über `/mcp` je eingebautem Werkzeug und Ergebnis (`ok`, `refused`, `invalid`, `failed`); dieselben Aufrufe je Token in `mcp_call` |
| `herd_http_requests_total{route="/mcp",status}` | Zähler | API | alle Anfragen an `/mcp`: 200, 401 (Token ungültig), 403 (`Origin`), 405, 413, 429 (Ratenbegrenzung) |
| `herd_external_tool_calls_total{outcome,effect}` | Zähler | Worker | Aufrufe externer Werkzeuge in Läufen, nach dem Commit ihres Schritts: `ok`, `error` (das Werkzeug meldet einen Fehler), `refused` (nicht gesendet: Richtlinie, Freigabe abgelehnt oder veraltet, Werkzeug nicht brauchbar, Person nicht verbunden), `limited` (Grenze des Laufs), `failed` (gesendet und gescheitert, oder Zugang nicht nutzbar), `timeout`, `unknown` (gesendet, Ergebnis nicht festgehalten, auch wenn die Laufzeit des Laufs den Aufruf abschnitt); `effect` `read` oder `write` |
| `herd_external_tool_definitions_left_out_total` | Zähler | Worker | Externe Werkzeuge, die die Grenze aller Werkzeugbeschreibungen eines Modellaufrufs (100.000 Zeichen) aus einem Lauf weglässt, bei jedem Start und jeder Fortsetzung; ohne Namen |
| `herd_oauth_refreshes_total{status}` | Zähler | API, Worker | Erneuerungen von OAuth-Token je Antwort des Anbieters: `ok`, `invalid_grant` (Konnektor getrennt), `rejected`, `blocked`, `timeout`, `unreachable`, `redirect`, `server_error`, `invalid_response` |
| `herd_mcp_catalog_problems` | Gauge | API | übersprungene Katalog-Dateien beim letzten Lesen (bei jedem Scrape neu geprüft) |

Alarme in der PrometheusRule des Charts (`metrics.prometheusRule.enabled`), je als
Warnung, mit promtool-Tests (`deploy/helm/to-herd-cats-ai/tests/rules-test.yaml`):

- `HerdExternalToolsFailing`: mehr als die Hälfte der gesendeten externen Aufrufe der
  letzten 15 Minuten (mindestens 3) scheiterte oder lief in das Zeitlimit, 5 Minuten
  lang. Abhilfe: Server in der KI-Verwaltung testen (Zustand `unreachable`,
  `unauthorized`, `forbidden`, `server_error`, `timeout`, `blocked`), Logzeilen
  `mcp.tool_call` des Workers, Netzfreigabe und `HERD_MCP_ALLOWED_HOSTS`;
  `HerdOAuthRefreshFailing` mitlesen.
- `HerdOAuthRefreshFailing`: mindestens 3 Erneuerungen in 30 Minuten scheiterten aus
  einem anderen Grund als `invalid_grant`, 5 Minuten lang. Der Anbieter ist nicht
  erreichbar oder lehnt den Client ab; Logzeilen `oauth.token_request` (Grant
  `refresh_token`, Zustand). Die Token bleiben und werden wieder versucht.
  `invalid_grant` allein alarmiert nicht: Dann ist ein einzelner Konnektor getrennt
  (meist hat die Person den Zugang beim Anbieter widerrufen) und wird neu verbunden.
- `HerdMcpAuthFailures`: mehr als 50 Antworten 401 an `/mcp` in 5 Minuten, 10 Minuten
  lang. Jemand probiert Token, oder ein Client ruft mit einem widerrufenen oder
  abgelaufenen Token immer wieder an. Das Zugriffsprotokoll des Proxys nennt die
  Clients (die App protokolliert `http.request` mit Pfad und Status, nie das Token);
  Token in der KI-Verwaltung widerrufen oder den Client am Proxy sperren.
- `HerdMcpCatalogProblems`: Katalog-Dateien werden seit 15 Minuten übersprungen
  (`GET /api/ai/mcp-catalog/problems`, Logzeilen `mcp.catalog_problem`); die Dateien
  mit `uv run python -m scripts.check_mcp_catalog <dir>` prüfen und die ConfigMap
  berichtigen.

Ein eigener Alarm für die Ratenbegrenzung (429) fehlt bewusst: Sie schützt die
Installation und trifft nur das Token, das zu oft fragt; wer sie beobachten will, liest
`herd_http_requests_total{route="/mcp",status="429"}`.

Logzeilen (nur IDs, Codes, Dauer und Größe): `mcp.tool_call` (API: Werkzeug über
`/mcp`; Worker: externer Aufruf mit Zustand), `mcp.list_tools`, `oauth.token_request`,
`mcp.catalog_problem`, `http.request`.

### Rolling Update

`/mcp` hält keine Verbindungen offen; ein Pod, der beendet wird, beantwortet laufende
Anfragen und nimmt keine neuen an (wie `/api`). Ein Client, dessen Anfrage dabei
abbricht, wiederholt sie; lesende Werkzeuge sind gefahrlos, ein schreibendes Werkzeug
kann dann zweimal wirken (wie jeder abgebrochene `POST`). Die Migrationen von M8
erweitern nur; ein Pod des vorigen Releases bedient `/mcp` nicht, bis er ersetzt ist.

## Sicherheit: was ein externer Client sieht

Ein externer Client (Claude Code, Codex, ein Skript mit Token) **sieht**:

- über ein persönliches Token: was seine Person jetzt lesen darf, geschnitten mit dem
  Umfang des Tokens und dem, was die KI-Richtlinie für den Datenort von `/mcp` erlaubt
  (Standard `external`); über ein Agenten-Token zusätzlich nur die Bereiche des Agenten.
  Bei jedem Aufruf neu geprüft: ein entzogener Bereich, ein widerrufenes Token, eine
  inaktive Person, „keine KI“ oder der Schalter aus wirken sofort;
- nur veröffentlichte Seiten, Tickets, Bereiche und den Seitenbaum, die Versionsliste
  (ohne Inhalt) nur mit `write`-Token;
- die eingebauten Werkzeuge seines Modus mit ihren Beschreibungen.

Er **sieht nicht**:

- **Entwürfe**, auch nicht die eigenen; Seiten und Bereiche mit KI-Sperre (`no_ai`);
  Bereiche, deren Richtlinie den Datenort ausschließt. Alles davon antwortet wie eine
  unbekannte ID („Nothing found (or not readable).“), auch in Suche und Listen;
- Nachrichten, Kanäle, Direktnachrichten und Threads (es gibt kein lesendes Werkzeug
  dafür), Läufe der Agenten, ihr Journal, Gedächtnis und Skills, Freigaben,
  Rückfragen, Audit, Personen- und Gruppenverwaltung, Konnektoren, Geheimnisse und
  externe MCP-Server: `/mcp` bietet nur die Werkzeuge oben;
- Werkzeuge, die im System eine Freigabe verlangen, und `assign_ticket`;
- interne Einzelheiten: Fehler kommen als feste Codes und Wörter, nie mit Stack,
  SQL oder den Werten ungültiger Argumente.

Was er **schreibt** (nur mit `write`-Token), trägt das KI-Kennzeichen mit dem Namen des
Tokens (`via_token`), geht durch dieselben Dienste und Rechte wie bei der Person, schreibt
Seiten direkt nur in Bereichen mit `agent_write_policy = direct` und setzt Tickets nie
auf „erledigt“. Jeder Aufruf eines schreibenden Werkzeugs steht im Audit.

Für die **eigenen Agenten als Client** gilt umgekehrt: Was ein externer Server liefert
(Ergebnisse, Beschreibungen), ist nicht vertrauenswürdig, wird gerahmt
(`<untrusted …>`) und gekürzt, gibt nie ein Recht, eine Stufe oder eine Freigabe; ein
geändertes Werkzeug (anderer Fingerabdruck) ist gesperrt, bis die Verwaltung es neu
freigibt; der Katalog schlägt nur vor und gibt nie frei; schreibende externe Werkzeuge
laufen nur mit der Freigabe der fragenden Person für genau diese Argumente; was über
den persönlichen Zugang einer Person gelesen wurde, schreibt der Lauf nirgends hin, wo
andere es lesen könnten. Zugänge stehen nie im Prompt, in Argumenten, im Journal, im
Log oder im Audit.
