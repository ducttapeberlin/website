// Mail-Links: Mailprogramm öffnen und die Adresse zusätzlich kopieren,
// falls kein Mailprogramm eingerichtet ist (oder die Seite eingebettet ist).
document.querySelectorAll('a[href^="mailto:"]').forEach(a => a.addEventListener('click', () => {
  const addr = a.getAttribute('href').slice(7).split('?')[0];
  const done = () => {
    let t = document.querySelector('.mail-toast');
    if (!t) { t = document.createElement('div'); t.className = 'mail-toast'; t.setAttribute('role', 'status'); document.body.append(t); }
    t.textContent = `${addr} kopiert`;
    t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 2600);
  };
  try { navigator.clipboard.writeText(addr).then(done, () => {}); } catch (e) {}
  // In eingebetteten Vorschauen den Link im obersten Fenster öffnen
  if (window.top !== window.self) { try { window.open(a.href, '_top'); } catch (e) {} }
}));
