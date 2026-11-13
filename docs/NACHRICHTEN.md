# Nachrichten: Bedienung und Betrieb

Kanäle, Direktnachrichten, Seiten-Diskussionen und die Aktivität gibt es seit
Meilenstein 3. Diese Seite beschreibt, wer was darf, was live ankommt und was nicht,
die Einsicht der Verwaltung in Direktnachrichten, den Worker mit der Outbox und den
Betrieb der Live-Zustellung (SSE) hinter einem Reverse Proxy. Die Regeln selbst stehen
in der Spezifikation (Abschnitte 4.3, 5.3, 5.5, 6) und im Plan M3
(`docs/superpowers/plans/2026-11-13-m3-nachrichten.md`, „Entscheidungen“).

## Bedienung

### Gespräche und wer sie sieht

Die Seitenleiste zeigt über den Bereichen „Aktivität“, „Kanäle“ und
„Direktnachrichten“, jeweils mit Zähler für Ungelesenes (Erwähnungen hervorgehoben).

| Gespräch | sieht | schreibt |
|---|---|---|
| Kanal (`#name`) | wer den Bereich lesen darf | ab Leser (`channel.post`): schreiben, antworten, reagieren |
| Direktnachricht | nur die Teilnehmenden | die Teilnehmenden |
| Diskussion einer Seite | wer die Seite sehen darf (Entwürfe nur mit `page.edit`, nichts im Papierkorb) | wie in den Kanälen des Bereichs (`channel.post`) |

- **Kanäle** gehören zu einem Bereich. Anlegen, umbenennen und archivieren dürfen
  Moderatoren und Verwalter des Bereichs (`channel.manage`); sie dürfen auch fremde
  Nachrichten löschen (steht im Audit als `message.moderated`). Der Name ist 1 bis 80
  Zeichen lang und je Bereich eindeutig, ohne Rücksicht auf Groß- und Kleinschreibung.
  Persönliche Bereiche haben keine Kanäle. Der offene Bereich der Organisation hat ab
  der Einrichtung `#allgemein`. In einen archivierten Kanal schreibt niemand mehr.
  Umbenennen und Archivieren gibt es bisher nur über die API, nicht in der Oberfläche.
- **Direktnachrichten** haben 2 bis 9 Teilnehmende (man selbst und bis zu 8 weitere),
  die sich nie ändern. Gibt es das Gespräch dieser Personen schon, öffnet „Direktnachricht
  beginnen“ dasselbe. Gäste können in Direktnachrichten antworten, aber keine beginnen.
  Administratoren haben in fremden Direktnachrichten kein Leserecht, nur die Einsicht
  (unten).
- Wer ein Gespräch nicht sehen darf, für den gibt es es nicht: Die API antwortet mit
  404 `conversation.not_found`, nie mit 403, und weder Listen noch Zähler noch Suche
  nennen es.

### Nachrichten, Threads, Erwähnungen, Reaktionen

- Eingabe sendet, Umschalt+Eingabe beginnt eine neue Zeile. Markdown wird mit demselben
  sicheren Renderer wie im Wiki gezeigt (kein rohes HTML, nur erlaubte Link-Ziele).
  Eine Nachricht hat höchstens 20.000 Zeichen. Was man tippt, bleibt als Entwurf je
  Gespräch, solange der Tab offen ist.
- Gesendet wird sofort sichtbar; scheitert das Senden, steht an der Nachricht „Erneut
  senden“. Ein erneutes Senden schickt dieselbe Nachricht (gleiche `client_id`), nie eine
  zweite.
- Bearbeiten nur, wer die Nachricht geschrieben hat; Löschen sie oder ein Moderator.
  Eine gelöschte Nachricht zeigt „Diese Nachricht wurde gelöscht.“, ihre Antworten im
  Thread bleiben.
- **Threads:** „Im Thread antworten“ öffnet rechts die Thread-Leiste. Antworten zählen
  an der Nachricht („2 Antworten“). Die Nachricht selbst steht oben in der Leiste nur,
  wenn sie im geladenen Verlauf ist (es gibt keinen Abruf einer einzelnen Nachricht);
  sonst stehen dort nur die Antworten.
