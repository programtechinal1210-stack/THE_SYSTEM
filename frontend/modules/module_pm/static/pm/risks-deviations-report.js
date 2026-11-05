(() => {
  const root = document.querySelector('.rdr');
  if (!root) return;

  const readJson = (id) => {
    const element = document.getElementById(id);
    try { return JSON.parse(element?.textContent || '[]'); } catch { return []; }
  };
  const risks = readJson('rdr-risk-data');
  const actions = readJson('rdr-action-data');
  const riskBody = root.querySelector('[data-rdr-risk-body]');
  const actionBody = root.querySelector('[data-rdr-action-body]');
  const pager = root.querySelector('[data-rdr-pagination]');
  const detailPanel = root.querySelector('[data-rdr-details]');
  const detailContent = root.querySelector('[data-rdr-detail-content]');
  const layout = root.querySelector('.rdr-layout');
  let page = 1;
  let pageSize = 10;
  let sortKey = 'importance';
  let sortDirection = -1;

  const escapeHtml = (value) => String(value ?? '—').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
  const linkedItem = (row) => [row.phase_code, row.task_code, row.activity_code].filter(Boolean).join(' / ') || 'المشروع';

  const renderRisks = () => {
    const sorted = [...risks].sort((left, right) => {
      const a = left[sortKey] ?? '';
      const b = right[sortKey] ?? '';
      const comparison = sortKey === 'importance' || sortKey === 'probability' || sortKey === 'impact'
        ? Number(a) - Number(b) : String(a).localeCompare(String(b), 'ar');
      return comparison * sortDirection;
    });
    const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
    page = Math.min(page, pages);
    const start = (page - 1) * pageSize;
    const visible = sorted.slice(start, start + pageSize);
    riskBody.innerHTML = visible.map((row) => {
      const index = risks.indexOf(row);
      return `<tr><td><b class="rdr-code">${escapeHtml(row.risk_code)}</b></td><td><strong>${escapeHtml(row.description || row.name)}</strong><small>${escapeHtml(row.classification || 'دون تصنيف')}</small></td><td>${escapeHtml(linkedItem(row))}</td><td>${escapeHtml(row.probability)}%</td><td>${escapeHtml(row.impact)} / 5</td><td><span class="rdr-pill ${escapeHtml(row.severity_key)}">${escapeHtml(row.severity_label)} · ${escapeHtml(row.importance)}</span></td><td><span class="rdr-pill ${row.status === 'active' ? 'active' : 'closed'}">${escapeHtml(row.status_label)}</span></td><td>${escapeHtml(row.owner_name || 'غير محدد')}</td><td>${escapeHtml(row.record_date)}</td><td><button type="button" class="rdr-detail-button" data-rdr-risk-detail="${index}" title="عرض تقييم الخطر وخطة الاستجابة والمسؤول">التفاصيل</button></td></tr>`;
    }).join('');
    pager.innerHTML = `<span>عرض ${sorted.length ? start + 1 : 0}–${Math.min(start + pageSize, sorted.length)} من ${sorted.length}</span><div><button type="button" data-page="prev" ${page <= 1 ? 'disabled' : ''} aria-label="الصفحة السابقة">‹</button><span>${page} / ${pages}</span><button type="button" data-page="next" ${page >= pages ? 'disabled' : ''} aria-label="الصفحة التالية">›</button></div>`;
  };

  const renderActions = () => {
    actionBody.innerHTML = actions.length ? actions.map((row, index) => `<tr><td><b class="rdr-code">${escapeHtml(row.risk_code)}</b> · ${escapeHtml(row.description || row.name)}</td><td>${escapeHtml(row.corrective_action)}</td><td>${escapeHtml(row.owner_name || 'غير محدد')}</td><td><span class="rdr-pill active">الخطر نشط</span></td><td>غير متوفر</td><td><button type="button" class="rdr-detail-button" data-rdr-action-detail="${index}">التفاصيل</button></td></tr>`).join('') : '<tr><td colspan="6" class="rdr-empty-cell">لا توجد إجراءات معالجة مسجلة على المخاطر النشطة.</td></tr>';
  };

  const showDetails = (title, row, kind) => {
    const fields = kind === 'risk' ? [
      ['وصف الخطر', row.description || row.name], ['المشروع / العنصر المرتبط', linkedItem(row)],
      ['الاحتمالية', `${row.probability ?? '—'}%`], ['التأثير', `${row.impact ?? '—'} / 5`],
      ['مستوى الأهمية', `${row.severity_label} · ${row.importance ?? '—'}`],
      ['خطة الاستجابة', row.corrective_action || 'لا توجد خطة مسجلة'], ['المسؤول', row.owner_name || 'غير محدد'],
      ['حالة الخطر', row.status_label], ['تاريخ الاكتشاف / الإنشاء', row.record_date],
      ['آخر تحديث', row.updated_at || 'غير متوفر'],
    ] : [
      ['الإجراء المسجل', row.corrective_action], ['الخطر المرتبط', `${row.risk_code} · ${row.description || row.name}`],
      ['المسؤول', row.owner_name || 'غير محدد'], ['الحالة', 'الخطر نشط؛ لا توجد حالة مستقلة للإجراء'],
      ['موعد التنفيذ', 'غير متوفر في سجل المخاطر'],
    ];
    detailContent.innerHTML = `<span class="rdr-detail-kicker">${kind === 'risk' ? 'تفاصيل الخطر' : 'تفاصيل الإجراء المسجل'}</span><h2>${escapeHtml(title)}</h2>${fields.map(([label, value]) => `<div class="rdr-detail-field"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></div>`).join('')}`;
    detailPanel.hidden = false;
    layout.classList.add('has-details');
    detailPanel.querySelector('[data-rdr-close]').focus();
  };

  root.querySelectorAll('[data-rdr-tab]').forEach((tab) => tab.addEventListener('click', () => {
    root.querySelectorAll('[data-rdr-tab]').forEach((item) => item.setAttribute('aria-selected', String(item === tab)));
    root.querySelectorAll('[data-rdr-panel]').forEach((panel) => { panel.hidden = panel.dataset.rdrPanel !== tab.dataset.rdrTab; });
  }));
  root.querySelector('[data-rdr-page-size]')?.addEventListener('change', (event) => {
    pageSize = Number(event.target.value) || 10;
    page = 1;
    renderRisks();
  });
  pager?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-page]');
    if (!button || button.disabled) return;
    page += button.dataset.page === 'next' ? 1 : -1;
    renderRisks();
  });
  riskBody?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rdr-risk-detail]');
    if (!button) return;
    const row = risks[Number(button.dataset.rdrRiskDetail)];
    if (row) showDetails(row.risk_code || 'الخطر', row, 'risk');
  });
  actionBody?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rdr-action-detail]');
    if (!button) return;
    const row = actions[Number(button.dataset.rdrActionDetail)];
    if (row) showDetails(row.risk_code || 'الإجراء', row, 'action');
  });
  detailPanel?.querySelector('[data-rdr-close]')?.addEventListener('click', () => {
    detailPanel.hidden = true;
    layout.classList.remove('has-details');
  });
  root.querySelector('[data-rdr-print]')?.addEventListener('click', () => window.print());
  root.querySelector('[data-rdr-project]')?.addEventListener('change', (event) => {
    const projectId = event.target.value;
    if (!projectId) return;
    const url = new URL(`/pm/projects/${encodeURIComponent(projectId)}/reporting/`, window.location.origin);
    url.searchParams.set('report', 'risk');
    window.location.assign(url);
  });
  root.querySelectorAll('.rdr-table thead th').forEach((header, index) => {
    const keys = ['risk_code', 'description', 'phase_code', 'probability', 'impact', 'importance', 'status', 'owner_name', 'discovery_date'];
    if (!keys[index]) return;
    header.tabIndex = 0;
    header.setAttribute('role', 'button');
    header.setAttribute('aria-label', `ترتيب حسب ${header.textContent.trim()}`);
    const sort = () => {
      sortDirection = sortKey === keys[index] ? sortDirection * -1 : 1;
      sortKey = keys[index];
      page = 1;
      renderRisks();
    };
    header.addEventListener('click', sort);
    header.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); sort(); } });
  });
  renderRisks();
  renderActions();
})();
