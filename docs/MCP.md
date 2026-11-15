# MCP: das System als MCP-Server und als MCP-Client

Dieses Dokument wächst mit M8. Bisher beschrieben: **Zugangstoken und das Recht
`mcp.use`** (Plan M8, Task 1), **Konnektoren** (Task 5) und **externe MCP-Server**
mit Werkzeugfreigabe (Task 6). Der Endpunkt `/mcp` selbst, externe Agenten, externe
Werkzeuge im Lauf und der Katalog folgen.

## Zugangstoken

Externe KI-Clients (Claude Code, Codex) melden sich am Endpunkt `/mcp` mit einem
**persönlichen Zugangstoken** an. Ein Token handelt als seine Person, nie mit mehr
Rechten als sie, und nur in seinem Umfang.

### Wer Token haben darf: `mcp.use`

- Das Recht `mcp.use` wird nie an der Person gespeichert. Es gilt für **jede aktive
  Person außer Gästen**, solange der **MCP-Schalter der Organisation** an ist
  (Standard: aus).
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

### Rechte eines Tokens

Bei **jedem Aufruf** wird das Token neu aufgelöst, nichts wird zwischengespeichert:

- Lesbar ist die Schnittmenge aus den **Rechten der Person** (wie sie jetzt sind:
  Rolle, Gruppen, Mitgliedschaften), dem **Umfang des Tokens** und dem, was die
  **KI-Richtlinie** für den Datenort des Endpunkts erlaubt. Wird der Person ein
  Bereich entzogen, ist er für das Token sofort weg.
- Ein `read`-Token schreibt nirgends. Ein `write`-Token schreibt höchstens in den
  Bereichen seines Umfangs und nur, was die Person dort selbst darf (welche
  Werkzeuge es dafür gibt, beschreibt Task 3).
- Ist die Person nicht mehr aktiv, wird sie Gast oder ist der Schalter aus,
  antwortet das Token 401.

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

### Einstellungen

| Variable | Standard | Bedeutung |
|---|---|---|
| `HERD_MCP_RATE_PER_MINUTE` | `120` | Aufrufe je Token und Minute (API; Chart `mcp.ratePerMinute`) |
| `HERD_MCP_ALLOWED_HOSTS` | leer | private Hosts externer MCP-Server: Hostnamen oder private Netze (CIDR), kommagetrennt (API und Worker; Chart `mcp.allowedHosts`; siehe „Externe MCP-Server“) |

### Für die folgenden Tasks

`backend/app/modules/tokens/resolve.py` stellt die Abhängigkeit `TokenActorDep` bereit
(Akteur der Person mit Umfang, Modus, Token-Name und Datenort);
`backend/app/modules/tokens/reach.py` sagt in SQL, was ein solcher Akteur lesen darf
(`readable_space_ids`, `readable_spaces`, `readable_page_ids`).

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
  sichtbares ASCII ohne Leerzeichen (wie bei KI-Schlüsseln, `core/secrets.py`). OAuth
  folgt mit Task 8.
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
  Server mit `connected`. Wird der Server gelöscht, gehen die daran gebundenen
  persönlichen Konnektoren mit.
- **In Gebrauch**: Ein geteilter Konnektor, den ein Server nennt, wird nicht gelöscht
  (409 `connector.in_use`).

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
  (`local`/`eu`/`external`, wie bei einer Verbindung; die KI-Richtlinie nutzt es mit
  Task 7), `connector_scope` (`none`, `shared` mit `connector_id` eines geteilten
  Konnektors, `personal`: der Zugang der Person, in deren Auftrag aufgerufen wird),
  `enabled`, `version` (409 `mcp_server.version_conflict`).
- **Werkzeugliste**: wird beim Anlegen und mit `POST …/{id}/refresh` eingelesen, ohne
  offene Transaktion, mit Zeitlimit (20 s) und Größenlimit (2 MiB); höchstens 500
  Werkzeuge, Namen nur aus `A-Z a-z 0-9 _ - .` (1–128 Zeichen), Beschreibungen
  gespeichert bis 10.000 Zeichen. Das Ergebnis ist ein Zustand mit Zahlen
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
  wieder `approved`). Werkzeuge, die der Server nicht mehr nennt, sind `missing` und
  nicht freizugeben (409 `mcp_tool.missing`). Eine neue Adresse des Servers zieht alle
  Freigaben zurück.
- **Einstufung** `read`/`write`: Vorschlag `read` nur, wenn der Server das Werkzeug als
  nur lesend kennzeichnet (`readOnlyHint`), sonst `write`. Ein nicht so gekennzeichnetes
  Werkzeug auf `read` zu setzen, verlangt `confirm_loosen: true` (422
  `mcp_tool.loosen_unconfirmed`); das Audit vermerkt `loosened`.
- **Aufruf** (für Läufe, Task 7: `ToolCaller.call_tool` in
  `backend/app/modules/mcp_servers/calls.py`): nur ein freigegebenes, noch gelistetes
  Werkzeug mit dem freigegebenen Fingerabdruck eines eingeschalteten Servers. Im selben
  Gespräch mit dem Server wird zuerst die Werkzeugliste gelesen; nennt der Server das
  Werkzeug anders als freigegeben, unterbleibt der Aufruf, das Werkzeug wird `changed`
  (bzw. `missing`). Der Zugang wird serverseitig eingesetzt; fehlt bei `personal` der
  Konnektor der Person, ist das ein Fehler `mcp_tool.not_connected`. Zeitlimit 60 s,
  Antworten höchstens 512 KiB (`too_large`). Das Ergebnis ist nicht vertrauenswürdig
  und wird vom Aufrufer gerahmt.
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
  gelistetes Netz erlaubt jede Adresse darin, gleich über welchen Namen; deshalb sind
  exakte Hostnamen die engere Wahl. Es bleibt bei https. Ein gelisteter Host wird direkt
  gewählt, nicht über `HERD_AI_EGRESS_PROXY` (der Proxy ist für draußen gedacht); mit
  `networkPolicy.enabled` im Chart muss `networkPolicy.aiEgress` den Weg zu ihm
  zusätzlich öffnen. Gelesen wird die Einstellung von der API (Werkzeuglisten, Test)
  und vom Worker (Aufrufe in Läufen); Compose `HERD_MCP_ALLOWED_HOSTS`, Chart
  `mcp.allowedHosts` (Liste).
- **Tests** laufen gegen einen echten MCP-Server aus dem SDK
  (`backend/tests/support/mcp_stub.py`, https für `mcp.test` auf 127.0.0.1, skriptbar:
  Werkzeugliste, Ergebnisse, Verzögerung, Umleitung, Fehlerstatus, verlangter Kopf),
  nie gegen das Netz. Das SDK (`mcp`) wird nur unter `backend/app/mcp/` importiert
  (`tests/test_mcp_imports.py`).
