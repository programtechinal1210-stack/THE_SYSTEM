(() => {
  const root = document.querySelector('[data-weekly-report]');
  const drawer = document.querySelector('[data-week-drawer]');
  if (!root || !drawer) return;
  const commitmentTotal = Number(root.querySelector('.wr-donut strong')?.textContent || 0);
  const commitmentCounts = [...root.querySelectorAll('.wr-donut-wrap dd')];
  if (commitmentCounts.length === 3) {
    commitmentCounts[2].textContent = Math.max(
      commitmentTotal - Number(commitmentCounts[0].textContent || 0) - Number(commitmentCounts[1].textContent || 0),
      0,
    );
  }
  const close = () => { drawer.hidden = true; document.body.classList.remove('wr-drawer-open'); };
  root.querySelector('[data-week-search]')?.addEventListener('input', event => {
    const term = event.target.value.trim().toLowerCase();
    root.querySelectorAll('[data-week-row]').forEach(row => { row.hidden = Boolean(term) && !row.dataset.search.toLowerCase().includes(term); });
  });
  root.querySelectorAll('[data-open-week]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('[data-week-row]');
    if (!row) return;
    const cells = row.querySelectorAll(':scope > td');
    drawer.querySelector('[data-week-code]').textContent = cells[1].innerText;
    drawer.querySelector('[data-week-period]').textContent = `${cells[2].innerText} — ${cells[3].innerText}`;
    drawer.querySelector('[data-week-status]').textContent = cells[8].innerText;
    drawer.querySelector('[data-week-items-output]').innerHTML = row.querySelector('[data-week-items]')?.innerHTML || '<tr><td colspan="5">لا توجد التزامات ضمن الخطة.</td></tr>';
    drawer.hidden = false; document.body.classList.add('wr-drawer-open'); drawer.querySelector('[data-close-week]')?.focus();
  }));
  drawer.querySelector('[data-close-week]')?.addEventListener('click', close);
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !drawer.hidden) close(); });
})();
