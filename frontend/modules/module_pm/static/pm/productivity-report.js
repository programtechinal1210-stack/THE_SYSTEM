(() => {
  const root = document.querySelector('[data-productivity-report]');
  const drawer = root?.querySelector('[data-pr-drawer]');
  if (!root || !drawer) return;
  const set = (key, value) => { const node = drawer.querySelector(`[data-detail="${key}"]`); if (node) node.textContent = value || 'غير متاح'; };
  root.querySelectorAll('[data-pr-details]').forEach(button => button.addEventListener('click', () => {
    set('name', button.dataset.name); set('code', button.dataset.code); set('path', `${button.dataset.phase || '—'} / ${button.dataset.task || '—'}`);
    ['quantity','hours','time-type','target','actual','status','source','reason'].forEach(key => set(key, button.dataset[key]));
    drawer.hidden = false; drawer.querySelector('[data-pr-close]')?.focus();
  }));
  drawer.querySelector('[data-pr-close]')?.addEventListener('click', () => { drawer.hidden = true; });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') drawer.hidden = true; });
  const search = root.querySelector('[data-pr-search]');
  search?.addEventListener('input', () => { const term = search.value.trim().toLocaleLowerCase('ar'); root.querySelectorAll('[data-pr-row]').forEach(row => { row.hidden = Boolean(term) && !row.dataset.prSearch.toLocaleLowerCase('ar').includes(term); }); });
})();
