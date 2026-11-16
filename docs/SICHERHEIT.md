# Sicherheit: Prüfung gegen OWASP ASVS 5.0, Stufe 2

Stand 16.11.2026 (M9, Task 9; Jans Antworten und die Planung der Lücken mit Task 11
nachgetragen; der zweite Faktor mit M9b Task 16). Geprüft wurde to-herd-cats-ai gegen den **OWASP
Application Security Verification Standard 5.0.0** (Mai 2025), Stufe 2 (L2). Jede
Anforderung der Stufen 1 und 2 hat unten eine Zeile; die Stufe 3 ist nicht geprüft.

- Quelle: die maschinenlesbare Fassung des Standards,
  <https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv>
  (Tag `v5.0.0`, SHA-256 `98c8fe911b9edb403af8ee05d3ce8201ecac2659e313b053890a62847cdcf680`),
  Lizenz CC BY-SA 4.0. Die Spalte „Thema“ ist eine eigene deutsche Kurzfassung, nicht der
  Wortlaut; maßgeblich ist der Text des Standards zur jeweiligen Nummer.
- Umfang: 345 Anforderungen, davon 253 in den Stufen 1 und 2 (70 L1, 183 L2).
- Ergebnis: **188 erfüllt**, **53 nicht anwendbar**, **12 Lücke** (L1: 60 erfüllt,
  10 nicht anwendbar, 0 Lücke; L2: 128 erfüllt, 43 nicht anwendbar, 12 Lücke). Mit
  M9b Task 16 (TOTP) sind V6.4.4 und V6.5.1 bis V6.5.5 erfüllt.
- `backend/tests/test_security_doc.py` prüft, dass diese Liste jede Nummer genau einmal
  enthält, nur die drei Status nutzt und jede Lücke ihrer Frage (J3, J7 bis J14) und
  entweder der Aufgabe, die sie schließt (Task 16, Task 18), oder einer dokumentierten
  Abweichung zuordnet.

Status: **erfüllt** heißt, die Anforderung ist umgesetzt und der Beleg zeigt wo (Datei,
meist auch der Test). **Nicht anwendbar** heißt, es gibt die Funktion nicht (kein LDAP,
kein GraphQL) oder sie liegt beim Betrieb (dann mit Betriebsvoraussetzung B1 bis B3).
**Lücke** heißt, es fehlt etwas; jede Lücke hat eine Frage an Jan und ist entweder für
M9b geplant (Task 16, Task 18) oder eine dokumentierte Abweichung (unten).

Pfade in den Belegen sind gekürzt: `core/`, `web/`, `ops/`, `mcp/`, `worker/` liegen unter
`backend/app/`, Modulnamen wie `auth/`, `oidc/`, `users/` unter `backend/app/modules/`,
`tests/` unter `backend/`; Dateien des Frontends (`.tsx`) unter `frontend/src/`
(meist `features/`). `datei.funktion` nennt eine Funktion in der Datei, `datei::test`
einen Test.

## Behoben in dieser Prüfung

Lücken, die in höchstens einem halben Tag zu schließen waren, sind behoben, jede zuerst
mit einem Test und in einem eigenen Commit:

| Anforderung | Was | Commit |
|---|---|---|
| V2.2.1 | Die Routen des Frontends (`validateSearch`) behalten keinen ungeprüften Suchparameter mehr | `security: keep no unchecked search value in any route` |
| V3.4.1, V3.4.3 | HSTS mit `includeSubDomains`; jede Antwort hat eine CSP (die API `default-src 'none'`), `base-uri 'none'` | `security: send a CSP on every answer and HSTS for subdomains` |
| V14.2.2, V14.3.2 | `Cache-Control: no-store` für `/api` und `/mcp` | `security: keep API answers out of browser and proxy caches` |
| V3.3.1, V3.3.3 | Sitzungs- und OIDC-Cookie unter https mit dem Präfix `__Host-` | `security: bind the sign-in cookies to the host with __Host-` |
| V3.3.1, V13.4.2 | Der Produktionsstart verweigert `HERD_COOKIE_SECURE=false` bei einer https-Adresse | `security: refuse a production start with insecure cookies behind https` |
| V16.5.1 | Eine 422 nennt nur Felder der API, nie gesendete Schlüssel oder Werte | `security: name only the API's own fields in a validation error` |
| V6.2.4, V6.2.11, V6.2.12 | Häufige, geleakte und kontextbezogene Passwörter werden abgelehnt | `security: refuse breached and context passwords` |
| V16.3.1 | Jeder Anmeldeversuch und jede Abmeldung hat eine Protokollzeile | `security: log every sign-in attempt and sign-out` |
| V7.2.4 | Eine Anmeldung beendet die Sitzung, die sie ersetzt | `security: end the session a sign-in replaces` |
| V11.2.2 | Passwort-Hashes mit alten Parametern werden beim Login erneuert | `security: rehash a password made with old parameters at login` |
| V7.4.3 | Das Lösen einer OIDC-Verknüpfung beendet die anderen Sitzungen der Person | `security: end the other sessions when a sign-in identity is unlinked` |
| V7.4.5 | Admins melden eine Person überall ab | `security: let administrators sign a person out everywhere` |
| V13.4.4 | Test: TRACE wird nicht unterstützt | mit diesem Dokument |

## Offene Lücken: Entscheidungen und Planung

Diese Lücken sind größer als ein halber Tag oder brauchten eine Entscheidung. Nichts davon
ist in M9a gebaut. J3 hat Jan am 15.11.2026 beantwortet; J7 bis J14 sind Fragen der
Sicherheitstechnik, nicht des Produkts: Claude hat sie entschieden (Jan kann
widersprechen), gebaut werden sie in **M9b Task 18** (Plan
`docs/superpowers/plans/2026-11-15-m9-produktion.md`). Zwei Teile bleiben dokumentierte
Abweichungen: MFA für lokale Passwortkonten (J3) und TLS zwischen API und
Collab-Prozess (J12 b).

