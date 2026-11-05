(() => {
  const root = document.querySelector('[data-approval-page]');
  if (!root) return;
  const summary = root.querySelector('.approval-progress-summary');
  const total = Number(summary?.dataset.total || 0);
  const approved = Number(summary?.dataset.approved || 0);
  const percent = total ? Math.round((approved / total) * 100) : 0;
  const percentNode = summary?.querySelector('[data-approval-percent], .approval-ring strong');
  if (percentNode) percentNode.textContent = `${percent}%`;
  summary?.querySelector('.approval-ring')?.style.setProperty('--approval-percent', `${percent}%`);

  const cards = [...root.querySelectorAll('[data-approval-card]')];
  let filter = 'all';
  const applyFilter = () => {
    const query = (root.querySelector('[data-approval-search]')?.value || '').trim().toLocaleLowerCase();
    cards.forEach(card => {
      const matchesFilter = filter === 'all' || card.dataset.status === filter;
      const matchesSearch = !query || (card.dataset.search || '').toLocaleLowerCase().includes(query);
      card.hidden = !(matchesFilter && matchesSearch);
    });
  };
  root.querySelectorAll('[data-approval-filter]').forEach(button => {
    button.addEventListener('click', () => {
      filter = button.dataset.approvalFilter;
      root.querySelectorAll('[data-approval-filter]').forEach(item => item.classList.toggle('is-active', item === button));
      applyFilter();
    });
  });
  root.querySelector('[data-approval-search]')?.addEventListener('input', applyFilter);

  const panel = root.querySelector('[data-approval-panel]');
  const backdrop = root.querySelector('[data-approval-backdrop]');
  const closePanel = () => {
    panel?.classList.remove('is-open');
    backdrop?.classList.remove('is-open');
    panel?.setAttribute('aria-hidden', 'true');
  };
  root.querySelector('[data-approval-panel-close]')?.addEventListener('click', closePanel);
  backdrop?.addEventListener('click', closePanel);
  root.querySelectorAll('[data-approval-details]').forEach(button => {
    button.addEventListener('click', () => {
      const card = button.closest('[data-approval-card]');
      const requirements = document.querySelectorAll('[data-activity-requirements]')[cards.indexOf(card)];
      const requirementText = requirements ? requirements.innerHTML : '<span>لا توجد احتياجات مسجلة.</span>';
      const history = `<section class="approval-history"><h3>سجل الإقرار</h3><dl class="approval-detail-list"><div><dt>الحالة</dt><dd>${card.querySelector('.approval-badge')?.textContent || '—'}</dd></div><div><dt>السبب أو الملاحظة</dt><dd>${card.querySelector('.approval-reason')?.textContent || 'لا توجد ملاحظة.'}</dd></div><div><dt>المستخدم والتاريخ</dt><dd>يعرضهما سجل التدقيق بعد القرار.</dd></div></dl></section>`;
      panel.querySelector('[data-approval-detail-title]').textContent = card.querySelector('h2').textContent;
      panel.querySelector('[data-approval-detail-content]').innerHTML = `<p class="approval-path">${card.querySelector('.approval-path').innerHTML}</p><dl class="approval-detail-list">${[...card.querySelectorAll('.approval-metrics div')].map(item => `<div>${item.innerHTML}</div>`).join('')}</dl><section class="approval-history"><h3>الاحتياجات والموارد</h3><div class="approval-requirements">${requirementText}</div></section>${history}`;
      panel.classList.add('is-open');
      backdrop?.classList.add('is-open');
      panel.setAttribute('aria-hidden', 'false');
    });
  });
  root.querySelectorAll('[data-approval-reject]').forEach(button => button.addEventListener('click', () => button.closest('[data-approval-card]').querySelector('dialog').showModal()));
  root.querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  root.querySelector('[data-approval-bulk-form]')?.addEventListener('submit', event => {
    const count = event.currentTarget.querySelector('button span')?.textContent || '';
    if (!confirm(`سيتم فحص وإقرار الأنشطة المؤهلة فقط (${count}). هل تريد المتابعة؟`)) event.preventDefault();
  });
})();
