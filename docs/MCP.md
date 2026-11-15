# MCP: das System als MCP-Server und als MCP-Client

Dieses Dokument wächst mit M8. Bisher beschrieben: **Zugangstoken und das Recht
`mcp.use`** (Plan M8, Task 1), **Konnektoren** (Task 5) mit **OAuth** (Task 8) und
**externe MCP-Server** mit Werkzeugfreigabe (Task 6). Der Endpunkt `/mcp` selbst, externe Agenten, externe
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
  Server mit `connected`. Wird der Server gelöscht, gehen die daran gebundenen
  persönlichen Konnektoren mit.
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
- Audit `oauth_client.created`, `.updated` (Feldnamen, beim Geheimnis nur seine Art),
  `.deleted`; nie Werte.
- **Beim Anbieter registrieren**: Als Rückleitungsadresse (Callback-URL) trägt man
  `<HERD_PUBLIC_URL>/api/ai/oauth/callback` ein, genau so.
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
- **Rückkehr**: Der Anbieter schickt den Browser an `GET /api/ai/oauth/callback`. Der
  Code wird eingelöst (mit Prüfwert, derselben Rückleitungsadresse und `resource`),
  die Token als `enc:` gespeichert, die Version des Konnektors erhöht, Audit
  `connector.connected` (Geltung, ob ein Erneuerungstoken kam). Danach geht der
  Browser auf die Seite `/ai/oauth/done?status=…` (mit `connector` und `scope`, wenn
  bekannt); `status` ist `connected`, `denied` (abgelehnt beim Anbieter), `failed`
  (Fehler des Anbieters oder beim Einlösen) oder `invalid` (unbekannter, benutzter,
  abgelaufener oder fremder `state`, Konnektor weg, Rechte weg). Was der Anbieter
  sagt, steht nie in dieser Adresse.
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
- Die **Rückleitungsadresse** ist `HERD_PUBLIC_URL` plus `/api/ai/oauth/callback`, nie
  aus Kopfzeilen der Anfrage (`Host`, `X-Forwarded-Host`). Ohne `HERD_PUBLIC_URL` oder
  mit `http` außer für `localhost`/`127.0.0.1` gibt es kein OAuth (422
  `connector.oauth_unconfigured`).
- Das Sitzungs-Cookie ist `SameSite=Lax`; die Rückkehr ist eine Navigation, es kommt
  also mit. Ohne gültige Sitzung endet sie mit `invalid`.

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
  (freigegeben, unverändert, gelistet, Server eingeschaltet). Lesende Werkzeuge sind
  Stufe 2; schreibende Stufe 4 und immer mit Freigabe der fragenden Person
  (Fingerabdruck über Werkzeug, Argumente und die Versionen von Server und Werkzeug:
  ändert sich eins davon vor dem Ausführen, ist die Freigabe veraltet, und nichts wird
  gesendet). In Läufen von Ereignisregeln gilt das ebenso. Vor jedem Aufruf entscheidet
  die KI-Richtlinie aller bisher gelesenen Bereiche (und des Bereichs des Ortes) über
  den `data_location` des Servers wie über den einer Verbindung; lässt sie ihn nicht
  zu, wird nicht aufgerufen (`policy_blocked` als Ergebnis). Der Zugang ist der
  geteilte Konnektor oder bei `personal` der eigene der fragenden Person. Das Ergebnis
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
