(() => {
  const root = document.querySelector('[data-work-orders-report]');
  const drawer = document.querySelector('[data-wo-drawer]');
  if (!root || !drawer) return;
  const close = () => { drawer.hidden = true; document.body.classList.remove('wo-drawer-open'); };
  root.querySelector('[data-wo-search]')?.addEventListener('input', event => {
    const term = event.target.value.trim().toLowerCase();
    root.querySelectorAll('[data-wo-row]').forEach(row => { row.hidden = Boolean(term) && !row.dataset.search.toLowerCase().includes(term); });
  });
  root.querySelectorAll('[data-open-wo]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('[data-wo-row]');
    if (!row) return;
    const cells = row.querySelectorAll('td');
    drawer.querySelector('[data-wo-code]').textContent = cells[1].innerText;
    drawer.querySelector('[data-wo-activity]').textContent = cells[2].innerText;
    drawer.querySelector('[data-wo-phase]').textContent = cells[3].innerText;
    drawer.querySelector('[data-wo-status]').textContent = cells[4].innerText;
    drawer.querySelector('[data-wo-quantity]').textContent = `${cells[5].innerText} / ${cells[6].innerText}`;
    drawer.querySelector('[data-wo-cost]').textContent = cells[8].innerText;
    drawer.hidden = false; document.body.classList.add('wo-drawer-open'); drawer.querySelector('[data-close-wo]')?.focus();
  }));
  drawer.querySelector('[data-close-wo]')?.addEventListener('click', close);
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !drawer.hidden) close(); });
})();