**J3 – Mehr-Faktor-Anmeldung (V6.3.3). Abweichung.** Jans Antwort: TOTP vorerst **nur
optional**, auch für Owner und Admins, ohne Pflicht. M9b Task 16 hat TOTP für
Passwortkonten als freiwilligen zweiten Faktor gebaut (`backend/app/modules/totp/`,
[`ANMELDUNG.md`](ANMELDUNG.md#zweiter-faktor-totp)) und erfüllt damit V6.4.4 und V6.5.1
bis V6.5.5 (Wiederherstellung bei Verlust, Codes nur einmal, Wiederherstellungscodes
gehasht, Seeds aus CSPRNG, Lebensdauer); für Personen mit TOTP verlangen das Anlegen von
Zugangstoken und eine Anmeldung über OIDC den zweiten Faktor ebenfalls (V6.3.4). Weil
niemand ihn einrichten muss, bleibt V6.3.3 eine **dokumentierte Abweichung von ASVS L2**
für lokale Passwortkonten.
Konten, die sich über OIDC anmelden, bekommen den zweiten Faktor vom Anbieter (Google
Workspace, Entra ID, Keycloak …); wer ASVS L2 ohne Abweichung braucht, meldet sich nur
über einen Anbieter mit Pflicht-MFA an und vergibt keine Passwörter.

**J7 – Inaktivitätsgrenze (V7.3.1). Geplant, M9b Task 18.** Eine Sitzung gilt 7 Tage,
auch wenn niemand sie nutzt. *Entscheidung:* bauen. `HERD_SESSION_IDLE_HOURS` (Standard
24, 0 = aus); die Sitzung merkt `last_used_at`, bei der Auflösung höchstens einmal je
Minute geschrieben; danach 401 `auth.session_invalid`. Die offene Live-Verbindung (SSE)
zählt nicht als Nutzung. Einstellung in Compose, Chart und Doku.

**J8 – Eigene Sitzungen sehen und beenden (V7.5.2). Geplant, M9b Task 18.**
*Entscheidung:* bauen, im Profil: Liste der eigenen Sitzungen (Gerätehinweis aus dem
gekürzten User-Agent, Anmeldezeit, letzte Nutzung aus J7) mit „Abmelden“ je Sitzung und
„Alle anderen abmelden“; `GET/DELETE /api/auth/me/sessions` (paginiert, Audit).

**J9 – Erneute Anmeldung vor sensiblen Änderungen (V7.5.1). Geplant, M9b Task 18.**
*Entscheidung:* bauen. Vor dem Verknüpfen einer neuen OIDC-Identität im Profil fragt die
App das Passwort ab; Personen ohne Passwort brauchen eine Anmeldung über einen schon
verknüpften Anbieter, die höchstens 10 Minuten alt ist (an der Sitzung gemerkt).

**J10 – Anti-Automatisierung für gewöhnliche Schreibvorgänge (V2.4.1). Geplant, M9b
Task 18.** *Entscheidung:* bauen. Eine Grenze je Person in PostgreSQL (wie
`core/ratelimit.py`) für Nachrichten, Seiten, Tickets und Uploads, großzügige Standards
(etwa 120 Schreibvorgänge und 30 Uploads je Minute), 429 `rate.limited` mit
`Retry-After`; Agenten zählen wie Personen. Der Lasttest (Task 10) darf nicht anschlagen.

**J11 – Virenscan (V5.4.3). Geplant, M9b Task 18 (optional).** *Entscheidung:* optional
bauen. ClamAV (`clamd`, als eigener Dienst über TCP angesprochen, nicht gelinkt) über
`HERD_CLAMAV_ADDRESS`, Standard aus (dann wie heute). Ist er eingestellt, werden Anhänge
und Importe vor dem Speichern geprüft; ein Fund lehnt mit 422 ab, ein nicht erreichbarer
oder scheiternder Scanner ebenfalls (fail closed). Ohne Scanner bleibt V5.4.3 offen;
das ist eine Entscheidung des Betriebs.

**J12 – Verschlüsselung und Authentisierung im Cluster (V12.3.1, V12.3.3, V12.3.4,
V13.2.1). Teils geplant (M9b Task 18), teils Abweichung.** *Entscheidung:* (a) TLS zur
Datenbank: `sslmode` und CA als Einstellungen und im Chart (CA aus einem Secret);
empfohlen ist `verify-full` (Task 18, V12.3.1). (b) API ↔ Collab-Prozess: **dokumentierte
Abweichung**; die App leistet kein TLS im Cluster, Betriebsvoraussetzung ist ein
Service-Mesh mit mTLS oder die NetworkPolicy des Charts (V12.3.3, V12.3.4). (c) Das
interne Token wird rotierbar: zwei gültige Werte zugleich, wie `HERD_SECRET_KEY_PREVIOUS`
(Task 18, V13.2.1).

**J13 – Mix-up-Schutz für den OAuth-Client der Konnektoren (V10.2.2). Geplant, M9b
Task 18.** OIDC ist schon geschützt (eigene Rückruf-Adresse je Anbieter, `iss` im
ID-Token exakt). *Entscheidung:* bauen. Eine Rückruf-Adresse je OAuth-Client
(`/api/ai/oauth/<client_id>/callback`) und die Prüfung von `iss` in der
Autorisierungsantwort (RFC 9207), wenn der Server ihn schickt. Bestehende Registrierungen
brauchen die neue Rückruf-Adresse (Hinweis in `docs/MCP.md`).

**J14 – Getrennte Datenbankrollen (V13.2.2). Geplant, M9b Task 18.** *Entscheidung:*
bauen, als Option. Eine Migrationsrolle besitzt das Schema, die Laufzeitrolle bekommt nur
DML-Rechte (`GRANT` in einer Migration); Compose und Chart können zwei Rollen nutzen. Der
Standard bleibt eine Rolle für kleine Installationen (dokumentiert); Sicherung und
Wiederherstellung laufen mit der Migrationsrolle.

## Betriebsvoraussetzungen und Hinweise

Einige Anforderungen erfüllt nicht die Anwendung, sondern ihr Betrieb. Sie stehen in den
Zeilen als „nicht anwendbar“ mit Verweis hierher:

- **B1 – TLS am Eingang.** TLS (1.2 oder 1.3, empfohlene Cipher Suites, öffentlich
  vertrautes Zertifikat) endet am Ingress oder Reverse Proxy. Er leitet http nur für die
  Oberfläche auf https um, nicht für `/api` und `/mcp` (dort antwortet er auf http mit
  einem Fehler oder gar nicht), und steht in `HERD_FORWARDED_ALLOW_IPS`. Mit
  `HERD_PUBLIC_URL=https://…` verlangt der Produktionsstart `HERD_COOKIE_SECURE=true`.
- **B2 – Eigener Hostname.** to-herd-cats-ai läuft unter einem eigenen Hostnamen, den
  keine andere Anwendung teilt (Oberfläche, API und Live-Bearbeitung sind ein Ursprung).
- **B3 – Schutz der Protokolle.** Die App schreibt Protokolle nur nach stdout. Sammeln,
  Zugriffsschutz, Unveränderlichkeit und Aufbewahrung leistet die Log-Plattform des
  Betriebs, getrennt von der App.

Hinweise:

- **H1 – Vollständige Leak-Prüfung.** Neue Passwörter werden gegen die 142.518
  häufigsten Passwörter mit 10 bis 200 Zeichen aus Leak-Sammlungen geprüft (offline).
  Eine Abfrage eines vollständigen Leak-Bestands (Have I Been Pwned, k-Anonymität) wäre
  ein Aufruf nach außen bei jedem Passwortwechsel und ist bewusst nicht eingebaut; über
  OIDC angemeldete Personen betrifft das nicht.

## Vertrauensbereich Collab-Prozess

(Aus dem Steckbrief hierher verschoben; Review M2 R14, umgesetzt in M9.) Das
Sitzungs-Cookie verlässt die API nicht. Für jede Live-Verbindung stellt das Relay eine
Berechtigung aus, die nur für genau eine Seite und Generation gilt, zehn Minuten ab der
letzten Prüfung, und nur als SHA-256 gespeichert ist. Ein übernommener Collab-Prozess
kann damit nur die Seiten lesen und überschreiben, die gerade in ihm offen sind, im
Namen der dort verbundenen Personen, solange sie die Seite bearbeiten dürfen; er hält
keine Anmeldung, mit der er die öffentliche API aufrufen könnte, erreicht keine andere
Seite, und mit erfundenen oder fremden Berechtigungen beendet er keine Live-Sitzung. Im
Chart trennt die NetworkPolicy den Collab-Pod zusätzlich von der öffentlichen API; in
Compose laufen beide im selben Container ([`WIKI.md`](WIKI.md), „Berechtigungen des
Collab-Prozesses“). Offen bleibt das statische interne Token (J12).

## Eingaben und Grenzen

Jede Eingabe prüft das Backend gegen ein Pydantic-Schema (Typ, Länge, Muster,
Aufzählung, bei Änderungen keine unbekannten Felder); das OpenAPI-Dokument
(`frontend/openapi.json`) beschreibt sie vollständig, das Frontend leitet seine
Formularprüfung nur daraus ab. NUL-Zeichen werden überall abgelehnt. Grenzen, die über
einzelne Felder hinausgehen:

| Grenze | Standard | Einstellung |
|---|---|---|
| Größe eines Anfragekörpers | 1 MiB | `HERD_MAX_BODY_BYTES` |
| Anhang | 25 MiB | `HERD_ATTACHMENT_MAX_BYTES` |
| Import (ZIP) | 100 MiB gepackt, 200 MiB entpackt, 2.000 Einträge | `HERD_IMPORT_MAX_BYTES` |
| Skill (SKILL.md oder ZIP) | 10 MiB | – |
| Listen | `limit` höchstens 100, Cursor | – |
| Vergleich zweier Seitenversionen | 20.000 Zeilen | `HERD_DIFF_MAX_LINES` |
| Passwort | 10 bis 200 Zeichen | – |
| Anmeldeversuche | 30 je Adresse und Minute, 5 Fehlversuche je Adresse und E-Mail | `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE`, `HERD_LOGIN_RATE_LIMIT_PER_MINUTE` |
| Falsches altes Passwort im Profil | wie Fehlversuche je Person | – |
| OIDC-Starts und Rückrufe | 30 je Adresse und Minute | `HERD_OIDC_RATE_PER_MINUTE` |
| Gleichzeitiges Passwort-Hashing | 2 je Prozess, 16 wartend, sonst 429 `server.busy` | `HERD_PASSWORD_HASH_CONCURRENCY`, `HERD_PASSWORD_HASH_QUEUE` |
| `/mcp` | 120 Aufrufe je Token und Minute | `HERD_MCP_RATE_PER_MINUTE` |
| Externe Aufrufe je Lauf | 20 | `HERD_MCP_MAX_CALLS_PER_RUN` |
| Persönliche Agenten je Person | 5 | `HERD_AI_PERSONAL_AGENTS_MAX` |
| Automatisierungen je Person | 20 | `HERD_AI_AUTOMATIONS_MAX` |
| KI-Kosten | Budgets je Organisation, Person und Agent und UTC-Tag | Verwaltung, [`AGENTEN.md`](AGENTEN.md) |

Zusammenhänge zwischen Feldern (Ticket-Hierarchie, Sprint gehört zum Bereich,
Statuskategorien) beschreibt [`TICKETS.md`](TICKETS.md), Rollen und Rechte der Bereiche
[`WIKI.md`](WIKI.md); was Zeit und Geld kostet, der [Steckbrief](STECKBRIEF.md)
(„Funktionen mit Laufzeit und Kosten“). Für gewöhnliche Schreibvorgänge gibt es keine
Ratenbegrenzung je Person (J10).

## Dateien

Hochgeladen werden Anhänge (Wiki, Nachrichten, Tickets), Wiki-Importe (ZIP) und Skills
(SKILL.md oder ZIP). Der Typ wird am Inhalt erkannt (Magic Bytes, Office-Formate an den
ZIP-Einträgen, Text als gültiges UTF-8) und muss zur Endung passen; HTML, SVG und
ausführbare Formate werden abgelehnt. Archive werden vor dem Entpacken an ihrem
Verzeichnis geprüft (Anzahl, entpackte Größe, kein Zip64, keine Pfade nach oben).
Gespeichert wird inhaltsadressiert (`attachments/<org_id>/<sha256>` unter
`HERD_DATA_DIR`), der Dateiname ist nur Metadatum. Ausgeliefert wird jede Datei mit
`Content-Disposition` nach RFC 6266, `nosniff` und einer CSP mit `sandbox`; nur
Rasterbilder zeigt die Seite `inline`, alles andere ist ein Download.
Ein Virenscan fehlt (J11). Einzelheiten: [`WIKI.md`](WIKI.md) (Anhänge, Import),
[`AGENTEN.md`](AGENTEN.md) (Skills).

## Anmeldung

Wege, auf denen sich jemand gegenüber der App ausweist (es gibt keine weiteren):

| Weg | Wer | Wo | Nachweis |
|---|---|---|---|
| E-Mail und Passwort | Personen mit lokalem Passwort | `POST /api/auth/login` (mit TOTP danach `POST /api/auth/login/second-factor`) | Sitzungs-Cookie |
| OIDC (Google, allgemeiner Anbieter) | Personen mit verknüpfter Identität | `/api/auth/oidc/<Schlüssel>/…`, [`ANMELDUNG.md`](ANMELDUNG.md) | Sitzungs-Cookie |
| Zugangstoken `herd_pat_`/`herd_agt_` | Personen und externe Agenten | nur `/mcp`, [`MCP.md`](MCP.md) | `Authorization: Bearer` |
| Collab-Berechtigung `herd_cg_` | der Collab-Prozess im Namen einer Person | nur `/internal/collab/*` | `Authorization: Bearer` |
| Internes Token | Collab-Prozess, Proben | nur der interne Port | `X-Herd-Internal-Token` |

Das Sitzungs-Cookie nehmen nur die öffentliche API (mit `/api/stream`) und das Relay
`/collab` an; `/mcp` nimmt nur Zugangstoken, der interne Port nur das interne Token. Es gibt keine
Standardkonten: das erste Konto entsteht nur aus `HERD_BOOTSTRAP_ADMIN_EMAIL` und
`HERD_BOOTSTRAP_ADMIN_PASSWORD`.

**Schutz gegen Raten.** Je Client-Adresse (IPv6 je /64) höchstens 30 Versuche je Minute,
je Adresse und E-Mail 5 Fehlversuche; gezählt in PostgreSQL über alle Knoten, ein
unbekanntes Konto kostet dieselbe Hash-Arbeit (Dummy-Hash). Es gibt keine Kontosperre,
die ein Fremder auslösen könnte: eine andere Adresse kommt weiter durch. OIDC-Starts und
Rückrufe sind je Adresse begrenzt, falsche alte Passwörter im Profil je Person, falsche
TOTP- und Wiederherstellungscodes je Person (5 je Minute) und je wartender Anmeldung
(nach 5 ist sie beendet).

**Zweiter Faktor.** Freiwillig mit TOTP (RFC 6238, eigener Code auf `hmac`), für jede
Person mit Passwort; Einzelheiten in [`ANMELDUNG.md`](ANMELDUNG.md#zweiter-faktor-totp).
Das Passwort allein öffnet dann keine Sitzung, nur eine wartende Anmeldung (5 Minuten,
einmal, an ein HttpOnly-Cookie gebunden, nur ihr Hash in PostgreSQL).

**Passwortregeln.** 10 bis 200 Zeichen, sonst keine Regeln zur Zusammensetzung; das
Passwort wird unverändert gehasht (kein Kürzen, kein Trimmen). Abgelehnt wird ein neues
Passwort (Anlegen und Ändern durch Admins, eigener Wechsel), wenn es

- ohne Groß- und Kleinschreibung in der Liste der 142.518 häufigsten Passwörter mit 10
  bis 200 Zeichen steht (`backend/app/core/common_passwords.txt.gz`, aus der
  Top-Million von Pwdb-Public, MIT, Hinweise in `common_passwords.LICENSE`):
  422 `auth.password_common`;
- ein **Kontextwort** enthält: den Produktnamen (`toherdcats`, `herdcats`), den Namen
  der Organisation, den lokalen Teil der E-Mail-Adresse und seine Teile zwischen
  Punkten, den ersten Teil ihrer Domain (`beispiel` aus `beispiel.de`), den Namen der
  Person und seine Teile; jedes Wort ab 4 Buchstaben oder Ziffern, verglichen ohne
  Groß- und Kleinschreibung, Leer- und Satzzeichen: 422 `auth.password_context`.

Passwörter laufen nicht ab. Es gibt keinen Selbstbedienungs-Reset: ein Admin setzt ein
neues Passwort, dann enden alle Sitzungen der Person.

**Föderierte Anmeldung.** Eine Identität ist `(Anbieter, sub)`; über die E-Mail
verknüpft wird nur, wenn der Anbieter für die Adresse maßgeblich ist. ID-Token werden
mit dem JWKS des Anbieters geprüft (nur RS256 und ES256), dazu `iss`, `aud`, `azp`,
`exp`, `iat`, `nbf` und `nonce`. Die App wertet `acr` und `amr` nicht aus und verlangt
für keine Funktion eine bestimmte Stärke: eine OIDC-Anmeldung zählt wie ein Faktor; ob
der Anbieter einen zweiten Faktor verlangt, entscheidet seine Verwaltung.

## Sitzungen

- Eine Sitzung ist ein zufälliges 256-Bit-Token im Cookie `herd_session` (unter https
  `__Host-herd_session`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`); gespeichert
  ist nur sein SHA-256. Jede Anfrage löst es in PostgreSQL auf.
- **Absolute Dauer** 7 Tage (`HERD_SESSION_TTL_HOURS`, Standard 168), nie verlängert,
  auch nicht durch Nutzung. **Keine Inaktivitätsgrenze** (Lücke V7.3.1, J7). Das
  weicht von NIST SP 800-63B-4 ab (AAL2: erneute Anmeldung spätestens nach 24
  Stunden und nach 1 Stunde Inaktivität): gewählt für ein Arbeitswerkzeug, das man täglich offen hat;
  ausgeglichen durch Abmelden überall durch Admins, Ende aller Sitzungen bei Passwort-
  wechsel, Deaktivierung und Lösen einer OIDC-Verknüpfung.
- **Gleichzeitige Sitzungen:** keine Höchstzahl; jedes Gerät und jeder Browser hat
  eine eigene. Eine neue Anmeldung im selben Browser beendet die vorige.
- **Föderierte Sitzungen:** die Sitzung der App ist unabhängig von der beim Anbieter.
  Sie entsteht nur nach dem Klick auf den Anbieter, gilt höchstens
  `HERD_SESSION_TTL_HOURS` und endet nicht, wenn man sich beim Anbieter abmeldet (kein
  Single Logout); danach führt die Anmeldeseite wieder zum Anbieter.
- **Ende:** Abmelden (setzt den Ablauf in der Datenbank auf jetzt), Ablauf,
  Passwortwechsel (alle anderen), Lösen einer OIDC-Verknüpfung (alle anderen),
  Deaktivieren (alle), „Abmelden“ in der Personenverwaltung (alle, Audit
  `user.signed_out`). Eine offene Live-Bearbeitung speichert ihre letzten Änderungen
  noch bis zu einer Stunde, lässt aber niemanden neu zu (Review M2 R2).

## Kryptografie

Inventar (eigener Code verwendet nur diese Verfahren, alle aus erprobten Bibliotheken):

| Zweck | Verfahren | Schlüssel bzw. Zufall | Code |
|---|---|---|---|
| Passwörter | argon2id, Bibliotheksstandard (RFC 9106: 64 MiB, t=3, p=4), Rehash bei neuen Parametern | Salz je Hash | `core/security.py` (`argon2-cffi`) |
| Sitzungs-, Zugangs-, Collab-Token | 256 Bit aus `secrets`, gespeichert als SHA-256, Vergleich in konstanter Zeit | – | `core/security.py`, `tokens/values.py`, `wiki/collab_grants.py` |
| Gespeicherte Geheimnisse (`enc:`) | Fernet (AES-128-CBC, HMAC-SHA256) | aus `HERD_SECRET_KEY` per HKDF-SHA256 | `core/secrets.py` (`cryptography`) |
| OIDC `state`, `nonce`, PKCE, Bindungs-Cookie | 256 Bit aus `secrets`, S256 | – | `oidc/flow.py` |
| OAuth der Konnektoren | `state` und PKCE S256 | – | `oauth/flow.py`, `oauth/protocol.py` |
| ID-Token | RS256, ES256 prüfen | JWKS des Anbieters | `oidc/id_token.py` (PyJWT) |
| Prüfsummen, Fingerabdrücke | SHA-256 | – | Anhänge, Sicherung, MCP-Werkzeuge |
| Sicherung offsite | restic (AES-256, Poly1305) | `HERD_BACKUP_OFFSITE_PASSWORD` | `ops/offsite.py` |
| Transport | TLS am Ingress (B1), https nach außen | – | `core/egress.py` |

**Lebenszyklus von `HERD_SECRET_KEY`:** ein zufälliger Wert von mindestens 32 Zeichen
(`openssl rand -hex 32`), nur in der Umgebung bzw. einem Kubernetes-Secret, nie in der
Datenbank. Rotation: neuen Schlüssel setzen, alten als `HERD_SECRET_KEY_PREVIOUS`, mit
`scripts/rotate_secrets.py` alle `enc:`-Werte neu verschlüsseln, dann den alten
entfernen ([`KI.md`](KI.md)). Das Sicherungsmanifest nennt die Schlüsselkennung, damit
eine Wiederherstellung den passenden Schlüssel findet ([`SICHERUNG.md`](SICHERUNG.md)).
Ein verlorener Schlüssel macht nur die `enc:`-Werte unbrauchbar (neu eintragen; wer
TOTP eingerichtet hat, meldet sich mit einem Wiederherstellungscode an oder lässt TOTP
von einem Admin zurücksetzen).

## Verbindungen

| Von | Nach | Protokoll | Authentisierung |
|---|---|---|---|
| Browser | Ingress → API, öffentlicher Port 8080 (`/`, `/api`, `/api/stream`) | https (B1) | Sitzungs-Cookie, CSRF-Prüfung |
| Browser | Relay `/collab` → Collab-Prozess | wss (B1), im Cluster ws | Sitzungs-Cookie am Relay, dann Collab-Berechtigung |
| MCP-Clients | `/mcp` | https (B1) | Zugangstoken |
| Collab-Prozess | API, interner Port 9090 (`/internal/collab/*`) | http im Cluster (J12) | internes Token und Collab-Berechtigung |
| Prometheus, Kubelet | interner Port 9090 (`/metrics`, `/live`, `/ready`) | http im Cluster | keine; nur aus dem Cluster erreichbar (NetworkPolicy) |
| API, Worker, Migration | PostgreSQL | TLS nur, wenn in der URL verlangt (J12) | Passwort (`HERD_DATABASE_PASSWORD_FILE`) |
| API, Worker | KI-Anbieter, MCP-Server, OIDC-Anbieter, OAuth-Server | https über `core/egress.py` (KI optional über `HERD_AI_EGRESS_PROXY`) | Schlüssel bzw. Token des Ziels, nur an seinen Ursprung |
| Worker | restic-Repository | Protokoll des Repositorys | `HERD_BACKUP_OFFSITE_PASSWORD` und Zugangsdaten des Speichers |
| alle Prozesse | OTLP-Collector (optional) | `OTEL_EXPORTER_OTLP_ENDPOINT` | nach Betrieb |

Ziele nach außen trägt nur die Verwaltung ein; die Egress-Sperre lässt nur https zu
öffentlichen Adressen zu (private nur aus `HERD_MCP_ALLOWED_HOSTS` bzw.
`HERD_OIDC_ALLOWED_HOSTS`, Metadaten-Adressen nie) und folgt keinen Weiterleitungen.

## Datenklassen

| Klasse | Beispiele | Schutz |
|---|---|---|
| Anmeldegeheimnisse | Passwörter, Sitzungs-, Zugangs- und Collab-Token, internes Token, `HERD_SECRET_KEY` | Nur Hash gespeichert (argon2id bzw. SHA-256) oder nur in der Umgebung; nie in Protokollen, URLs, Fehlern oder dem Audit; Zugangstoken einmal angezeigt |
| Zugangsdaten Dritter | KI-Schlüssel, Client-Secrets, Token der Konnektoren | `enc:` (Fernet) oder `env:`-Verweis; Klartext nur im Moment des Aufrufs und nur an den eingetragenen Ursprung |
| Inhalte | Seiten, Nachrichten und DMs, Tickets, Anhänge, Läufe, Skills, Gedächtnis | Je Organisation, Rechte in SQL gefiltert; nie in Protokollen, Outbox, `NOTIFY` oder Metriken; an KI nur nach Richtlinie und `no_ai`; Admin-Einsicht in DMs nur auditiert; Sicherungen im Volume unverschlüsselt (Datenträger des Betriebs), offsite verschlüsselt |
| Personenbezogene Stammdaten | Name, E-Mail, Rollen, OIDC-Subjekt, Adressen im Audit | Je Organisation; Protokolle nennen nur IDs; Aufbewahrung nach dem Katalog `core/retention.py` |
| Betriebsdaten | Protokolle, Metriken, Traces | Nur IDs, Codes, Zahlen, Routen-Vorlagen; Pfade mit `code`/`state` sind vom Tracing ausgenommen |

## Abhängigkeiten

Alle Abhängigkeiten sind mit Hashes gesperrt (`backend/uv.lock`, die `package-lock.json`
von frontend, collab und e2e), ihre Lizenzen prüft `backend/scripts/check_licenses.py`.
Die CI führt bei jedem Lauf `pip-audit`, `npm audit --audit-level=high` und Trivy für
das Image aus. Stand 15.11.2026 (lokal ausgeführt, die CI startet derzeit kontoseitig
keine Jobs): `pip-audit` für die Laufzeitabhängigkeiten ohne Befund, `npm audit` in
allen drei Paketen 0 Schwachstellen.

**Fristen (von Jan bestätigt, 16.11.2026):** eine bekannte Schwachstelle in einer
Laufzeitabhängigkeit oder dem Image wird behoben – kritisch (CVSS ≥ 9) binnen 7 Tagen,
hoch (≥ 7) binnen 30 Tagen, mittel binnen 90 Tagen, niedrig mit dem nächsten
regulären Update. Werkzeuge nur für Entwicklung und Tests (dev-Abhängigkeiten, e2e)
binnen 90 Tagen. Ohne Fix: Abwägung und Eintrag hier.

## Protokolle

Alle Prozesse schreiben JSON-Zeilen nach stdout (`HERD_LOG_FORMAT=json`), jede mit
`timestamp` (UTC), `level`, `logger`, `message`, `service` (`to-herd-cats-ai`),
`trace_id` und `span_id`. Ziele: nur stdout, optional Traces über OTLP. Inhalte,
Kopfzeilenwerte, Cookies, Passwörter, Token und Körper stehen nie darin.

| Ereignis | Logger | Felder |
|---|---|---|
| `http.request` (jede Anfrage) | `app.request` | Methode, Routen-Vorlage, Status, Dauer, `org_id` und `actor`, falls angemeldet, `client_trace_id` |
| `auth.sign_in` (jeder Anmeldeversuch; Warnung, wenn abgelehnt) | `app.auth` | Weg (`password`, `oidc`), Ergebnis (Wort oder Code), Client-Adresse, Anbieter, bei Erfolg `user_id` |
| `auth.sign_out` | `app.auth` | `user_id` |
| `unhandled exception` | `app.core.errors` | Ausnahme ohne gebundene Werte (Datenbankfehler ohne Parameter) |
| `db.conflict_retry` | `app.core.errors` | SQLSTATE |
| Worker, Läufe, Fälligkeiten (`runs.*`, `outbox.*`, `automations.*`) | `app.worker.*` | IDs, Codes, Zähler |
| Live-Zustellung (`live.*`) | `app.modules.messaging.*` | IDs, Codes |
| MCP, Anbieter (`mcp.tool_failed` u. a.) | `app.modules.*` | IDs, Codes |
| Sicherung (`backup.*`), Bootstrap (`bootstrap.*`) | `app.ops.*`, `app.modules.orgs.service` | Dateinamen, Größen, Codes, IDs |

Was jemand mit Rechten getan hat (Rollen, Personen, Einsichten in DMs, Verbindungen,
Abmelden überall), steht zusätzlich im Audit-Log der Organisation (Datenbank, lesbar nur mit dem Recht
`audit.read`). Sammlung, Schutz und Aufbewahrung der Protokolle liegen beim Betrieb
(B3).

## Anforderungen im Einzelnen


### V1 Encoding and Sanitization

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V1.1 | V1.1.1 | L2 | Eingaben nur einmal dekodieren | erfüllt | FastAPI/Starlette dekodieren Pfad, Query und JSON genau einmal vor der Pydantic-Prüfung; keine eigene Nachdekodierung (`core/nul_guard.py` prüft danach nur auf NUL). `tests/test_nul_input.py` |
| V1.1 | V1.1.2 | L2 | Kodierung erst am Ziel | erfüllt | React kodiert beim Rendern, `JSONResponse` beim Serialisieren, SQLAlchemy bindet Parameter, `core/downloads.content_disposition` kodiert Dateinamen im Header. |
| V1.2 | V1.2.1 | L1 | Kontextgerechte Ausgabekodierung | erfüllt | JSX-Textknoten, JSON, RFC-6266-Dateinamen (`core/downloads.py`); kein `dangerouslySetInnerHTML` im Frontend. `tests/test_wiki_attachments.py` |
| V1.2 | V1.2.2 | L1 | URLs sicher bauen, nur sichere Protokolle | erfüllt | Pfadparameter über openapi-fetch (kodiert); Links in Markdown nur http(s)/mailto/App-Pfade (`urlTransform` in `frontend/src/features/wiki/MarkdownContent.tsx`, `messaging/MessageMarkdown.tsx`; Tests `MarkdownContent.test.tsx`, `MessageMarkdown.test.tsx`). |
| V1.2 | V1.2.3 | L1 | JS/JSON-Injektion | erfüllt | JSON nur über `json`/`JSONResponse` bzw. `JSON.stringify`; kein dynamisch gebautes JavaScript; CSP ohne `unsafe-eval`, zod `jitless` (`frontend/src/lib/schemas.ts`). |
| V1.2 | V1.2.4 | L1 | SQL-Injektion | erfüllt | SQLAlchemy mit gebundenen Parametern; die wenigen `text(f"…")` setzen nur Konstanten oder zitierte Bezeichner ein (`ops/snapshot.py`, `audit/models.py`); LIKE mit `autoescape`/`escape` (`skills/repository.py`, `agents/past_runs_repository.py`). `tests/test_hostile_cursors.py` |
| V1.2 | V1.2.5 | L1 | OS-Befehls-Injektion | erfüllt | Kindprozesse nur mit Argumentlisten, nie über eine Shell (`pg_dump`/`pg_restore`, `restic`, `node`): `app/ops/`, `app/launch.py`; kein `shell=True`/`os.system` im Code. |
| V1.2 | V1.2.6 | L2 | LDAP-Injektion | nicht anwendbar | Kein LDAP. |
| V1.2 | V1.2.7 | L2 | XPath-Injektion | nicht anwendbar | Kein XPath, kein XML-Parser. |
| V1.2 | V1.2.8 | L2 | LaTeX-Injektion | nicht anwendbar | Kein LaTeX-Prozessor. |
| V1.2 | V1.2.9 | L2 | Sonderzeichen in regulären Ausdrücken | erfüllt | Reguläre Ausdrücke werden nur aus Konstanten gebaut (`frontend/src/features/tickets/refs.ts`); Nutzereingaben gehen in Postgres-Volltextsuche (`websearch_to_tsquery`) oder LIKE mit Escape, nie in einen Regex. |
| V1.3 | V1.3.1 | L1 | HTML aus WYSIWYG-Editoren | erfüllt | Der Live-Editor kennt nur das Schema `collab/schema.mjs` (ProseMirror verwirft alles andere, auch eingefügtes HTML: `collab/tables.mjs`), gespeichert wird Markdown; angezeigt ohne rohes HTML (react-markdown ohne rehype-raw). |
| V1.3 | V1.3.2 | L1 | Kein eval | erfüllt | Kein `eval`/`new Function` (zod `jitless`, CSP ohne `unsafe-eval`: `web/spa.py`, `tests/test_spa.py::test_csp_starts_from_self_and_forbids_framing`). |
| V1.3 | V1.3.3 | L2 | Daten für gefährliche Ziele bereinigen | erfüllt | Längen- und Musterprüfung aller Eingaben (Pydantic-Schemas), NUL-Sperre (`core/nul_guard.py`), Argumentlisten für Kindprozesse, Egress-Prüfung für URLs. |
| V1.3 | V1.3.4 | L2 | SVG-Inhalte | erfüllt | SVG und HTML werden als Anhang abgelehnt (`modules/wiki/filetypes.py`, `_MARKUP`; `docs/WIKI.md` Anhänge); `tests/test_wiki_filetypes.py`, `tests/test_wiki_attachments.py`. |
| V1.3 | V1.3.5 | L2 | Markdown und andere Skriptsprachen | erfüllt | Markdown ohne rohes HTML und mit Link-Filter (`MarkdownContent.tsx`, `MessageMarkdown.tsx` und Tests); kein CSS/XSL/BBCode von Nutzern. |
| V1.3 | V1.3.6 | L2 | SSRF | erfüllt | Jeder Aufruf nach außen (KI, MCP, OAuth, OIDC) geht über `core/egress.py`: https, nur öffentliche Adressen (private nur per `HERD_MCP_ALLOWED_HOSTS`/`HERD_OIDC_ALLOWED_HOSTS`), Auflösung beim Verbinden geprüft, keine Weiterleitungen. `tests/test_egress.py`, `test_egress_allowance.py`, `test_mcp_egress.py`. |
| V1.3 | V1.3.7 | L2 | Template-Injektion | nicht anwendbar | Keine Template-Engine; Texte für Modelle werden als Daten gerahmt (`app/runtime/untrusted.py`), nicht als Vorlage ausgewertet. |
| V1.3 | V1.3.8 | L2 | JNDI | nicht anwendbar | Kein Java/JNDI. |
| V1.3 | V1.3.9 | L2 | Memcache | nicht anwendbar | Kein Memcache (Zustand nur in Postgres, ADR 0007). |
| V1.3 | V1.3.10 | L2 | Formatstrings | erfüllt | Protokolle mit festen Nachrichten und `extra`-Feldern; keine Formatstrings aus Eingaben; i18next interpoliert nur benannte Werte, React kodiert. |
| V1.3 | V1.3.11 | L2 | SMTP/IMAP-Injektion | nicht anwendbar | Die App versendet und liest keine E-Mails. |
| V1.4 | V1.4.1 | L2 | Speichersichere Strings | nicht anwendbar | Kein eigener nativer Code (Python, TypeScript). |
| V1.4 | V1.4.2 | L2 | Ganzzahlüberläufe | erfüllt | Zahlen mit Grenzen in den Schemas (`ge`/`le`, z. B. `limit` ≤ 100, Generation ≤ 9 Ziffern in `web/collab_proxy.py`); Python-Ganzzahlen laufen nicht über. |
| V1.4 | V1.4.3 | L2 | Freigabe von Speicher | nicht anwendbar | Speicherverwaltung durch Python/Node; kein eigener nativer Code. |
| V1.5 | V1.5.1 | L1 | XML/XXE | nicht anwendbar | Kein XML-Parser; Office-Dateien werden nur an ihren ZIP-Einträgen erkannt (`modules/wiki/filetypes.py`). |
| V1.5 | V1.5.2 | L2 | Unsichere Deserialisierung | erfüllt | Nur JSON (Pydantic) und YAML mit `SafeLoader` (`modules/skills/format.py`); kein pickle. |

### V2 Validation and Business Logic

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V2.1 | V2.1.1 | L1 | Eingaberegeln dokumentiert | erfüllt | Das OpenAPI-Dokument (`frontend/openapi.json`, geprüft mit `npm run check:api`) beschreibt jedes Feld mit Typ, Länge, Muster und Grenzen; Abschnitt „Eingaben und Grenzen“. |
| V2.1 | V2.1.2 | L2 | Zusammenhänge kombinierter Daten dokumentiert | erfüllt | Spezifikation und Bedienungsdokus (Ticket-Hierarchie, Sprint gehört zum Bereich, Statuskategorien: `docs/TICKETS.md`; Bereichsrollen: `docs/WIKI.md`). |
| V2.1 | V2.1.3 | L2 | Grenzen der Geschäftslogik dokumentiert | erfüllt | Abschnitt „Eingaben und Grenzen“ dieses Dokuments, Einstellungen in `README.md`, `docs/AGENTEN.md`, `docs/MCP.md`, `docs/STECKBRIEF.md`. |
| V2.2 | V2.2.1 | L1 | Positive Prüfung aller Eingaben | erfüllt | Jede Route nimmt Pydantic-Schemas mit Typ, Länge, Muster, Aufzählung (`extra="forbid"` bei Änderungen); `tests/test_errors.py`, `tests/test_nul_input.py`, `tests/test_hostile_cursors.py`. Im Frontend lassen die Routen nur geprüfte Suchparameter durch (`frontend/src/app/router/search.ts`, `search.test.ts`). |
| V2.2 | V2.2.2 | L1 | Prüfung auf vertrauenswürdiger Schicht | erfüllt | Prüfung in Schemas und Services des Backends; das Frontend leitet seine zod-Schemas nur aus `openapi.json` ab (Bequemlichkeit, keine Sicherheitsgrenze). |
| V2.2 | V2.2.3 | L2 | Kombinationen plausibel | erfüllt | Services prüfen Zusammenhänge (Sprint gehört zum Bereich per Fremdschlüssel `(sprint_id, space_id)`, Hierarchie, Generation der Live-Bearbeitung); z. B. `tests/test_sprints*.py`, `tests/test_collab_grants.py`. |
| V2.3 | V2.3.1 | L1 | Abläufe nur in Reihenfolge | erfüllt | OIDC/OAuth-Abläufe einmalig und gebunden (`oidc/flow.py`, `oauth/flow.py`: `take` mit DELETE…RETURNING), Freigaben/Fragen/Vorschläge mit Zustandsautomaten und `version`. `tests/test_oidc_flow.py`, `tests/test_oauth_flow.py`. |
| V2.3 | V2.3.2 | L2 | Grenzen umgesetzt | erfüllt | Budgets je Organisation/Person/Agent (`ai/budgets.py`), Höchstzahlen (persönliche Agenten, Automatisierungen, externe Aufrufe je Lauf), Größen (`HERD_MAX_BODY_BYTES`, Anhänge, Importe). `tests/test_ai_budgets.py`, `tests/test_body_limit.py`. |
| V2.3 | V2.3.3 | L2 | Transaktionen | erfüllt | Eine Transaktion je Anfrage (`core/db.py`, `auth/deps.py` SessionDep), je Termin, je Ereignis-Charge; Fehler rollen ganz zurück. `tests/test_errors.py::test_a_deadlock_or_serialization_failure_asks_to_try_again`. |
| V2.3 | V2.3.4 | L2 | Sperren gegen Doppelbuchung | erfüllt | `version`-Spalten mit 409, Zeilensperren (`FOR UPDATE`, `SKIP LOCKED`), eindeutige Schlüssel (z. B. `(automation_id, due_at)`, Ticketnummern). `tests/test_concurrency.py`, `tests/test_budget_races.py`. |
| V2.4 | V2.4.1 | L2 | Anti-Automatisierung | Lücke | Begrenzt sind Anmeldung, OIDC, `/mcp` je Token, KI-Kosten (Budgets), Hash-Warteschlange, Größen. Es fehlt eine Grenze je Person für gewöhnliche Schreibvorgänge (Nachrichten, Seiten, Tickets, Hochladen). J10, geplant M9b Task 18. |

### V3 Web Frontend Security

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V3.2 | V3.2.1 | L1 | Inhalte nicht im falschen Kontext | erfüllt | API-Antworten mit CSP `default-src 'none'`, Anhänge als `attachment` mit CSP `sandbox` und `nosniff` (inline nur Rasterbilder). `tests/test_security_headers.py::test_security_headers_on_every_public_route`, `tests/test_wiki_attachments.py`. |
| V3.2 | V3.2.2 | L1 | Text als Text darstellen | erfüllt | React rendert Texte als Textknoten; kein `dangerouslySetInnerHTML`, kein `innerHTML` im Frontend. |
| V3.3 | V3.3.1 | L1 | Cookies Secure mit Präfix | erfüllt | Über https und mit `HERD_COOKIE_SECURE` heißen die Cookies `__Host-herd_session`/`__Host-herd_oidc` und sind Secure (`modules/auth/cookies.py`). `tests/test_cookie_security.py::test_cookies_are_httponly_samesite_and_secure_in_production`; Produktion mit https-Adresse startet nicht ohne `HERD_COOKIE_SECURE` (`tests/test_config.py::test_production_start_refuses_unsafe_settings`). |
| V3.3 | V3.3.2 | L2 | SameSite passend | erfüllt | Beide Cookies `SameSite=Lax` (Navigation vom IdP zurück muss das Bindungs-Cookie tragen); dazu die CSRF-Kopfzeile für schreibende Anfragen. `tests/test_cookie_security.py`. |
| V3.3 | V3.3.3 | L2 | `__Host-`-Präfix | erfüllt | Wie V3.3.1; über https wird nur der Name mit Präfix gelesen (`tests/test_cookie_security.py::test_a_plain_session_cookie_counts_nothing_over_https`). Über reines http (Ausprobieren) bleiben die Namen ohne Präfix, weil Browser dort keine Präfix-Cookies annehmen. |
| V3.3 | V3.3.4 | L2 | HttpOnly, Token nur per Set-Cookie | erfüllt | Sitzungs- und Bindungs-Cookie HttpOnly; das Sitzungstoken steht nur in `Set-Cookie` (nie im Body, nie in einer URL). `tests/test_cookie_security.py`, `tests/test_auth.py`. |
| V3.4 | V3.4.1 | L1 | HSTS ein Jahr mit Subdomains | erfüllt | `max-age=31536000; includeSubDomains` auf jeder Antwort über https (`core/security_headers.py`). `tests/test_security_headers.py::test_security_headers_on_every_public_route`, `test_hsts_only_over_https`. |
| V3.4 | V3.4.2 | L1 | CORS | erfüllt | Kein CORS: die App setzt nie `Access-Control-Allow-Origin` (keine CORS-Middleware), fremde Ursprünge bekommen keine Freigabe. |
| V3.4 | V3.4.3 | L2 | Content-Security-Policy | erfüllt | SPA: `default-src 'self'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'` (`web/spa.py`); jede andere Antwort `default-src 'none'` u. a. (`core/security_headers.API_POLICY`). `tests/test_spa.py`, `tests/test_security_headers.py`. Swagger UI nur außerhalb der Produktion ohne CSP. |
| V3.4 | V3.4.4 | L2 | nosniff | erfüllt | Auf jeder Antwort (`core/security_headers.py`). `tests/test_security_headers.py`. |
| V3.4 | V3.4.5 | L2 | Referrer-Policy | erfüllt | `Referrer-Policy: same-origin` auf jeder Antwort. `tests/test_security_headers.py`. |
| V3.4 | V3.4.6 | L2 | frame-ancestors | erfüllt | `frame-ancestors 'none'` auf jeder Antwort (SPA, API, Fehler, Anhänge). `tests/test_security_headers.py::test_security_headers_on_every_public_route`. |
| V3.5 | V3.5.1 | L1 | CSRF | erfüllt | Schreibende Methoden unter `/api` brauchen `X-Requested-With: herd` (`auth/deps.csrf_guard`, für alle `/api`-Routen in `web/public.py`); `/mcp` nutzt Bearer-Token statt Cookies. `tests/test_auth.py::test_csrf_header_required_for_unsafe_methods`. |
| V3.5 | V3.5.2 | L1 | Kein Umgehen des Preflights | erfüllt | Die verlangte Kopfzeile ist nicht CORS-safelisted, löst also immer einen Preflight aus, den die App nie freigibt (V3.4.2). |
| V3.5 | V3.5.3 | L1 | Keine Wirkung über sichere Methoden | erfüllt | Zustandsänderungen nur über POST/PUT/PATCH/DELETE; die GET-Routen `…/oidc/{key}/start` und die Rückrufe sind Navigationsschritte von Anmeldeabläufen (einmalig, gebunden, V2.3.1). |
| V3.5 | V3.5.4 | L2 | Getrennte Anwendungen auf eigenen Hostnamen | erfüllt | SPA, API und Live-Bearbeitung sind eine Anwendung unter einem Ursprung; Betriebsvoraussetzung B2: ein eigener Hostname, nicht mit anderen Anwendungen geteilt. |
| V3.5 | V3.5.5 | L2 | postMessage | nicht anwendbar | Das Frontend nutzt `postMessage` nicht (nur der Collab-Prozess zwischen eigenen Worker-Threads in Node). |
| V3.7 | V3.7.1 | L2 | Nur unterstützte Client-Technik | erfüllt | React 19, kein Plugin (Flash, Applets o. ä.). |
| V3.7 | V3.7.2 | L2 | Weiterleitungen nur an erlaubte Ziele | erfüllt | Nach der Anmeldung nur App-Pfade (`safeRedirect`, `frontend/src/app/router/search.ts`); nach außen nur zu den von Admins eingetragenen Anbietern (OIDC, OAuth). `frontend/src/app/router/search.test.ts`. |

### V4 API and Web Service

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V4.1 | V4.1.1 | L1 | Content-Type mit Zeichensatz | erfüllt | JSON als `application/json` (UTF-8 laut RFC 8259), HTML/Text mit `charset=utf-8` (Starlette), Downloads mit dem erkannten Typ und `nosniff`. |
| V4.1 | V4.1.2 | L2 | http→https nur für Browser-Endpunkte | nicht anwendbar | Die App leitet nie um; TLS und Umleitung macht der Ingress (Betriebsvoraussetzung B1: Umleitung nur für die Oberfläche, nicht für `/api` und `/mcp`). |
| V4.1 | V4.1.3 | L2 | Kopfzeilen von Zwischenstationen nicht fälschbar | erfüllt | `X-Forwarded-For/-Proto` gelten nur von `HERD_FORWARDED_ALLOW_IPS` (Standard `127.0.0.1`, uvicorn `forwarded_allow_ips`); keine anderen Identitäts-Kopfzeilen. `README.md` Betriebshinweise. |
| V4.2 | V4.2.1 | L2 | Request Smuggling | erfüllt | Nachrichtengrenzen bestimmt der HTTP-Parser von uvicorn (h11/httptools nach RFC 9112); vor der App steht der Ingress. Kein eigener Parser, kein eigener Test. |
| V4.3 | V4.3.1 | L2 | GraphQL-Kosten | nicht anwendbar | Kein GraphQL. |
| V4.3 | V4.3.2 | L2 | GraphQL-Introspektion | nicht anwendbar | Kein GraphQL. |
| V4.4 | V4.4.1 | L1 | WebSocket über TLS | erfüllt | Die Seite wählt `wss` unter https (`frontend/src/features/wiki/collab/connect.ts`); der einzige WebSocket ist das Relay `/collab` hinter demselben TLS-Endpunkt. |
| V4.4 | V4.4.2 | L2 | Origin beim Handshake | erfüllt | Das Relay prüft `Origin` gegen `HERD_PUBLIC_URL` bzw. den Host (`web/collab_proxy.py`). `tests/test_collab_proxy.py::test_rejects_foreign_origin`, `test_origin_without_public_url_must_match_the_host`. |
| V4.4 | V4.4.3 | L2 | Eigene Token für WebSockets | erfüllt | Der Browser nutzt die normale Sitzung; zum Collab-Prozess geht je Verbindung eine Berechtigung `herd_cg_…` (256 Bit, nur SHA-256 gespeichert, 10 Minuten, an Seite und Generation gebunden: `modules/wiki/collab_grants.py`). `tests/test_collab_grants.py`. |
| V4.4 | V4.4.4 | L2 | WebSocket-Token aus der angemeldeten Sitzung | erfüllt | Die Berechtigung entsteht erst, nachdem das Relay Sitzungs-Cookie, Seite und `page.edit` geprüft hat. `tests/test_collab_proxy.py::test_checks_session_and_page_edit_like_the_api`, `test_the_relay_sends_no_cookie_upstream`. |

### V5 File Handling

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V5.1 | V5.1.1 | L2 | Dateitypen und Größen dokumentiert | erfüllt | `docs/WIKI.md` (Anhänge: Typen, 25 MiB; Import: ZIP, 100 MiB gepackt, 200 MiB entpackt, 2.000 Einträge), `docs/AGENTEN.md` (Skills: SKILL.md/ZIP, 10 MiB), Abschnitt „Dateien“. |
| V5.2 | V5.2.1 | L1 | Größengrenzen | erfüllt | `HERD_MAX_BODY_BYTES`, `HERD_ATTACHMENT_MAX_BYTES`, `HERD_IMPORT_MAX_BYTES`, Zeitgrenzen für Körper (`core/body_limit.py`, `core/uploads.py`). `tests/test_body_limit.py`. |
| V5.2 | V5.2.2 | L1 | Endung und Inhalt passen | erfüllt | Der Typ wird am Inhalt erkannt (Magic Bytes, Office/ZIP an den Einträgen, Text als UTF-8) und muss zur Endung passen (`modules/wiki/filetypes.py`). `tests/test_wiki_filetypes.py`, `tests/test_wiki_attachments.py`. |
| V5.2 | V5.2.3 | L2 | Archive vor dem Entpacken prüfen | erfüllt | Anzahl und entpackte Größe aus dem Verzeichnis, Zip64 abgelehnt, bevor `zipfile` liest (`modules/wiki/archive.py`; Skills nutzen dieselben Grenzen). `tests/test_wiki_archive_limits.py`, `tests/test_wiki_import_scale.py`. |
| V5.3 | V5.3.1 | L1 | Hochgeladenes nie ausführen | erfüllt | Dateien liegen inhaltsadressiert unter `HERD_DATA_DIR` außerhalb des SPA-Verzeichnisses (`core/storage.py`) und werden nur mit `nosniff` und einer CSP mit `sandbox` ausgeliefert (Rasterbilder auf Wunsch `inline`, alles andere als Download). |
| V5.3 | V5.3.2 | L1 | Pfade nicht aus Dateinamen | erfüllt | Speicherschlüssel `attachments/<org_id>/<sha256>` (`core/storage.py`); der Name ist nur Metadatum. SPA-Pfade ohne `..`/Symlinks (`web/spa.py`, `tests/test_spa.py`). |
| V5.4 | V5.4.1 | L2 | Dateiname im Content-Disposition | erfüllt | Immer `Content-Disposition` mit dem gespeicherten Namen (`core/downloads.content_disposition`); Namen aus der Anfrage werden ignoriert. |
| V5.4 | V5.4.2 | L2 | Dateinamen kodiert (RFC 6266) | erfüllt | ASCII-Ersatz ohne Anführungszeichen und Steuerzeichen plus `filename*=UTF-8''…` (`core/downloads.py`). |
| V5.4 | V5.4.3 | L2 | Virenscan | Lücke | Kein Virenscanner. J11, optional geplant M9b Task 18 (ClamAV, Standard aus). |

### V6 Authentication

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V6.1 | V6.1.1 | L1 | Schutz gegen Raten dokumentiert | erfüllt | Abschnitt „Anmeldung“: Grenzen je Adresse und je Adresse+Konto, Ausgang ohne fremde Sperre, Einstellungen. |
| V6.1 | V6.1.2 | L2 | Liste kontextbezogener Wörter dokumentiert | erfüllt | Abschnitt „Anmeldung“, Passwortregeln. |
| V6.1 | V6.1.3 | L2 | Alle Anmeldewege dokumentiert | erfüllt | Abschnitt „Anmeldung“ (Passwort mit optionalem TOTP, OIDC, Zugangstoken für `/mcp`, Collab-Berechtigung, internes Token); `docs/ANMELDUNG.md`, `docs/MCP.md`. |
| V6.2 | V6.2.1 | L1 | Mindestens 8 Zeichen | erfüllt | Mindestens 10 (`core/password_rule.py`). `tests/test_users.py::test_create_validates_input`. |
| V6.2 | V6.2.2 | L1 | Passwort änderbar | erfüllt | `POST /api/auth/me/password` und Profil (`users/profile.py`, `features/profile/PasswordForm.tsx`). `tests/test_profile.py`. |
| V6.2 | V6.2.3 | L1 | Änderung braucht altes und neues Passwort | erfüllt | `PasswordChangeIn` verlangt beide; falsches altes 422 `auth.wrong_password`, Fehlversuche begrenzt. `tests/test_profile.py`. |
| V6.2 | V6.2.4 | L1 | Gegen die häufigsten Passwörter prüfen | erfüllt | 142.518 häufigste Passwörter mit 10 bis 200 Zeichen (Pwdb-Public, MIT) in `core/common_passwords.txt.gz`, ohne Groß/Klein (`core/password_check.py`); jedes Passwort, das Personen oder Admins setzen, und das der ersten Inhaberin (`HERD_BOOTSTRAP_ADMIN_PASSWORD`). `tests/test_password_guessing.py`, `tests/test_bootstrap_password.py`. |
| V6.2 | V6.2.5 | L1 | Keine Zusammensetzungsregeln | erfüllt | Nur Länge 10 bis 200; jedes Zeichen erlaubt. `tests/test_password_guessing.py::test_any_composition_of_an_unguessable_password_is_accepted`. |
| V6.2 | V6.2.6 | L1 | Passwortfelder maskiert | erfüllt | `type="password"` in Anmeldung, Profil, Personenverwaltung (`LoginPage.tsx`, `PasswordForm.tsx`, `CreateUserDialog.tsx`, `EditUserDialog.tsx`). |
| V6.2 | V6.2.7 | L1 | Einfügen und Passwortmanager erlaubt | erfüllt | Kein Abfangen von Einfügen; `autoComplete="current-password"`/`"new-password"`. |
| V6.2 | V6.2.8 | L1 | Passwort exakt prüfen | erfüllt | argon2 über den unveränderten String (kein Kürzen, kein Trimmen, keine Umwandlung; über 200 Zeichen wird abgelehnt, nicht gekürzt): `core/security.py`, `auth/schemas.py`. |
| V6.2 | V6.2.9 | L2 | Mindestens 64 Zeichen erlaubt | erfüllt | Bis 200 Zeichen (`core/password_rule.py`). |
| V6.2 | V6.2.10 | L2 | Kein erzwungener Wechsel | erfüllt | Passwörter laufen nicht ab. |
| V6.2 | V6.2.11 | L2 | Kontextwörter verhindern | erfüllt | Produkt, Organisation, E-Mail (lokaler Teil, Domain), Name (`core/password_check.context_words`); auch für das Passwort der ersten Inhaberin aus `HERD_BOOTSTRAP_ADMIN_PASSWORD` (sonst bricht der Start ab). `tests/test_password_guessing.py::test_a_guessable_new_password_is_refused`, `tests/test_bootstrap_password.py`. |
| V6.2 | V6.2.12 | L2 | Gegen geleakte Passwörter prüfen | erfüllt | Die Liste aus V6.2.4 stammt aus Leak-Sammlungen (Top-Million von Pwdb-Public). Nicht abgefragt wird ein vollständiger Leak-Bestand (etwa Have I Been Pwned per k-Anonymität): das wäre ein Aufruf nach außen bei jedem Passwortwechsel (Hinweis H1). |
| V6.3 | V6.3.1 | L1 | Schutz gegen Credential Stuffing umgesetzt | erfüllt | `auth/service.py` (Grenzen je Adresse und je Adresse+Konto, Dummy-Hash bei unbekannten Konten), OIDC je Adresse. `tests/test_login_limits.py`, `tests/test_auth.py::test_login_is_rate_limited`. |
| V6.3 | V6.3.2 | L1 | Keine Standardkonten | erfüllt | Das erste Konto entsteht nur aus `HERD_BOOTSTRAP_ADMIN_EMAIL`/`_PASSWORD` (Compose verlangt beide, kein Standardwert). `tests/test_auth.py::test_bootstrap_without_credentials_creates_nothing`. |
| V6.3 | V6.3.3 | L2 | Mehr-Faktor-Anmeldung | Lücke | TOTP gibt es für jede Person mit Passwort (M9b Task 16, `totp/`), aber freiwillig: Jans Antwort J3 (nur optional, auch für Owner und Admins). Über OIDC leistet den zweiten Faktor der Anbieter. Dokumentierte Abweichung. |
| V6.3 | V6.3.4 | L2 | Keine undokumentierten Wege, gleiche Stärke | erfüllt | Abschnitt „Anmeldung“ nennt alle Wege; `/mcp` nimmt nur Zugangstoken, `/internal` nur das interne Token, alles andere nur die Sitzung. Wer TOTP eingeschaltet hat, gibt den Code nach dem Passwort und nach einem OIDC-Anbieter, und für jedes neue Zugangstoken (`totp/gate.py`). `tests/test_totp_oidc.py`, `tests/test_totp_tokens.py`. |
| V6.4 | V6.4.1 | L1 | Erstpasswörter | nicht anwendbar | Das System erzeugt keine Erstpasswörter oder Aktivierungscodes (Admins setzen ein Passwort, oder die Person meldet sich über OIDC an). |
| V6.4 | V6.4.2 | L1 | Keine Passworthinweise/Sicherheitsfragen | erfüllt | Gibt es nicht. |
| V6.4 | V6.4.3 | L2 | Sicheres Zurücksetzen | erfüllt | Kein Selbstbedienungs-Reset; ein Admin (`user.manage`, das Passwort eines Owners nur ein Owner) setzt ein neues, alle Sitzungen enden, Audit `user.password_changed` (`users/service.py`). `tests/test_users.py`. |
| V6.4 | V6.4.4 | L2 | Verlorener zweiter Faktor | erfüllt | Wiederherstellungscodes (einmal je Code) oder Zurücksetzen durch einen Admin (`user.manage`, den eines Owners nur ein Owner) mit Audit `user.totp_reset`; die Doku verlangt dieselbe Identitätsprüfung wie beim Anlegen des Kontos (`users/service.reset_totp`, `docs/ANMELDUNG.md`). `tests/test_totp_admin.py`. |
| V6.5 | V6.5.1 | L2 | Einmalcodes nur einmal | erfüllt | Ein TOTP-Schritt gilt nur, wenn er neuer ist als der zuletzt angenommene (eine Anweisung, `totp/repository.use_step`); ein Wiederherstellungscode wird von der Anweisung gelöscht, die ihn annimmt. `tests/test_totp_setup.py::test_the_code_that_confirmed_cannot_turn_it_off`, `::test_an_earlier_step_is_refused_after_a_later_one`, `tests/test_totp_sign_in.py::test_a_recovery_code_opens_the_session_once`, `::test_a_used_step_is_refused_at_sign_in`. |
| V6.5 | V6.5.2 | L2 | Wiederherstellungscodes gehasht | erfüllt | Je 120 Zufallsbits (über 112), daher SHA-256 ohne Salz zulässig; nur der Hash steht in `totp_recovery_code` (`totp/recovery.py`). `tests/test_totp_setup.py::test_confirming_turns_it_on_with_ten_hashed_recovery_codes`. |
| V6.5 | V6.5.3 | L2 | Seeds aus CSPRNG | erfüllt | TOTP-Schlüssel 160 Bit und Wiederherstellungscodes aus `secrets.token_bytes` (`totp/codes.new_secret`, `totp/recovery.new_codes`); der Schlüssel liegt `enc:` unter `HERD_SECRET_KEY`. `tests/test_totp_codes.py::test_new_secrets_are_160_random_bits_in_base32`. |
| V6.5 | V6.5.4 | L2 | Mindestens 20 Bit | erfüllt | Wiederherstellungscodes 120 Bit; TOTP sechs Ziffern (RFC 6238). |
| V6.5 | V6.5.5 | L2 | Lebensdauer von Codes | erfüllt | TOTP-Schritt 30 s, angenommen höchstens ein Schritt davor und danach; eine wartende Anmeldung gilt 5 Minuten (`totp/codes.py`, `totp/challenges.py`). `tests/test_totp_codes.py::test_the_current_step_and_one_on_either_side_match`, `tests/test_totp_sign_in.py::test_codes_outside_the_window_are_refused`, `::test_a_challenge_expires`. |
| V6.6 | V6.6.1 | L2 | SMS/Telefon | nicht anwendbar | Kein Out-of-Band-Verfahren. |
| V6.6 | V6.6.2 | L2 | Out-of-Band gebunden | nicht anwendbar | Kein Out-of-Band-Verfahren. |
| V6.6 | V6.6.3 | L2 | Out-of-Band gegen Raten | nicht anwendbar | Kein Out-of-Band-Verfahren. |
| V6.8 | V6.8.1 | L2 | Keine Identität über einen anderen IdP | erfüllt | Verknüpfung über `(provider_id, subject)` (`oidc/models.py` `user_identity`, `oidc/accounts.py`); E-Mail nur, wenn der Anbieter für sie maßgeblich ist. `tests/test_oidc_admission.py`, `tests/test_oidc_flow.py`. |
| V6.8 | V6.8.2 | L2 | Signaturen immer prüfen | erfüllt | PyJWT mit dem JWKS des Anbieters, nie unsigniert (`oidc/id_token.py`). `tests/test_oidc_id_token.py::test_verify_id_token_refuses`. |
| V6.8 | V6.8.3 | L2 | SAML-Assertions einmalig | nicht anwendbar | Kein SAML. |
| V6.8 | V6.8.4 | L2 | Stärke der IdP-Anmeldung | erfüllt | Keine Funktion verlangt eine bestimmte Stärke; dokumentierte Annahme: eine OIDC-Anmeldung zählt wie ein Faktor (`acr`/`amr` werden nicht ausgewertet). Abschnitt „Anmeldung“. |

### V7 Session Management

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V7.1 | V7.1.1 | L2 | Zeitgrenzen dokumentiert | erfüllt | Abschnitt „Sitzungen“: 7 Tage absolut, keine Inaktivitätsgrenze (Lücke V7.3.1), Abweichung von NIST SP 800-63B begründet. |
| V7.1 | V7.1.2 | L2 | Gleichzeitige Sitzungen dokumentiert | erfüllt | Abschnitt „Sitzungen“: keine Höchstzahl, jedes Gerät eine Sitzung. |
| V7.1 | V7.1.3 | L2 | Föderierte Sitzungen dokumentiert | erfüllt | Abschnitt „Sitzungen“: die Sitzung der App ist von der des IdP unabhängig; kein Single Logout. |
| V7.2 | V7.2.1 | L1 | Prüfung im Backend | erfüllt | Jede Anfrage löst das Cookie in Postgres auf (`auth/service.resolve`). |
| V7.2 | V7.2.2 | L1 | Dynamische Token | erfüllt | Zufällige Referenztoken je Anmeldung (`core/security.new_session_token`). |
| V7.2 | V7.2.3 | L1 | 128 Bit aus CSPRNG | erfüllt | 256 Bit aus `secrets.token_urlsafe(32)`, nur SHA-256 gespeichert. `tests/test_auth.py::test_session_token_is_stored_hashed`. |
| V7.2 | V7.2.4 | L1 | Neues Token bei Anmeldung, altes endet | erfüllt | Jede Anmeldung (Passwort, OIDC) erzeugt ein neues Token und beendet das mitgebrachte (`auth/service.end_replaced`). `tests/test_cookie_security.py::test_signing_in_again_ends_the_session_it_replaces`, `test_an_oidc_sign_in_ends_the_session_it_replaces`. |
| V7.3 | V7.3.1 | L2 | Inaktivitätsgrenze | Lücke | Es gibt keine; eine Sitzung gilt bis zu ihrem Ablauf. J7, geplant M9b Task 18 (`HERD_SESSION_IDLE_HOURS`, Standard 24). |
| V7.3 | V7.3.2 | L2 | Absolute Höchstdauer | erfüllt | `HERD_SESSION_TTL_HOURS` (Standard 168), nie verlängert (`auth/service.open_session`). `tests/test_auth.py::test_expired_session_is_rejected`. |
| V7.4 | V7.4.1 | L1 | Abmelden beendet die Sitzung im Backend | erfüllt | `end_by_hash` setzt den Ablauf auf jetzt (`auth/repository.py`). `tests/test_auth.py::test_logout_invalidates_session`. Bewusste Ausnahme (Review M2 R2): eine bereits offene Live-Bearbeitung speichert ihre letzten Änderungen noch bis zu einer Stunde, lässt aber niemanden neu zu. |
| V7.4 | V7.4.2 | L1 | Deaktivieren beendet alle Sitzungen | erfüllt | `users/service.deactivate` löscht sie. `tests/test_users.py::test_deactivate_deletes_sessions_and_blocks_login`. |
| V7.4 | V7.4.3 | L2 | Andere Sitzungen enden nach Änderung eines Faktors | erfüllt | Passwortwechsel (eigener oder durch Admins) und das Lösen einer OIDC-Verknüpfung beenden alle anderen Sitzungen; das Löschen eines Anbieters beendet die Sitzungen aller mit ihm verknüpften Personen. `tests/test_profile.py`, `tests/test_oidc_admin.py::test_unlinking_an_identity_ends_the_persons_other_sessions`, `tests/test_oidc_provider_sessions.py`. |
| V7.4 | V7.4.4 | L2 | Abmelden überall erreichbar | erfüllt | Personenmenü in der Kopfleiste jeder angemeldeten Seite (`frontend/src/app/shell/UserMenu.tsx`). |
| V7.4 | V7.4.5 | L2 | Admins beenden Sitzungen | erfüllt | `POST /api/admin/users/{id}/sign-out` und Knopf „Abmelden“ in der Personenverwaltung (`users/service.sign_out`, `UsersPage.tsx`). `tests/test_users.py::test_an_administrator_signs_a_person_out_everywhere`, `AdminPages.test.tsx`. |
| V7.5 | V7.5.1 | L2 | Erneute Anmeldung vor sensiblen Änderungen | Lücke | E-Mail kann niemand selbst ändern, das Passwort nur mit dem alten. Aber eine neue OIDC-Verknüpfung (ein neuer Anmeldeweg) braucht nur die laufende Sitzung. J9, geplant M9b Task 18. |
| V7.5 | V7.5.2 | L2 | Eigene Sitzungen sehen und beenden | Lücke | Es gibt keine Liste der eigenen Sitzungen (nur „alle anderen enden“ beim Passwortwechsel). J8, geplant M9b Task 18. |
| V7.6 | V7.6.1 | L2 | Föderierte Lebensdauer wie dokumentiert | erfüllt | Abschnitt „Sitzungen“: höchstens `HERD_SESSION_TTL_HOURS` nach der IdP-Anmeldung, dann neu über den IdP. |
| V7.6 | V7.6.2 | L2 | Sitzung nur mit Zutun | erfüllt | Eine OIDC-Sitzung entsteht nur nach dem Klick auf den Anbieter und mit gebundenem Ablauf (`oidc/flow.py`, Bindungs-Cookie gegen Login-CSRF). `tests/test_oidc_flow.py`. |

### V8 Authorization

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V8.1 | V8.1.1 | L1 | Berechtigungsregeln dokumentiert | erfüllt | Spezifikation Abschnitt 5 (Rollen, Rechte, Bereiche), Rollentabellen in `docs/WIKI.md`, `docs/TICKETS.md`, `docs/AGENTEN.md`; im Code `core/permissions.py`, `core/access.py`. |
| V8.1 | V8.1.2 | L2 | Feldregeln dokumentiert | erfüllt | `CLAUDE.md` und Spezifikation: was je Rolle sichtbar ist (z. B. geschwärzte Laufergebnisse, persönliche Marke, `message.personal`, nie `password_hash`/Geheimnisse); Antwortschemas legen die Felder fest. |
| V8.2 | V8.2.1 | L1 | Funktionen nur mit Recht | erfüllt | `require`/`can` im Service; jede Admin-Route 403 ohne Recht. `tests/test_route_guards.py`, `tests/test_route_table.py`. |
| V8.2 | V8.2.2 | L1 | Daten nur mit Recht (IDOR) | erfüllt | Sichtbarkeit in SQL gefiltert (`core/access.py`, `ai/policy_filters.py`); Unsichtbares antwortet wie eine unbekannte ID. `tests/test_route_hiding.py`, `tests/test_hostile_cursors.py`. |
| V8.2 | V8.2.3 | L2 | Felder nur mit Recht | erfüllt | Antwortschemas ohne geheime Felder (`users/schemas.py`: nie `password_hash`; Geheimnisse nur als Art/Zustand), geschwärzte Läufe (`agents/run_view.py`). z. B. `tests/test_oauth_secrecy.py`, `tests/test_token_secrecy.py`. |
| V8.3 | V8.3.1 | L1 | Durchsetzung im Backend | erfüllt | Alle Entscheidungen in Services/SQL; das Frontend zeigt nur nach `permissions`/`my_role` (Regel 12). |
| V8.4 | V8.4.1 | L2 | Mandantentrennung | erfüllt | `org_id` an jeder Tabelle, jede Abfrage nach der Organisation des Akteurs. `tests/test_users.py::test_other_organisations_are_invisible`, `tests/test_mcp_other_org.py`. |

### V9 Self-contained Tokens

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V9.1 | V9.1.1 | L1 | Signatur vor dem Inhalt | erfüllt | Die einzigen selbsttragenden Token sind ID-Token; PyJWT prüft die Signatur, bevor ein Claim gelesen wird (`oidc/id_token.py`). `tests/test_oidc_id_token.py`. |
| V9.1 | V9.1.2 | L1 | Algorithmen-Allowlist | erfüllt | Nur RS256 und ES256, nie `none` oder HMAC. `tests/test_oidc_id_token.py::test_verify_id_token_refuses`. |
| V9.1 | V9.1.3 | L1 | Schlüssel nur aus vertrauter Quelle | erfüllt | Schlüssel nur aus dem JWKS des eingetragenen Anbieters (gespeichert, über `core/egress.py`); `jku`/`x5u`/`jwk` im Kopf werden nie benutzt (`oidc/keys.py`). `tests/test_oidc_google_and_keys.py`. |
| V9.2 | V9.2.1 | L1 | Gültigkeitszeitraum | erfüllt | `exp`, `iat`, `nbf` mit 60 s Spielraum. `tests/test_oidc_id_token.py::test_a_token_within_the_leeway_is_accepted`, `test_verify_id_token_refuses`. |
| V9.2 | V9.2.2 | L2 | Richtiger Tokentyp | erfüllt | Nur ID-Token beweisen eine Anmeldung; Zugangstoken von Konnektoren werden nur an ihren Ursprung weitergereicht, nie zur Anmeldung genutzt; eigene Token sind Referenztoken mit Präfix (`herd_pat_`, `herd_agt_`, `herd_cg_`). |
| V9.2 | V9.2.3 | L2 | Zielgruppe | erfüllt | `aud` muss die Client-ID enthalten, bei mehreren `azp` gleich ihr. `tests/test_oidc_id_token.py`. |
| V9.2 | V9.2.4 | L2 | Zielgruppe beim Ausstellen | nicht anwendbar | Die App stellt keine selbsttragenden Token aus. |

### V10 OAuth and OIDC

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V10.1 | V10.1.1 | L2 | Token nur dorthin, wo nötig | erfüllt | OAuth-Token der Konnektoren bleiben im Backend (`enc:`), Klartext nur in `connectors/credentials.headers_for` für ihren Ursprung (`connectors/moving.py`); der Browser sieht sie nie. `tests/test_oauth_secrecy.py`. |
| V10.1 | V10.1.2 | L2 | Werte nur aus eigenem Ablauf | erfüllt | OIDC: `state`, `nonce`, PKCE je 256 Bit, an den Browser gebunden (Bindungs-Cookie) und einmalig; OAuth der Konnektoren: `state` an die Sitzung gebunden (`oauth/flow.py`). `tests/test_oidc_flow.py`, `tests/test_oauth_flow.py`. |
| V10.2 | V10.2.1 | L2 | CSRF beim Code-Flow | erfüllt | PKCE S256 und `state` in beiden Clients. `tests/test_oidc_flow.py::test_the_authorization_request_carries_pkce_nonce_and_the_public_callback`. |
| V10.2 | V10.2.2 | L2 | Mix-up-Schutz | Lücke | OIDC ja (eigene Rückruf-URL je Anbieter, `iss` im ID-Token exakt). Der OAuth-Client der Konnektoren hat eine gemeinsame Rückruf-URL und prüft `iss` (RFC 9207) nicht. J13, geplant M9b Task 18. |
| V10.3 | V10.3.1 | L2 | Resource Server: Zielgruppe | erfüllt | `/mcp` nimmt nur eigene Referenztoken (`herd_pat_`/`herd_agt_`), gültig nur dort (`modules/tokens`). `tests/test_token_resolve.py`. |
| V10.3 | V10.3.2 | L2 | Resource Server: Entscheidung nach Claims | erfüllt | Bei jedem Aufruf: Rechte der Person, Bereiche des Tokens, KI-Richtlinie (`mcp_tools`, `tokens`). `tests/test_token_reach.py`, `tests/test_token_no_ai.py`. |
| V10.3 | V10.3.3 | L2 | Resource Server: Person eindeutig | erfüllt | Das Token verweist auf genau eine Person oder einen Agenten (`tokens/models.py`). |
| V10.3 | V10.3.4 | L2 | Resource Server: Stärke | nicht anwendbar | Keine Funktion verlangt eine bestimmte Anmeldestärke. |
| V10.4 | V10.4.1 | L1 | AS: Redirect-URIs | nicht anwendbar | Die App ist kein Autorisierungsserver (Zugangstoken entstehen in der Oberfläche, nicht über OAuth). |
| V10.4 | V10.4.2 | L1 | AS: Code einmalig | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.3 | L1 | AS: Code kurzlebig | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.4 | L1 | AS: nur nötige Grants | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.5 | L1 | AS: Refresh-Token-Replay | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.6 | L2 | AS: PKCE verlangen | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.7 | L2 | AS: dynamische Registrierung | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.8 | L2 | AS: Refresh-Token-Ablauf | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.9 | L2 | AS: Widerruf durch Nutzer | nicht anwendbar | Kein Autorisierungsserver. (Eigene Zugangstoken widerrufen Personen und Admins in der Oberfläche: `tests/test_token_api.py`, `tests/test_token_admin.py`.) |
| V10.4 | V10.4.10 | L2 | AS: Client-Authentifizierung | nicht anwendbar | Kein Autorisierungsserver. |
| V10.4 | V10.4.11 | L2 | AS: nur nötige Scopes | nicht anwendbar | Kein Autorisierungsserver. |
| V10.5 | V10.5.1 | L2 | OIDC: Replay des ID-Tokens | erfüllt | `nonce` aus dem eigenen Ablauf muss passen; der Ablauf ist einmalig (`oidc/flow.py`, `oidc/id_token.py`). `tests/test_oidc_id_token.py`, `tests/test_oidc_flow.py`. |
| V10.5 | V10.5.2 | L2 | OIDC: Person über `sub` | erfüllt | `user_identity (provider_id, subject)`. `tests/test_oidc_flow.py::test_a_trusted_email_links_and_the_next_sign_in_finds_the_subject`. |
| V10.5 | V10.5.3 | L2 | OIDC: Issuer der Metadaten exakt | erfüllt | Discovery wird abgelehnt, wenn `issuer` nicht exakt dem eingetragenen entspricht (`oidc.issuer_mismatch`, `oidc/keys.py`). `tests/test_oidc_google_and_keys.py`. |
| V10.5 | V10.5.4 | L2 | OIDC: `aud` = Client-ID | erfüllt | Wie V9.2.3. |
| V10.5 | V10.5.5 | L2 | OIDC: Back-Channel-Logout | nicht anwendbar | Nicht angeboten. |
| V10.6 | V10.6.1 | L2 | OP: Response-Modes | nicht anwendbar | Die App ist kein OpenID Provider. |
| V10.6 | V10.6.2 | L2 | OP: erzwungenes Abmelden | nicht anwendbar | Kein OpenID Provider. |
| V10.7 | V10.7.1 | L2 | AS: Zustimmung | nicht anwendbar | Kein Autorisierungsserver. |
| V10.7 | V10.7.2 | L2 | AS: Inhalt der Zustimmung | nicht anwendbar | Kein Autorisierungsserver. |
| V10.7 | V10.7.3 | L2 | AS: Zustimmungen verwalten | nicht anwendbar | Kein Autorisierungsserver. |

### V11 Cryptography

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V11.1 | V11.1.1 | L2 | Schlüsselverwaltung dokumentiert | erfüllt | Abschnitt „Kryptografie“ (Lebenszyklus von `HERD_SECRET_KEY`, Rotation mit `scripts/rotate_secrets.py`, Schlüsselkennung im Sicherungsmanifest); `docs/KI.md`, `docs/SICHERUNG.md`. |
| V11.1 | V11.1.2 | L2 | Krypto-Inventar | erfüllt | Abschnitt „Kryptografie“. |
| V11.2 | V11.2.1 | L2 | Erprobte Implementierungen | erfüllt | `cryptography` (Fernet, HKDF), `argon2-cffi`, `hashlib`, `secrets`, PyJWT mit `cryptography`; kein eigener Algorithmus. |
| V11.2 | V11.2.2 | L2 | Krypto-Agilität | erfüllt | `enc:`-Werte lassen sich unter neuem Schlüssel neu verschlüsseln (`scripts/rotate_secrets.py`, `tests/test_secrets.py::test_rotation_reencrypts_under_the_new_key`); argon2-Hashes tragen ihre Parameter und werden bei neuen Parametern beim Login ersetzt (`tests/test_auth.py::test_a_login_rehashes_a_password_stored_with_old_parameters`). |
| V11.2 | V11.2.3 | L2 | Mindestens 128 Bit Sicherheit | erfüllt | Eigene Primitive: AES-128 + HMAC-SHA256, SHA-256, 256-Bit-Token, argon2id. Die Signaturschlüssel der IdP wählt der Anbieter (Google: RSA-2048, rund 112 Bit); die App nimmt nur RS256/ES256 an. |
| V11.3 | V11.3.1 | L1 | Keine unsicheren Modi | erfüllt | Fernet (AES-CBC mit zufälligem IV, Encrypt-then-MAC); kein ECB, kein RSA-Padding. |
| V11.3 | V11.3.2 | L1 | Nur zugelassene Verfahren | erfüllt | AES (Fernet) für gespeicherte Geheimnisse; TLS über die Standardbibliotheken. |
| V11.3 | V11.3.3 | L2 | Schutz gegen Veränderung | erfüllt | Fernet authentifiziert (HMAC-SHA256); ein veränderter Wert entschlüsselt nicht. `tests/test_secrets.py::test_a_wrong_key_does_not_decrypt`. |
| V11.4 | V11.4.1 | L1 | Nur zugelassene Hashfunktionen | erfüllt | SHA-256 (Token, Prüfsummen, Fingerabdrücke), HMAC-SHA256, HKDF-SHA256; kein MD5/SHA-1. |
| V11.4 | V11.4.2 | L2 | Passwort-Hashing | erfüllt | argon2id mit den Standardparametern der Bibliothek (RFC 9106: 64 MiB, t=3, p=4) (`core/security.py`). |
| V11.4 | V11.4.3 | L2 | Kollisionsresistente Hashes | erfüllt | SHA-256 (256 Bit) für Integrität (Archive, Anhänge, Fingerabdrücke). |
| V11.4 | V11.4.4 | L2 | Schlüssel aus Passwörtern | nicht anwendbar | Kein Schlüssel wird aus einem Passwort abgeleitet: `HERD_SECRET_KEY` ist ein zufälliger Wert (mindestens 32 Zeichen, `openssl rand -hex 32`), daraus HKDF. |
| V11.5 | V11.5.1 | L2 | Zufall mit 128 Bit | erfüllt | Token, `state`, `nonce`, Verifier, Bindungen: `secrets.token_urlsafe(32)`; UUIDs sind nur Kennungen, nie Geheimnisse. |
| V11.6 | V11.6.1 | L2 | Public-Key-Verfahren | erfüllt | Nur Prüfen von RS256/ES256-Signaturen (PyJWT/`cryptography`); die App erzeugt keine Schlüsselpaare. |

### V12 Secure Communication

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V12.1 | V12.1.1 | L1 | TLS 1.2/1.3 | nicht anwendbar | TLS endet am Ingress bzw. Reverse Proxy, liegt beim Betrieb (Betriebsvoraussetzung B1). |
| V12.1 | V12.1.2 | L2 | Empfohlene Cipher Suites | nicht anwendbar | Wie V12.1.1, liegt beim Betrieb (B1). |
| V12.1 | V12.1.3 | L2 | mTLS-Clientzertifikate | nicht anwendbar | Keine Anmeldung mit Clientzertifikaten. |
| V12.2 | V12.2.1 | L1 | TLS zu allen externen Diensten | nicht anwendbar | Wie V12.1.1, liegt beim Betrieb (B1). Die App setzt HSTS und verlangt für OIDC eine https-Adresse. |
| V12.2 | V12.2.2 | L1 | Öffentlich vertraute Zertifikate | nicht anwendbar | Wie V12.1.1, liegt beim Betrieb (B1). |
| V12.3 | V12.3.1 | L2 | Verschlüsselt zu Datenbank und Diensten | Lücke | Ausgehende Aufrufe der App (KI, MCP, OIDC, OAuth, restic) nur über https; die Datenbankverbindung nutzt TLS nur, wenn der Betrieb es in der URL verlangt (Standard: ohne). J12 (a), geplant M9b Task 18 (`sslmode` und CA). |
| V12.3 | V12.3.2 | L2 | TLS-Clients prüfen Zertifikate | erfüllt | httpx mit Zertifikatsprüfung, auch bei gepinnter Adresse (`core/egress.py`). `tests/test_egress.py::test_tls_to_a_pinned_address_still_verifies_the_name`. |
| V12.3 | V12.3.3 | L2 | TLS zwischen internen HTTP-Diensten | Lücke | API ↔ Collab-Prozess (WebSocket und interne API, Port 9090) laufen im Cluster unverschlüsselt; geschützt nur durch NetworkPolicy und das interne Token. J12 (b): Abweichung, Betriebsvoraussetzung Mesh mit mTLS oder NetworkPolicy. |
| V12.3 | V12.3.4 | L2 | Vertraute Zertifikate intern | Lücke | Folgt aus V12.3.3. J12 (b): Abweichung. |

### V13 Configuration

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V13.1 | V13.1.1 | L2 | Kommunikation dokumentiert | erfüllt | Abschnitt „Verbindungen“. |
| V13.2 | V13.2.1 | L2 | Dienste untereinander authentifiziert | Lücke | Collab → API trägt je Aufruf eine kurzlebige Berechtigung, zusätzlich aber das statische, geteilte `HERD_INTERNAL_TOKEN` (keine Rotation ohne Ausfall). Datenbank: eigenes Dienstkonto mit Passwort. J12 (c), geplant M9b Task 18 (zwei gültige Token zum Rotieren). |
| V13.2 | V13.2.2 | L2 | Geringste Rechte der Dienstkonten | Lücke | Container laufen ohne root (uid 10001); aber App und Migration nutzen dieselbe Datenbankrolle, die das Schema besitzt. J14, geplant M9b Task 18 (Migrations- und Laufzeitrolle als Option). |
| V13.2 | V13.2.3 | L2 | Keine Standard-Zugangsdaten | erfüllt | Compose verlangt `POSTGRES_PASSWORD` und das Bootstrap-Passwort ohne Standardwert (`deploy/compose/compose.yml`); `HERD_INTERNAL_TOKEN` mindestens 32 Zeichen (`tests/test_config.py`). |
| V13.2 | V13.2.4 | L2 | Allowlist für Ziele nach außen | erfüllt | Nach außen nur zu Zielen, die Admins eintragen (KI-Verbindungen, MCP-Server, OIDC-Anbieter, OAuth-Clients) und nur an öffentliche Adressen (private nur per Allowlist): `core/egress.py`, `core/egress_allowance.py`; im Chart zusätzlich NetworkPolicy-Egress. |
| V13.2 | V13.2.5 | L2 | Server mit Allowlist | erfüllt | Wie V13.2.4; Dateien nur unter `HERD_DATA_DIR`, SPA nur aus `HERD_STATIC_DIR`. |
| V13.3 | V13.3.1 | L2 | Geheimnisverwaltung | erfüllt | Geheimnisse aus der Umgebung bzw. Kubernetes-Secrets (`existingSecret`, `HERD_DATABASE_PASSWORD_FILE`), gespeicherte als `enc:` unter `HERD_SECRET_KEY`; nichts im Code oder Image (`.dockerignore`). `tests/test_secrets.py`, `tests/test_config.py`. |
| V13.3 | V13.3.2 | L2 | Geringste Rechte für Geheimnisse | erfüllt | `env:`-Verweise nur auf `HERD_AI_*`/`HERD_OIDC_*`, ohne die eigenen Einstellungen (`core/secrets.py`); der Collab-Prozess bekommt nur das interne Token, restic nur seine eigene Umgebung (`app/ops`). `tests/test_secrets.py::test_env_references_are_limited_to_the_ai_prefix`. |
| V13.4 | V13.4.1 | L1 | Keine Versionsverwaltungsdaten | erfüllt | Das Image enthält nur freigegebene Pfade (`.dockerignore` mit `*` und Ausnahmen), kein `.git`. |
| V13.4 | V13.4.2 | L2 | Kein Debug-Modus | erfüllt | FastAPI ohne `debug`, keine Swagger UI in Produktion (`web/public.py`, `tests/test_errors.py::test_swagger_ui_is_not_served_in_production`), Fehler ohne Stacktrace (V16.5.1). |
| V13.4 | V13.4.3 | L2 | Keine Verzeichnislisten | erfüllt | Die SPA liefert nur Dateien aus, sonst `index.html` (`web/spa.py`, `tests/test_spa.py`). |
| V13.4 | V13.4.4 | L2 | Kein TRACE | erfüllt | TRACE antwortet 404/405 und spiegelt nichts. `tests/test_spa.py::test_trace_is_not_supported`. |
| V13.4 | V13.4.5 | L2 | Doku und Überwachung nicht offen | erfüllt | `/metrics` und Proben nur auf dem internen Port 9090 (`web/internal.py`); Swagger UI nicht in Produktion. `/api/openapi.json` bleibt bewusst öffentlich (beschreibt nur die Schnittstelle, keine Daten). |

### V14 Data Protection

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V14.1 | V14.1.1 | L2 | Daten klassifiziert | erfüllt | Abschnitt „Datenklassen“. |
| V14.1 | V14.1.2 | L2 | Schutzanforderungen je Klasse | erfüllt | Abschnitt „Datenklassen“. |
| V14.2 | V14.2.1 | L1 | Keine sensiblen Daten in URLs | erfüllt | Token nur in Cookies bzw. `Authorization`; Geheimnisse nie in URLs (Regel 10). Ausnahme nach Protokoll: `code`/`state` der OAuth/OIDC-Rückrufe, einmalig und kurzlebig; deren Pfade sind vom Tracing ausgenommen. |
| V14.2 | V14.2.2 | L2 | Kein Zwischenspeichern in Servern | erfüllt | `Cache-Control: no-store` auf allen Antworten unter `/api` und `/mcp`; Downloads `private, no-cache`. `tests/test_security_headers.py::test_api_answers_are_not_stored_by_browsers`. |
| V14.2 | V14.2.3 | L2 | Keine Daten an Dritte | erfüllt | Keine Tracker, keine Anfragen an Dritte aus dem Browser (`default-src 'self'`); Daten an KI-Anbieter nur nach Richtlinie und Zuordnung (`ai/policy.py`). |
| V14.2 | V14.2.4 | L2 | Schutz nach Klasse umgesetzt | erfüllt | Aufbewahrungskatalog (`core/retention.py`, `tests/test_retention.py`), Protokollregeln (V16.2.5), Verschlüsselung der Geheimnisse (V11). |
| V14.3 | V14.3.1 | L1 | Clientdaten beim Abmelden löschen | erfüllt | Beim Abmelden leert das Frontend den Query-Cache, auch ohne Server (`features/auth/queries.ts` `useLogout`, `onSettled`). |
| V14.3 | V14.3.2 | L2 | Anti-Caching-Kopfzeilen | erfüllt | Wie V14.2.2. |
| V14.3 | V14.3.3 | L2 | Nichts Sensibles im Browserspeicher | erfüllt | `localStorage` hält nur die Sprache (`frontend/src/lib/i18n.ts`); keine Inhalte, keine Token. |

### V15 Secure Coding and Architecture

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V15.1 | V15.1.1 | L1 | Fristen für verwundbare Komponenten | erfüllt | Abschnitt „Abhängigkeiten“. |
| V15.1 | V15.1.2 | L2 | Inventar der Komponenten (SBOM) | erfüllt | Gesperrte Abhängigkeiten mit Hashes (`backend/uv.lock`, `package-lock.json` der drei Pakete) aus PyPI/npm, Lizenzprüfung `backend/scripts/check_licenses.py`; Trivy prüft das Image. |
| V15.1 | V15.1.3 | L2 | Teure Funktionen dokumentiert | erfüllt | `docs/STECKBRIEF.md` „Funktionen mit Laufzeit und Kosten“, Abschnitt „Eingaben und Grenzen“. |
| V15.2 | V15.2.1 | L1 | Komponenten innerhalb der Fristen | erfüllt | Stand 2026-11-15: `pip-audit` (Laufzeitabhängigkeiten) und `npm audit --audit-level=high` (frontend, collab, e2e) ohne Befund; in der CI bei jedem Lauf (die CI startet derzeit kontoseitig keine Jobs). |
| V15.2 | V15.2.2 | L2 | Schutz der Verfügbarkeit | erfüllt | Zeit- und Größengrenzen, Hash-Warteschlange (429 `server.busy`), Budgets, Worker-Zeitgrenzen, Leases (`core/security.py`, `core/uploads.py`, `app/worker/`). `tests/test_hashing_pool.py`, `tests/test_body_limit.py`. |
| V15.2 | V15.2.3 | L2 | Keine Test- oder Entwicklungsfunktionen | erfüllt | Testrouten nur mit `HERD_ENVIRONMENT=test` (`web/public.py`), Tests und e2e-Uhr nicht im Image (`.dockerignore`). |
| V15.3 | V15.3.1 | L1 | Nur nötige Felder | erfüllt | `response_model`-Schemas je Route (V8.2.3). |
| V15.3 | V15.3.2 | L2 | Weiterleitungen nicht folgen | erfüllt | Ausgehende Clients folgen keinen Weiterleitungen (`core/egress.py`). `tests/test_egress.py::test_redirects_are_not_followed`. |
| V15.3 | V15.3.3 | L2 | Mass Assignment | erfüllt | Eigene Eingabeschemas je Aktion, Änderungen mit `extra="forbid"` (`users/schemas.py` u. a.); Services setzen Felder einzeln. |
| V15.3 | V15.3.4 | L2 | Echte Client-Adresse | erfüllt | Wie V4.1.3; Ratenbegrenzung zählt IPv6 je /64 (`core/ratelimit.limit_key`). `tests/test_login_limits.py`. |
| V15.3 | V15.3.5 | L2 | Typen streng | erfüllt | Pydantic, `mypy --strict`, TypeScript strict; keine losen Vergleiche. |
| V15.3 | V15.3.6 | L2 | Prototype Pollution | erfüllt | Kein Zusammenführen fremder Objekte (kein Deep-Merge, `Object.assign` nur mit eigenen Objekten); Eingaben werden mit zod/TypeScript-Typen gelesen. |
| V15.3 | V15.3.7 | L2 | Parameter Pollution | erfüllt | FastAPI trennt Quellen (Pfad, Query, Body, Kopf, Cookie) je Parameter ausdrücklich. |

### V16 Security Logging and Error Handling

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V16.1 | V16.1.1 | L2 | Protokoll-Inventar | erfüllt | Abschnitt „Protokolle“. |
| V16.2 | V16.2.1 | L2 | Wann, wo, wer, was | erfüllt | JSON-Zeilen mit Zeit, `service`, `logger`, `trace_id`, Route, Status, Akteur (`core/logging.py`, `core/request_log.py`). `tests/test_logging.py::test_request_line_is_json_with_required_fields`. |
| V16.2 | V16.2.2 | L2 | UTC | erfüllt | Zeitstempel in UTC mit Offset (`core/logging.py`). |
| V16.2 | V16.2.3 | L2 | Nur dokumentierte Ziele | erfüllt | Nur stdout (und optional OTLP-Traces); Abschnitt „Protokolle“. |
| V16.2 | V16.2.4 | L2 | Gemeinsames Format | erfüllt | Eine JSON-Zeile je Ereignis (`HERD_LOG_FORMAT=json`, Standard). |
| V16.2 | V16.2.5 | L2 | Sensibles nach Klasse protokollieren | erfüllt | Nie Kopfzeilenwerte, Cookies, Passwörter, Körper, Inhalte, Token (Regeln 9, 10). `tests/test_logging.py::test_secrets_never_reach_logs`, `tests/test_auth.py::test_password_is_never_logged`, `tests/test_auth_log.py`. |
| V16.3 | V16.3.1 | L2 | Anmeldungen protokolliert | erfüllt | `auth.sign_in` (Weg, Ergebnis, Adresse, Person bei Erfolg) und `auth.sign_out` (`auth/sign_in_log.py`). `tests/test_auth_log.py`. |
| V16.3 | V16.3.2 | L2 | Fehlgeschlagene Berechtigungen protokolliert | erfüllt | Jede Anfrage hat eine Zeile `http.request` mit Status (401/403/404) und Akteur (`core/request_log.py`). `tests/test_auth.py::test_resolved_user_is_bound_to_log_lines`. |
| V16.3 | V16.3.3 | L2 | Sicherheitsereignisse und Umgehungsversuche | erfüllt | CSRF (403), Prüffehler (422), Ratenbegrenzung (429), Anmeldeversuche (`auth.sign_in`), OIDC-Ausgänge (Metrik und Zeile), Admin-Einsichten im Audit. |
| V16.3 | V16.3.4 | L2 | Unerwartete Fehler | erfüllt | `UnhandledErrorMiddleware` protokolliert jede Ausnahme einmal (ohne Daten, `core/errors.py`); Fehler nach außen als Codes (z. B. `oidc.provider_unreachable`, `HerdOidcFailing`). `tests/test_logging.py::test_unhandled_error_is_logged_and_agrees_with_error_body`. |
| V16.4 | V16.4.1 | L2 | Log-Injektion | erfüllt | JSON-Kodierung jeder Zeile (Zeilenumbrüche und Steuerzeichen maskiert). |
| V16.4 | V16.4.2 | L2 | Protokolle geschützt | nicht anwendbar | Die App schreibt nur nach stdout und kann Protokolle weder lesen noch ändern; Schutz und Unveränderlichkeit liegt beim Betrieb (B3). |
| V16.4 | V16.4.3 | L2 | Protokolle in getrenntem System | nicht anwendbar | Wie V16.4.2, liegt beim Betrieb (B3). |
| V16.5 | V16.5.1 | L2 | Allgemeine Fehlermeldung | erfüllt | Einheitliche Fehlerform ohne Stacktrace; 422 nennt nur die Felder der API, nie gesendete Werte oder Schlüssel (`core/validation_message.py`). `tests/test_errors.py::test_error_bodies_never_echo_input`, `test_unhandled_exception_is_500_with_generic_message`. |
| V16.5 | V16.5.2 | L2 | Sicher weiter bei Ausfällen | erfüllt | Zeitgrenzen und Codes für Anbieter (KI, MCP, OIDC); ein ausgefallener Anbieter beendet einen Lauf mit Code, nicht die App; Live-Hub verwirft bei Rückstau. |
| V16.5 | V16.5.3 | L2 | Fail closed | erfüllt | Ausnahme → Rollback der Transaktion und 500; Prüfungen vor der Wirkung (Rechte, Richtlinie, Budget vor jedem Modellaufruf). |

### V17 WebRTC

| Kapitel | Nummer | Stufe | Thema | Status | Beleg |
|---|---|---|---|---|---|
| V17.1 | V17.1.1 | L2 | TURN | nicht anwendbar | Kein WebRTC. |
| V17.2 | V17.2.1 | L2 | DTLS-Schlüssel | nicht anwendbar | Kein WebRTC. |
| V17.2 | V17.2.2 | L2 | DTLS-Suites | nicht anwendbar | Kein WebRTC. |
| V17.2 | V17.2.3 | L2 | SRTP | nicht anwendbar | Kein WebRTC. |
| V17.2 | V17.2.4 | L2 | Fehlerhafte SRTP-Pakete | nicht anwendbar | Kein WebRTC. |
| V17.3 | V17.3.1 | L2 | Signalisierung unter Last | nicht anwendbar | Kein WebRTC. |
| V17.3 | V17.3.2 | L2 | Fehlerhafte Signalisierung | nicht anwendbar | Kein WebRTC. |
