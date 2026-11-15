# Anmeldung: Passwort und OIDC (Google und andere)

Stand M9 (Task 4 und 5). Neben der Anmeldung mit E-Mail und Passwort kann sich eine
Person über einen OpenID-Connect-Anbieter (OIDC) anmelden: Google als fertige Vorlage,
jeder andere Anbieter mit Discovery (Keycloak, Entra ID, Authentik …) als „allgemein“.
Optional legen sich Personen aus erlaubten Domains dabei selbst ein Konto an.

## Voraussetzungen (Betrieb)

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `HERD_PUBLIC_URL` | leer | Pflicht für OIDC: die Rückruf-Adresse ist `HERD_PUBLIC_URL` + `/api/auth/oidc/<Schlüssel>/callback`. Ohne sie (oder mit `http` außer `localhost`) lässt sich kein Anbieter einschalten (`oidc.public_url_missing`). |
| `HERD_OIDC_ALLOWED_HOSTS` | leer | Private Hosts oder Netze (CIDR, kommagetrennt), auf denen ein Anbieter laufen darf (ein Keycloak im Firmennetz). Leer: nur öffentliche Adressen. Google braucht hier nichts. |
| `HERD_OIDC_RATE_PER_MINUTE` | 30 | Starts und Rückrufe je Client-Adresse und Minute, gezählt in PostgreSQL über alle API-Knoten. |
| `HERD_OIDC_<NAME>` | – | Client-Secrets, die ein Anbieter als `env:HERD_OIDC_<NAME>` nennt. Alternativ speichert die Verwaltung das Secret verschlüsselt (`enc:`, braucht `HERD_SECRET_KEY`). |

Compose: beide Einstellungen stehen in `compose.yml` und `compose.nodes.yml`; Secrets
`HERD_OIDC_<NAME>` gehören in `ai.env` (siehe `ai.env.example`). Helm: `oidc.allowedHosts`,
`oidc.ratePerMinute`, `oidc.existingSecret` (ein Secret mit `HERD_OIDC_<NAME>` für die
API-Pods); mit `networkPolicy.enabled` muss `oidc.egress` den API-Pods den Weg
zum Anbieter erlauben (Google: `accounts.google.com`, `oauth2.googleapis.com`,
`www.googleapis.com`, Port 443; NetworkPolicy kennt keine Hostnamen, also deren
Adressbereiche oder öffentliche Adressen auf 443, siehe `ci/production-values.yaml`).
Die Regeln gelten nur für die API-Pods; `networkPolicy.aiEgress` deckt OIDC nicht ab,
weil OIDC nie über `HERD_AI_EGRESS_PROXY` geht. Ohne `oidc.egress` meldet „Prüfen“
`provider_unreachable`.

Alle Aufrufe zum Anbieter (Discovery, Token-Endpunkt, JWKS) gehen durch die
Egress-Sperre (`core/egress.py`): nur https, keine Weiterleitungen, kein Proxy aus der
Umgebung, private Adressen nur aus `HERD_OIDC_ALLOWED_HOSTS`, Link-local- und
Metadaten-Adressen nie. `HERD_AI_EGRESS_PROXY` gilt für OIDC nicht.

## Google einrichten

1. In der Google Cloud Console ein Projekt wählen, den OAuth-Zustimmungsbildschirm
   einrichten (für eine Workspace-Organisation „Intern“) und unter „Anmeldedaten“ eine
   **OAuth-Client-ID** vom Typ **Webanwendung** anlegen.
2. In to-herd-cats-ai unter **Verwaltung → Anmeldung → Google hinzufügen** Client-ID
   und Client-Secret aus Google eintragen (oder das Secret als Umgebungsvariable
   `HERD_OIDC_…` nennen), optional Selbstregistrierung und Domains setzen, ohne
   „Eingeschaltet“ speichern.
3. Die **Rückruf-Adresse** auf der Karte des Anbieters (auch im Dialog **Bearbeiten**)
   kopieren und in Google beim Client als „Autorisierte Weiterleitungs-URI“ eintragen.
4. **Prüfen** (Discovery und Schlüssel werden geholt), dann **Einschalten**: der Knopf
   „Mit Google anmelden“ erscheint auf der Anmeldeseite.

Die Schritte in der Google Cloud Console sind hier nicht nachgeprüft (kein Zugang aus
der Bauumgebung); die Bezeichnungen können abweichen.

Die Vorlage legt fest (nicht änderbar):

- Issuer `https://accounts.google.com`; als `iss` im ID-Token gilt auch
  `accounts.google.com` (ältere Integrationen).
