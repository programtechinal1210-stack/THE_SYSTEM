document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-risk-register]');
  if (!root) return;
  const rows = [...root.querySelectorAll('[data-risk-row]')];
  const search = root.querySelector('[data-risk-search]');
  const level = root.querySelector('[data-risk-filter]');
  const status = root.querySelector('[data-risk-status]');
  const results = root.querySelector('[data-risk-results]');
  const panel = root.querySelector('[data-risk-details]');
  const apply = () => { const term = (search?.value || '').trim().toLocaleLowerCase(); const selectedLevel = level?.value || ''; const selectedStatus = status?.value || ''; let visible = 0; rows.forEach((row) => { const shown = (!term || row.dataset.riskText.toLocaleLowerCase().includes(term)) && (!selectedLevel || row.dataset.riskLevel === selectedLevel) && (!selectedStatus || row.dataset.riskStatus === selectedStatus); row.hidden = !shown; if (shown) visible += 1; }); if (results) results.textContent = `عرض ${visible} من ${rows.length} خطر`; };
  search?.addEventListener('input', apply); level?.addEventListener('change', apply); status?.addEventListener('change', apply);
  ['high', 'medium', 'low'].forEach((key) => { const target = root.querySelector(`[data-risk-count="${key}"]`); if (target) target.textContent = rows.filter((row) => row.dataset.riskLevel === key).length; });
  root.addEventListener('click', (event) => { const button = event.target.closest('[data-risk-detail]'); if (!button || !root.contains(button)) return; const row = button.closest('[data-risk-row]'); if (!row) return; panel.hidden = false; root.querySelector('[data-risk-detail-title]').textContent = `${row.dataset.riskCode} — ${row.dataset.riskDescription}`; root.querySelector('[data-risk-detail-description]').textContent = 'مراجعة البيانات وإجراءات المعالجة المرتبطة بهذا الخطر.'; root.querySelector('[data-risk-detail-action]').textContent = row.dataset.riskAction; root.querySelector('[data-risk-detail-owner]').textContent = row.dataset.riskOwner; panel.scrollIntoView({behavior:'smooth', block:'nearest'}); });
  root.querySelector('[data-risk-close]')?.addEventListener('click', () => { panel.hidden = true; }); root.querySelector('[data-risk-refresh]')?.addEventListener('click', () => window.location.reload()); root.querySelector('[data-risk-print]')?.addEventListener('click', () => window.print());
  root.querySelector('[data-risk-export]')?.addEventListener('click', () => { const data = rows.filter((row) => !row.hidden).map((row) => ({code: row.dataset.riskCode, description: row.dataset.riskDescription, action: row.dataset.riskAction, owner: row.dataset.riskOwner})); const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'project-risks.json'; link.click(); URL.revokeObjectURL(link.href); });
  apply();
});
