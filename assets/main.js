// Sprache der Seite: Texte, die das Skript selbst einsetzt, gibt es auf Deutsch und Englisch
const EN = document.documentElement.lang === 'en';
const t = (de, en) => EN ? en : de;

// Unterseiten immer oben öffnen (der Browser übernimmt sonst teils die Scrollposition der vorigen Seite)
// Ohne Sprungmarke nach ganz oben, mit Sprungmarke genau zum Abschnitt. Nach dem Laden von Bildern und
// Schriften wird das wiederholt, damit sich nichts verschiebt, außer man hat inzwischen selbst gescrollt.
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
const goStart = () => {
  const id = decodeURIComponent(location.hash.slice(1));
  const el = id && document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'instant', block: 'start' });
  else if (!id) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
};
let userScrolled = false;
['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(e => addEventListener(e, () => { userScrolled = true; }, { once: true, passive: true }));
goStart();
addEventListener('DOMContentLoaded', () => { if (!userScrolled) goStart(); });
addEventListener('load', () => { if (!userScrolled) goStart(); setTimeout(() => { if (!userScrolled) goStart(); }, 300); });

// Mobile-Menü
const toggle = document.querySelector('.nav-toggle');
const nav = document.getElementById('nav');
if (toggle && nav) {
  const mobile = matchMedia('(max-width: 820px)');
  const groups = [...nav.querySelectorAll('.nav-group')];
  const setOpen = open => {
    nav.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', open);
    document.documentElement.classList.toggle('nav-locked', open);
    if (!open) groups.forEach(g => { g.classList.remove('is-open'); g.firstElementChild.setAttribute('aria-expanded', 'false'); });
  };
  toggle.addEventListener('click', () => setOpen(!nav.classList.contains('open')));
  // Mobil: Hauptpunkte klappen ihre Unterpunkte auf (immer nur einer offen)
  groups.forEach(g => {
    const head = g.firstElementChild;
    head.setAttribute('aria-expanded', 'false');
    head.addEventListener('click', e => {
      if (!mobile.matches) return;
      e.preventDefault();
      e.stopPropagation();
      const open = !g.classList.contains('is-open');
      groups.forEach(o => { o.classList.toggle('is-open', o === g && open); o.firstElementChild.setAttribute('aria-expanded', o === g && open); });
    });
  });
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => { if (!a.matches('.nav-group > a') || !mobile.matches) setOpen(false); }));
  mobile.addEventListener('change', () => setOpen(false));
}

// Vergangene Termine ausblenden (auch Tage in Highlight-Karten), nächsten Termin oben anzeigen
const today = new Date().toLocaleDateString('sv-SE');
document.querySelectorAll('.event[data-date], .featured-dates li[data-date], .tevent[data-date]').forEach(el => {
  if (el.dataset.date < today) el.remove();
});
document.querySelectorAll('.month').forEach(m => { if (!m.querySelector('.tevent')) m.remove(); });
document.querySelectorAll('.featured').forEach(f => { if (!f.querySelector('.featured-dates li')) f.remove(); });
const upcoming = [...document.querySelectorAll('.event[data-date]')];
const list = document.querySelector('.events');
if (list && !upcoming.length && !document.querySelector('.featured') && !list.querySelector('.events-empty')) {
  list.insertAdjacentHTML('beforeend', `<li class="events-empty">${t('Neue Termine folgen in Kürze.', 'New dates coming soon.')}</li>`);
}
// Lange Liste kürzen: neben dem Featured-Event erst 4 Termine, "Weitere Termine" zeigt 4 mehr,
// danach führt "Alle Termine anzeigen" auf die Termine-Seite mit Postern und Beschreibungen
const fmtPage = !!list?.closest('.fmt-dates');
const SHOW = fmtPage ? 3 : 4;
if (list && upcoming.length) {
  const actions = document.createElement('div');
  actions.className = 'events-actions';
  const all = document.createElement('a');
  all.className = 'btn btn-ghost events-more';
  all.href = t('termine', 'dates');
  all.textContent = t('Alle Termine anzeigen', 'See all dates');
  if (upcoming.length > SHOW) {
    upcoming.slice(SHOW).forEach(ev => ev.classList.add('is-more'));
    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'btn btn-ghost events-more';
    more.textContent = t('Weitere Termine anzeigen', 'Show more dates');
    more.addEventListener('click', () => {
      // Format-Seiten (Drag Brunch usw.): alle eigenen Termine zeigen, kein Link auf alle Termine
      upcoming.filter(ev => ev.classList.contains('is-more')).slice(0, fmtPage ? undefined : SHOW).forEach(ev => ev.classList.remove('is-more'));
      fmtPage ? more.remove() : more.replaceWith(all);
    });
    actions.append(more);
  } else if (!fmtPage) {
    actions.append(all);
  }
  if (actions.children.length) list.after(actions);
}
// Menü "Events": erster Unterpunkt ist die Featured Show, falls es eine gibt
const feat = document.querySelector('.featured');
const featLink = document.querySelector('.nav-featured');
if (feat && featLink) {
  feat.id = 'featured';
  featLink.textContent = feat.querySelector('h3')?.textContent.trim() ?? 'Featured Show';
  // direkt auf die Eventseite, falls verlinkt; sonst zur Karte auf dieser Seite
  const page = feat.querySelector('h3 a[href]');
  if (page) { featLink.href = page.href; if (page.target) { featLink.target = '_blank'; featLink.rel = 'noopener'; } }
  featLink.hidden = false;
}

