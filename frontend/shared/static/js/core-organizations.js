(() => {
  const root = document.querySelector('[data-org-workspace]');
  if (!root) return;
  const records = [...root.querySelectorAll('[data-org-record]')];
  const search = root.querySelector('[data-org-search]');
  search?.addEventListener('input', () => {
    const term = search.value.trim().toLocaleLowerCase();
    records.forEach((record) => { record.hidden = term && !record.textContent.toLocaleLowerCase().includes(term); });
  });
  root.querySelectorAll('[data-org-tab]').forEach((tab) => tab.addEventListener('click', () => {
    root.querySelectorAll('[data-org-tab]').forEach((item) => { item.classList.toggle('selected', item === tab); item.setAttribute('aria-selected', item === tab ? 'true' : 'false'); });
    root.querySelectorAll('[data-org-panel]').forEach((panel) => { panel.classList.toggle('org-panel-focus', tab.dataset.orgTab === 'entities' ? panel.dataset.orgPanel === 'entities' : panel.dataset.orgPanel === 'units'); });
  }));
})();
