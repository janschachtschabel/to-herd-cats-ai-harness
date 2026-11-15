# MCP: das System als MCP-Server und als MCP-Client

Dieses Dokument wächst mit M8. Bisher beschrieben: **Zugangstoken und das Recht
`mcp.use`** (Plan M8, Task 1) und **Konnektoren** (Task 5). Der Endpunkt `/mcp`
selbst, externe Agenten, externe MCP-Server und der Katalog folgen.

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
