(() => {
  const tabs = [...document.querySelectorAll('[data-detail-tab]')];
  const panels = [...document.querySelectorAll('[data-detail-panel]')];
  if (!tabs.length) return;
  const activate = key => {
    tabs.forEach(tab => tab.setAttribute('aria-selected', String(tab.dataset.detailTab === key)));
    panels.forEach(panel => {
      const active = panel.dataset.detailPanel === key;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });
  };
  tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.detailTab)));
  activate(tabs.find(tab => tab.getAttribute('aria-selected') === 'true')?.dataset.detailTab || 'overview');
})();
