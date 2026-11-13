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
| Leser (`viewer`) | veröffentlichte Seiten in ihrer aktuellen Fassung lesen, exportieren, suchen (keine Versionsgeschichte) |
| Autor (`editor`) | dazu Seiten anlegen, bearbeiten (Markdown und live), umbenennen, verschieben, Tags setzen, Anhänge hochladen; Versionen ansehen, vergleichen, benennen und wiederherstellen; Entwürfe aller sehen, eigene veröffentlichen |
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
  haben, sehen die Änderungen der anderen sofort, dazu Namen und Cursor (Name und
  Farbe setzt der Server aus der Anmeldung; niemand kann sich als jemand anderes
  ausgeben oder den Eintrag eines anderen überschreiben). Gespeichert
  wird automatisch (höchstens alle 2 s, spätestens nach 10 s); die Statusanzeige zeigt
  „Synchronisiert“, „Speichert …“ oder „Getrennt“. **Fertig** speichert sofort und
  zeigt danach die Seite so, wie der Server sie hat; kann der Server das nicht
  bestätigen (z. B. API kurz weg), bleibt der Editor offen und sagt das. Leser bekommen
  diese Schaltfläche nicht. Der Collab-Prozess bestätigt jeder Verbindung jeden
  gespeicherten Stand; solange eine eigene Änderung nicht in einem bestätigten Stand
  steckt, wird beim Verlassen erst gespeichert: Wer innerhalb der App weitergeht (Link,
  Seitenbaum, Zurück), dessen Änderungen speichert der Editor sofort, und gefragt wird
  nur, wenn der Server das nicht bestätigt. Die Frage sagt, warum: Änderungen nicht
  beim Server angekommen (Verbindung unterbrochen), Stand lässt sich nicht speichern
  (Hinweis), oder Speichern nicht bestätigt. Neu laden und Tab schließen können nicht
  warten; der Browser fragt dann mit seiner eigenen Meldung, solange eine Änderung
  nicht bestätigt ist (was beim Server angekommen ist, speichert er beim Trennen
  trotzdem). Ohne eigene Änderung fragt nichts, auch nicht während „Verbindet …“ oder
  des ersten Abgleichs. „Fertig“ wartet auf die Bestätigung.
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
  (bis 20.000 Zeilen), benennen und wiederherstellen (als neue Version). Die
  Versionsgeschichte sieht nur, wer die Seite bearbeiten darf; Leser sehen nur die
  aktuelle veröffentlichte Fassung, nie Entwurfsstände oder deren Autoren.
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
- **Links beim Tippen:** Zum Link wird beim Tippen oder Einfügen nur, was mit
  `http://`, `https://` oder `www.` beginnt, wie die Seitenansicht es verlinkt;
  Dateinamen und Wörter mit Punkt (`README.md`, `app.py`, `example.com`) bleiben Text.
  Einen Link nimmt die Schaltfläche „Link entfernen“ der Werkzeugleiste wieder weg (der
  Text bleibt); aus dem Text erreicht man sie mit Umschalt+Tab.
- **Unverändert durchgereicht:** Was der Editor nicht darstellen kann (rohes HTML,
  Referenzlinks, Fußnoten, verlinkte Bilder und Ähnliches), erscheint dort als
  Codeblock und wird beim Speichern genau so zurückgeschrieben, wie es kam. Ebenso jeder
  Block, den der Editor sonst anders zurückschreiben würde, als er gemeint war.
