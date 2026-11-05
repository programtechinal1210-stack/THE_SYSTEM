(() => {
  const form = document.querySelector('[data-inventory-request]');
  if (!form) return;
  const lines = form.querySelector('[data-request-lines]');
  const error = form.querySelector('[data-form-error]');
  const updateRows = () => {
    lines.querySelectorAll('[data-request-line]').forEach((row, index) => {
      row.querySelectorAll('[data-line-number]').forEach(node => node.textContent = index + 1);
      const select = row.querySelector('[data-item-select]');
      const unit = row.querySelector('[data-unit-label]');
      if (select && unit) unit.textContent = select.selectedOptions[0]?.dataset.unit || 'الوحدة الأساسية';
    });
  };
  form.querySelector('[data-add-request-line]').addEventListener('click', () => {
    if (lines.children.length >= 100) return;
    const row = lines.firstElementChild.cloneNode(true);
    row.querySelectorAll('input').forEach(input => input.value = '');
    row.querySelectorAll('select').forEach(select => select.selectedIndex = 0);
    lines.append(row);
    updateRows();
    lines.lastElementChild.querySelector('select')?.focus();
  });
  lines.addEventListener('change', event => {
    if (event.target.matches('[data-item-select]')) updateRows();
  });
  lines.addEventListener('click', event => {
    if (event.target.closest('[data-remove-request-line]') && lines.children.length > 1) {
      event.target.closest('[data-request-line]').remove();
      updateRows();
    }
  });
  form.addEventListener('submit', event => {
    const values = [...lines.querySelectorAll('[data-request-line]')].map(row => ({
      item: row.querySelector('[data-item-select]').value,
      quantity: Number(row.querySelector('[name="quantity"]').value)
    }));
    const duplicate = values.some((value, index) => value.item && values.findIndex(other => other.item === value.item) !== index);
    const invalid = values.some(value => !value.item || !Number.isFinite(value.quantity) || value.quantity <= 0);
    if (invalid || duplicate) {
      event.preventDefault();
      error.textContent = duplicate ? 'لا يمكن تكرار الصنف نفسه في أكثر من بند.' : 'اختر الصنف وأدخل كمية موجبة لكل بند.';
      error.hidden = false;
      return;
    }
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; button.setAttribute('aria-busy', 'true'); });
  });
  updateRows();
})();
