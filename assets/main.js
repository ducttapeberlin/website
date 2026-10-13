// Unterseiten immer oben öffnen (der Browser übernimmt sonst teils die Scrollposition der vorigen Seite)
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
if (!location.hash) window.scrollTo(0, 0);

// Mobile-Menü
const toggle = document.querySelector('.nav-toggle');
const nav = document.getElementById('nav');
if (toggle && nav) {
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open);
  });
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));
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
  list.insertAdjacentHTML('beforeend', '<li class="events-empty">Neue Termine folgen in Kürze.</li>');
}
// Lange Liste kürzen: neben dem Featured-Event erst 4 Termine, "Weitere Termine" zeigt 4 mehr,
// danach führt "Alle Termine anzeigen" auf die Termine-Seite mit Postern und Beschreibungen
const SHOW = 4;
if (list && upcoming.length) {
  const actions = document.createElement('div');
  actions.className = 'events-actions';
  const all = document.createElement('a');
  all.className = 'btn btn-ghost events-more';
  all.href = 'termine.html';
  all.textContent = 'Alle Termine anzeigen';
  if (upcoming.length > SHOW) {
    upcoming.slice(SHOW).forEach(ev => ev.classList.add('is-more'));
    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'btn btn-ghost events-more';
    more.textContent = 'Weitere Termine anzeigen';
    more.addEventListener('click', () => {
      upcoming.filter(ev => ev.classList.contains('is-more')).slice(0, SHOW).forEach(ev => ev.classList.remove('is-more'));
      more.replaceWith(all);
    });
    actions.append(more);
  } else {
    actions.append(all);
  }
  list.after(actions);
}
// Menü "Events": erster Unterpunkt ist die Featured Show, falls es eine gibt
const feat = document.querySelector('.featured');
const featLink = document.querySelector('.nav-featured');
if (feat && featLink) {
  feat.id = 'featured';
  featLink.textContent = feat.querySelector('h3')?.textContent.trim() ?? 'Featured Show';
  // direkt auf die Eventseite, falls verlinkt; sonst zur Karte auf dieser Seite
  const page = feat.querySelector('h3 a[href^="http"]');
  if (page) { featLink.href = page.href; featLink.target = '_blank'; featLink.rel = 'noopener'; }
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
const dlg = document.getElementById('tickets');
if (dlg) {
  const body = document.getElementById('tickets-body');
  document.querySelectorAll('[data-tickets]').forEach(btn => btn.addEventListener('click', () => {
    const slug = btn.dataset.tickets;
    document.getElementById('tickets-title').textContent = btn.dataset.label ?? 'Tickets';
    document.getElementById('tickets-fallback').href = `https://t.rausgegangen.de/tickets/${slug}`;
    body.innerHTML = '<p class="tickets-loading">Ticketshop lädt …</p>';
    const s = document.createElement('script');
    s.src = `https://t.rausgegangen.de/tickets/${slug}/external-loader.js`;
    s.id = 'purchase-widget-loader';
    s.dataset.layout = 'fullwidth';
    body.appendChild(s);
    dlg.showModal();
  }));
  dlg.querySelector('.tickets-close').addEventListener('click', () => dlg.close());
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('close', () => { body.innerHTML = ''; });
}

const year = document.getElementById('year');
if (year) year.textContent = new Date().getFullYear();

// Termine-Seite: aufgeklappte Eventtexte unten wieder zuklappen
document.querySelectorAll('.tevent-desc details').forEach(d => {
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'tevent-less';
  close.textContent = 'Weniger anzeigen';
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
    const ig = (btn.dataset.reels || '').split(' ').filter(Boolean).map(id =>
      `<figure class="reel"><iframe src="https://www.instagram.com/reel/${id}/embed/" allowfullscreen title="Instagram-Video"></iframe>` +
      `<a href="https://www.instagram.com/reel/${id}/" target="_blank" rel="noopener">Auf Instagram öffnen ↗</a></figure>`).join('');
    body.innerHTML = (yt ? `<h3 class="reels-label">hot stuff × eBay · YouTube</h3><div class="yt-grid">${yt}</div>` +
      (btn.dataset.playlist ? `<a class="reels-more" href="https://www.youtube.com/playlist?list=${btn.dataset.playlist}" target="_blank" rel="noopener">Alle Folgen auf YouTube ↗</a>` : '') : '') +
      (ig ? `<h3 class="reels-label">Instagram</h3><div class="reels-grid">${ig}</div>` : '');
    reels.showModal();
  }));
  reels.querySelector('.tickets-close').addEventListener('click', () => reels.close());
  reels.addEventListener('click', e => { if (e.target === reels) reels.close(); });
  reels.addEventListener('close', () => { body.innerHTML = ''; });
}
