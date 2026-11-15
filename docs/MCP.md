# MCP: das System als MCP-Server und als MCP-Client

Dieses Dokument wächst mit M8. Bisher beschrieben: **Zugangstoken und das Recht
`mcp.use`** (Plan M8, Task 1). Der Endpunkt `/mcp` selbst, externe Agenten, externe
MCP-Server, Konnektoren und der Katalog folgen (Tasks 2 bis 13).

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
