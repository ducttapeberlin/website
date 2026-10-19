"""Holt alle DUCT TAPE Events von rausgegangen und schreibt sie in index.html (zwischen EVENTS:START und EVENTS:END)
und mit Poster und Beschreibung in termine.html (zwischen ALL:START und ALL:END), dasselbe auf Englisch in
en/index.html und en/dates.html. Die Format-Seiten (drag-brunch.html usw.) bekommen ihre eigenen Termine (FMT:START/END). Die Eventbeschreibungen bleiben, wie sie auf rausgegangen stehen.

Läuft stündlich über .github/workflows/termine.yml. Quelle ist die Organizer-Seite (gerendertes HTML in
$RAUSGEGANGEN_HTML) und die Eventseiten dahinter (JSON-LD). Was rausgegangen nicht hergibt (Featured, Einlass,
Gäste, Termine die dort fehlen), steht in scripts/termine-config.json.
"""
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import shutil
import unicodedata
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ORGANIZER = "https://rausgegangen.de/organizations/duct-tape/"
ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
TERMINE = ROOT / "termine.html"
EN_INDEX = ROOT / "en" / "index.html"
EN_TERMINE = ROOT / "en" / "dates.html"
POSTERS = ROOT / "assets" / "img" / "termine"
CACHE = Path(__file__).resolve().parent / "termine-details.json"
CONFIG = Path(__file__).resolve().parent / "termine-config.json"
REFETCH = dt.timedelta(hours=6)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
START, END = "<!-- EVENTS:START -->", "<!-- EVENTS:END -->"
F_START, F_END = "<!-- FEATURED:START -->", "<!-- FEATURED:END -->"
A_START, A_END = "<!-- ALL:START -->", "<!-- ALL:END -->"
LD_START, LD_END = "<!-- LD:START -->", "<!-- LD:END -->"
FMT_START, FMT_END = "<!-- FMT:START -->", "<!-- FMT:END -->"
# Format-Seiten (drag-brunch.html usw., EN unter en/): dort stehen nur die Termine des jeweiligen Formats
FORMAT_PAGES = {
    "drag-bingo": lambda r: (r.get("Format") or "").strip() == "Drag Bingo",
    "drag-brunch": lambda r: "brunch" in (r.get("Titel") or "").lower(),
    "drag-shows": lambda r: (r.get("Format") or "").strip() == "Show",
}
SITE = "https://ducttape.berlin/"
INDENT, F_INDENT = "        ", "      "
MONTH_NAMES = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
               "November", "Dezember"]
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12}
OPENTABLE = "https://www.opentable.de/booking/restref/availability?lang={lang}&restRef=514161&dateTime={date}T{time}&partySize=2"

# Texte je Sprache; L ist die gerade erzeugte Sprache (main() schaltet um)
DE = {"weekdays": WEEKDAYS, "wd_short": 2, "months": MONTH_NAMES,
      "with": "mit", "and": "und", "doors": "Einlass", "table": "Tisch reservieren", "event_page": "Eventseite",
      "more": "Weiterlesen", "empty": "Neue Termine folgen in Kürze.", "opentable": "de-DE", "prefix": ""}
EN = {"weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "wd_short": 3,
      "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"],
      "with": "with", "and": "and", "doors": "Doors",
      "table": "Book a table", "event_page": "Event page", "more": "Read more", "empty": "New dates coming soon.",
      "opentable": "en-GB", "prefix": "../"}
L = DE


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
    """'Harpy @wowharpywow, Symba @symba4ever' -> 'mit Harpy & Symba' (nur Namen, ohne Links)."""
    out = []
    for part in re.split(r"[,;\n]", s or ""):
        part = part.strip()
        if not part:
            continue
        handle = re.search(r"@([A-Za-z0-9_.]+)", part)
        name = re.sub(r"\s*@[A-Za-z0-9_.]+\s*", " ", part).strip() or (handle[1] if handle else part)
        out.append(esc(name))
    if not out:
        return ""
    if len(out) == 1:
        return f"{L['with']} {out[0]}"
    if len(out) == 2:
        return f"{L['with']} {out[0]} &amp; {out[1]}"
    return f"{L['with']} {', '.join(out[:-1])} {L['and']} {out[-1]}"


def ticket_slug(s):
    m = re.search(r"t\.rausgegangen\.de/tickets/([A-Za-z0-9_-]+)", s or "")
    if m:
        return m[1]
    s = (s or "").strip()
    return s if re.fullmatch(r"[a-z0-9-]+", s) else None


