# MCP: Konnektoren und externe Server

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
