"""Schreibt die Termine aus der Google-Tabelle in index.html (zwischen EVENTS:START und EVENTS:END)
und mit Poster und Beschreibung in termine.html (zwischen ALL:START und ALL:END).

Läuft stündlich über .github/workflows/termine.yml. Fehlt in der Tabelle die Eventseite, sucht das Skript
den Termin am selben Tag auf der rausgegangen-Organizer-Seite (gerendertes HTML in $RAUSGEGANGEN_HTML).
Lokal testen:
    python3 scripts/termine.py              # liest die Tabelle online
    python3 scripts/termine.py termine.csv  # liest eine heruntergeladene CSV
"""
import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

SHEET_ID = "17gTptLrfvTtNU7fB6bJKMsSKL1nsc0myymPQorFi5YQ"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
TERMINE = ROOT / "termine.html"
POSTERS = ROOT / "assets" / "img" / "termine"
CACHE = Path(__file__).resolve().parent / "termine-details.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
START, END = "<!-- EVENTS:START -->", "<!-- EVENTS:END -->"
F_START, F_END = "<!-- FEATURED:START -->", "<!-- FEATURED:END -->"
A_START, A_END = "<!-- ALL:START -->", "<!-- ALL:END -->"
INDENT, F_INDENT = "        ", "      "
MONTH_NAMES = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
               "November", "Dezember"]
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


# ---------- Termine-Seite: Beschreibung und Poster ----------

def fetch(url):
    """HTML einer Seite. rausgegangen blockt einfache Abrufe, deshalb über Headless-Chrome, wenn vorhanden."""
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome and "rausgegangen.de" in url:
        try:
            r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=8000",
                                f"--user-agent={UA}", "--dump-dom", url], capture_output=True, timeout=45)
            return r.stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            return ""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except OSError:
        return ""


def clean_text(s):
    """HTML-Beschreibung -> Klartext mit Absätzen."""
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in s.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


EMOJI = "\u2600-\u27bf\U0001f000-\U0001faff"


def add_breaks(s):
    """rausgegangen liefert die Beschreibung ohne Zeilenumbrüche ("...zusammen.Am 4. ..."). Wo nach Satzende oder
    Emoji ohne Leerzeichen ein neuer Satz beginnt, war ursprünglich ein Absatz."""
    if "\n" in s:
        return s
    s = re.sub(r"([.!?…])(?=[A-ZÄÖÜ" + EMOJI + "])", "\\1\n\n", s)
    s = re.sub(r"([" + EMOJI + "]\ufe0f?)(?=[A-ZÄÖÜ])", "\\1\n\n", s)
    return re.sub(r"(?<=[a-zäöüß])(?=[" + EMOJI + "] [A-ZÄÖÜ])", "\n\n", s)


def page_details(src):
    """Beschreibung und Bild aus einer Eventseite (JSON-LD, sonst Open-Graph-Tags)."""
    desc = image = ""
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', src, re.S):
        try:
            data = json.loads(html.unescape(block))
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if isinstance(it, dict) and "Event" in str(it.get("@type", "")):
                desc = desc or clean_text(it.get("description") or "")
                img = it.get("image")
                img = img[0] if isinstance(img, list) and img else img
                img = img.get("url") if isinstance(img, dict) else img
                image = image or (img if isinstance(img, str) else "")

    def meta(prop):
        m = re.search(rf'<meta[^>]+(?:property|name)="{prop}"[^>]+content="([^"]*)"', src) or \
            re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{prop}"', src)
        return html.unescape(m[1]).strip() if m else ""
    return desc or meta("og:description") or meta("description"), image or meta("og:image")


def drive_direct(url):
    """Google-Drive-Freigabelink -> direkter Download-Link."""
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=)([A-Za-z0-9_-]+)", url)
    return f"https://drive.google.com/uc?export=download&id={m[1]}" if m else url


