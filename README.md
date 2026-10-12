# DUCT TAPE – Website

Statische Website des Berliner Drag-Kollektivs DUCT TAPE. Kein Build-Schritt: reines HTML/CSS/JS, gehostet über GitHub Pages.

- `index.html` – Startseite (Shows, Über uns, Galerie, Booking, Newsletter)
- `impressum.html`, `datenschutz.html` – Rechtliches
- `assets/style.css` – Design; Markenfarben oben unter `:root`
- `assets/main.js` – Mobile-Menü, blendet vergangene Termine aus
- `assets/img/` – Logo und Fotos
- `assets/fonts/` – selbst gehostete Schriften (Anton, Inter; SIL Open Font License)

Neue Termine: in `index.html` ein `<li class="event" data-date="JJJJ-MM-TT">` ergänzen.
