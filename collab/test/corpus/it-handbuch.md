IT-Handbuch
===========

Kurzanleitung für häufige Aufgaben. Befehle stehen in `Code`, Platzhalter in
spitzen Klammern: `ssh <benutzer>@<host>`.

Drucker einrichten
------------------

1. Systemeinstellungen öffnen
2. Drucker hinzufügen:

   ```bash
   lpadmin -p buero -E -v ipp://drucker.local/ipp/print
   ```

   Danach den Treiber *Generic PostScript* wählen.
3. Testseite drucken

## Netzlaufwerke

| Laufwerk | Pfad | Wer |
|:--|:--|--:|
| `H:` | `\\server\home` | alle |
| `P:` | `\\server\projekte` | Projektteams |
| `X:` | — | *frei* |

Die Pfade gelten nur im VPN. Bei 2 * 3 = 6 Fehlern bitte ein Ticket.

## Häufige Fehler

### "Zugriff verweigert"

Meist fehlt die Gruppe `fs_projekte`. Prüfen mit:

    id -Gn

\# ist kein Kommentar im Laufwerkspfad, und 50 % der Fälle lösen sich nach einem Neustart.

### Passwort vergessen

Siehe [Self-Service](https://sso.example.org/reset "Passwort zurücksetzen") – das geht
auch vom Handy.\
Notfall-Hotline: **0800 123 456**
