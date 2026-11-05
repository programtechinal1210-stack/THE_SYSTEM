(() => {
  const grid = document.getElementById('ec-project-grid');
  const input = document.getElementById('ec-search');
  if (!grid || !input) return;
  const cards = [...grid.querySelectorAll('[data-ec-project]')];
  grid.addEventListener('click', event => {
    const summary = event.target instanceof Element
      ? event.target.closest('.ec-details > summary')
      : null;
    if (!summary) return;
    const current = summary.parentElement;
    if (current.open) return;
    grid.querySelectorAll('.ec-details[open]').forEach(other => {
      if (other !== current) other.open = false;
    });
  });
  const filters = [...document.querySelectorAll('[data-ec-filter]')];
  const views = [...document.querySelectorAll('[data-ec-view]')];
  const fields = ['manager', 'client', 'status', 'date-from', 'date-to']
    .map(key => [key, document.getElementById('ec-' + key)]);
  const controls = Object.fromEntries(fields);
  const empty = document.getElementById('ec-no-results');
  const count = document.getElementById('ec-results-count');
  let active = grid.dataset.activeFilter || filters[0]?.dataset.ecFilter || 'planned';
  function populate(key) {
    const select = controls[key];
    if (!select) return;
    [...new Set(cards.map(card => card.dataset[key]).filter(Boolean))].sort()
      .forEach(value => { const option = document.createElement('option'); option.value = value; option.textContent = value; select.appendChild(option); });
  }
  populate('manager');
  populate('client');
  function update() {
    const term = input.value.trim().toLocaleLowerCase('ar');
    let visible = 0;
    cards.forEach(card => {
      const matches = (!term || (card.dataset.search || '').toLocaleLowerCase('ar').includes(term))
        && (active === 'all' || (card.dataset.buckets || '').split(',').includes(active))
        && (!controls.manager?.value || card.dataset.manager === controls.manager.value)
        && (!controls.client?.value || card.dataset.client === controls.client.value)
        && (!controls.status?.value || card.dataset.status === controls.status.value)
        && (!controls['date-from']?.value || (card.dataset.date && card.dataset.date >= controls['date-from'].value))
        && (!controls['date-to']?.value || (card.dataset.date && card.dataset.date <= controls['date-to'].value));
      card.hidden = !matches;
      if (matches) visible++;
    });
    if (empty) empty.hidden = visible > 0 || cards.length === 0;
    if (count) count.textContent = `عرض ${visible} من ${cards.length} مشروع`;
  }
  input.addEventListener('input', update);
  fields.forEach(([, control]) => control?.addEventListener('change', update));
  document.getElementById('ec-reset')?.addEventListener('click', () => {
    input.value = '';
    fields.forEach(([, control]) => { if (control) control.value = ''; });
    update();
  });
  filters.forEach(button => button.addEventListener('click', () => {
    active = button.dataset.ecFilter;
    filters.forEach(item => {
      const selected = item === button;
      item.classList.toggle('is-active', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
    update();
  }));
  views.forEach(button => button.addEventListener('click', () => {
    grid.dataset.view = button.dataset.ecView;
    views.forEach(item => {
      const selected = item === button;
      item.classList.toggle('is-active', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
  }));
  const dialog = document.getElementById('ec-confirm-dialog');
  document.querySelectorAll('[data-ec-start-form]').forEach(form => form.addEventListener('submit', event => {
    if (!dialog || typeof dialog.showModal !== 'function') return;
    event.preventDefault();
    dialog.querySelector('[data-ec-confirm-name]').textContent = form.dataset.projectName;
    dialog.querySelector('[data-ec-confirm-code]').textContent = form.dataset.projectCode;
    dialog.querySelector('[value="confirm"]').onclick = () => { dialog.close('confirm'); form.submit(); };
    dialog.showModal();
  }));
  update();
})();
