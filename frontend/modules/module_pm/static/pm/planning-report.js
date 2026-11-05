(() => {
  const root = document.querySelector('[data-planning-report]');
  const panel = root?.querySelector('[data-planning-details]');
  if (!root || !panel) return;
  const set = (key, value) => { const node = panel.querySelector(`[data-detail="${key}"]`); if (node) node.textContent = value || 'غير متاح'; };
  root.querySelectorAll('[data-wbs-details]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('[data-wbs-row]');
    const title = row?.querySelector('.wbs-name strong, .timeline-name strong')?.textContent?.trim() || 'العنصر';
    const titleNode = panel.querySelector('#planning-details-title');
    if (titleNode) titleNode.textContent = title;
    ['kind', 'code', 'phase', 'planned', 'actual'].forEach(key => set(key, button.dataset[key]));
    panel.hidden = false;
    panel.querySelector('[data-planning-details-close]')?.focus();
  }));
  panel.querySelector('[data-planning-details-close]')?.addEventListener('click', () => { panel.hidden = true; });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') panel.hidden = true; });
  const search = root.querySelector('#planning-wbs-search');
  const filterRows = () => {
    const term = search?.value.trim().toLocaleLowerCase('ar') || '';
    root.querySelectorAll('[data-search-text]').forEach(row => { row.hidden = Boolean(term) && !row.dataset.searchText.toLocaleLowerCase('ar').includes(term); });
  };
  search?.addEventListener('input', filterRows);
  root.querySelector('[data-show-all]')?.addEventListener('click', () => { search.value = ''; filterRows(); root.querySelector('.planning-overdue')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  root.querySelector('[data-wbs-expand]')?.addEventListener('click', () => root.querySelectorAll('[data-wbs-row]').forEach(row => { row.hidden = false; }));
  root.querySelector('[data-wbs-collapse]')?.addEventListener('click', () => root.querySelectorAll('[data-wbs-row]').forEach(row => { row.hidden = false; }));
})();
