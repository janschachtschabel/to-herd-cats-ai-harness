# Anmeldung: Passwort, zweiter Faktor und OIDC (Google und andere)

Stand M9a (Tasks 4, 5, 5b und 9) und M9b (Task 16: zweiter Faktor mit TOTP; Task 18:
Leerlaufgrenze, eigene Sitzungen, erneute Anmeldung vor dem Verknüpfen; mit den
Korrekturen der Reviews, Abschluss 19.11.2026). Neben der Anmeldung mit E-Mail und Passwort kann sich
eine Person über einen OpenID-Connect-Anbieter (OIDC) anmelden: Google als fertige
Vorlage, jeder andere Anbieter mit Discovery (Keycloak, Entra ID, Authentik …) als
„allgemein“. Optional legen sich Personen aus erlaubten Domains dabei selbst ein Konto
an; es wartet, bis ein Admin es freigibt.

## Anmeldung mit Passwort

Das erste Konto (Inhaberin) entsteht beim allerersten Start aus
`HERD_BOOTSTRAP_ADMIN_EMAIL` und `HERD_BOOTSTRAP_ADMIN_PASSWORD` (das Passwort muss die
Regeln unten erfüllen, mit dem Namen aus `HERD_BOOTSTRAP_ORG_NAME` und der Adresse als
Kontext; sonst bricht der Start mit `bootstrap refused` und Exit-Status 4 ab, ohne
etwas anzulegen); weitere legen Admins
unter **Verwaltung → Personen** an. Es gibt keinen Selbstbedienungs-Reset: ein Admin
setzt ein neues Passwort, dann enden alle Sitzungen der Person. Jede Person ändert ihr
eigenes Passwort im Profil (mit dem alten).

