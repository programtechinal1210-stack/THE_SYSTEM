(() => {
  const root = document.querySelector('[data-portfolio-report]');
  if (!root) return;
  const panel = root.querySelector('[data-portfolio-panel]');
  const set = (key, value) => { const node = panel?.querySelector(`[data-detail="${key}"]`); if (node) node.textContent = value || 'غير متاح'; };
  root.querySelectorAll('[data-portfolio-details]').forEach(button => button.addEventListener('click', () => {
    const data = button.dataset;
    const title = panel.querySelector('#portfolio-details-title');
    if (title) title.textContent = data.name || 'المشروع';
    ['code','status','progress','planned','actual','reason'].forEach(key => set(key, data[key]));
    const link = panel.querySelector('[data-detail-link]');
    if (link) link.href = data.href || '#';
    panel.hidden = false;
    panel.querySelector('[data-portfolio-close]')?.focus();
  }));
  panel.querySelector('[data-portfolio-close]')?.addEventListener('click', () => { panel.hidden = true; });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && panel) panel.hidden = true; });
  const search = root.querySelector('[data-portfolio-search]');
  search?.addEventListener('input', () => {
    const term = search.value.trim().toLocaleLowerCase('ar');
    root.querySelectorAll('[data-portfolio-row]').forEach(row => { row.hidden = term && !row.dataset.search.toLocaleLowerCase('ar').includes(term); });
  });
  root.querySelector('[data-portfolio-export]')?.addEventListener('click', () => {
    const params = new URLSearchParams(window.location.search);
    params.set('download', 'json');
    window.location.href = `?${params.toString()}`;
  });
})();