- **Umgeschrieben, aber gleichbedeutend:** Nach einer Live-Speicherung kann das Markdown
  anders aussehen als vorher: Tabellen stehen kompakt (eine Leerstelle um jede Zelle,
  kein Auffüllen auf Spaltenbreite), Listen- und Hervorhebungszeichen werden
  vereinheitlicht (`*` → `-` bei Listen, `*kursiv*` → `_kursiv_`, `__fett__` →
  `**fett**`; folgt eine Liste direkt auf eine andere, nimmt sie das andere Zeichen,
  damit es zwei bleiben), Setext- werden ATX-Überschriften, eingerückter Code wird zum
  Codeblock mit Zäunen, lockere Listen werden eng, wo der Inhalt das zulässt, benannte
  Zeichen wie `&copy;` stehen als Zeichen (`©`), Adressen im Text als `<https://…>` bzw.
  `<name@example.org>`, Zeichen mit Markdown-Bedeutung im Text werden maskiert (aus
  `[x]` wird `\[x\]`, Wiki-Links ausgenommen). Die Seitenansicht zeigt danach dasselbe;
  der Diff der Versionen zeigt die Schreibweise als Änderung, aber erst, wenn jemand
  live etwas geändert hat.
- **Wiki-Links** `[[Titel]]` gelten nur im Text, wie die Seitenansicht sie liest: in
  Code, Codeblöcken und in Link-Texten sind sie keine. Ein `(` direkt nach `]]` wird
  maskiert, damit kein Link daraus wird.
- **Tabellen** sind, wie GFM sie kennt: Zellen halten eine Zeile Text (Markdown hat
  keine Zeilenumbrüche in Zellen), Enter, Umschalt+Enter und Strg+Enter fügen dort
  nichts ein. Wird in eine Zelle mehr als eine Zeile eingefügt (Text, Absätze, Zeilen
  oder Spalten einer Tabellenkalkulation), kommt alles in diese Zelle, Zeilen und
  Tabulatoren durch je ein Leerzeichen getrennt; die Tabelle bleibt eine. Die erste Zeile ist die Kopfzeile. Jede Zeile ist so breit wie die
  breiteste: eine kürzere bekommt leere Zellen am Ende, und hat eine Zeile mehr Zellen
  als die Kopfzeile, bekommt die Kopfzeile leere Zellen am Ende (jede Zelle bleibt über
  ihrer Überschrift; die Seitenansicht zeigte die überzähligen Zellen nicht).
  Verbundene Zellen gibt es nicht: eine eingefügte Tabelle mit `colspan`/`rowspan` wird
  vorher aufgeteilt, der Inhalt steht in der ersten Zelle. Eine Spalte hat eine
  Ausrichtung, die ihrer Kopfzelle; eine mit Tab angefügte Zeile übernimmt sie.
- **Bilder** stehen im Text wie in Markdown; `![Alt](adresse)` getippt wird zum Bild.
  Wie Links nur mit `http`-, `https`- und relativen Adressen, wie die Seitenansicht sie
  zeigt: ein eingefügtes oder getipptes Bild aus `blob:`, `file:` oder `data:` nimmt der
  Editor nicht an, und ein solches Bild im gespeicherten Markdown erscheint als
  Codeblock (die Seitenansicht zeigt es nicht). Schickt ein anderer Client trotzdem ein
  solches Bild in den gemeinsamen Stand, lädt der Editor es nicht (er zeigt nur die
  Stelle), und speichern lässt sich dieser Stand nicht.
- **Speicherprüfung:** Vor jeder Live-Speicherung liest der Collab-Prozess das Markdown,
  das er schreiben will, wieder ein und vergleicht es mit dem Dokument im Editor;
  außerdem muss es die Prüfung beim Öffnen (unten) bestehen. Fällt eine der beiden
  durch, wird dieser Stand nicht gespeichert: das zuletzt gespeicherte Markdown bleibt,
  `herd_collab_saves_total{result="unrepresentable"}` zählt mit, und alle im Editor
  sehen einen Hinweis („Der aktuelle Stand lässt sich so nicht als Markdown
  speichern …“), die Sitzung läuft weiter. Der Hinweis nennt die Art der Ursache
  (würde als Markdown anders gelesen; ließe sich live nicht wieder öffnen; Aufbau
  ungültig) und, soweit die Prüfung es weiß, den Block (Nummer und Textanfang): den
  ersten, der auch allein durchfällt, sonst die ersten zwei Nachbarn, die nur zusammen
  durchfallen. Bei „würde anders gelesen“ nennt er, wenn bekannt, die Art (Code mit
  Backslash in einer Tabellenzelle; eine Adresse, die die Seite anders verlinkt; eine
  Liste, die als anderer Block gelesen würde) mit einem passenden Beispiel, sonst keins.
  Wer den Editor so verlässt, wird gefragt.
  Sobald ein späterer Stand gespeichert ist, verschwindet der Hinweis. Bekannter Fall:
  Code in einer Tabellenzelle mit einem Backslash direkt vor `|` (GFM liest `\|` dort
  als maskierten Strich und `\\|` als Zellenende; kein Markdown sagt das). Geprüft
  wird das mit erzeugten Dokumenten (`collab/test/generative.test.mjs`, 2.000 je Lauf;
  ein Lauf über 20.000 fand nach den Korrekturen keinen weiteren Fall).