const first = [...document.querySelectorAll('.event[data-date], .featured-dates li[data-date]')]
  .sort((a, b) => a.dataset.date.localeCompare(b.dataset.date))[0];
const strip = document.getElementById('next-up');
if (first && strip) {
  const box = first.closest('.featured') ?? first;
  const tag = box.querySelector('.event-tag')?.textContent ?? '';
  const title = box.querySelector('h3')?.textContent ?? '';
  const label = !tag || title.toLowerCase().includes(tag.toLowerCase()) ? title : `${tag} – ${title}`;
  const d = first.dataset.date;
  document.getElementById('next-title').textContent = `Next: ${label}`;
  document.getElementById('next-when').textContent = `${d.slice(8, 10)}.${d.slice(5, 7)}.`;
  strip.hidden = false;
}

// Leistungs-Kacheln: Bilder aus data-images laden, beim Hover (Handy: wenn sichtbar) als Slideshow abspielen
const touch = window.matchMedia('(hover: none)').matches;
document.querySelectorAll('.service[data-images]').forEach(tile => {
  const srcs = tile.dataset.images.split(',').map(s => s.trim()).filter(Boolean);
  if (!srcs.length) return;
  const media = tile.querySelector('.service-media');
  const imgs = srcs.map(entry => {
    const [src, pos] = entry.split('@').map(s => s.trim());
    const img = document.createElement('img');
    img.src = src; img.alt = ''; img.loading = 'lazy';
    if (pos) img.style.objectPosition = pos;
    media.appendChild(img);
    return img;
  });
  let i = 0, timer = null;
  imgs[0].classList.add('on');
  const step = () => { imgs[i].classList.remove('on'); i = (i + 1) % imgs.length; imgs[i].classList.add('on'); };
  const play = () => { tile.classList.add('playing'); if (!timer && imgs.length > 1) { step(); timer = setInterval(step, 1400); } };
  const stop = () => { tile.classList.remove('playing'); clearInterval(timer); timer = null; };
  if (touch) {
    new IntersectionObserver(([e]) => e.isIntersecting ? play() : stop(), { threshold: .6 }).observe(tile);
  } else {
    tile.addEventListener('mouseenter', play);
    tile.addEventListener('mouseleave', stop);
  }
});