- **Erwähnungen:** `@` öffnet die Personenauswahl (aus dem Verzeichnis); im Text steht
  dann `@[Name](user:<id>)`. Höchstens 50 je Nachricht. Benachrichtigt wird nur, wer das
  Gespräch sehen darf; die anderen nennt der Composer („Nicht benachrichtigt: … – kann
  dieses Gespräch nicht sehen“). Ob jemand zu einem Bereich gehört, verrät das nicht:
  Unbekannte, deaktivierte und unberechtigte Personen werden gleich behandelt.
- **Reaktionen:** ein Emoji je Klick (Schnellauswahl in der Oberfläche; die API nimmt
  jedes einzelne Emoji bis 32 Codepunkte, keine Wörter). Nochmal klicken nimmt die
  eigene Reaktion zurück.
- **Gelesen:** Was im Gespräch sichtbar war, gilt als gelesen. Ungelesen zählen nur
  Nachrichten anderer auf oberster Ebene; Erwähnungen zählen auch in Threads. Die
  Markierung „Neu“ zeigt, wo das Ungelesene beim Öffnen anfing.

### Seiten-Diskussion und Systemmeldungen

Jede Wiki-Seite hat eine Diskussion (Schaltfläche „Diskussion“ an der Seite). Sie
enthält Beiträge und, grau, was mit der Seite geschah: angelegt, veröffentlicht,
verschoben, in den Papierkorb gelegt, wiederhergestellt, Version wiederhergestellt.
„Systemmeldungen ausblenden“ blendet diese Zeilen aus. Systemmeldungen schreibt nur der
Worker, nur in Seiten-Diskussionen (die Datenbank verhindert sie in Kanälen und
Direktnachrichten); sie lassen sich weder bearbeiten noch löschen, zählen nicht als
ungelesen und benachrichtigen niemanden. Inhaltliche Änderungen (Markdown- oder
Live-Speichern) erzeugen keine Systemmeldung. Ein Import erzeugt keine Meldungen je
Seite; die Diskussionen importierter Seiten beginnen leer. Liegt eine Seite im
Papierkorb, ist auch ihre Diskussion für alle unsichtbar, bis die Seite wiederhergestellt
ist; endgültiges Löschen der Seite löscht die Diskussion mit.

### Aktivität

„Aktivität“ (Reiter „Für mich“) listet Erwähnungen und Antworten in Threads, an denen
man beteiligt ist (als Starter oder mit einer früheren Antwort), neueste zuerst.
„Öffnen“ springt zur Nachricht, „Erledigt“ nimmt einen Eintrag aus der offenen Liste,
„Alle als gelesen markieren“ setzt den Zähler zurück. Der Zähler steht in der
Seitenleiste und im Fenstertitel („(3) Herd“). Einträge zu Gesprächen, die man nicht
mehr sehen darf, oder zu gelöschten Nachrichten verschwinden. Weitere Gründe und Reiter
kommen mit Aufgaben (M4) und Agenten (M6).

### Suche

Strg+K durchsucht Seiten und Nachrichten zusammen: Kanäle lesbarer Bereiche, eigene
Direktnachrichten, Diskussionen sichtbarer Seiten. Nie gefunden werden fremde
Direktnachrichten (auch nicht während einer Einsicht), Systemmeldungen und gelöschte
Nachrichten. Mit „Nur in diesem Bereich“ fallen Direktnachrichten weg. Ein Treffer
öffnet das Gespräch an der Nachricht.

### Was live ankommt und was nicht

Live (ohne Neuladen, über `/api/stream`): neue, geänderte und gelöschte Nachrichten
und Thread-Antworten, Reaktionen, Lesestand aus anderen Tabs, neue Kanäle und
Kanaländerungen, Aktivität und ihr Zähler, Systemmeldungen der Seiten-Diskussion.
Nach jeder Unterbrechung lädt der Browser die offenen Ansichten neu (`resync`); verpasste
Ereignisse werden nicht nachgespielt.

Nicht live (bekannte Lücken, zur Prüfung des Moduls vorgemerkt):