- **Sicherheitsnetz:** Bevor eine Seite live geöffnet wird, liest der Collab-Prozess
  ihr Markdown mit demselben Parser wie die Seitenansicht (micromark mit GFM), wandelt
  es in den Editor und zurück und vergleicht beide Syntaxbäume (Leerraum innerhalb von
  Text und eng/locker bei Listen zählen nicht). Weichen sie ab, wird der betroffene
  Block als Codeblock unverändert durchgereicht; geht auch das nicht, öffnet der
  Live-Editor die Seite nicht (Close-Code 4422) und bietet den Markdown-Editor an. Das
  betrifft nur Ausgefallenes, etwa einen eingerückten Codeblock direkt vor einer mit 0
  beginnenden nummerierten Liste aus HTML. Als Codeblock bleiben unter anderem
  nummerierte Aufgabenlisten (`1. [ ] …`), die der Editor nicht kennt, und Listen, die
  Aufgaben und gewöhnliche Punkte mischen (`- [ ] eins` / `- zwei`): Der Editor hat
  dafür zwei Listenarten, aus einer Liste würden zwei. Eine Listenart mit wahlweisem
  Kästchen würde das beheben, ist aber eine Änderung am gespeicherten Live-Format und
  steht noch aus. Ebenso bleiben fettgedruckte oder verlinkte Bilder Codeblöcke.
- **Öffnen ohne Ändern ändert nichts:** Wer den Live-Editor öffnet und ohne Eingabe
  wieder schließt, erzeugt weder eine Version noch ein anderes Markdown. Auch eine
  Änderung, die wieder zurückgenommen wurde, lässt das gespeicherte Markdown, wie es war.
  Dafür lässt der Collab-Prozess den Editor des Browsers ohne Oberfläche über das
  Dokument laufen, bevor er es ausliefert (`collab/settle.mjs`): was dessen Erweiterungen
  beim Laden ändern würden (Tabellen ausgleichen, Adressen verlinken …), steckt schon im
  ausgelieferten Dokument, sofern es die Bedeutung nicht ändert; sonst wird der Block
  ein Codeblock bzw. ein gespeicherter Live-Stand nicht geöffnet (4422). Als letztes Netz
  schickt der Browser keine Änderung, die nicht aus einer Eingabe stammt (Tastatur,
  Einfügen, Ziehen, Werkzeugleiste): Ändert sein Editor das Dokument trotzdem von
  selbst, beendet er die Sitzung mit dem Hinweis, dass er die Seite nicht unverändert
  darstellen kann, und meldet das (`herd_collab_load_mutations_total`, soll 0 sein).
- **Leerraum:** Mehrere Leerzeichen, Leerzeichen am Zeilenanfang und leere Absätze zeigt
  der Editor, die Seitenansicht nicht: Markdown fasst sie zusammen, und die
  Speicherprüfung vergleicht, was die Seitenansicht zeigt.
- **Adressen ohne Leerzeichen danach:** Eine Adresse, die direkt am Ende eines Absatzes,
  mitten in einem Wort oder mit einem Satzzeichen direkt danach getippt wird
  (`(https://example.org/x).`), und eine E-Mail-Adresse sind im Editor Text, auf der
  Seite aber ein Link (GFM verlinkt sie). Beim nächsten Öffnen zeigt auch der Editor den Link, und die
  nächste Speicherung schreibt `<https://…>`. Markdown kann „nicht verlinkt“ dort nicht
  ausdrücken (`collab/autolink.mjs`).
