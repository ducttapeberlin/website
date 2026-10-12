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

// Vergangene Termine ausblenden, nächsten Termin oben anzeigen
const today = new Date().toISOString().slice(0, 10);
const upcoming = [];
document.querySelectorAll('.event[data-date]').forEach(ev => {
  if (ev.dataset.date < today) ev.remove();
  else upcoming.push(ev);
});
const first = upcoming[0];
const strip = document.getElementById('next-up');
if (first && strip) {
  const tag = first.querySelector('.event-tag')?.textContent ?? '';
  const title = first.querySelector('h3')?.textContent ?? '';
  document.getElementById('next-title').textContent = `Next: ${tag} – ${title}`;
  document.getElementById('next-when').textContent = first.querySelector('.event-date')?.firstChild.textContent.trim() ?? '';
  strip.hidden = false;
}

// Leistungs-Kacheln: Bilder aus data-images laden, beim Hover (Handy: wenn sichtbar) als Slideshow abspielen
const touch = window.matchMedia('(hover: none)').matches;
document.querySelectorAll('.service[data-images]').forEach(tile => {
  const srcs = tile.dataset.images.split(',').map(s => s.trim()).filter(Boolean);
  if (!srcs.length) return;
  const media = tile.querySelector('.service-media');
  const imgs = srcs.map(src => {
    const img = document.createElement('img');
    img.src = src; img.alt = ''; img.loading = 'lazy';
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

// Tickets: rausgegangen-Shop erst beim Klick laden (Datenschutz) und im Overlay anzeigen
const dlg = document.getElementById('tickets');
if (dlg) {
  const body = document.getElementById('tickets-body');
  document.querySelectorAll('[data-tickets]').forEach(btn => btn.addEventListener('click', () => {
    const slug = btn.dataset.tickets;
    const event = btn.closest('.event');
    const day = event?.querySelector('.event-date small')?.textContent ?? '';
    const date = event?.querySelector('.event-date')?.firstChild.textContent.trim() ?? '';
    document.getElementById('tickets-title').textContent = `${event?.querySelector('h3')?.textContent ?? 'Tickets'} · ${day} ${date}`;
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