def hour_en(t, suffix=True):
    """(19, 30) -> '7:30 pm'."""
    h = t[0] % 12 or 12
    return (f"{h}" if t[1] == 0 else f"{h}:{t[1]:02d}") + ((" am" if t[0] < 12 else " pm") if suffix else "")


def when(row):
    """Datum, Wochentag und Zeiten einer Zeile."""
    date = parse_date(row.get("Datum"))
    begin, end, doors = (parse_time(row.get(k)) for k in ("Beginn", "Ende", "Einlass"))
    if L is EN:
        same = begin and end and (begin[0] < 12) == (end[0] < 12)
        time = (f"{hour_en(begin, not same)}–{hour_en(end)}" if begin and end else f"from {hour_en(begin)}" if begin else "")
        return date, begin, time, f"{L['doors']} {hour_en(doors)}" if doors else ""
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
        label = f"{(row.get('Titel') or '').strip()} · {L['weekdays'][date.weekday()]} {date:%d.%m.}"
        return f'<button class="btn btn-primary" type="button" data-tickets="{esc(slug)}" data-label="{esc(label)}">Tickets</button>'
    if booking.lower() == "opentable":
        t = begin or (12, 0)
        booking = OPENTABLE.format(lang=L["opentable"], date=date.isoformat(), time=f"{t[0]:02d}%3A{t[1]:02d}")
    if booking.startswith("http"):
        return f'<a class="btn btn-ghost" href="{esc(booking)}" target="_blank" rel="noopener">{L["table"]}</a>'
    return None


def tag_html(row, cls="event-tag"):
    """Format-Etikett; verlinkt auf die Format-Seite (z. B. drag-brunch), wenn es sie gibt."""
    tag = (row.get("Format") or "").strip()
    if not tag:
        return ""
    for motto in ("halloween", "winter", "christmas"):  # Brunch-Ausgaben bekommen ihr eigenes Etikett-Design
        if motto in tag.lower():
            cls += f" tag-{motto}"
    for slug, match in FORMAT_PAGES.items():
        if match(row) and (ROOT / f"{slug}.html").exists():
            return f'<a class="{cls}" href="{slug}">{esc(tag)}</a>'
    return f'<span class="{cls}">{esc(tag)}</span>'