- **Regeln:** 10 bis 200 Zeichen, keine Regeln zur Zusammensetzung. Abgelehnt wird ein
  Passwort aus der Liste häufiger und geleakter Passwörter (`auth.password_common`) und
  eines, das ein Wort aus dem Kontext enthält: Produktname, Name der Organisation,
  Teile der E-Mail-Adresse oder des Namens, je ab 4 Zeichen (`auth.password_context`).
  Einzelheiten in [`SICHERHEIT.md`](SICHERHEIT.md#anmeldung).
- **Raten bremsen:** je Client-Adresse höchstens `HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE`
  (30) Versuche je Minute, je Adresse und E-Mail `HERD_LOGIN_RATE_LIMIT_PER_MINUTE` (5)
  Fehlversuche; gezählt in PostgreSQL über alle API-Knoten. Keine Kontosperre.
- **Sitzung:** ein Cookie, gültig `HERD_SESSION_TTL_HOURS` (168, also 7 Tage) ab der
  Anmeldung, durch Nutzung nicht verlängert. Ohne Nutzung endet sie schon nach
  `HERD_SESSION_IDLE_HOURS` Stunden (Standard 24, `0` schaltet die Grenze ab; ASVS
  V7.3.1, [`SICHERHEIT.md`](SICHERHEIT.md#sitzungen)): Die Sitzung merkt ihre letzte
  Nutzung, höchstens einmal je Minute geschrieben; danach antwortet die API 401
  `auth.session_invalid` und die App zeigt die Anmeldung. Dieses Ende wird an der
  Sitzung vermerkt wie eine Abmeldung (bei der nächsten Anfrage, sonst vom Worker), eine
  später längere oder abgeschaltete Grenze belebt sie nicht wieder. Nutzung ist, was
  die Person tut: Ein offener Tab ohne Eingabe hält die Sitzung nicht am Leben. Die
  Live-Verbindung (`/api/stream`) zählt nie; die Anfragen, die die App von sich aus
  stellt (nach einem Live-Ereignis, im Intervall, beim Fokus), zählen nicht, wenn der Tab
  über 60 Sekunden keine Eingabe sah (Zeiger, Taste, Mausrad, Berührung, Fokus, Tab
  wieder sichtbar): Die App schickt sie dann mit `X-Herd-Unattended: 1`. Umgekehrt
  meldet ein Tab, in dem jemand arbeitet, ohne dass die App die API fragt (etwa nur
  Tippen im Live-Editor), höchstens alle 5 Minuten eine Nutzung
  (`POST /api/auth/me/touch`, 204, keine Schreibaktion für die Schreibgrenze). Die
  Markierung ist ein Hinweis eines ehrlichen Browsers, kein Schutz gegen ein Programm,
  das die Sitzung absichtlich am Leben hält. Compose setzt den Wert in
  beiden Dateien, Helm als `api.sessionIdleHours`. Abmelden beendet sie; ein
  Passwortwechsel, eine Deaktivierung und **Verwaltung → Personen → „Abmelden“** („überall abmelden“, Audit)
  beenden alle Sitzungen einer Person.
- **Eigene Sitzungen:** Im Profil unter „Angemeldete Geräte“ sieht jede Person ihre
  laufenden Sitzungen (Browser und System ohne Version, etwa „Firefox · Linux“,
  Anmeldezeit, letzte Nutzung; „Dieses Gerät“ markiert die eigene) und meldet eine
  einzelne oder „Alle anderen“ ab (ASVS V7.5.2). Das beendet die Sitzung sofort, auch
  ihre Live-Verbindungen; Audit `user.session_ended` mit der Kennung der Sitzung bzw.
  der Anzahl der Sitzungen, die noch liefen, nie dem Gerät. Die Beschreibung darüber
  nennt die eingestellten Grenzen (`GET /api/auth/me` → `session_limits`:
  `idle_hours`, `null` ohne Inaktivitätsgrenze, und `ttl_hours`). API: `GET /api/auth/me/sessions` (paginiert),
  `DELETE /api/auth/me/sessions/{id}` (eine fremde oder beendete Sitzung antwortet wie
  eine unbekannte: 404 `auth.session_not_found`),
  `POST /api/auth/me/sessions/sign-out-others`. Die Adresse eines Geräts speichert die
  App nicht.
- **Cookie-Name:** `HERD_SESSION_COOKIE_NAME` (Standard `herd_session`); über https
  (oder mit `HERD_COOKIE_SECURE=true`) bekommt er das Präfix `__Host-`, also
  `__Host-herd_session` (Secure, HttpOnly, SameSite=Lax, Pfad `/`), über reines http
  bleibt er `herd_session`. Ein Name, der schon mit `__Host-` oder `__Secure-` beginnt,
  bleibt, wie er ist. Hinter
  einem Reverse Proxy muss die App https erkennen (`HERD_FORWARDED_ALLOW_IPS`), sonst
  fehlt das Präfix. **Nach dem Update auf M9 wird jede über https angemeldete Person
  einmal abgemeldet**, weil das alte Cookie ohne Präfix dort nicht mehr zählt
  ([README](../README.md#freigaben-und-updates)).
- **Zweiter Faktor:** freiwillig mit TOTP, auch für Owner und Admins (Jans Antwort J3),
  siehe [unten](#zweiter-faktor-totp). Niemand muss ihn einrichten; wer MFA für alle
  braucht, lässt die Personen nur über einen Anbieter mit Pflicht-MFA anmelden.

## Zweiter Faktor (TOTP)

Jede Person mit Passwort kann im **Profil → Zwei-Faktor-Anmeldung** einen zweiten Faktor
einschalten: einen sechsstelligen Code aus einer Authenticator-App (TOTP nach RFC 6238,
SHA-1, 30 Sekunden; etwa Aegis, FreeOTP, Google Authenticator, 1Password, Bitwarden).
Er ist freiwillig, auch für Owner und Admins (Jans Antwort J3).

- **Einrichten:** mit dem aktuellen Passwort bestätigen; die App zeigt einmal einen
  Schlüssel (160 Zufallsbits) als QR-Code und als Text. Der QR-Code entsteht im Browser
  (keine Anfrage an einen Dritten). Eingeschaltet ist der zweite Faktor erst, wenn ein
  Code aus der App bestätigt ist; dann zeigt das Profil **einmal zehn
  Wiederherstellungscodes** (je 120 Zufallsbits, `ABCDEF-GHIJKL-…`), und alle anderen
  Sitzungen der Person enden (sie wurden ohne zweiten Faktor geöffnet). Der Schlüssel
  liegt verschlüsselt (`enc:` unter `HERD_SECRET_KEY`) in `user_totp` und wird nie
  wieder angezeigt, geloggt oder protokolliert; die Wiederherstellungscodes nur als
  SHA-256.
- **Anmelden:** nach dem richtigen Passwort öffnet die App noch keine Sitzung. Sie
  antwortet `202` und merkt sich eine wartende Anmeldung (`sign_in_challenge`, nur der
  Hash des Zufallswerts aus dem HttpOnly-Cookie `herd_sign_in`, über https
  `__Host-herd_sign_in`), gültig 5 Minuten und einmal verwendbar. Die Anmeldeseite
  fragt dann nach dem Code oder einem Wiederherstellungscode
  (`POST /api/auth/login/second-factor`); erst dann entsteht die Sitzung. Dasselbe gilt
  nach einer Anmeldung über einen OIDC-Anbieter, wenn die Person TOTP eingeschaltet hat:
  der Rückruf führt auf `/login?second_factor=totp`.
- **Gültigkeit eines Codes:** der Code des aktuellen 30-Sekunden-Schritts und je ein
  Schritt davor und danach (Uhrabweichung, Tippzeit), also höchstens 90 Sekunden. Jeder
  Schritt gilt nur einmal: Ein Code wird nach seiner Verwendung (auch auf einem anderen
  Weg) und jeder ältere abgelehnt. Ein Wiederherstellungscode gilt genau einmal.
- **Raten bremsen:** falsche Codes zählen je Person (`HERD_LOGIN_RATE_LIMIT_PER_MINUTE`,
  5 je Minute, egal wofür: Anmeldung, Ausschalten, neue Codes, Zugangstoken), jede
  Anfrage des zweiten Schritts zusätzlich je Client-Adresse wie die Passwort-Anmeldung
  (`HERD_LOGIN_IP_RATE_LIMIT_PER_MINUTE`); nach 5 falschen Codes ist eine wartende
  Anmeldung beendet (zurück zum Passwort). Antwort dann 429 `auth.too_many_attempts`.
- **Sperre:** 10 falsche Codes innerhalb von 24 Stunden sperren den zweiten Faktor der
  Person für eine Stunde (429 `auth.second_factor_locked`, auch für einen richtigen
  Code; Anmelden, Ausschalten, neue Codes und Zugangstoken warten so lange). Die Sperre
  steht im Audit (`user.totp_locked`, als `system`), und die Person findet in ihrer
  Aktivität einen Hinweis (es könnte jemand ihr Passwort kennen). Ein richtiger Code
  setzt die Zählung zurück; ein Admin-Reset des zweiten Faktors hebt auch die Sperre
  auf. Auslösen kann sie nur, wer das Passwort kennt oder angemeldet ist.
- **Ausschalten:** im Profil mit einem aktuellen Code oder einem
  Wiederherstellungscode. **Neue Wiederherstellungscodes** (die alten werden ungültig)
  mit einem aktuellen Code aus der App.
- **Gerät verloren:** mit einem Wiederherstellungscode anmelden und TOTP neu
  einrichten. Ohne Code setzt ein Admin unter **Verwaltung → Personen → „Zwei-Faktor
  zurücksetzen“** zurück (`POST /api/admin/users/{id}/totp/reset`, `user.manage`; den
  zweiten Faktor eines Owners nur ein Owner; Audit `user.totp_reset`). Der Admin
  vergewissert sich vorher, wer fragt, auf demselben Weg wie beim Anlegen des Kontos
  (persönlich, über einen bekannten Rückrufweg; ASVS V6.4.4). Danach meldet sich die
  Person nur mit dem Passwort an, bis sie TOTP neu einrichtet; laufende Sitzungen
  bleiben, wartende Anmeldungen enden.
- **Zugangstoken:** wer TOTP eingeschaltet hat, gibt beim Anlegen eines Zugangstokens
  (eigenes oder das eines externen Agenten) einen aktuellen Code an (403
  `auth.second_factor_required` ohne, 422 `auth.second_factor_invalid` bei einem
  falschen); ein Token ist ein weiterer Weg hinein und soll nicht leichter zu bekommen
  sein als eine Anmeldung.
- **Ohne Passwort, ohne Schlüssel:** Konten ohne Passwort (nur über einen Anbieter)
  richten keinen TOTP ein, dort gilt der zweite Faktor des Anbieters. Ohne
  `HERD_SECRET_KEY` bietet das Profil TOTP nicht an (409 `totp.no_secret_key`). Wird
  der Schlüssel gewechselt, schlüsselt `scripts/rotate_secrets.py` die TOTP-Schlüssel
  mit um ([`KI.md`](KI.md)); geht er verloren (oder wird eine Sicherung mit
  `--without-secrets` eingespielt), helfen nur noch Wiederherstellungscodes oder das
  Zurücksetzen durch einen Admin.
- **Protokoll:** `auth.sign_in` mit `outcome=second_factor` nach dem ersten Schritt,
  dann `method=password+totp` (bzw. `oidc+recovery_code` …) und `outcome=ok`, oder
  `method=second_factor` mit dem Ablehnungscode; nie ein Code, Schlüssel oder Cookie.
  Audit: `user.totp_enabled`, `user.totp_disabled`, `user.totp_recovery_codes_renewed`,
  `user.totp_reset`, ohne Inhalte.
- **Nach einem Update:** Eine ältere Version kennt die TOTP-Tabellen nicht und würde
  Personen mit TOTP nur mit dem Passwort anmelden; nicht auf eine ältere Version
  zurückgehen, sobald jemand TOTP eingeschaltet hat.

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
Firmenverzeichnis, in dem niemand seine Adresse selbst ändern kann); dann verknüpft die
erste Anmeldung ein bestehendes Konto mit derselben Adresse. **Selbstregistrierung**
über einen allgemeinen Anbieter geht nur zusammen mit „E-Mail vertrauen“ (sonst 422
`oidc.signup_needs_trust`): Ein Anbieter, der für die Adressen nicht bürgt, darf
auch keine neuen Konten unter ihnen anlegen. Sonst bekäme, wer dort `email_verified`
für `chefin@firma.example` erreicht (ein Verzeichnis, in dem Personen ihr Profil selbst
pflegen, ein Verzeichnis mit mehreren Mandanten), ein wartendes Konto unter dieser
Adresse, das ein Admin für das der Chefin halten könnte.

## Wie eine Anmeldung entschieden wird

1. Ist das Konto beim Anbieter (`sub`) schon verknüpft, meldet es seine Person an
   (wartet noch auf Freigabe: `oidc.account_pending`; deaktiviert:
   `oidc.account_inactive`; ein abgelehntes Konto gibt es nicht mehr).
2. Sonst muss die E-Mail vorhanden und bestätigt sein (`email_verified`), sonst
   `oidc.email_unverified`.
3. Gibt es ein aktives Konto mit dieser E-Mail, wird es nur verknüpft, wenn der
   Anbieter für die Adresse maßgeblich ist (Google wie oben, ein allgemeiner nur mit
   „E-Mail vertrauen“). Sonst `oidc.link_refused`: erst mit Passwort anmelden und im
   Profil unter **Verknüpfte Konten** verknüpfen. Ein Konto, das auf Freigabe wartet
   oder deaktiviert ist, wird nicht verknüpft (Codes wie in 1).
4. Ohne Konto: Selbstregistrierung, wenn der Anbieter sie erlaubt **und** Domains
   nennt und, bei einem allgemeinen Anbieter, „E-Mail vertrauen“ an ist
   (`oidc.signup_closed` sonst). Die Domain der bestätigten E-Mail muss genau
   gelistet sein (klein geschrieben, ohne Subdomains, ohne Punkt am Ende); bei Google
   muss außerdem `hd` gleich dieser Domain sein (für `gmail.com` nur, wenn
   ausdrücklich gelistet). Sonst `oidc.domain_not_allowed`.

## Selbstregistrierung und Freigabe

Ohne Freigabe kommt niemand ins System (Entscheidung J2, Plan M9 Task 5b). Ein selbst
registriertes Konto ist `member`, ohne Passwort, Sprache Deutsch, hat seinen
persönlichen Bereich und eine eigene KI-Zuordnung **„keine KI“** (Kosten und
Datenabfluss erst nach Entscheidung eines Admins; zu ändern an einer Stelle,
`SIGNUP_GETS_NO_AI` in `backend/app/modules/oidc/admission.py`). Es entsteht aber
**deaktiviert und wartet auf Freigabe** (`awaiting_approval_since`): Es wird keine
Sitzung geöffnet, die Person landet auf der Seite „Dein Konto wartet auf Freigabe“
(`/login?error=oidc.account_pending`), und jede weitere Anmeldung endet dort, bis
entschieden ist. Wie jedes deaktivierte Konto erscheint es nicht im Verzeichnis, in
Erwähnungen oder Auswahllisten. Audit: `user.self_registered` (durch die neue Person).

- **Benachrichtigung:** Jede aktive Person mit `user.manage` (Owner, Admin) bekommt in
  **Aktivität** einen Eintrag „… hat sich registriert und wartet auf Freigabe“, der zur
  Liste führt. In der Navigation zeigt **Verwaltung → Personen** die Zahl der
  wartenden Konten. Ereignisse tragen nur IDs (`user.signup_pending`), nie Adresse
  oder Name.
- **Verwaltung → Personen → Wartet auf Freigabe** (`/admin/users?filter=pending`,
  API `GET /api/admin/users?pending=true`, Zahl `GET /api/admin/users/pending/count`):
  - **Freigeben** (`POST /api/admin/users/{id}/approve`, Body `{"version": n}`): das
    Konto wird aktiv, als `member`, weiterhin ohne KI; die Person meldet sich wieder
    über den Anbieter an. Offene Bereiche sieht sie ohne Mitgliedschaft. Audit
    `user.signup_approved`.
  - **Ablehnen** (`POST /api/admin/users/{id}/reject`, gleicher Body, Antwort 204):
    das Konto wird **gelöscht**, denn es war nie aktiv, mit allem, was die
    Registrierung angelegt hat (Verknüpfung beim Anbieter, persönlicher Bereich,
    eigene KI-Zuordnung, die Benachrichtigungen der Admins) und den Mitgliedschaften,
    die ein Admin ihm in der Wartezeit gab. Die Adresse ist danach wieder frei: Ein
    Admin kann die Person anlegen, oder sie registriert sich erneut (dann wartet sie
    wieder). Audit `user.signup_rejected` nur mit der ID des Kontos, nie Adresse oder
    Name. Wer schon einmal aktiv war, wird nie gelöscht, nur deaktiviert.
  - Beides nennt die gelesene Version; hat jemand anderes inzwischen entschieden oder
    geändert, antwortet die API 409 (`users.version_conflict`, `users.not_pending`).
  - Hat ein Owner ein wartendes Konto inzwischen zum Owner gemacht, entscheidet nur ein
    Owner darüber (403 `users.owner_only`), wie beim Reaktivieren.
  - Ein wartendes Konto wird freigegeben, nicht reaktiviert
    (`…/reactivate` antwortet 409 `users.awaiting_approval`), damit jeder Weg hinein
    einen Freigabe-Eintrag im Protokoll hat.
- Die Rolle ändert sich durch Freigabe nicht; KI gibt ein Admin in der KI-Verwaltung
  frei (Zuordnung der Person entfernen oder setzen).
- Andere Wege zu einem Konto sind schon Handlungen von Admins bzw. Betrieb und brauchen
  keine Freigabe: **Person anlegen** (Admin), der erste Owner aus `HERD_BOOTSTRAP_*`
  (nur solange es niemanden gibt), eine Wiederherstellung. Verknüpfen (Profil oder
  „E-Mail vertrauen“) legt kein Konto an, sondern hängt es an ein bestehendes.

## Verknüpfen und lösen

- **Profil → Verknüpfte Konten**: eigene Verknüpfungen sehen, eine neue anlegen
  (Weiterleitung zum Anbieter, danach zurück ins Profil) und lösen. Die E-Mail beim
  Anbieter muss dafür nicht passen; ein Konto, das schon mit einer anderen Person
  verknüpft ist, wird abgelehnt (`oidc.identity_taken`).
- **Erneut anmelden vor dem Verknüpfen** (ASVS V7.5.1): Ein neues Konto ist ein weiterer
  Weg in das Konto, deshalb fragt die App vorher das aktuelle Passwort ab (Dialog
  „Erneut anmelden“; `POST /api/auth/me/identities/{key}/link` mit `{"password": …}`).
  Wer kein Passwort hat, meldet sich im Dialog über „Erneut über … anmelden“ bei einem
  schon verknüpften Anbieter neu an (`GET /api/auth/oidc/{key}/start?reauth=true`). Die
  App verlangt dabei vom Anbieter eine frische Anmeldung (`prompt=login`,
  `max_age=600`); nennt das ID-Token `auth_time`, zählt nur eine Anmeldung der letzten
  10 Minuten, sonst kommt die Person mit `link_error=oidc.reauth_stale` ins Profil
  zurück. Die so geöffnete Sitzung (auch mit TOTP danach) verknüpft 10 Minuten lang ohne
  Passwort (`user_session.reauth_at`); danach geht es zurück ins Profil. Eine gewöhnliche
  Anmeldung über einen Anbieter zählt nicht: Bei einer laufenden Sitzung beim Anbieter
  kann sie ohne jede Eingabe gelingen. Ob der Anbieter `prompt=login` wirklich mit einer
  Eingabe beantwortet, entscheidet er selbst. Sonst 403 `auth.reauth_required`; ein falsches Passwort 422 `auth.wrong_password`,
  gezählt wie beim Passwortwechsel (`HERD_LOGIN_RATE_LIMIT_PER_MINUTE` je Person).
- **Verwaltung → Personen → Bearbeiten**: mit `user.manage` die Verknüpfungen jeder
  Person sehen und lösen (die eines Owners nur als Owner).
- Ein Konto ohne Passwort behält seine letzte Verknüpfung (409 `oidc.last_identity`).
- Eine Verknüpfung zu lösen beendet alle anderen Sitzungen der Person (auch eine, die
  über diesen Anbieter begann); wer die eigene löst, bleibt in der laufenden Sitzung
  angemeldet, löst ein Admin sie, endet jede Sitzung der Person.
- Audit: `user.identity_linked` (Anbieter, `via` `email` oder `profile`),
  `user.identity_unlinked`; Anbieter: `oidc_provider.created|updated|deleted`. Nie
  das Subjekt, die E-Mail oder ein Secret.
- Einen Anbieter zu löschen löst alle seine Verknüpfungen und beendet, wie das Lösen,
  jede Sitzung der Personen, die mit ihm verknüpft waren (etwa wenn der Anbieter als
  kompromittiert gilt); nur die Sitzung des löschenden Admins bleibt. Audit
  `oidc_provider.deleted` mit Schlüssel und Zahl der Personen. Ausschalten beendet
  keine Sitzung: Wer angemeldet ist, bleibt es, bis die Sitzung abläuft; neue
  Anmeldungen über den Anbieter gehen nicht mehr.

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
| `oidc.signup_closed` | Kein Konto, Selbstregistrierung aus (oder ein allgemeiner Anbieter ohne „E-Mail vertrauen“). |
| `oidc.domain_not_allowed` | Die Domain ist nicht freigegeben (bei Google: oder `hd` passt nicht). |
| `oidc.email_unverified` | Der Anbieter meldet keine bestätigte E-Mail. |
| `oidc.account_pending` | Das Konto (selbst registriert) wartet auf Freigabe durch einen Admin. |
| `oidc.account_inactive` | Das Konto ist deaktiviert. |
| `oidc.identity_taken` | Das Konto beim Anbieter gehört schon einer anderen Person. |
| `oidc.flow_invalid` | Abgelaufen, schon benutzt, aus einem anderen Browser oder für einen anderen Anbieter. |
| `oidc.denied` | Beim Anbieter abgebrochen. |
| `oidc.not_found` / `oidc.unavailable` | Anbieter unbekannt oder ausgeschaltet. |
| `oidc.rate_limited` | Zu viele Versuche von dieser Adresse. |
| `oidc.provider_unreachable` | Anbieter nicht erreichbar (Egress-Sperre, Netz, Zeitüberschreitung). |
| `oidc.provider_error`, `oidc.issuer_mismatch`, `oidc.id_token_invalid` | Antwort des Anbieters unbrauchbar bzw. ID-Token ungültig. |
| `oidc.public_url_missing` | `HERD_PUBLIC_URL` fehlt (Verwaltung). |
| `oidc.reauth_stale` | Die erneute Anmeldung beim Anbieter vor dem Verknüpfen ist älter als 10 Minuten (`auth_time`); noch einmal anmelden. |

Sitzungen und Verknüpfen (Antworten der API):

| Code | Bedeutung |
|---|---|
| `auth.session_invalid` | Die Sitzung ist abgelaufen, beendet oder war länger als `HERD_SESSION_IDLE_HOURS` ungenutzt: neu anmelden. |
| `auth.session_not_found` | Eine Sitzung beenden, die nicht die eigene ist oder schon endete. |
| `auth.reauth_required` | Verknüpfen ohne Passwort und ohne eine Anmeldung beim Anbieter in den letzten 10 Minuten. |
| `auth.wrong_password` | Das Passwort zur Bestätigung (Verknüpfen, TOTP einrichten, Passwort ändern) ist falsch. |

Zweiter Faktor (Antworten der API):

| Code | Bedeutung |
|---|---|
| `auth.second_factor_invalid` | Code falsch, außerhalb des Zeitfensters oder schon verwendet; Wiederherstellungscode unbekannt oder verbraucht. |
| `auth.second_factor_expired` | Keine wartende Anmeldung (abgelaufen, schon verwendet, nach 5 falschen Codes beendet, Cookie fehlt, TOTP inzwischen zurückgesetzt, Person deaktiviert): noch einmal mit dem Passwort. |
| `auth.second_factor_required` | Ein Zugangstoken braucht einen aktuellen Code. |
| `auth.too_many_attempts` | Zu viele falsche Codes der Person (oder Anfragen der Adresse) in der letzten Minute. |
| `auth.second_factor_locked` | 10 falsche Codes in 24 Stunden: der zweite Faktor ist für eine Stunde gesperrt. |
| `totp.already_enabled`, `totp.no_setup`, `totp.not_enabled` | Einrichten, obwohl eingeschaltet; Bestätigen ohne begonnene Einrichtung; Ausschalten, obwohl aus. |
| `totp.no_password`, `totp.no_secret_key` | Konto ohne Passwort; kein `HERD_SECRET_KEY` gesetzt. |

## Überwachung

Metrik `herd_oidc_logins_total{outcome}` (API): je Rückruf und je gescheitertem Start ein fester Ausgang (`login`,
`link`, `signup` (neues Konto, wartet auf Freigabe), `profile_link` oder der Code
ohne `oidc.`, etwa `account_pending`). Alarm `HerdOidcFailing`:
mehr als die Hälfte der Rückrufe in 15 Minuten scheiterte am Anbieter
(`provider_unreachable`, `provider_error`, `issuer_mismatch`, `id_token_invalid`),
mindestens drei, für 5 Minuten. Anmeldung mit Passwort funktioniert weiter.
