(() => {
  const input = document.getElementById('pm-dashboard-search');
  if (!input) return;
  const table = document.querySelector('.pm-home-project-table');
  const message = document.createElement('p');
  message.className = 'pm-home-no-data';
  message.setAttribute('role', 'status');
  message.hidden = true;
  if (table) {
    const rows = [...table.querySelectorAll('tbody tr')].filter(row => row.querySelector('.pm-home-project-name'));
    table.after(message);
    input.addEventListener('input', () => {
      const term = input.value.trim().toLocaleLowerCase('ar');
      let visible = 0;
      rows.forEach(row => {
        row.hidden = !row.textContent.toLocaleLowerCase('ar').includes(term);
        if (!row.hidden) visible++;
      });
      message.hidden = !term || visible > 0;
      message.textContent = visible ? '' : 'لا توجد مشاريع مطابقة للبحث';
    });
    return;
  }

  const links = [...document.querySelectorAll(
    '.pm-home-landing .pm-home-card, .pm-home-landing .pm-home-stage-link, .pm-home-landing .pm-home-stage-extra a, .pm-home-landing .pm-home-utility-links a, .pm-home-landing .pm-home-compact-links a'
  )];
  if (!links.length) return;
  const resultAnchor = document.querySelector('.pm-home-landing .pm-home-additional')
    || document.querySelector('.pm-home-landing .pm-home-kpis')
    || document.querySelector('.pm-home-landing .pm-home-actions-panel');
  resultAnchor?.after(message);
  input.addEventListener('input', () => {
    const term = input.value.trim().toLocaleLowerCase('ar');
    let visible = 0;
    links.forEach(link => {
      link.hidden = !link.textContent.toLocaleLowerCase('ar').includes(term);
      if (!link.hidden) visible++;
    });
    message.hidden = !term || visible > 0;
    message.textContent = visible ? '' : 'لا توجد إجراءات مطابقة للبحث';
  });
})();