def render(row):
    date, _, time, doors = when(row)
    meta = [f"<span>{L['weekdays'][date.weekday()]}</span>"]
    meta += [f"<span>{time}</span>"] if time else []
    meta += [f'<span class="event-doors">{doors}</span>'] if doors else []
    tag = (row.get("Format") or "").strip()
    sub = subtitle(row)
    btn = button(row)
    lines = [
        f'<li class="event" data-date="{date.isoformat()}">',
        f'  <div class="event-date">{date:%d.%m.}<small>{"".join(meta)}</small></div>',
        "  <div>",
        *([f"    {tag_html(row)}"] if tag else []),
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
        *([f"    {tag_html(first)}"] if tag else []),
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
            f"      <div><strong>{L['weekdays'][date.weekday()][:L['wd_short']]} {date:%d.%m.}</strong><small>{small}</small></div>",
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
    s = unicodedata.normalize("NFC", html.unescape(re.sub(r"<[^>]+>", "", s)))  # "fu\u0308r" -> "für"
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


CREW = {"EMI", "Symba", "Magda von Pfeffer"}
PARTICLES = {"von", "van", "de", "la", "le", "del", "da"}


def performers(desc):
    """Auftretende aus der Beschreibung ("Durch den Brunch führen euch: 👑 EMI 👑 Harpy Freut euch …").
    Ein Name endet vor dem nächsten 👑, einem Emoji oder dem nächsten Satz (großes Wort, dann kleines Wort).
    Steht das ganze Kollektiv drin, bleibt die Zeile leer (dann tritt einfach DUCT TAPE auf)."""
    names = []
    for seg in (desc or "").split("👑")[1:]:
        words, out = seg.split(), []
        for i, w in enumerate(words):
            nxt = words[i + 1] if i + 1 < len(words) else ""
            if re.search("[" + EMOJI + "]", w) or not (w[:1].isupper() or (w in PARTICLES and nxt[:1].isupper())):
                break
            if out and w[:1].isupper() and nxt[:1].islower() and nxt not in PARTICLES:
                break
            out.append(w)
        name = " ".join(out).strip(" .,:;!")
        if name and name not in names:
            names.append(name)
    return "" if CREW <= set(names) else ", ".join(names)


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


def details(row):
    """Beschreibung und Poster (von der rausgegangen-Eventseite, Poster lokal gespeichert)."""
    desc = (row.get("Beschreibung") or "").strip()
    poster = (row.get("Poster") or "").strip()
    return desc, save_poster(poster) if poster.startswith("http") else ""


def render_all(events):
    """Alle Termine mit Poster und Beschreibung für termine.html, nach Monaten gruppiert."""
    out, month = [], None
    for date, _, r in events:
        if (date.year, date.month) != month:
            if month:
                out.append("</div>")
            month = (date.year, date.month)
            out += [f'<div class="month" data-month="{date:%Y-%m}">', f"  <h2>{L['months'][date.month - 1]} {date.year}</h2>"]
        _, _, time, doors = when(r)
        desc, poster = details(r)
        desc = add_breaks(desc)
        title = (r.get("Titel") or "").strip()
        tag = (r.get("Format") or "").strip()
        sub = subtitle(r)
        btn = button(r)
        page = (r.get("Eventseite") or "").strip()
        day = (f"{L['weekdays'][date.weekday()]}, {date.day} {L['months'][date.month - 1]} {date.year}" if L is EN
               else f"{WEEKDAYS[date.weekday()]}, {date:%d.%m.%Y}")
        when_line = " · ".join(x for x in [day, time, doors] if x)
        media = (f'<img src="{L["prefix"]}{poster}" alt="Poster: {esc(title)}" loading="lazy">' if poster else
                 f'<div class="tevent-noposter"><span>{date:%d.%m.}</span></div>')
        paras = [f"      <p>{esc(p).replace(chr(10), '<br>')}</p>" for p in desc.split("\n\n") if p.strip()]
        if len(paras) > 3:  # lange Texte: Rest hinter "Weiterlesen"
            paras = paras[:2] + ["      <details>", f"        <summary>{L['more']}</summary>", *["  " + p for p in paras[2:]], "      </details>"]
        actions = ([f"      {btn}"] if btn else []) + (
            [f'      <a class="btn btn-ghost" href="{esc(page)}" target="_blank" rel="noopener">{L["event_page"]}</a>'] if page.startswith("http") else [])
        out += [
            f'  <article class="tevent{theme_class(r.get("Featured") or "ja")}" data-date="{date.isoformat()}">',
            f'    <div class="tevent-poster">{media}</div>',
            '    <div class="tevent-body">',
            f'      <p class="tevent-when">{when_line}</p>',
            *([f"      {tag_html(r)}"] if tag else []),
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


def events_ld(events):
    """Strukturierte Daten (schema.org/Event) für Google und KI-Suchen, als JSON-LD im <head> der Terminseiten."""
    group = {"@type": "PerformingGroup", "name": "DUCT TAPE", "url": SITE}
    items = []
    for date, start, r in events:
        end = parse_time(r.get("Ende"))
        iso = lambda hm: dt.datetime(date.year, date.month, date.day, *hm, tzinfo=ZoneInfo("Europe/Berlin")).isoformat()
        loc = r.get("_location") or {"@type": "Place", "name": (r.get("Location") or "").strip() or "Berlin",
                                     "address": {"@type": "PostalAddress", "addressLocality": "Berlin", "addressCountry": "DE"}}
        _, poster = details(r)
        page = (r.get("Eventseite") or "").strip()
        tickets = (r.get("Tickets") or "").strip()
        free = (r.get("Free Entry") or "").strip() or str(r.get("_price")) in ("0", "0.0", "0.00")
        ev = {"@type": "Event", "name": (r.get("Titel") or "").strip(), "startDate": iso(start),
              "eventStatus": "https://schema.org/EventScheduled",
              "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
              "location": loc, "organizer": group, "performer": group}
        if end and end > start:
            ev["endDate"] = iso(end)
        desc = re.sub(r"\s+", " ", r.get("Beschreibung") or "").strip()
        if desc:
            ev["description"] = desc[:300].rsplit(" ", 1)[0] + "…" if len(desc) > 300 else desc
        if poster:
            ev["image"] = SITE + poster
        if page.startswith("http"):
            ev["url"] = page
        if free or tickets:
            offer = {"@type": "Offer", "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
                     "url": tickets if tickets.startswith("http") else page or SITE}
            if free:
                offer["price"] = 0
            elif r.get("_price"):
                offer["price"] = r["_price"]
            ev["offers"] = offer
        items.append(ev)
    data = {"@context": "https://schema.org", "@graph": items}
    return '  <script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def replace_between(src, start, end, body, indent):
    a, b = src.index(start) + len(start), src.index(end)
    return src[:a] + "\n" + (body + "\n" if body else "") + indent + src[b:]


KEEP_CAPS = {"DUCT", "TAPE", "HOP", "CSD", "DJ", "XMAS", "LGBTQ", "NYE"}


def tidy(s):
    """'DRAG BINGO NIGHT' -> 'Drag Bingo Night', 'CHRISTMAS SHOW' -> 'Christmas Show'; kurze Wörter und Kürzel bleiben."""
    return " ".join(w.capitalize() if w.isupper() and len(w) > 2 and w not in KEEP_CAPS else w for w in s.split())


def slug_of(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def series(slug):
    """'a-berlin-drag-queens-christmas-show-1' -> 'a-berlin-drag-queens-christmas-show' (Termine einer Reihe)."""
    return re.sub(r"-\d+$", "", slug)


def event_ld(url, cache, now):
    """JSON-LD der Eventseite, zwischengespeichert und alle paar Stunden neu geholt."""
    hit = cache.get(url)
    if hit and hit.get("ld") and dt.datetime.fromisoformat(hit["fetched"]) > now - REFETCH:
        return hit["ld"]
    src = fetch(url)
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', src, re.S):
        try:
            data = json.loads(html.unescape(block))
        except ValueError:
            continue
        for it in data if isinstance(data, list) else [data]:
            if isinstance(it, dict) and it.get("@type") == "Event":
                cache[url] = {**(hit or {}), "ld": it, "fetched": now.isoformat(timespec="seconds")}
                return it
    return hit.get("ld") if hit else None  # Abruf fehlgeschlagen: alte Daten behalten


def ticket_exists(slug, entry):
    """Prüft einmal, ob es den Ticketshop zum geratenen Kürzel gibt. Nur ein klares 404 zählt als nein."""
    if entry.get("tickets") != slug:
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"https://t.rausgegangen.de/tickets/{slug}/external-loader.js", headers={"User-Agent": UA}), timeout=20)
            ok = True
        except urllib.error.HTTPError as e:
            ok = e.code != 404
        except OSError:
            return True  # Netzproblem: lieber den Button zeigen und beim nächsten Lauf neu prüfen
        entry.update({"tickets": slug, "tickets_ok": ok})
    return entry["tickets_ok"]


def to_row(url, ld):
    """Eventseite -> Zeile im selben Format wie früher die Tabelle."""
    name = ld.get("name", "")
    start = dt.datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", ld["startDate"]))
    end = ld.get("endDate")
    end = dt.datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", end)) if end else None
    low = name.lower()
    title = re.split(r"\s+(?:@|\||//)\s+", name)[0]
    title = re.sub(r"\s+by DUCT TAPE\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*\([^)]*\)", "", title)
    tag, row = "", {}
    if "brunch" in low:
        edition = re.search(r"([A-Za-zÄÖÜäöüß]+\s+edition)\b", name, re.I)  # z. B. "Christmas Edition", egal wo im Namen
        title = "Fritz-Kola Drag Brunch" if "fritz" in low else "Drag Brunch"
        tag = tidy(edition[1]) if edition else "Drag Brunch"
        row.update({"Free Entry": "ja", "Reservierung": "OpenTable"})
    elif "bingo" in low:
        tag = "Drag Bingo"
    elif "show" in low:
        tag = "Show"
    elif "party" in low or "pride" in low:
        tag = "Party"
    offers = ld.get("offers") or {}
    tickets = ""
    if isinstance(offers, dict):
        if offers.get("url"):
            tickets = offers["url"]
        elif offers.get("offerCount") or offers.get("offers") or float(offers.get("price") or 0) > 0:
            s = slug_of(url)
            tickets = s[:-2] if s.endswith("-0") else s  # Ticketshop-Kürzel: ohne "-0", ab dem zweiten Termin mit "-1" usw.
    img = ld.get("image")
    img = img[0] if isinstance(img, list) and img else img
    row.update({
        "Datum": f"{start:%d.%m.%Y}", "Beginn": f"{start:%H:%M}", "Ende": f"{end:%H:%M}" if end and end.date() == start.date() else "",
        "Format": tag, "Titel": tidy(title), "Location": tidy(re.sub(r"\s*\([^)]*\)", "", (ld.get("location") or {}).get("name", ""))),
        "Eventseite": url, "Tickets": tickets, "Beschreibung": clean_text(ld.get("description") or ""),
        "Gäste": performers(clean_text(ld.get("description") or "")),
        "Poster": img if isinstance(img, str) else "",
        "_location": ld.get("location") if isinstance(ld.get("location"), dict) else None,
        "_price": offers.get("lowPrice") or offers.get("price") if isinstance(offers, dict) else None,
    })
    return row


def main():
    try:
        organizer = Path(os.environ["RAUSGEGANGEN_HTML"]).read_text(encoding="utf-8")
    except (KeyError, OSError):
        organizer = ""
    urls = sorted({f"https://rausgegangen.de/events/{m}/"
                   for m in re.findall(r'href="(?:https://rausgegangen\.de)?(?:/en)?/events/([^"/?#]+)/?', organizer)})
    if not urls:
        # Warnung statt Fehler: die Website bleibt unverändert, und GitHub verschickt nicht stündlich Fehler-Mails.
        print("::warning::rausgegangen-Organizer-Seite nicht lesbar. Termine bleiben unverändert.")
        return

    now = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    today = now.date()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    cache = {k: v for k, v in cache.items() if "ld" in v}
    hidden = set(config.get("ausblenden", []))
    rows = []
    for url in urls:
        slug = slug_of(url)
        if slug in hidden or series(slug) in hidden:
            continue
        ld = event_ld(url, cache, now)
        organizers = ld and ld.get("organizer")
        organizers = organizers if isinstance(organizers, list) else [organizers or {}]
        if not ld or not any("duct-tape" in (o or {}).get("url", "") for o in organizers):
            continue  # Werbung oder fremdes Event auf der Organizer-Seite
        row = to_row(url, ld)
        if ticket_slug(row["Tickets"]) and not ticket_exists(ticket_slug(row["Tickets"]), cache[url]):
            row["Tickets"] = ""
        for key in (series(slug), slug):  # Ergänzungen aus der Config, für die ganze Reihe oder einen Termin
            row.update(config.get("ergaenzungen", {}).get(key, {}))
        if config.get("featured", {}).get(series(slug)):
            row["Featured"] = config["featured"][series(slug)]
        rows.append(row)
    rows += [dict(r) for r in config.get("zusaetzliche_termine", [])]

    events = []
    for r in rows:
        date = parse_date(r.get("Datum"))
        if date and date >= today and (r.get("Titel") or "").strip():
            events.append((date, parse_time(r.get("Beginn")) or (0, 0), r))
    events.sort(key=lambda e: e[:2])
    featured = {}
    for *_, r in events:
        if (r.get("Featured") or "").strip():
            featured.setdefault((r["Titel"].strip(), r["Featured"].strip()), []).append(r)
    listed = [r for *_, r in events if not (r.get("Featured") or "").strip()]

    global L
    changed, used = False, set()
    for L, index, termine in ((DE, INDEX, TERMINE), (EN, EN_INDEX, EN_TERMINE)):
        if not index.exists() or not termine.exists():
            continue
        body = "\n".join(render(r) for r in listed) or (INDENT + f'<li class="events-empty">{L["empty"]}</li>')
        src = index.read_text(encoding="utf-8")
        new = replace_between(src, START, END, body, INDENT)
        new = replace_between(new, F_START, F_END, "\n".join(render_featured(g) for g in featured.values()), F_INDENT)
        if new != src:
            index.write_text(new, encoding="utf-8")

        # Termine-Seite mit Postern und Beschreibungen
        all_src = termine.read_text(encoding="utf-8")
        all_body = render_all(events) or (F_INDENT + f'<p class="events-empty">{L["empty"]}</p>')
        all_new = replace_between(all_src, A_START, A_END, all_body, F_INDENT)
        if LD_START in all_new:
            all_new = replace_between(all_new, LD_START, LD_END, events_ld(events), "  ")
        if all_new != all_src:
            termine.write_text(all_new, encoding="utf-8")
        changed = changed or new != src or all_new != all_src

        # Format-Seiten
        for slug, match in FORMAT_PAGES.items():
            page = (ROOT / f"{slug}.html") if L is DE else (ROOT / "en" / f"{slug}.html")
            if not page.exists():
                continue
            own = [e for e in events if match(e[2])]
            f_src = page.read_text(encoding="utf-8")
            f_body = "\n".join(render(r) for *_, r in own) or (INDENT + f'<li class="events-empty">{L["empty"]}</li>')
            f_new = replace_between(f_src, FMT_START, FMT_END, f_body, INDENT)
            if LD_START in f_new:
                f_new = replace_between(f_new, LD_START, LD_END, events_ld(own), "  ")
            if f_new != f_src:
                page.write_text(f_new, encoding="utf-8")
                changed = True
        used |= set(re.findall(r"assets/img/termine/([\w.]+)", all_new))
    L = DE
    cache = {k: v for k, v in cache.items() if k in urls}
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for f in POSTERS.glob("*.jpg") if POSTERS.exists() else []:
        if f.name not in used:
            f.unlink()
    print(f"{len(events)} Termine, {len(featured)} Highlight(s)", "aktualisiert" if changed else "unverändert")


if __name__ == "__main__":
    main()
