(() => {
  const root = document.querySelector('[data-dw-report]');
  if (!root) return;
  root.querySelector('[data-search]')?.addEventListener('input', event => {
    const value = event.target.value.trim().toLocaleLowerCase();
    root.querySelectorAll('[data-item-row]').forEach(row => {
      row.hidden = Boolean(value) && !row.dataset.search.toLocaleLowerCase().includes(value);
    });
  });
  root.querySelector('[data-print]')?.addEventListener('click', () => window.print());
})();
