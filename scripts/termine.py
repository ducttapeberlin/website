"""Schreibt die Termine aus der Google-Tabelle in index.html (zwischen EVENTS:START und EVENTS:END).

Läuft stündlich über .github/workflows/termine.yml. Fehlt in der Tabelle die Eventseite, sucht das Skript
den Termin am selben Tag auf der rausgegangen-Organizer-Seite (gerendertes HTML in $RAUSGEGANGEN_HTML).
Lokal testen:
    python3 scripts/termine.py              # liest die Tabelle online
    python3 scripts/termine.py termine.csv  # liest eine heruntergeladene CSV
"""
import csv
import datetime as dt
import html
import io
import os
import re
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

SHEET_ID = "17gTptLrfvTtNU7fB6bJKMsSKL1nsc0myymPQorFi5YQ"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
INDEX = Path(__file__).resolve().parent.parent / "index.html"
START, END = "<!-- EVENTS:START -->", "<!-- EVENTS:END -->"
F_START, F_END = "<!-- FEATURED:START -->", "<!-- FEATURED:END -->"
INDENT, F_INDENT = "        ", "      "
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12}
OPENTABLE = "https://www.opentable.de/booking/restref/availability?lang=de-DE&restRef=514161&dateTime={date}T{time}&partySize=2"


def esc(s):
    return html.escape(s, quote=True)


def link(url, text):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>'


def parse_date(s):
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*", s or "")
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    return dt.date(y + 2000 if y < 100 else y, mo, d)


def parse_time(s):
    m = re.match(r"\s*(\d{1,2})(?:[:.](\d{2}))?", s or "")
    return (int(m[1]), int(m[2] or 0)) if m else None


def hour(t):
    return f"{t[0]}" if t[1] == 0 else f"{t[0]}:{t[1]:02d}"


def guests(s):
    """'Harpy @wowharpywow, Symba @symba4ever' -> Untertitel-Teil mit Instagram-Links."""
    out = []
    for part in re.split(r"[,;\n]", s or ""):
        part = part.strip()
        if not part:
            continue
        handle = re.search(r"@([A-Za-z0-9_.]+)", part)
        name = re.sub(r"\s*@[A-Za-z0-9_.]+\s*", " ", part).strip() or (handle[1] if handle else part)
        out.append(link(f"https://www.instagram.com/{handle[1]}/", name) if handle else esc(name))
    if not out:
        return ""
    if len(out) == 1:
        return f"Special Guest {out[0]}"
    if len(out) == 2:
        return f"Special Guests {out[0]} &amp; {out[1]}"
    return f"mit {', '.join(out[:-1])} und {out[-1]}"


def ticket_slug(s):
    m = re.search(r"t\.rausgegangen\.de/tickets/([A-Za-z0-9_-]+)", s or "")
    if m:
        return m[1]
    s = (s or "").strip()
    return s if re.fullmatch(r"[a-z0-9-]+", s) else None


