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
  sicheren Renderer wie im Wiki gezeigt (kein rohes HTML, nur erlaubte Link-Ziele;
  Bilder nur von dieser Installation, bei fremden Adressen steht nur der Bildtext).
  Eine Nachricht hat höchstens 20.000 Zeichen. Was man tippt, bleibt als Entwurf je
  Gespräch, solange der Tab offen ist.
- Gesendet wird sofort sichtbar; scheitert das Senden, steht an der Nachricht „Erneut
  senden“. Ein erneutes Senden schickt dieselbe Nachricht (gleiche `client_id`), nie eine
  zweite.
- Bearbeiten nur, wer die Nachricht geschrieben hat; Löschen sie oder ein Moderator.
  Eine gelöschte Nachricht zeigt „Diese Nachricht wurde gelöscht.“, ihre Antworten im
  Thread bleiben.
- **Threads:** „Im Thread antworten“ öffnet rechts die Thread-Leiste. Antworten zählen
  an der Nachricht („2 Antworten“). Die Nachricht selbst steht oben in der Leiste, auch
  wenn sie nicht im geladenen Verlauf ist (ältere Nachricht, Link aus der Aktivität oder
  der Suche): dann holt die Leiste sie einzeln (`GET /api/messages/{id}`, gleiche Rechte
  wie das Gespräch, sonst 404). Threads haben genau eine Ebene; das prüft auch die
  Datenbank (Trigger `message_one_level_threads`).
- **Erwähnungen:** `@` öffnet die Personenauswahl (aus dem Verzeichnis, nur wer den
  Bereich des Gesprächs sehen darf: `GET /api/directory?space_id=…`; in einer
  Direktnachricht nur deren Teilnehmende; das Eingabefeld ist dabei eine Combobox mit
  der Liste als Popup); im Text steht dann
  `@[Name](user:<id>)`. Entfernt eine Bearbeitung eine Erwähnung, verschwindet die noch
  ungelesene Benachrichtigung dieser Person; eine schon gelesene bleibt. Höchstens 50 je Nachricht. Benachrichtigt wird nur, wer das
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
Worker, nur in Seiten- und Aufgaben-Diskussionen (die Datenbank verhindert sie in
Kanälen und Direktnachrichten). Auf eine Systemmeldung antwortet niemand (422
`message.bad_parent`). Sie tragen die Zeit der Änderung (auch in ihrer ID), stehen also in
der Reihenfolge der Änderungen, auch wenn ein Worker sie später oder in anderer
Reihenfolge schreibt. Sie lassen sich weder bearbeiten noch löschen, zählen nicht als
ungelesen und benachrichtigen niemanden. Inhaltliche Änderungen (Markdown- oder
Live-Speichern) erzeugen keine Systemmeldung. Ein Import erzeugt keine Meldungen je
Seite; die Diskussionen importierter Seiten beginnen leer. Liegt eine Seite im
Papierkorb, ist auch ihre Diskussion für alle unsichtbar, bis die Seite wiederhergestellt
ist; endgültiges Löschen der Seite löscht die Diskussion mit.

### Aufgaben-Diskussion

Jede Aufgabe hat genau eine Diskussion, angelegt mit der Aufgabe
(`GET /api/tickets/{number}/thread`). Sehen darf sie, wer die Aufgabe sehen darf
(`ticket.read` im Bereich, ab Leser); schreiben, wer im Bereich schreiben darf
(`channel.post`). Wer den Bereich verlässt, sieht die Diskussion nicht mehr. Der Worker
schreibt je geänderte Eigenschaft eine Systemmeldung (angelegt, Status, Zuständigkeit,
Priorität, Art, übergeordnete Aufgabe, Fälligkeit, Titel, Beschreibung, Seite
verknüpft oder gelöst) mit altem und neuem Wert (Status-, Personen- und Aufgabennamen
und Seitentitel löst die API beim Lesen auf; eine Seite, die die lesende Person nicht
sehen darf, erscheint ohne Titel und ohne Kennung); Titel und Beschreibung werden nur
genannt, nie wiedergegeben. Tags an einer Aufgabe ergeben keine Systemmeldung. In
Kanäle und Direktnachrichten schreibt keine Aufgabe etwas. Mehr zu Tickets:
[`docs/TICKETS.md`](TICKETS.md).

