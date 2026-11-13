# Wiki: Bedienung und Betrieb

Das Wiki ist seit Meilenstein 2 in jedem Bereich vorhanden. Diese Seite beschreibt, wer
was darf, wie die beiden Editoren zusammenspielen, wo die Markdown-Abbildung des
Live-Editors Grenzen hat und wie die Live-Bearbeitung hinter einem Reverse Proxy
betrieben wird. Die Regeln selbst stehen in der Spezifikation (Abschnitte 9, 10
„Tags“, 11 „Suche“).

## Bedienung

### Rechte

Was jemand sieht, entscheidet die Rolle im Bereich (`my_role`); die API prüft jede
Aktion noch einmal.

| Rolle im Bereich | darf |
|---|---|
| Leser (`viewer`) | veröffentlichte Seiten lesen, Versionen ansehen, exportieren, suchen |
| Autor (`editor`) | dazu Seiten anlegen, bearbeiten (Markdown und live), umbenennen, verschieben, Tags setzen, Anhänge hochladen; Entwürfe aller sehen, eigene veröffentlichen |
| Moderator (`moderator`) | dazu fremde Entwürfe veröffentlichen, Seiten in den Papierkorb legen und wiederherstellen, Tags des Bereichs verwalten |
| Verwalter (`admin`) | dazu Mitglieder, Einstellungen, Import |

Systemweit: Endgültiges Löschen aus dem Papierkorb (`page.purge`) und systemweite Tags
(`tag.manage`) haben nur Inhaber und Administratoren. Bereiche, die jemand nicht sehen
darf, und Seiten darin gibt es für ihn nicht: Die API antwortet mit 404, die Suche
zählt sie nicht mit.

### Seiten und Baum

- Links steht der Seitenbaum. Pfeiltasten bewegen, Rechts/Links klappen auf und zu,
  Pos1/Ende springen, Eingabe öffnet. Verschieben und Sortieren geht über „Weitere
  Aktionen“ → „Verschieben“ (Ziel und Stelle); Ziehen mit der Maus gibt es nicht.
- „Nach Tag filtern“ über dem Baum zeigt nur die Seiten mit diesem Tag; ein Klick auf
  einen Tag an einer Seite tut dasselbe.
- Eine neue Seite ist ein Entwurf. Veröffentlichen geht nur, wenn die übergeordnete
  Seite veröffentlicht ist; eine veröffentlichte Seite lässt sich nicht unter einen
  Entwurf verschieben.
- `[[Titel]]` verlinkt eine andere Seite des Bereichs nach ihrem Titel. Gibt es sie
  nicht, ist der Link als fehlend markiert, und wer Seiten anlegen darf, kann sie von
  dort anlegen.
- Höchstens 16 Ebenen, 200.000 Zeichen Markdown je Seite.

### Zwei Editoren

- **Bearbeiten** öffnet den Markdown-Editor mit Vorschau daneben. Speichern mit
  Strg+S, optional mit Änderungstext. Hat jemand anderes dazwischen gespeichert, fragt
  ein Dialog: die eigene Fassung auf den aktuellen Stand setzen und erneut speichern,
  oder verwerfen.
- **Gemeinsam bearbeiten** öffnet den Live-Editor: Alle, die die Seite so geöffnet
  haben, sehen die Änderungen der anderen sofort, dazu Namen und Cursor. Gespeichert
  wird automatisch (höchstens alle 2 s, spätestens nach 10 s); die Statusanzeige zeigt
  „Synchronisiert“, „Speichert …“ oder „Getrennt“. **Fertig** speichert sofort und
  zeigt danach die Seite so, wie der Server sie hat; kann der Server das nicht
  bestätigen (z. B. API kurz weg), bleibt der Editor offen und sagt das. Leser bekommen
  diese Schaltfläche nicht.
- **Generationen:** Speichern im Markdown-Editor, Wiederherstellen einer Version,
  Verschieben und Papierkorb beenden eine laufende Live-Sitzung. Die offenen
  Live-Editoren melden „Die Seite wurde außerhalb der Live-Sitzung geändert“, laden den
  neuen Stand und arbeiten in einer neuen Sitzung weiter. Wer dabei einen anderen Text
  hatte, kann ihn als Markdown kopieren. Ein alter Live-Stand überschreibt den neuen
  nie; bis die offenen Editoren das Ende bemerken, vergehen bis zu 5 s.
- Verliert jemand während der Live-Bearbeitung das Schreibrecht (Rolle, Deaktivierung,
  Abmeldung durch einen Administrator), wird seine Verbindung getrennt und sein Editor
  schreibgeschützt; seine ungespeicherten Eingaben werden verworfen. Eine normale
  Abmeldung oder abgelaufene Sitzung ist kein Rechteentzug: Was die Person getippt hat,
  wird zuerst gespeichert, dann endet nur ihre Verbindung.

### Versionen, Papierkorb, Tags, Anhänge, Suche