- **Nicht vorhanden:** Unterstreichen (kein Markdown dafür), eigene Größen oder
  Farben, eingebettete Inhalte.
- Ein Live-Zustand hat höchstens 5 MiB und 200.000 Zeichen Markdown, ein
  WebSocket-Frame höchstens einen ganzen Zustand (5 MiB + 64 KiB: wer einer Seite
  beitritt, bekommt den Zustand in einer Nachricht; die API reicht genau so viel durch
  wie der Collab-Prozess annimmt, beide aus derselben Zustandsgrenze). Eine Seite, deren
  Zustand schon beim Öffnen darüber läge, öffnet der Live-Editor nicht (4413). Nahe der Grenze misst der Collab-Prozess vor jeder
  Änderung genau, wie groß die Seite damit würde (höchstens einmal je Sekunde und
  Seite; eine weitere Änderung in derselben Sekunde wartet bis zur nächsten Messung);
  eine Änderung darüber wird abgelehnt, nur für die Person, die sie geschickt hat
  (4413), die anderen arbeiten weiter. Größere Seiten bearbeitet man im
  Markdown-Editor; der Live-Editor sagt das dann.
- **Große Seiten:** Das Öffnen und die Speicherprüfung einer Seite von 200.000 Zeichen
  dauern einige Sekunden. Sie laufen in eigenen Threads des Collab-Prozesses
  (`HERD_COLLAB_CHECK_WORKERS`, Standard 1), damit alle anderen Live-Seiten
  währenddessen flüssig bleiben; bereits geprüfte Blöcke werden nicht erneut geprüft.
  Ein Thread prüft eine Seite nach der anderen; wartende Prüfungen kommen nach Größe
  dran, die kleinste zuerst, damit eine kleine Seite nicht hinter großen wartet. Eine
  große Prüfung wird höchstens viermal überholt, dann ist sie dran (sie wartet also nie
  endlos). Jeder dieser Threads hat höchstens 192 MB Heap (im Speicherlimit
  eingeplant, siehe „Speicher des Collab-Prozesses“). Braucht eine Prüfung mehr, endet
  nur diese Prüfung, und sie wird nicht wiederholt: Die Seite ist dann zu groß für die
  Live-Bearbeitung (4413, Markdown-Editor), bzw. ein solcher Stand wird nicht
  gespeichert und alle sehen den Hinweis (Ursache unbekannt). Der Thread wird ersetzt,
  und die Prüfungen, die auf ihn warteten, laufen auf dem neuen; andere Seiten merken
  davon nur die Wartezeit. Jeder weitere Thread braucht bis zu rund 250 MB mehr.
- **Zeitlimit der Prüfung:** Eine Prüfung darf höchstens
  `HERD_COLLAB_CHECK_TIMEOUT_SECONDS` dauern (Standard 10). Danach wird ihr Thread
  beendet und ersetzt, wie beim Speichermangel: Beim Öffnen ist die Seite „zu groß oder
  zu aufwendig“ für die Live-Bearbeitung (4413, Markdown-Editor, nichts gespeichert,
  dieselbe Seite wird danach sofort abgelehnt, ohne neue Prüfung); beim Speichern wird
  der Stand nicht gespeichert, und alle sehen den Hinweis „Prüfung hat zu lange
  gedauert“. Die Prüfungen, die warteten, laufen auf dem neuen Thread; eine kleine Seite
  wartet so höchstens das Zeitlimit und den Start eines Threads (gemessen: Limit + rund
  0,3 s). Solange die Seite einer Verbindung noch geöffnet wird, schließt der
  Collab-Prozess sie nicht wegen des Handshake-Timeouts (10 s), höchstens zwei Zeitlimits
  länger. Aufwendig sind vor allem sehr viele Hervorhebungen in einem einzigen Absatz:
  Der Markdown-Parser (micromark, wie in der Seitenansicht) braucht dafür Zeit, die mit
  ihrer Zahl quadratisch wächst (40.000 `*a*` in einem Absatz: rund 8 s je Lesen, das
  Öffnen liest die Seite mehrmals).
