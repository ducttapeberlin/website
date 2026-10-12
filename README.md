# DUCT TAPE – Website

Statische Website des Berliner Drag-Kollektivs DUCT TAPE. Kein Build-Schritt: reines HTML/CSS/JS, gehostet über GitHub Pages.

- `index.html` – Startseite (Shows, Über uns, Galerie, Booking, Newsletter)
- `impressum.html`, `datenschutz.html` – Rechtliches
- `assets/style.css` – Design; Markenfarben oben unter `:root`
- `assets/main.js` – Mobile-Menü, blendet vergangene Termine aus, Ticket-Fenster
- `scripts/termine.py` + `.github/workflows/termine.yml` – holen stündlich die Termine aus der Google-Tabelle
- `assets/img/` – Logo und Fotos
- `assets/fonts/` – selbst gehostete Schriften (Anton, Inter; SIL Open Font License)

## Termine

Termine werden in der Google-Tabelle **DUCT TAPE Termine (Website)** (Drive-Ordner DUCTTAPE) gepflegt, eine Zeile pro Termin; der Tab „Anleitung“ erklärt die Spalten.
Die Action „Termine aktualisieren“ liest die Tabelle stündlich, schreibt die Liste zwischen `EVENTS:START` und `EVENTS:END` in `index.html` und committet nur bei Änderungen.
Steht in der Spalte „Featured“ etwas, kommt der Termin als Highlight-Karte über die Liste („ja“ = gelb, „Weihnachten“ = Weihnachtsfarben; weitere Farbthemen als `.featured.theme-…` in `assets/style.css`).
Fehlt in einer Zeile die Eventseite, sucht das Skript den Termin am selben Tag auf https://rausgegangen.de/organizations/duct-tape/ und verlinkt ihn.
Sofort aktualisieren: GitHub → Actions → „Termine aktualisieren“ → Run workflow.

Voraussetzung: Die Tabelle ist per Link lesbar (Teilen → Allgemeiner Zugriff → Jeder mit dem Link → Betrachter).