def save_poster(url):
    """Lädt das Poster einmal herunter (Datenschutz: keine fremden Bildserver beim Seitenaufruf). Gibt den Pfad zurück."""
    name = hashlib.sha1(url.encode()).hexdigest()[:12] + ".jpg"
    path = POSTERS / name
    if not path.exists():
        try:
            with urllib.request.urlopen(urllib.request.Request(drive_direct(url), headers={"User-Agent": UA}), timeout=30) as r:
                data = r.read()
        except OSError:
            return ""
        if not (data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG" or data[8:12] == b"WEBP"):
            return ""  # kein Bild, z. B. eine Drive-Seite, weil die Datei nicht freigegeben ist
        POSTERS.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((900, 1400))
            im.save(path, "JPEG", quality=82, optimize=True, progressive=True)
        except ImportError:
            path.write_bytes(data)
        except Exception:
            return ""
    return f"assets/img/termine/{name}"


def details(row, cache):
    """Beschreibung und Poster: aus der Tabelle, sonst von der rausgegangen-Eventseite (zwischengespeichert)."""
    desc = (row.get("Beschreibung") or "").strip()
    poster = (row.get("Poster") or "").strip()
    page = (row.get("Eventseite") or "").strip()
    if (not desc or not poster) and page.startswith("http"):
        if page not in cache:
            src = fetch(page)
            if src:
                d, img = page_details(src)
                cache[page] = {"description": d, "image": img}
        desc = desc or cache.get(page, {}).get("description", "")
        poster = poster or cache.get(page, {}).get("image", "")
    return desc, save_poster(poster) if poster.startswith("http") else ""


def render_all(events, cache):
    """Alle Termine mit Poster und Beschreibung für termine.html, nach Monaten gruppiert."""
    out, month = [], None
    for date, _, r in events:
        if (date.year, date.month) != month:
            if month:
                out.append("</div>")
            month = (date.year, date.month)
            out += [f'<div class="month" data-month="{date:%Y-%m}">', f"  <h2>{MONTH_NAMES[date.month - 1]} {date.year}</h2>"]
        _, _, time, doors = when(r)
        desc, poster = details(r, cache)
        desc = add_breaks(desc)
        title = (r.get("Titel") or "").strip()
        tag = (r.get("Format") or "").strip()
        sub = subtitle(r)
        btn = button(r)
        page = (r.get("Eventseite") or "").strip()
        when_line = " · ".join(x for x in [f"{WEEKDAYS[date.weekday()]}, {date:%d.%m.%Y}", time, doors] if x)
        media = (f'<img src="{poster}" alt="Poster: {esc(title)}" loading="lazy">' if poster else
                 f'<div class="tevent-noposter"><span>{date:%d.%m.}</span></div>')
        paras = [f"      <p>{esc(p).replace(chr(10), '<br>')}</p>" for p in desc.split("\n\n") if p.strip()]
        if len(paras) > 3:  # lange Texte: Rest hinter "Weiterlesen"
            paras = paras[:2] + ["      <details>", "        <summary>Weiterlesen</summary>", *["  " + p for p in paras[2:]], "      </details>"]
        actions = ([f"      {btn}"] if btn else []) + (
            [f'      <a class="btn btn-ghost" href="{esc(page)}" target="_blank" rel="noopener">Eventseite</a>'] if page.startswith("http") else [])
        out += [
            f'  <article class="tevent" data-date="{date.isoformat()}">',
            f'    <div class="tevent-poster">{media}</div>',
            '    <div class="tevent-body">',
            f'      <p class="tevent-when">{when_line}</p>',
            *([f'      <span class="event-tag">{esc(tag)}</span>'] if tag else []),
            f"      <h3>{esc(title)}</h3>",
            *([f'      <p class="tevent-sub">{sub}</p>'] if sub else []),
            *([f'      <div class="tevent-desc">', *["  " + p for p in paras], "      </div>"] if paras else []),
            *([f'      <div class="tevent-actions">', *["  " + a for a in actions], "      </div>"] if actions else []),
            "    </div>",
            "  </article>",
        ]
    if month:
        out.append("</div>")
    return "\n".join(F_INDENT + l for l in out)


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

    # Termine-Seite mit Postern und Beschreibungen
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    all_src = TERMINE.read_text(encoding="utf-8")
    all_body = render_all(events, cache) or (F_INDENT + '<p class="events-empty">Neue Termine folgen in Kürze.</p>')
    all_new = replace_between(all_src, A_START, A_END, all_body, F_INDENT)
    if all_new != all_src:
        TERMINE.write_text(all_new, encoding="utf-8")
    pages_now = {(r.get("Eventseite") or "").strip() for *_, r in events}
    cache = {k: v for k, v in cache.items() if k in pages_now}
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    used = set(re.findall(r"assets/img/termine/([\w.]+)", all_new))
    for f in POSTERS.glob("*.jpg") if POSTERS.exists() else []:
        if f.name not in used:
            f.unlink()
    changed = new != src or all_new != all_src
    print(f"{len(events)} Termine, {len(featured)} Highlight(s)", "aktualisiert" if changed else "unverändert")


if __name__ == "__main__":
    main()
