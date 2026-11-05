(() => {
  const report = document.querySelector('[data-execution-report]');
  const drawer = document.querySelector('[data-activity-drawer]');
  if (!report || !drawer) return;
  const fields = {
    name: '[data-drawer-name]', code: '[data-drawer-code]', hierarchy: '[data-drawer-hierarchy]',
    planned: '[data-drawer-planned]', actual: '[data-drawer-actual]', remaining: '[data-drawer-remaining]',
    progress: '[data-drawer-progress]', dates: '[data-drawer-dates]', orders: '[data-drawer-orders]'
  };
  const close = () => { drawer.hidden = true; document.body.classList.remove('execution-drawer-open'); };
  report.querySelectorAll('[data-open-activity]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('[data-activity-row]');
    if (!row) return;
    Object.entries(fields).forEach(([key, selector]) => {
      const field = drawer.querySelector(selector);
      if (!field) return;
      if (key === 'hierarchy') field.textContent = `${row.dataset.phase} / ${row.dataset.task}`;
      else if (key === 'dates') field.textContent = `${row.dataset.start} — ${row.dataset.end}`;
      else field.textContent = row.dataset[key] || 'غير متاح';
    });
    drawer.hidden = false;
    document.body.classList.add('execution-drawer-open');
    drawer.querySelector('[data-close-activity]')?.focus();
  }));
  drawer.querySelector('[data-close-activity]')?.addEventListener('click', close);
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !drawer.hidden) close(); });
})();