- **Zugang verloren:** Wer aus einem Bereich entfernt wird, bekommt ab dem nächsten
  Ereignis nichts mehr zugestellt, aber kein eigenes Ereignis. Eine offene Ansicht merkt
  es beim nächsten Abruf: spätestens nach 60 s (das offene Gespräch wird jede Minute
  neu geladen), beim Zurückkehren ins Fenster oder bei der nächsten Aktion; dann sagt
  sie „Dieses Gespräch gibt es nicht (mehr) …“ und die Seitenleiste vergisst es.
- **Hinweis auf eine Einsicht** erscheint bei den Teilnehmenden beim nächsten Laden des
  Gesprächs, nicht sofort.
- Eine einzelne Nachricht lässt sich nicht abrufen (siehe Threads); ein Link auf eine
  Antwort öffnet das Gespräch mit ihrem Thread.

## Einsicht in Direktnachrichten

Nur Inhaber und Administratoren (`dm.inspect`), unter „Verwaltung → Einsicht in
Direktnachrichten“ (Spezifikation 5.5, Plan M3 Entscheidung 6):

1. Person suchen. Die Liste ihrer Direktnachrichten (wer mit wem, wann zuletzt) steht
   als `dm.admin_lookup` im Audit, einmal je Suche.
2. Gespräch wählen und eine **Begründung** von 10 bis 500 Zeichen angeben (Leerraum am
   Rand zählt nicht). Ohne gültige Begründung keine Einsicht (422).
3. Die Einsicht gilt **60 Minuten** und nur für diese Person; sie zeigt alle Nachrichten
   einschließlich Thread-Antworten, neueste zuerst, **nur lesend** (keine Eingabe,
   keine Reaktion, kein Bearbeiten oder Löschen). Danach, oder für jemand anderes,
   antwortet die API 404 `dm_inspection.not_found`; eine neue Einsicht braucht eine neue
   Begründung.
4. Das Audit vermerkt `dm.admin_access` mit Begründung und Einsicht. Die Teilnehmenden
   sehen im Gespräch „Von der Verwaltung eingesehen am … (Name)“.

Die Einsicht macht die Administratorin nicht zur Teilnehmerin: Sie bekommt keine
Live-Ereignisse, keine Benachrichtigungen und keine Suchtreffer aus dem Gespräch.

## Worker und Outbox

Jede ändernde Aktion schreibt in derselben Transaktion ein Ereignis in `event_outbox`
(nur IDs, nie Inhalte). Der **Worker** verteilt es an die Handler: Benachrichtigungen
(`notify_on_message`), Systemmeldungen (`page_timeline`) und Live-Zustellung
(`publish_live`, ein `NOTIFY herd_live`). Bis M6 läuft der Verteiler ohne DBOS (Plan M3,
Entscheidung 1).

- **Rollen:** `HERD_ROLE=worker` ist ein eigener Prozess nur mit dem internen Port
  (`/health`, `/ready`, `/metrics` auf 9090). `HERD_ROLE=all` (Compose) startet den
  Worker im API-Prozess mit; er teilt sich dort den Datenbank-Pool der API (bewusst so).
  Mehrere Worker sind sicher: Sie holen getrennte Stapel (`FOR NO KEY UPDATE SKIP
  LOCKED`). Der Worker braucht zwei Datenbankverbindungen gleichzeitig (Stapel und
  Handler) und eine dritte zum Lauschen auf `herd_outbox`.
- **Zustellung mindestens einmal:** Jeder Handler läuft je Ereignis in einer eigenen
  Transaktion, die zugleich einen Zustellnachweis (`event_delivery`) schreibt. Stirbt der
  Worker mitten drin, bekommt beim nächsten Durchlauf nur der fehlende Handler das
  Ereignis noch einmal. Die Handler sind idempotent: keine doppelte Benachrichtigung,
  keine doppelte Systemmeldung.
- **Takt:** Der Worker wacht bei jedem Commit mit Ereignissen auf (`NOTIFY
  herd_outbox`), sonst alle 2 s; je Durchlauf höchstens 50 Ereignisse. Scheitert ein
  Handler, wartet das Ereignis 2^Versuche Sekunden (höchstens 5 Minuten) und geht dann
  nur an die fehlenden Handler; nach 10 gescheiterten Durchläufen ist es
  „fehlgeschlagen“ (Log `outbox.failed`, ohne Nutzlast). Verteilte Ereignisse werden
  nach 7 Tagen gelöscht (je Minute höchstens 1.000).