def rausgegangen_pages(path, today):
    """Eventseiten von der Organizer-Seite: {Datum: [(Kartentext, URL), …]}. Leer, wenn die Seite fehlt."""
    try:
        src = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return {}
    pages = {}
    for m in re.finditer(r'<a[^>]*href="(?:https://rausgegangen\.de)?(?:/en)?/events/([^"/]+)/?"[^>]*>(.*?)</a>', src, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", " ", m[2]))
        d = re.search(r"(\d{1,2})\.\s*([A-Za-zä]{3})", text)
        day, mon = (d[1], d[2]) if d else (None, None)
        if not d and (d := re.search(r"\b([A-Z][a-z]{2})\s+(\d{1,2})\b", text)):
            day, mon = d[2], d[1]
        if not day or mon.lower() not in MONTHS:
            continue
        try:
            date = dt.date(today.year, MONTHS[mon.lower()], int(day))
            if date < today - dt.timedelta(days=7):
                date = date.replace(year=today.year + 1)
        except ValueError:
            continue
        url = f"https://rausgegangen.de/events/{m[1]}/"
        if url not in (u for _, u in pages.get(date, [])):
            pages.setdefault(date, []).append((text.lower(), url))
    return pages


def match_page(row, date, pages):
    """Bei mehreren Events am selben Tag gewinnt das mit den meisten gemeinsamen Wörtern aus Titel und Location."""
    words = set(re.findall(r"\w{3,}", f"{row.get('Titel')} {row.get('Location')}".lower()))
    best = max(pages.get(date, []), key=lambda p: len(words & set(re.findall(r"\w{3,}", p[0]))), default=None)
    return best[1] if best else ""


def when(row):
    """Datum, Wochentag und Zeiten einer Zeile."""
    date = parse_date(row.get("Datum"))
    begin, end, doors = (parse_time(row.get(k)) for k in ("Beginn", "Ende", "Einlass"))
    time = f"{hour(begin)}–{hour(end)} Uhr" if begin and end else f"ab {hour(begin)} Uhr" if begin else ""
    return date, begin, time, f"Einlass {hour(doors)} Uhr" if doors else ""


def title_html(row):
    page = (row.get("Eventseite") or "").strip()
    title = (row.get("Titel") or "").strip()
    return link(page, title) if page.startswith("http") else esc(title)


def subtitle(row):
    sub = [esc(x) for x in [(row.get("Location") or "").strip()] if x]
    if g := guests(row.get("Gäste")):
        sub.append(g)
    if (row.get("Free Entry") or "").strip().lower() in ("ja", "yes", "x", "true"):
        sub.append("Free Entry")
    return " · ".join(sub)


def button(row):
    """Tickets (rausgegangen-Overlay) oder Reservierung; None, wenn es nichts zu buchen gibt."""
    date, begin, *_ = when(row)
    slug = ticket_slug(row.get("Tickets"))
    booking = (row.get("Reservierung") or "").strip()
    if slug:
        label = f"{(row.get('Titel') or '').strip()} · {WEEKDAYS[date.weekday()]} {date:%d.%m.}"
        return f'<button class="btn btn-primary" type="button" data-tickets="{esc(slug)}" data-label="{esc(label)}">Tickets</button>'
    if booking.lower() == "opentable":
        t = begin or (12, 0)
        booking = OPENTABLE.format(date=date.isoformat(), time=f"{t[0]:02d}%3A{t[1]:02d}")
    if booking.startswith("http"):
        return f'<a class="btn btn-ghost" href="{esc(booking)}" target="_blank" rel="noopener">Tisch reservieren</a>'
    return None


def render(row):
    date, _, time, doors = when(row)
    meta = [f"<span>{WEEKDAYS[date.weekday()]}</span>"]
    meta += [f"<span>{time}</span>"] if time else []
    meta += [f'<span class="event-doors">{doors}</span>'] if doors else []
    tag = (row.get("Format") or "").strip()
    sub = subtitle(row)
    btn = button(row)
    lines = [
        f'<li class="event" data-date="{date.isoformat()}">',
        f'  <div class="event-date">{date:%d.%m.}<small>{"".join(meta)}</small></div>',
        "  <div>",
        *([f'    <span class="event-tag">{esc(tag)}</span>'] if tag else []),
        f"    <h3>{title_html(row)}</h3>",
        *([f"    <p>{sub}</p>"] if sub else []),
        "  </div>",
        *([f"  {btn}"] if btn else []),
        "</li>",
    ]
    return "\n".join(INDENT + l for l in lines)


def theme_class(value):
    """'ja' = Standard-Highlight (gelb), sonst ein Farbthema wie 'Weihnachten' -> theme-weihnachten."""
    v = value.strip().lower()
    if v in ("ja", "yes", "x", "true"):
        return ""
    v = v.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return " theme-" + re.sub(r"[^a-z0-9]+", "-", v).strip("-")


def render_featured(rows):
    """Eine Highlight-Karte für alle Termine mit gleichem Titel, z. B. beide Christmas-Show-Tage."""
    first = rows[0]
    tag = (first.get("Format") or "").strip()
    sub = subtitle(first)
    lines = [
        f'<article class="featured{theme_class(first.get("Featured", ""))}">',
        '  <div class="featured-body">',
        *([f'    <span class="event-tag">{esc(tag)}</span>'] if tag else []),
        f"    <h3>{title_html(first)}</h3>",
        *([f"    <p>{sub}</p>"] if sub else []),
        "  </div>",
        '  <ul class="featured-dates">',
    ]
    for r in rows:
        date, _, time, doors = when(r)
        small = time + (f'<span class="event-doors">{doors}</span>' if doors else "")
        btn = button(r)
        lines += [
            f'    <li data-date="{date.isoformat()}">',
            f"      <div><strong>{WEEKDAYS[date.weekday()][:2]} {date:%d.%m.}</strong><small>{small}</small></div>",
            *([f"      {btn}"] if btn else []),
            "    </li>",
        ]
    lines += ["  </ul>", "</article>"]
    return "\n".join(F_INDENT + l for l in lines)


def replace_between(src, start, end, body, indent):
    a, b = src.index(start) + len(start), src.index(end)
    return src[:a] + "\n" + (body + "\n" if body else "") + indent + src[b:]


def main():
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        try:
            with urllib.request.urlopen(CSV_URL, timeout=30) as r:
                text = r.read().decode("utf-8")
        except OSError as e:
            text = f"<{e}>"
    if text.lstrip().startswith("<"):
        # Warnung statt Fehler: die Website bleibt unverändert, und GitHub verschickt nicht stündlich Fehler-Mails.
        print("::warning::Tabelle nicht lesbar (Teilen → Jeder mit dem Link → Betrachter). Termine bleiben unverändert.")
        return

    today = dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    rows = [{(k or "").strip(): (v or "") for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]
    pages = rausgegangen_pages(os.environ.get("RAUSGEGANGEN_HTML"), today)
    events = []
    for r in rows:
        date = parse_date(r.get("Datum"))
        if date and date >= today and (r.get("Titel") or "").strip():
            if not r.get("Eventseite", "").strip():
                r["Eventseite"] = match_page(r, date, pages)
            events.append((date, parse_time(r.get("Beginn")) or (0, 0), r))
    events.sort(key=lambda e: e[:2])
    featured = {}
    for *_, r in events:
        if (r.get("Featured") or "").strip():
            featured.setdefault((r["Titel"].strip(), r["Featured"].strip()), []).append(r)
    listed = [r for *_, r in events if not (r.get("Featured") or "").strip()]
    body = "\n".join(render(r) for r in listed) or (
        INDENT + '<li class="events-empty">Neue Termine folgen in Kürze.</li>')

    src = INDEX.read_text(encoding="utf-8")
    new = replace_between(src, START, END, body, INDENT)
    new = replace_between(new, F_START, F_END, "\n".join(render_featured(g) for g in featured.values()), F_INDENT)
    if new != src:
        INDEX.write_text(new, encoding="utf-8")
    print(f"{len(events)} Termine, {len(featured)} Highlight(s)", "aktualisiert" if new != src else "unverändert")


if __name__ == "__main__":
    main()