// Leistungen-Seite: Kacheln mit mehreren Bildern laufen beim Drüberfahren als Slideshow durch
document.querySelectorAll('.offer[data-images]').forEach(tile => {
  const media = tile.querySelector('.offer-frame');
  const first = media.querySelector('img');
  const imgs = [first, ...tile.dataset.images.split(',').map(s => s.trim()).filter(Boolean).slice(1).map(entry => {
    const [src, pos] = entry.split('@').map(s => s.trim());
    const img = document.createElement('img');
    img.src = src; img.alt = ''; img.loading = 'lazy';
    if (pos) img.style.objectPosition = pos;
    media.appendChild(img);
    return img;
  })];
  if (imgs.length < 2) return;
  tile.classList.add('slides');
  let i = 0, timer = null;
  first.classList.add('on');
  const step = () => { imgs[i].classList.remove('on'); i = (i + 1) % imgs.length; imgs[i].classList.add('on'); };
  const play = () => { if (!timer) { step(); timer = setInterval(step, 1400); } };
  const stop = () => { clearInterval(timer); timer = null; };
  if (touch) {  // Handy: solange die Kachel in der Bildmitte ist
    new IntersectionObserver(([e]) => e.isIntersecting ? play() : stop(), { rootMargin: '-40% 0px -40% 0px' }).observe(tile);
  } else {
    tile.addEventListener('mouseenter', play);
    tile.addEventListener('mouseleave', stop);
  }
});

// Leistungen auf dem Handy: die Kachel in der Bildmitte tritt nach vorne
if (touch) {
  document.querySelectorAll('.offer').forEach(o => new IntersectionObserver(([e]) => o.classList.toggle('is-pop', e.isIntersecting),
    { rootMargin: '-40% 0px -40% 0px' }).observe(o));
}

// Mitglieder: auf dem Handy tritt die Figur aus dem Rahmen, sobald die Karte mittig im Bild ist
if (touch) {
  document.querySelectorAll('.member').forEach(m => new IntersectionObserver(([e]) => m.classList.toggle('is-pop', e.isIntersecting),
    { rootMargin: '-35% 0px -35% 0px' }).observe(m));
}

// Tickets: rausgegangen-Shop erst beim Klick laden (Datenschutz) und im Overlay anzeigen
// Eventseite: Terminauswahl steuert Datum und Ticket-Button; ?tag=JJJJ-MM-TT wählt den Tag vor
document.querySelectorAll('.xs-card').forEach(card => {
  const buy = card.querySelector('.xs-buy');
  const pick = b => {
    card.querySelectorAll('.xs-date').forEach(x => { x.classList.toggle('is-active', x === b); x.setAttribute('aria-pressed', x === b); });
    card.querySelector('.xs-day').textContent = b.dataset.day;
    buy.dataset.tickets = b.dataset.slug;
    buy.dataset.label = b.dataset.label;
  };
  card.querySelectorAll('.xs-date').forEach(b => b.addEventListener('click', () => pick(b)));
  const tag = new URLSearchParams(location.search).get('tag');
  const pre = tag && card.querySelector(`.xs-date[data-date="${CSS.escape(tag)}"]`);
  if (pre) pick(pre);
});

// Ticket-Buttons öffnen den rausgegangen-Shop direkt in einem neuen Tab (eingebettet war der Zahlungsschritt nicht sauber darstellbar)
document.querySelectorAll('[data-tickets]').forEach(btn => btn.addEventListener('click', () => {
  window.open(`https://t.rausgegangen.de/tickets/${btn.dataset.tickets}`, '_blank', 'noopener');
}));

const year = document.getElementById('year');
if (year) year.textContent = new Date().getFullYear();

// Termine-Seite: aufgeklappte Eventtexte unten wieder zuklappen
document.querySelectorAll('.tevent-desc details').forEach(d => {
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'tevent-less';
  close.textContent = t('Weniger anzeigen', 'Show less');
  close.addEventListener('click', () => {
    d.open = false;
    const card = d.closest('.tevent');
    if (card.getBoundingClientRect().top < 0) card.scrollIntoView({ block: 'start' });
  });
  d.appendChild(close);
});