- **Ohne Worker** entstehen Nachrichten weiter, aber niemand bekommt sie live,
  Benachrichtigungen und Systemmeldungen bleiben aus; die Ereignisse warten und werden
  nachgeholt, sobald ein Worker läuft. Ein Browser sieht neue Nachrichten dann erst beim
  Neuladen (oder nach bis zu 60 s im offenen Gespräch).
- **Handler-Module importieren:** Der Worker kennt nur Handler, deren Modul geladen
  ist. Jedes Modul mit Handlern gehört in `backend/app/worker/handlers.py`, das
  `app/worker/main.py` vor dem Start importiert; ein Test startet einen frischen Prozess,
  der nur den Worker importiert.
- **Chart und Compose:** Im Chart ist der Worker ein eigenes Deployment
  `<release>-worker` (`worker.replicas`, Standard 1; `worker.env`, `worker.resources`)
  mit headless Service `<release>-worker` für den ServiceMonitor; seine NetworkPolicy
  erlaubt nur DNS und die Datenbank. In Compose steckt er in `app` (Rolle `all`); die
  Überlagerung `deploy/compose/compose.nodes.yml` startet ihn als eigenen Dienst neben
  zwei API-Knoten (`SMOKE_NODES=1 bash deploy/compose/smoke.sh` prüft damit: Nachricht
  an Knoten A, Ereignis im Stream von Knoten B).
- **Metriken** (Port 9090): `herd_outbox_pending` und
  `herd_outbox_oldest_pending_seconds` (offene Ereignisse, ältestes in Sekunden),
  `herd_outbox_dispatch_total{handler,result}` mit `ok`, `duplicate`, `error`, `failed`.
  Logs: `outbox.handler_failed` (Warnung: Ereignis, Typ, Handler, Fehlerklasse),
  `outbox.failed`, `outbox.pass_failed`. Die Gauges berechnet nur ein Prozess mit
  Worker; API-Pods melden sie als 0 (Dashboards auf den Job des Workers filtern).
- **Alarme** (PrometheusRule des Charts): `HerdOutboxBacklog` (ältestes offenes Ereignis
  älter als 5 Minuten, kritisch) und `HerdOutboxFailed` (ein Ereignis wurde nach allen
  Versuchen aufgegeben, Warnung; feuert auch einmal, wenn ein frisches Prometheus einen
  Worker mit früheren Fehlschlägen zum ersten Mal abfragt). Ein auf 0 Replikas
  skalierter Worker löst keinen Alarm aus, ebenso wenig ein Durchlauf, der hängt, ohne
  einen Fehler zu melden (der Gauge bleibt dann auf dem letzten Wert).

## Live-Zustellung (SSE)

Jeder Tab öffnet eine Verbindung `GET /api/stream` (Server-Sent Events) am öffentlichen
Port. Sie trägt nur IDs (`{conversation_id, message_id, parent_id}`), nie Inhalte; der
Browser lädt nach, was er zeigen will, mit seinen normalen Rechten.

- **Weg eines Ereignisses:** Commit → Worker → `publish_live` → `NOTIFY herd_live` →
  jeder API-Prozess (eine eigene `LISTEN`-Verbindung je Prozess, außerhalb des Pools)
  prüft mit einer Abfrage je Ereignis, welche seiner offenen Verbindungen es sehen dürfen
  (Sitzung gültig, Person aktiv, Gespräch jetzt sichtbar), und schickt es nur dorthin.
  Eine Nachricht, die an einem API-Knoten geschrieben wurde, kommt so auch an jedem
  anderen an (geprüft mit zwei echten Prozessen, `tests/test_live_two_nodes.py`).
- **Grenzen:** höchstens **5 Verbindungen je Anmeldung und API-Prozess** (die sechste
  bekommt 429 `live.too_many_streams`, die Oberfläche sagt „Zu viele offene Fenster:
  Live-Aktualisierung pausiert“). Die Grenze gilt je Prozess: Hinter einem Load
  Balancer kann eine Anmeldung je API-Pod fünf halten. Je Verbindung puffert der
  Prozess höchstens 100 Ereignisse; läuft der Puffer über, kommt `resync`.
