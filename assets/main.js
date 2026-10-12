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

const year = document.getElementById('year');
if (year) year.textContent = new Date().getFullYear();