// Kooperationen: Reels im Fenster, Instagram wird erst beim Klick geladen
const reels = document.getElementById('reels');
if (reels) {
  const body = document.getElementById('reels-body');
  document.querySelectorAll('[data-reels]').forEach(btn => btn.addEventListener('click', () => {
    const yt = (btn.dataset.youtube || '').split(' ').filter(Boolean).map(id =>
      `<figure class="yt"><iframe src="https://www.youtube-nocookie.com/embed/${id}?rel=0" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen title="YouTube-Video"></iframe></figure>`).join('');
    const titles = (btn.dataset.reelTitles || '').split('|');
    const ig = (btn.dataset.reels || '').split(' ').filter(Boolean).map((id, n) =>
      `<figure class="reel">${titles[n] ? `<figcaption class="reels-label">${titles[n]}</figcaption>` : ''}` +
      `<div class="reel-frame"><iframe src="https://www.instagram.com/reel/${id}/embed/" scrolling="no" allowfullscreen title="${titles[n] || 'Instagram-Video'}"></iframe></div>` +
      `<a href="https://www.instagram.com/reel/${id}/" target="_blank" rel="noopener">${t('Mehr auf Instagram', 'More on Instagram')} ↗</a></figure>`).join('');
    body.innerHTML = (yt ? `<h3 class="reels-label">eBay · hot stuff</h3>` +
      `<p class="reels-desc">${t('Talkshow-Reihe auf YouTube, umgesetzt von DUCT TAPE in Kooperation mit eBay.', 'YouTube talk show series, produced by DUCT TAPE in collaboration with eBay.')}</p>` +
      `<div class="yt-grid">${yt}</div>` +
      (btn.dataset.playlist ? `<a class="reels-more" href="https://www.youtube.com/playlist?list=${btn.dataset.playlist}" target="_blank" rel="noopener">${t('Alle Folgen auf YouTube', 'All episodes on YouTube')} ↗</a>` : '') : '') +
      (ig ? `<div class="reels-grid">${ig}</div>` : '');
    reels.showModal();
  }));
  reels.querySelector('.tickets-close').addEventListener('click', () => reels.close());
  reels.addEventListener('click', e => { if (e.target === reels) reels.close(); });
  reels.addEventListener('close', () => { body.innerHTML = ''; });
}

// Newsletter-Anmeldung an Brevo schicken, ohne die Seite zu verlassen
const nlForm = document.getElementById('nl-form');
if (nlForm) {
  const msg = document.getElementById('nl-msg');
  nlForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = nlForm.querySelector('button');
    btn.disabled = true;
    try {
      await fetch(nlForm.action + '?isAjax=1', { method: 'POST', body: new FormData(nlForm), mode: 'no-cors' });
      msg.textContent = t('Fast geschafft! Bitte bestätige deine Anmeldung über den Link in der Mail, die wir dir gerade geschickt haben.', 'Almost there! Please confirm your subscription via the link in the email we just sent you.');
      nlForm.style.display = 'none';
    } catch {
      // Falls der direkte Versand blockiert ist: normal an Brevo schicken (öffnet Brevos Bestätigung in neuem Tab)
      nlForm.target = '_blank';
      HTMLFormElement.prototype.submit.call(nlForm);
      msg.textContent = t('Fast geschafft! Bitte bestätige deine Anmeldung über den Link in der Mail, die wir dir gerade geschickt haben.', 'Almost there! Please confirm your subscription via the link in the email we just sent you.');
      nlForm.style.display = 'none';
    }
    msg.hidden = false;
  });
}