- **Beenden:** Endet die Anmeldung (Abmelden, Ablauf, Deaktivierung), bekommt die
  Verbindung ab dem nächsten Ereignis nichts mehr und wird spätestens nach 30 s
  geschlossen; ein neuer Versuch bekommt 401. Bei SIGTERM schließt der API-Prozess seine
  Verbindungen zuerst; die Browser verbinden sich nach 5 s neu (`retry: 5000`), dann mit
  wachsender Wartezeit (5, 10, 30, 60 s).
- **Metriken:** `herd_sse_connections` (offene Verbindungen),
  `herd_live_events_total{type}` (zugestellte Ereignisse je Typ). Logs:
  `live.payload_dropped`, `live.check_failed`, `live.deliver_failed`,
  `live.session_check_failed`, `listen.connection_lost`.

### Betrieb hinter einem Reverse Proxy

`/api/stream` ist eine gewöhnliche, lange GET-Antwort (`text/event-stream`). Daraus
folgt für Proxy und Ingress:

1. **Pufferung aus.** Die App sendet `X-Accel-Buffering: no` (nginx und ingress-nginx
   halten sich daran) und `Cache-Control: no-store`. Ein Proxy, der Antworten sammelt
   oder komprimiert, hält die Ereignisse zurück, bis der Puffer voll ist: dort für
   `/api/stream` Pufferung und Kompression ausschalten.
2. **Lese-Timeout:** Die App schickt alle 15 s einen Kommentar (`: ping`). Jedes
   Leerlauf-Timeout über 15 s genügt; empfohlen ist 1 h, damit ruhige Verbindungen nicht
   ständig neu aufgebaut werden. Ein Limit für die gesamte Dauer einer Antwort (etwa
   `timeoutSec` am GKE-Ingress) beendet die Verbindung regelmäßig; der Browser verbindet
   sich dann nach 5 s neu und lädt nach, es geht nichts verloren.
3. **HTTP/2 zum Browser.** Browser erlauben über HTTP/1.1 nur 6 Verbindungen je Host;
   jeder Tab hält eine davon dauerhaft. Mit mehreren Tabs warten dann andere Anfragen.
   TLS mit HTTP/2 am Proxy behebt das (zur App darf es HTTP/1.1 bleiben).
4. **Mehrere API-Replikas:** keine Sticky Sessions nötig. Jeder Pod braucht eine
   zusätzliche Datenbankverbindung (LISTEN) und eine kurze Abfrage je Ereignis, wenn er
   Verbindungen dieser Organisation hält.

Beispiel nginx vor Compose (zusätzlich zu dem Block für die Live-Bearbeitung in
[`WIKI.md`](WIKI.md#betrieb-hinter-einem-reverse-proxy)):

```nginx
location /api/stream {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    gzip off;
    proxy_read_timeout 1h;
}
```

ingress-nginx: `nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"` und
`proxy-send-timeout: "3600"` (so in `deploy/helm/to-herd-cats-ai/ci/production-values.yaml`;
die Pufferung schaltet der Header der App je Antwort ab). Das Chart setzt keine
Annotation von sich aus; `values.yaml` beschreibt sie bei `ingress.annotations`. Wie bei der Live-Bearbeitung folgen diese Hinweise den
Dokumentationen der Controller; geprüft sind hier nur der direkte Zugriff und Compose.

### Woran man Probleme erkennt

- Neue Nachrichten erscheinen erst nach Neuladen oder nach einer Minute: Der Worker
  läuft nicht (`/ready` des Workers, `herd_outbox_pending` wächst) oder der Proxy puffert
  `/api/stream` (in den Entwicklerwerkzeugen kommen keine Ereignisse an, obwohl die
  Verbindung offen ist).
- „Live-Aktualisierung unterbrochen – neuer Versuch …“: Die Verbindung bricht ab (Proxy-
  Timeout, Neustart eines Pods); bei jedem Wiederaufbau lädt der Browser nach.
- „Zu viele offene Fenster“: mehr als 5 Tabs derselben Anmeldung am selben API-Prozess.
- `herd_outbox_oldest_pending_seconds` steigt dauerhaft: Ein Handler scheitert
  (`outbox.handler_failed` im Log des Workers) oder der Worker kommt nicht hinterher
  (mehr Worker-Replikas helfen).
