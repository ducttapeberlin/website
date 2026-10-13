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
document.querySelectorAll('.event[data-date], .featured-dates li[data-date]').forEach(el => {
  if (el.dataset.date < today) el.remove();
});
document.querySelectorAll('.featured').forEach(f => { if (!f.querySelector('.featured-dates li')) f.remove(); });
const upcoming = [...document.querySelectorAll('.event[data-date]')];
const list = document.querySelector('.events');
if (list && !upcoming.length && !document.querySelector('.featured') && !list.querySelector('.events-empty')) {
  list.insertAdjacentHTML('beforeend', '<li class="events-empty">Neue Termine folgen in Kürze.</li>');
}
// Lange Liste kürzen: erst 6 Termine, Rest per Button
const SHOW = 6;
if (list && upcoming.length > SHOW + 1) {
  upcoming.slice(SHOW).forEach(ev => ev.classList.add('is-more'));
  const more = document.createElement('button');
  more.type = 'button';
  more.className = 'btn btn-ghost events-more';
  more.textContent = `Alle ${upcoming.length} Termine zeigen`;
  more.addEventListener('click', () => { list.classList.add('show-all'); more.remove(); });
  list.after(more);
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