- Scopes `openid email profile`.
- Anfrage mit `prompt=select_account`; wenn genau eine Domain (nicht `gmail.com`)
  erlaubt ist, zusätzlich `hd=<Domain>` – das ist nur eine Vorauswahl, entschieden
  wird über den `hd`-Claim im ID-Token.
- Google ist für eine Adresse maßgeblich, wenn sie auf `@gmail.com` endet oder der
  `hd`-Claim gleich ihrer Domain ist.

**Geprüft am 15.11.2026** gegen Googles OpenID-Connect-Referenz
(<https://developers.google.com/identity/openid-connect/reference>) und das
Discovery-Dokument (<https://accounts.google.com/.well-known/openid-configuration>):
beide Issuer-Formen, `hd` (Workspace-/Cloud-Organisation, „muss geprüft werden“, wenn
der Zugang auf Domains beschränkt wird), `email_verified`, die Scopes, `prompt=select_account`,
der `hd`-Parameter als Vereinfachung der Auswahl, RS256 als Signaturalgorithmus,
`sub` als Schlüssel des Kontos statt der E-Mail. **Nicht geprüft:** eine echte
Anmeldung gegen Google (die Tests laufen gegen den Stub `tests/support/oidc_stub.py`).

## Allgemeiner Anbieter

Schlüssel (in der URL, `a-z0-9-`), Name (auf dem Knopf), Issuer (https; das
Discovery-Dokument unter `<Issuer>/.well-known/openid-configuration` muss genau
diesen Issuer nennen), Client-ID, optional Client-Secret (ohne: öffentlicher Client,
nur PKCE), Scopes (mit `openid`). Der Client meldet sich am Token-Endpunkt mit HTTP
Basic an. **E-Mail vertrauen** (`trust_email`, Standard aus): nur einschalten, wenn
der Anbieter für jede bestätigte Adresse, die er meldet, maßgeblich ist (eigenes
Firmenverzeichnis); dann verknüpft die erste Anmeldung ein bestehendes Konto mit
derselben Adresse.

## Wie eine Anmeldung entschieden wird

1. Ist das Konto beim Anbieter (`sub`) schon verknüpft, meldet es seine Person an
   (deaktiviert: `oidc.account_inactive`).
2. Sonst muss die E-Mail vorhanden und bestätigt sein (`email_verified`), sonst
   `oidc.email_unverified`.
3. Gibt es ein aktives Konto mit dieser E-Mail, wird es nur verknüpft, wenn der
   Anbieter für die Adresse maßgeblich ist (Google wie oben, ein allgemeiner nur mit
   „E-Mail vertrauen“). Sonst `oidc.link_refused`: erst mit Passwort anmelden und im
   Profil unter **Verknüpfte Konten** verknüpfen.
4. Ohne Konto: Selbstregistrierung, wenn der Anbieter sie erlaubt **und** Domains
   nennt (`oidc.signup_closed` sonst). Die Domain der bestätigten E-Mail muss genau
   gelistet sein (klein geschrieben, ohne Subdomains, ohne Punkt am Ende); bei Google
   muss außerdem `hd` gleich dieser Domain sein (für `gmail.com` nur, wenn
   ausdrücklich gelistet). Sonst `oidc.domain_not_allowed`.

Ein selbst registriertes Konto ist `member`, aktiv, ohne Passwort, Sprache Deutsch,
hat seinen persönlichen Bereich und sieht die offenen Bereiche. Es bekommt eine eigene
KI-Zuordnung **„keine KI“** (Frage J2: Kosten und Datenabfluss erst nach Entscheidung
eines Admins; zu ändern an einer Stelle, `SIGNUP_GETS_NO_AI` in
`backend/app/modules/oidc/admission.py`). Ein Admin gibt KI in der KI-Verwaltung frei
(Zuordnung der Person entfernen oder setzen). Audit: `user.self_registered`.

## Verknüpfen und lösen

- **Profil → Verknüpfte Konten**: eigene Verknüpfungen sehen, eine neue anlegen
  (Weiterleitung zum Anbieter, danach zurück ins Profil) und lösen. Die E-Mail beim
  Anbieter muss dafür nicht passen; ein Konto, das schon mit einer anderen Person
  verknüpft ist, wird abgelehnt (`oidc.identity_taken`).
- **Verwaltung → Personen → Bearbeiten**: mit `user.manage` die Verknüpfungen jeder
  Person sehen und lösen (die eines Owners nur als Owner).
- Ein Konto ohne Passwort behält seine letzte Verknüpfung (409 `oidc.last_identity`).
- Eine Verknüpfung zu lösen beendet alle anderen Sitzungen der Person (auch eine, die
  über diesen Anbieter begann); wer die eigene löst, bleibt in der laufenden Sitzung
  angemeldet, löst ein Admin sie, endet jede Sitzung der Person.
- Audit: `user.identity_linked` (Anbieter, `via` `email` oder `profile`),
  `user.identity_unlinked`; Anbieter: `oidc_provider.created|updated|deleted`. Nie
  das Subjekt, die E-Mail oder ein Secret.
- Einen Anbieter zu löschen löst alle seine Verknüpfungen.

## Sicherheit des Ablaufs

Autorisierungscode mit PKCE (S256), `state` und `nonce` (je 256 Bit; gespeichert nur
der SHA-256 von `state`), 10 Minuten gültig, einmal verwendbar. Der Ablauf ist an den
Browser gebunden: das Cookie `__Host-herd_oidc` (über https: Secure, HttpOnly,
SameSite=Lax, Pfad `/`, ohne Domain; über http zum Ausprobieren `herd_oidc` mit Pfad
`/api/auth/oidc`) trägt einen Wert, dessen Hash am Ablauf steht; ein Rückruf aus einem
anderen Browser findet keinen Ablauf (`oidc.flow_invalid`, gegen Login-CSRF). Das
ID-Token wird mit PyJWT geprüft: nur RS256/ES256 (nie `none` oder HMAC), Schlüssel aus
dem JWKS des Anbieters (gespeichert; eine unbekannte `kid` holt es höchstens einmal je
Minute neu), `iss` exakt, `aud` enthält die Client-ID, `azp` bei mehreren Zielgruppen,
`exp`/`iat`/`nbf` mit 60 s Spielraum, `nonce`. Kein Userinfo-Aufruf. Nach einer
Wiederherstellung sind alle offenen Abläufe gelöscht.

Logs nennen nur den Schlüssel des Anbieters und feste Gründe, nie E-Mail, Name,
Subjekt, Code, `state` oder Tokens; der Rückruf hat keinen Trace-Span (seine Query trägt
Einmalwerte).

## Fehlercodes

Auf der Anmeldeseite (`/login?error=<code>`) bzw. im Profil (`/profile?link_error=<code>`):

| Code | Bedeutung |
|---|---|
| `oidc.link_refused` | Es gibt ein Konto mit dieser E-Mail, der Anbieter ist für sie nicht maßgeblich. Mit Passwort anmelden, im Profil verknüpfen. |
| `oidc.signup_closed` | Kein Konto, Selbstregistrierung aus. |
| `oidc.domain_not_allowed` | Die Domain ist nicht freigegeben (bei Google: oder `hd` passt nicht). |
| `oidc.email_unverified` | Der Anbieter meldet keine bestätigte E-Mail. |
| `oidc.account_inactive` | Das Konto ist deaktiviert. |
| `oidc.identity_taken` | Das Konto beim Anbieter gehört schon einer anderen Person. |
| `oidc.flow_invalid` | Abgelaufen, schon benutzt, aus einem anderen Browser oder für einen anderen Anbieter. |
| `oidc.denied` | Beim Anbieter abgebrochen. |
| `oidc.not_found` / `oidc.unavailable` | Anbieter unbekannt oder ausgeschaltet. |
| `oidc.rate_limited` | Zu viele Versuche von dieser Adresse. |
| `oidc.provider_unreachable` | Anbieter nicht erreichbar (Egress-Sperre, Netz, Zeitüberschreitung). |
| `oidc.provider_error`, `oidc.issuer_mismatch`, `oidc.id_token_invalid` | Antwort des Anbieters unbrauchbar bzw. ID-Token ungültig. |
| `oidc.public_url_missing` | `HERD_PUBLIC_URL` fehlt (Verwaltung). |

## Überwachung

Metrik `herd_oidc_logins_total{outcome}` (API): je Rückruf und je gescheitertem Start ein fester Ausgang (`login`,
`link`, `signup`, `profile_link` oder der Code ohne `oidc.`). Alarm `HerdOidcFailing`:
mehr als die Hälfte der Rückrufe in 15 Minuten scheiterte am Anbieter
(`provider_unreachable`, `provider_error`, `issuer_mismatch`, `id_token_invalid`),
mindestens drei, für 5 Minuten. Anmeldung mit Passwort funktioniert weiter.