- **Speicher des Collab-Prozesses:** Eine live geöffnete Seite kostet den
  Collab-Prozess ein Vielfaches ihres gespeicherten Umfangs. Gemessen (RSS, ein
  Prüf-Thread, 1 bis 12 Seiten zugleich geöffnet): 190.000 Zeichen Text rund 18 MB je
  Seite, 5.000 Tabellenzellen rund 25 MB, 9.600 Zellen rund 45 MB; dazu einmal der
  Prozess mit leerem Prüf-Thread (rund 130 MB) und der Prüf-Thread nach einer großen
  Prüfung (bis rund 250 MB, sein Heap ist auf 192 MB begrenzt). Der Collab-Prozess
  schätzt je geladener Seite 0,5 MB + 30 × Bytes des Live-Zustands + 3 KB je
  Tabellenzelle (etwas über dem Gemessenen; vor dem Laden aus dem gespeicherten Zustand
  oder 4 Bytes je Markdown-Zeichen + 100 je Zelle) und lädt keine weitere Seite, wenn
  die Summe `HERD_COLLAB_MEMORY_BUDGET_MB` (Standard 400) überschritte: Wer sie dann
  öffnet, sieht „Der Live-Editor ist gerade ausgelastet … Versuche es gleich noch
  einmal, oder bearbeite die Seite im Markdown-Editor“ (Close-Code 4507; der Browser
  verbindet sich nicht von selbst neu, „Neu laden“ und der Markdown-Editor werden
  angeboten; gespeichert wird nichts). Die erste Seite wird immer geladen. Verlässt die
  letzte Person eine Seite, wird sie entladen, sobald gespeichert ist, und ihre
  Schätzung freigegeben. Metriken am Port des
  Collab-Prozesses (`/metrics`, im Chart über den ServiceMonitor; in Rolle `all` am
  internen Port 9090 der App mit ausgegeben): `herd_collab_memory_estimate_bytes`,
  `herd_collab_memory_budget_bytes`, `herd_collab_memory_refusals_total`,
  `herd_collab_documents`.
  **Faustregel für das Speicherlimit:** Limit ≥ (130 MB + 250 MB × Prüf-Threads +
  Budget) / 0,8. Mit den Standards (ein Thread, Budget 400) sind das 975 MB: Chart und
  `compose.nodes.yml` setzen 1Gi. Wer das Budget erhöht, erhöht das Limit mit.
  In Rolle `all` (Compose mit einem Container) ist der Collab-Prozess ein Kindprozess;
  endet er (etwa weil der Kernel ihn wegen Speichermangels beendet), beendet sich die
  ganze App mit Code 3, und der Orchestrator (`restart: unless-stopped`, Kubernetes)
  startet sie neu. Das ist gewollt: Ohne Collab-Prozess wäre die Live-Bearbeitung
  still aus.
- **Tabellenzellen:** Die Tabellen einer Seite dürfen live zusammen höchstens 5.000
  Zellen haben (jede Zelle kostet im Live-Zustand rund hundert Bytes und im Speicher des
  Collab-Prozesses rund 1,5 KB, solange die Seite offen ist; die Prüfung sehr großer
  Tabellen sprengte den Thread, und wenige offene Seiten mit 9.600 Zellen brachten den
  Prozess über 512 MiB). Größere Tabellen bearbeitet man als Markdown-Quelltext im
  Markdown-Editor. Gezählt wird vor jeder Prüfung, ohne
  Thread: Eine Seite darüber öffnet der Live-Editor nicht (4413, „zu groß“, mit dem
  Angebot des Markdown-Editors); ein Stand darüber wird nicht gespeichert, alle sehen
  „zu groß für die Live-Bearbeitung“ mit dem betroffenen Block, und die Sitzung läuft
  weiter, damit man Zeilen wieder herausnehmen kann. Im Markdown-Editor gilt nur die
  Grenze von 200.000 Zeichen.
