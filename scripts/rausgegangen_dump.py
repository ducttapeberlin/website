"""Einmaliger Datenabzug: alle Events der rausgegangen-Organizer-Seite mit ihren JSON-LD-Daten nach scripts/rausgegangen-dump.json."""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import termine as t

src = Path(os.environ["RAUSGEGANGEN_HTML"]).read_text(encoding="utf-8")
urls = sorted({f"https://rausgegangen.de/events/{m}/" for m in re.findall(r'href="(?:https://rausgegangen\.de)?(?:/en)?/events/([^"/?#]+)/?', src)})
out = {}
for u in urls:
    page = t.fetch(u)
    lds = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            lds.append(json.loads(t.html.unescape(block)))
        except ValueError:
            pass
    tickets = sorted(set(re.findall(r't\.rausgegangen\.de/tickets/([A-Za-z0-9_-]+)', page)))
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    out[u] = {"title": title[1].strip() if title else "", "ld": lds, "tickets": tickets, "len": len(page)}
    print(u, len(page), len(lds), tickets)
Path(__file__).with_name("rausgegangen-dump.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