// Galerie: Filter nach Kategorie und Großansicht mit Blättern
const gal = document.getElementById('gal-grid');
if (gal) {
  const items = [...gal.querySelectorAll('.gal-item')];
  document.querySelectorAll('.gal-tab').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.gal-tab').forEach(x => x.setAttribute('aria-pressed', x === tab));
    items.forEach(a => { a.hidden = tab.dataset.cat !== 'all' && a.dataset.cat !== tab.dataset.cat; });
  }));
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lb-img');
  const cap = document.getElementById('lb-cap');
  let cur = 0;
  const visible = () => items.filter(a => !a.hidden && a.tagName === 'A');
  const show = i => {
    const v = visible();
    cur = (i + v.length) % v.length;
    const a = v[cur], thumb = a.querySelector('img');
    img.src = a.href; img.alt = thumb.alt; cap.textContent = 'caption' in a.dataset ? a.dataset.caption : thumb.alt;
  };
  items.filter(a => a.tagName === 'A').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    show(visible().indexOf(a));
    lb.showModal();
  }));
  lb.querySelector('.lb-prev').addEventListener('click', () => show(cur - 1));
  lb.querySelector('.lb-next').addEventListener('click', () => show(cur + 1));
  lb.querySelector('.lb-close').addEventListener('click', () => lb.close());
  lb.addEventListener('click', e => { if (e.target === lb) lb.close(); });
  lb.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') show(cur - 1);
    if (e.key === 'ArrowRight') show(cur + 1);
  });
  // Videos in der Galerie laufen nur, solange sie zu sehen sind
  const vids = gal.querySelectorAll('.gal-vid video');
  if (vids.length && 'IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) e.target.play().catch(() => {}); else e.target.pause();
    }), { threshold: .4 });
    vids.forEach(v => io.observe(v));
  }
  let x0 = null;
  lb.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
  lb.addEventListener('touchend', e => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) show(cur + (dx < 0 ? 1 : -1));
    x0 = null;
  });
}

// Profil: Porträts im Hero wechseln alle 2 Sekunden
document.querySelectorAll('.q-rot').forEach(box => {
  const imgs = [...box.querySelectorAll('img')];
  if (imgs.length < 2 || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  let i = 0;
  setInterval(() => {
    imgs[i].classList.remove('is-on');
    i = (i + 1) % imgs.length;
    imgs[i].classList.add('is-on');
  }, 2000);
});

// Kollektiv: Ton bei Videos zuschalten (laufen stumm automatisch)
document.querySelectorAll('.kv-mute').forEach(btn => {
  const v = btn.parentElement.querySelector('video');
  const lab = btn.getAttribute('aria-label');
  const off = document.documentElement.lang === 'en' ? 'Sound off' : 'Ton aus';
  btn.addEventListener('click', () => {
    const on = v.muted;
    if (on) document.querySelectorAll('.kv-vwrap video').forEach(o => { if (o !== v) { o.muted = true; const b = o.parentElement.querySelector('.kv-mute'); if (b) { b.setAttribute('aria-pressed', 'false'); b.setAttribute('aria-label', lab); } } });
    v.muted = !on; if (on) { v.currentTime = 0; v.play(); }
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.setAttribute('aria-label', on ? off : lab);
  });
});

// Booking-Anfrage: Zeitstempel (Spamschutz), Herkunft (Google-Ads-Messung), Act aus ?act= vorauswählen, Fehlerhinweis
(() => {
  const f = document.getElementById('enq-form'); if (!f) return;
  const q = new URLSearchParams(location.search);
  document.getElementById('enq-t').value = Math.floor(Date.now() / 1000);
  const src = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'gclid'].filter(k => q.get(k)).map(k => k + '=' + q.get(k));
  try { if (document.referrer) src.push('ref=' + new URL(document.referrer).hostname); } catch (e) {}
  document.getElementById('enq-src').value = src.join('; ').slice(0, 300);
  const act = document.getElementById('enq-act'); if (q.get('act') && act.querySelector(`option[value="${CSS.escape(q.get('act'))}"]`)) act.value = q.get('act');
  // Format aus ?programm= vorauswählen (Reihenfolge der Optionen ist in DE und EN gleich)
  const prog = { show: 1, bingo: 2, brunch: 3 }[q.get('programm')];
  if (prog) f.querySelector('select[name="programm"]').selectedIndex = prog;
  if (q.get('fehler')) document.getElementById('form-error').hidden = false;
})();