- **Abmelden:** Eine offene Live-Verbindung endet mit der nächsten Prüfung, also bis zu
  5 s nach dem Abmelden; was in diesen Sekunden noch ankommt, wird unter dem Namen der
  Person gespeichert. Sie hatte das Recht dazu (sonst wäre es ein Rechteentzug und
  würde verworfen); das ist so entschieden (Prüfung M2, S9).

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
   Leerlaufende HTTP-Verbindungen (Keep-Alive) hält die App `HERD_KEEP_ALIVE_SECONDS`
   lang offen (Standard 150, erlaubt 5 bis 3600; ein anderer Wert ist ein Startfehler).
   Regel: **länger als das Leerlauf-Timeout des Proxys zu seinen Upstreams.** Ein
   Proxy, der Verbindungen zur App wiederverwendet, muss sie früher schließen als die
   App, sonst trifft eine Anfrage gelegentlich eine Verbindung, die die App gerade
   schließt (502 vom Proxy). Ab Werk passen mit 150 s nginx und ALB (60 s), Traefik
   (90 s) und Caddy (120 s). Google-Load-Balancer halten Backend-Verbindungen 600 s:
   dort etwa `HERD_KEEP_ALIVE_SECONDS=620`; wer das Leerlauf-Timeout eines ALB
   hochsetzt, setzt den Wert darüber.
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
  1234 im Collab-Pod; in Compose ein Kindprozess der App). Endet der Aufbau dreimal in
  Folge mit 1011 (Serverfehler, etwa eine Nachricht, die ein Proxy dazwischen nicht
  durchlässt), hört der Editor auf und bietet den Markdown-Editor an („bricht beim
  Laden immer wieder mit einem Serverfehler ab“). Ohne `HERD_INTERNAL_TOKEN`
  meldet der Editor, dass die Live-Bearbeitung ausgeschaltet ist.
- Im Browser HTTP 403 beim WebSocket: Origin passt nicht zu `HERD_PUBLIC_URL` bzw. zum
  Host.
- Close-Codes (in den Entwicklerwerkzeugen des Browsers): 4401 Sitzung ungültig, 4403
  kein Schreibrecht, 4404 Seite nicht sichtbar, 4409 Generation beendet, 4413 Zustand
  zu groß, 4422 Seite nicht verlustfrei live bearbeitbar, 4429 zu viele Verbindungen
  (je Anmeldung 3 je Seite und 10 insgesamt, je Person 20 über alle Anmeldungen, nie
  mehr als ein Viertel aller), 4507 Live-Editor ausgelastet (Speicherbudget des
  Collab-Prozesses, siehe oben), 4408/4504 Verbindungsaufbau zu langsam oder 15 Minuten
  nichts gesendet (der Browser verbindet sich neu),
  4502/4503 Collab-Prozess nicht erreichbar bzw. aus.
- Metriken auf Port 9090: `herd_collab_connections` (offene Verbindungen),
  `herd_collab_saves_total{result}` (Speicherungen: `saved`, `generation_ended`,
  `revoked`, `too_large`, `refused`, `unrepresentable`: ein Stand, der sich nicht als
  Markdown speichern ließ), `herd_collab_load_mutations_total` (Editoren im Browser,
  die ein gerade geladenes Dokument von selbst geändert hätten und deshalb beendet
  wurden; jeder Wert über 0 ist ein Fehler im Editor). Am Port 1234 des
  Collab-Prozesses (`/metrics`; in Rolle `all` mit auf 9090): das Speicherbudget
  (`herd_collab_memory_estimate_bytes`, `…_budget_bytes`, `…_refusals_total`,
  `herd_collab_documents`). Steigen die Ablehnungen, ist das Budget zu klein für die
  Nutzung: Budget und Speicherlimit gemeinsam erhöhen (Faustregel oben).
