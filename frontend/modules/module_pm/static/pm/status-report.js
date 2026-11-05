(() => {
  const root = document.querySelector('[data-report-page]');
  const panel = root?.querySelector('[data-project-details-panel]');
  if (!root || !panel) return;
  const stages = ['صادر التوجيه', 'قيد التخطيط', 'بانتظار الإقرار', 'بانتظار بدء التنفيذ', 'قيد التنفيذ', 'الاكتمال', 'الاستلام', 'مغلق'];
  const setText = (key, value) => { const node = panel.querySelector(`[data-detail="${key}"]`); if (node) node.textContent = value || 'غير متاح'; };
  const open = button => {
    ['name', 'code', 'client', 'manager', 'status', 'progress', 'start', 'end', 'budget', 'currency'].forEach(key => setText(key, button.dataset[key]));
    setText('stage', `المرحلة ${button.dataset.stage || '—'} من 8`);
    const status = panel.querySelector('[data-detail="status"]');
    status?.classList.remove('directive', 'planning', 'planned', 'executing', 'completed');
    status?.classList.add(button.dataset.statusClass || 'planning');
    const lifecycle = panel.querySelector('[data-detail-lifecycle]');
    if (lifecycle) {
      const current = Number(button.dataset.stage || 0) - 1;
      lifecycle.replaceChildren(...stages.map((label, index) => {
        const item = document.createElement('li');
        item.className = index < current ? 'is-complete' : index === current ? 'is-current' : 'is-upcoming';
        item.innerHTML = `<span>${index < current ? '✓' : index === current ? '●' : '○'}</span><small>${label}</small>`;
        return item;
      }));
    }
    const projectLink = panel.querySelector('[data-detail-link="href"]');
    const reportLink = panel.querySelector('[data-detail-link="report"]');
    if (projectLink) projectLink.href = button.dataset.href || '#';
    if (reportLink) { reportLink.href = button.dataset.report || '#'; reportLink.hidden = !button.dataset.report; }
    panel.hidden = false;
    panel.classList.add('is-open');
    panel.querySelector('[data-project-details-close]')?.focus();
  };
  const close = () => { panel.hidden = true; panel.classList.remove('is-open'); };
  root.querySelectorAll('[data-project-details]').forEach(button => button.addEventListener('click', () => open(button)));
  panel.querySelector('[data-project-details-close]')?.addEventListener('click', close);
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !panel.hidden) close(); });
})();