- **Versionen:** Jede Speicherung ist eine Version mit Person, Zeit und Quelle
  (`human`, `collab`, `import`, `restore`). Live-Speicherungen derselben Sitzung werden
  über 60 s zu einer Version zusammengefasst. Zwei Versionen lassen sich vergleichen
  (bis 20.000 Zeilen), benennen und wiederherstellen (als neue Version).
- **Papierkorb:** In den Papierkorb gelegte Seiten nehmen ihre Unterseiten mit;
  Wiederherstellen setzt sie ans Ende ihrer Geschwister.
- **Tags:** Systemweite Tags (Verwaltung → Tags) gibt es in allen Bereichen,
  Bereichs-Tags (Einstellungen des Bereichs) nur dort. Name und Farbe sind änderbar;
  ein gelöschter Tag verschwindet von allen Seiten.
- **Anhänge:** bis 25 MiB, erkannt am Inhalt: PNG, JPEG, GIF, WebP (inline angezeigt),
  PDF, TXT, Markdown, CSV, JSON, DOCX, XLSX, PPTX, ZIP (als Download). SVG und HTML
  werden abgelehnt, auch umbenannt.
- **Suche:** Strg+K (oder „Suche“ in der Seitenleiste) durchsucht Titel und Inhalt
  aller Seiten, die man lesen darf, optional nur im aktuellen Bereich. Entwürfe findet
  nur, wer sie sehen darf.
- **Import und Export:** „Import/Export“ im Kopf des Bereichs. Export als ZIP mit einer
  `.md` je Seite (Front Matter `title`, `status`, `tags`) und den Anhängen; Import
  desselben Formats (Verwalter des Bereichs, bis 100 MiB, 2.000 Einträge). Jede Seite
  lässt sich auch einzeln als `.md` herunterladen.

## Grenzen der Markdown-Abbildung im Live-Editor

Markdown ist das gespeicherte Format; der Live-Editor arbeitet auf einem Dokumentbaum
(Tiptap/Yjs), den der Collab-Prozess beim Speichern wieder in Markdown schreibt. Der
Markdown-Editor speichert genau, was dasteht. Im Live-Editor gilt:

- **Darstellbar und bearbeitbar:** Überschriften, Absätze, fett, kursiv,
  durchgestrichen, Inline-Code, Links (nur `http`, `https`, `mailto` und relative
  Ziele), Bilder, Aufzählungen, nummerierte Listen, Aufgabenlisten (auch
  verschachtelt), Zitate, Codeblöcke, Tabellen, Trennlinien, Wiki-Links `[[Titel]]`.
- **Unverändert durchgereicht:** Was der Editor nicht darstellen kann (rohes HTML,
  Referenzlinks, Fußnoten, verlinkte Bilder und Ähnliches), erscheint dort als
  Codeblock und wird beim Speichern genau so zurückgeschrieben, wie es kam. Ebenso jeder
  Block, den der Editor sonst anders zurückschreiben würde, als er gemeint war.
- **Umgeschrieben, aber gleichbedeutend:** Nach einer Live-Speicherung kann das Markdown
  anders aussehen als vorher: Tabellenzellen werden aufgefüllt, Listen- und
  Hervorhebungszeichen vereinheitlicht (`*` → `-`, `_` → `*`), Setext- werden
  ATX-Überschriften, eingerückter Code wird zum Codeblock mit Zäunen, lockere Listen
  werden eng, benannte Zeichen wie `&copy;` stehen als Zeichen (`©`), Zeichen mit
  Markdown-Bedeutung im Text werden maskiert (aus `[x]` wird `\[x\]`, Wiki-Links
  ausgenommen). Die Seitenansicht zeigt danach dasselbe; der Diff der Versionen zeigt
  die Schreibweise als Änderung, aber erst, wenn jemand live etwas geändert hat.
- **Sicherheitsnetz:** Bevor eine Seite live geöffnet wird, liest der Collab-Prozess
  ihr Markdown mit demselben Parser wie die Seitenansicht (micromark mit GFM), wandelt
  es in den Editor und zurück und vergleicht beide Syntaxbäume (Leerraum innerhalb von
  Text und eng/locker bei Listen zählen nicht). Weichen sie ab, öffnet der Live-Editor
  die Seite nicht (Close-Code 4422) und bietet den Markdown-Editor an. Beispiel: zwei
  aufeinanderfolgende Listen mit verschiedenen Aufzählungszeichen (`-` und `*`), die
  der Editor zu einer Liste zusammenzöge.
- **Öffnen ohne Ändern ändert nichts:** Wer den Live-Editor öffnet und ohne Eingabe
  wieder schließt, erzeugt weder eine Version noch ein anderes Markdown. Auch eine
  Änderung, die wieder zurückgenommen wurde, lässt das gespeicherte Markdown, wie es war.
- **Nicht vorhanden:** Unterstreichen (kein Markdown dafür), eigene Größen oder
  Farben, eingebettete Inhalte.