// Booking-Anfrage: großer Kalender zum Datumsfeld (Eintippen geht weiterhin)
(() => {
  const inp = document.getElementById('enq-date'); if (!inp) return;
  const en = document.documentElement.lang === 'en';
  const monate = en ? ['January','February','March','April','May','June','July','August','September','October','November','December']
                    : ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
  const tage = en ? ['Mo','Tu','We','Th','Fr','Sa','Su'] : ['Mo','Di','Mi','Do','Fr','Sa','So'];
  const p2 = n => String(n).padStart(2, '0');
  const heute = new Date(); heute.setHours(0, 0, 0, 0);
  const cal = document.createElement('div'); cal.className = 'enq-cal'; cal.hidden = true;
  inp.parentNode.style.position = 'relative'; inp.after(cal);
  let ansicht = new Date(heute.getFullYear(), heute.getMonth(), 1);
  const gewaehlt = () => { const m = inp.value.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/); return m ? new Date(+m[3], m[2] - 1, +m[1]) : null; };
  const zeichne = () => {
    const j = ansicht.getFullYear(), mo = ansicht.getMonth(), sel = gewaehlt();
    const start = (new Date(j, mo, 1).getDay() + 6) % 7, anzahl = new Date(j, mo + 1, 0).getDate();
    let h = `<div class="enq-cal-kopf"><button type="button" data-n="-1" aria-label="${en ? 'Previous month' : 'Voriger Monat'}">‹</button><strong>${monate[mo]} ${j}</strong><button type="button" data-n="1" aria-label="${en ? 'Next month' : 'Nächster Monat'}">›</button></div><div class="enq-cal-grid">`;
    h += tage.map(t => `<span class="enq-cal-wt">${t}</span>`).join('') + '<span></span>'.repeat(start);
    for (let d = 1; d <= anzahl; d++) {
      const dt = new Date(j, mo, d), cls = [dt.getTime() === heute.getTime() ? 'heute' : '', sel && dt.getTime() === sel.getTime() ? 'an' : ''].join(' ');
      h += `<button type="button" class="${cls}" data-d="${d}"${dt < heute ? ' disabled' : ''}>${d}</button>`;
    }
    cal.innerHTML = h + '</div>';
  };
  const auf = () => { const s = gewaehlt(); if (s) ansicht = new Date(s.getFullYear(), s.getMonth(), 1); zeichne(); cal.hidden = false; };
  inp.addEventListener('focus', auf); inp.addEventListener('click', auf);
  inp.addEventListener('keydown', e => { if (e.key === 'Escape' || e.key === 'Tab') cal.hidden = true; });
  cal.addEventListener('mousedown', e => e.preventDefault());
  cal.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.n) { ansicht.setMonth(ansicht.getMonth() + +b.dataset.n); zeichne(); return; }
    inp.value = `${p2(b.dataset.d)}.${p2(ansicht.getMonth() + 1)}.${ansicht.getFullYear()}`; cal.hidden = true;
  });
  document.addEventListener('click', e => { if (e.target !== inp && !cal.contains(e.target)) cal.hidden = true; });
})();

// Schwebender Booking-Button: immer sichtbar, verschwindet, solange einer der normalen Booking-Buttons im Bild ist
(() => {
  document.querySelectorAll('.float-book').forEach(btn => {
    const ziele = btn.dataset.hideAt.split(' ').map(id => document.getElementById(id)).filter(Boolean);
    if (!ziele.length || !('IntersectionObserver' in window)) return;
    const sichtbar = new Set();
    const io = new IntersectionObserver(es => {
      es.forEach(e => e.isIntersecting ? sichtbar.add(e.target) : sichtbar.delete(e.target));
      btn.classList.toggle('weg', sichtbar.size > 0);
    });
    ziele.forEach(z => io.observe(z));
  });
})();

// Kollektiv mobil: lange Textblöcke gekürzt, mit „Mehr lesen“ aufklappbar
(() => {
  const en = document.documentElement.lang === 'en';
  document.querySelectorAll('.kv-more').forEach(box => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'kv-more-btn'; b.setAttribute('aria-expanded', 'false');
    b.textContent = en ? 'Read more' : 'Mehr lesen';
    b.addEventListener('click', () => {
      const auf = box.classList.toggle('offen');
      b.setAttribute('aria-expanded', auf ? 'true' : 'false');
      b.textContent = auf ? (en ? 'Show less' : 'Weniger anzeigen') : (en ? 'Read more' : 'Mehr lesen');
      if (!auf) box.scrollIntoView({ block: 'nearest' });
    });
    box.append(b);
  });
})();