### Aktivität

„Aktivität“ (Reiter „Für mich“) listet Erwähnungen und Antworten in Threads, an denen
man beteiligt ist (als Starter oder mit einer früheren Antwort), neueste zuerst; dazu
Zuweisungen einer Aufgabe durch jemand anderen (`assignment`, nicht wer sie selbst
übernimmt) und Beiträge in der Diskussion einer Aufgabe, die man bearbeitet oder
gemeldet hat (`ticket_comment`, nicht zusätzlich zu einer Erwähnung oder Antwort).
„Öffnen“ springt zur Nachricht, „Erledigt“ nimmt einen Eintrag aus der offenen Liste,
„Alle als gelesen markieren“ setzt den Zähler zurück. Eine Zuweisung zeigt, wer
zugewiesen hat, und keinen Textausschnitt (sie verweist auf die Systemmeldung im
Ticket-Thread). Der Zähler steht in der Seitenleiste und im Fenstertitel („(3) Herd“);
über 99 zeigen Zähler „99+“. Einträge zu Gesprächen, die man nicht
mehr sehen darf, oder zu gelöschten Nachrichten verschwinden. Weitere Gründe und Reiter
kommen mit Agenten (M6).

### Suche

Strg+K durchsucht Seiten, Nachrichten und (seit M4) Tickets zusammen: Kanäle lesbarer
Bereiche, eigene Direktnachrichten, Diskussionen sichtbarer Seiten und Tickets; eine
Eingabe wie `HC-42` oder `42` stellt das sichtbare Ticket mit dieser Nummer an den
Anfang (`GET /api/search`, siehe [`docs/TICKETS.md`](TICKETS.md#suche)). Nie gefunden werden fremde
Direktnachrichten (auch nicht während einer Einsicht), Systemmeldungen und gelöschte
Nachrichten. Mit „Nur in diesem Bereich“ fallen Direktnachrichten weg. Ein Treffer
öffnet das Gespräch an der Nachricht.

### Was live ankommt und was nicht

Live (ohne Neuladen, über `/api/stream`): neue, geänderte und gelöschte Nachrichten
und Thread-Antworten, Reaktionen, Lesestand aus anderen Tabs, neue Kanäle und
Kanaländerungen, Aktivität und ihr Zähler, Systemmeldungen der Seiten- und
Aufgaben-Diskussion, neue und geänderte Aufgaben (`ticket.created`, `ticket.updated`,
an alle, die Aufgaben im Bereich sehen dürfen; nur Kennungen),
der Hinweis auf eine Einsicht (an die Teilnehmenden, `dm.inspected`) und geänderter
Zugang: Wer in einen Bereich aufgenommen, daraus entfernt oder in der Rolle geändert
wird (direkt oder über eine Gruppe), oder wessen Gruppenmitgliedschaft sich ändert,
bekommt `access.changed`; der Browser lädt dann alles Gezeigte neu, ein nicht mehr
sichtbares Gespräch sagt sofort „Dieses Gespräch gibt es nicht (mehr) …“, und die
Seitenleiste vergisst es. Der Browser sammelt Ereignisse 250 ms und lädt danach jede
betroffene Ansicht einmal neu, nicht je Ereignis. Nach jeder Unterbrechung lädt er die
offenen Ansichten neu (`resync`); verpasste Ereignisse werden nicht nachgespielt.

Die Art eines Bereichs (offen, Team, persönlich) ändert sich nie (`PATCH` mit `kind`
ist 422); Zugang ändert sich nur über Mitgliedschaften, Rollen und Gruppen.

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
  LOCKED`). Der Worker braucht bis zu drei Datenbankverbindungen gleichzeitig (Stapel,
  Handler, Metriken) und eine weitere zum Lauschen auf `herd_outbox`.
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
  nach 7 Tagen gelöscht (je Minute höchstens 1.000); fehlgeschlagene bleiben in der
  Tabelle (Gauge `herd_outbox_failed`).
- **Zeitgrenze je Handler:** Jeder Handler-Aufruf hat höchstens
  `HERD_WORKER_HANDLER_TIMEOUT_SECONDS` (Standard 30 s), durchgesetzt in Python und in
  der Datenbank (`lock_timeout` und `statement_timeout` der Transaktion): Ein Handler,
  der an einer Sperre hängt, wird abgebrochen. Das zählt als gescheiterter Versuch
  (Log `outbox.handler_timeout`, Metrik `result="timeout"`), mit der üblichen Wartezeit.
  Ein Handler, der im Stapel einmal in die Zeitgrenze lief, wird für den Rest des
  Stapels übersprungen (dessen Ereignisse bleiben ohne gezählten Versuch fällig): Ein
  Hänger hält die anderen Handler höchstens eine Zeitgrenze lang auf.
- **Bereit (`/ready`)** ist der Worker, solange seine Schleife läuft, der letzte
  Durchlauf die Datenbank erreichte und er innerhalb von vier Zeitgrenzen (Standard
  120 s) einen Stapel abgeschlossen oder nichts Fälliges gefunden hat.
- **Ohne Worker** entstehen Nachrichten weiter, aber niemand bekommt sie live,
  Benachrichtigungen und Systemmeldungen bleiben aus; die Ereignisse warten und werden
  nachgeholt, sobald ein Worker läuft. Ein Browser sieht neue Nachrichten dann erst beim
  Neuladen (oder nach bis zu 60 s im offenen Gespräch). Der Alarm `HerdWorkerAbsent`
  meldet das.
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
- **Metriken** (Port 9090), nur von Prozessen mit Worker (Rolle `worker` oder `all`;
  ein API-Pod meldet sie nicht, statt eine leere Warteschlange vorzutäuschen), alle
  10 s aus der Datenbank gelesen, auch während ein Durchlauf hängt:
  `herd_outbox_pending` und `herd_outbox_oldest_pending_seconds` (offene Ereignisse,
  ältestes in Sekunden), `herd_outbox_failed` (aufgegebene Ereignisse in der Tabelle;
  übersteht Neustarts), `herd_worker_last_pass_timestamp_seconds` (Unix-Zeit des
  letzten abgeschlossenen Stapels oder Durchlaufs ohne Fälliges, je Worker), dazu
  `herd_outbox_dispatch_total{handler,result}` mit `ok`, `duplicate`, `error`,
  `timeout`, `failed`. Logs: `outbox.handler_failed` und `outbox.handler_timeout`
  (Warnung: Ereignis, Typ, Handler, Fehlerklasse), `outbox.failed`,
  `outbox.pass_failed`, `outbox.metrics_failed`.
- **Alarme** (PrometheusRule des Charts):
  - `HerdOutboxBacklog`: ältestes offenes Ereignis älter als 5 Minuten (kritisch).
  - `HerdOutboxFailed`: `herd_outbox_failed` ist in den letzten 15 Minuten gestiegen
    (Warnung); feuert auch 15 Minuten lang, wenn ein frisches Prometheus den Wert zum
    ersten Mal über 0 sieht. Ein Neustart oder neuer Pod mit gleichem Wert bleibt still.
  - `HerdWorkerStalled`: ein Worker hat seit mehr als 3 Minuten keinen Stapel
    abgeschlossen, 2 Minuten lang (Warnung, je Pod).
  - `HerdWorkerAbsent`: API-Pods laufen (`herd_sse_connections`), aber kein Worker
    ihres Releases meldet sich, 5 Minuten lang (kritisch; etwa `worker.replicas: 0`).
    Der Alarm ordnet Worker und API über die Service-Namen des Charts zu (Job
    `<release>-worker` gehört zu `<release>-internal`).

## Live-Zustellung (SSE)

Jeder Tab öffnet eine Verbindung `GET /api/stream` (Server-Sent Events) am öffentlichen
Port. Sie trägt nur IDs (`{conversation_id, message_id, parent_id}`), nie Inhalte; der
Browser lädt nach, was er zeigen will, mit seinen normalen Rechten.

- **Weg eines Ereignisses:** Commit → Worker → `publish_live` → `NOTIFY herd_live` →
  jeder API-Prozess (eine eigene `LISTEN`-Verbindung je Prozess, außerhalb des Pools)
  nimmt, was angekommen ist (bis 200 Ereignisse), prüft für diesen ganzen Stapel mit
  höchstens zwei Abfragen, welche seiner offenen Verbindungen welches Ereignis sehen
  dürfen (Sitzung gültig, Person aktiv, Gespräch jetzt sichtbar), und schickt es nur
  dorthin; was für eine Verbindung zusammen ansteht, geht in einem Schreibvorgang
  hinaus.
- **Nachhängen begrenzt:** Ist das älteste wartende Ereignis eines API-Prozesses älter
  als `HERD_LIVE_MAX_LAG_SECONDS` (Standard 5 s), verwirft der Prozess alles Wartende
  und schickt jeder Verbindung `resync` (Log `live.fell_behind`), statt immer später
  zuzustellen. Gemessen (100 Verbindungen, 50 Nachrichten/s, `docs/STECKBRIEF.md`).
- **Nach einem Verbindungsverlust** baut der Prozess die `LISTEN`-Verbindung nach 1 s
  wieder auf; die Wartezeit wächst (bis 30 s) nur, solange Versuche scheitern, und
  beginnt nach jeder funktionierenden Verbindung neu.
  Eine Nachricht, die an einem API-Knoten geschrieben wurde, kommt so auch an jedem
  anderen an (geprüft mit zwei echten Prozessen, `tests/test_live_two_nodes.py`).
- **Grenzen:** höchstens **5 Verbindungen je Anmeldung** und **10 je Person** (über alle
  ihre Anmeldungen) **je API-Prozess**; die nächste bekommt 429 `live.too_many_streams`,
  die Oberfläche sagt „Zu viele offene Fenster: Live-Aktualisierung pausiert“. Die
  Grenzen gelten je Prozess: Hinter einem Load Balancer kann eine Person je API-Pod
  zehn halten. Je Verbindung puffert der Prozess höchstens 100 Ereignisse; läuft der
  Puffer über, kommt `resync`.
- **Beenden:** Endet die Anmeldung (Abmelden, Ablauf, Deaktivierung), bekommt die
  Verbindung ab dem nächsten Ereignis nichts mehr und wird spätestens nach 30 s
  geschlossen; ein neuer Versuch bekommt 401. Bei SIGTERM schließt der API-Prozess seine
  Verbindungen zuerst; die Browser verbinden sich nach 5 s neu (`retry: 5000`), dann mit
  wachsender Wartezeit (5, 10, 30, 60 s).
- **Metriken:** `herd_sse_connections` (offene Verbindungen),
  `herd_live_events_total{type}` (empfangene Ereignisse je Typ), `herd_live_queue_depth`
  (empfangen, noch nicht verteilt), `herd_live_delivery_lag_seconds` (Histogramm: vom
  Eintreffen des `NOTIFY` bis zur Übergabe an die Verbindungen),
  `herd_live_resyncs_total{reason}` (`lag`, `overflow`, `reconnect`, `check_failed`).
  Logs: `live.payload_dropped`, `live.check_failed`, `live.deliver_failed`,
  `live.fell_behind`, `live.session_check_failed`, `listen.connection_lost`.
- **Bekannte Grenze (für M6 vorgemerkt):** Die Ungelesen-Zähler
  (`GET /api/conversations/unread`) zählen bei jedem Abruf alle ungelesenen Nachrichten
  je sichtbarem Gespräch; das kostet Zeit im Verhältnis zum Ungelesenen (gemessen
  13–22 ms bei 239, 187–237 ms bei 200.239 Ungelesenen in einem Kanal). Live-Ereignisse
  lösen den Abruf aus; der Browser bündelt sie (ein Abruf je 250 ms), die Zählung selbst
  ist noch nicht begrenzt.

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
   zusätzliche Datenbankverbindung (LISTEN) und höchstens zwei kurze Abfragen je Stapel
   von Ereignissen, wenn er Verbindungen dazu hält.

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
- „Zu viele offene Fenster“: mehr als 5 Tabs derselben Anmeldung (oder 10 derselben
  Person) am selben API-Prozess.
- `herd_outbox_oldest_pending_seconds` steigt dauerhaft: Ein Handler scheitert oder
  läuft in die Zeitgrenze (`outbox.handler_failed`, `outbox.handler_timeout` im Log des
  Workers), oder der Worker kommt nicht hinterher (mehr Worker-Replikas helfen).
- `herd_live_resyncs_total{reason="lag"}` steigt: Ein API-Prozess kommt mit dem Verteilen
  nicht nach (CPU des Pods, Datenbank); die Browser laden dann neu statt live zu
  bekommen. `herd_live_delivery_lag_seconds` zeigt, wie spät zugestellt wird.