- Ein Live-Zustand hat höchstens 5 MiB, ein WebSocket-Frame höchstens 1 MiB. Größere
  Seiten bearbeitet man im Markdown-Editor; der Live-Editor sagt das dann.

## Betrieb hinter einem Reverse Proxy

Die Live-Bearbeitung ist ein WebSocket auf `/collab/<seiten-id>?generation=<n>` am
öffentlichen Port (8080) der API, also am selben Host und Service wie alles andere. Die
API prüft Origin, Sitzungs-Cookie, Rechte und Generation und reicht erst dann an den
Collab-Prozess weiter. Daraus folgt für Proxy und Ingress:

1. **Upgrade durchreichen** (`Upgrade`- und `Connection`-Header, HTTP/1.1 zum
   Backend). Ein eigener Pfad für `/collab` ist nicht nötig.
2. **Origin:** `HERD_PUBLIC_URL` auf die Adresse setzen, unter der Browser die App
   öffnen (`https://wiki.example`). Ohne den Wert muss die Origin zum `Host` passen,
   den die App sieht; schreibt der Proxy den Host um, scheitert jede Live-Verbindung
   mit HTTP 403. Das Chart nimmt ohne `publicUrl` den ersten Ingress-Host.
3. **Leerlauf:** Die API schickt alle 20 s einen WebSocket-Ping. Jedes
   Leerlauf-Timeout ab 30 s genügt. Ein Limit für die gesamte Dauer einer Verbindung
   (GKE) beendet dagegen auch aktive Sitzungen: Der Editor verbindet sich dann neu,
   ohne Datenverlust, aber mit kurzem „Getrennt“.
4. **Größen:** Anhänge bis 25 MiB, Importe bis 100 MiB; der Proxy muss das
   durchlassen (sonst 413 vom Proxy). Alle anderen Anfragen höchstens 1 MiB.
5. **Client-Adresse und Schema:** `HERD_FORWARDED_ALLOW_IPS` auf die Adresse des
   Proxys setzen (Audit, Anmeldelimits, `Secure`-Cookie bei https).

Die folgenden Beispiele folgen den Dokumentationen der jeweiligen Controller; in diesem
Projekt geprüft sind nur der direkte Zugriff, Compose und `helm template`.

**ingress-nginx** (Upgrade ohne Einstellung; `proxy-read-timeout` 60 s passt):

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 100m
```

**Traefik:** WebSocket ohne Einstellung. Größenlimits setzt Traefik ab Werk keine;
wer eine Buffering-Middleware nutzt, stellt `maxRequestBodyBytes` auf mindestens
104857600.

**HAProxy** (haproxy-ingress, HAProxy Kubernetes Ingress Controller): Für WebSockets
gilt `timeout tunnel` (nicht `timeout client`/`server`); mindestens 30 s, üblich 1 h.

**AWS Load Balancer Controller (ALB):** Leerlauf-Timeout 60 s ab Werk, passt. Größer
nur bei Bedarf:

```yaml
annotations:
  alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=120
```

**GKE-Ingress (GCLB):** `timeoutSec` der BackendConfig begrenzt die gesamte Dauer
einer WebSocket-Verbindung (Standard 30 s). Eine BackendConfig mit `timeoutSec: 3600`
anlegen und am Service `<release>` mit der Annotation `cloud.google.com/backend-config`
verknüpfen (das Chart hat dafür keinen eigenen Wert; der Service lässt sich nachträglich
annotieren).

**nginx vor Compose:**

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;  # map $http_upgrade → "upgrade"/"close"
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    client_max_body_size 100m;
}
```

Dazu in `.env`: `HERD_PUBLIC_URL=https://wiki.example`, `HERD_FORWARDED_ALLOW_IPS` auf
die Adresse des nginx, `HERD_COOKIE_SECURE=true`.

### Woran man Probleme erkennt

- Der Live-Editor bleibt bei „Verbindet …“ oder „Getrennt – neuer Versuch …“: Das
  Upgrade kommt nicht durch, oder der Collab-Prozess läuft nicht (`/health` auf Port
  1234 im Collab-Pod; in Compose ein Kindprozess der App). Ohne `HERD_INTERNAL_TOKEN`
  meldet der Editor, dass die Live-Bearbeitung ausgeschaltet ist.
- Im Browser HTTP 403 beim WebSocket: Origin passt nicht zu `HERD_PUBLIC_URL` bzw. zum
  Host.
- Close-Codes (in den Entwicklerwerkzeugen des Browsers): 4401 Sitzung ungültig, 4403
  kein Schreibrecht, 4404 Seite nicht sichtbar, 4409 Generation beendet, 4413 Zustand
  zu groß, 4502/4503 Collab-Prozess nicht erreichbar bzw. aus.
- Metriken auf Port 9090: `herd_collab_connections` (offene Verbindungen),
  `herd_collab_saves_total{result}` (Speicherungen: `saved`, `generation_ended`,
  `revoked`, `too_large`, `refused`).
