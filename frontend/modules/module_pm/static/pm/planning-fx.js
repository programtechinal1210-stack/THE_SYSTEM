/* Dynamic unit labels, multi-requirement entry, and planned-cost FX preview. */
function updateRequirementUnitLabels(card) {
  const unit = card.querySelector('[name="unit"]')?.value.trim();
  const quantity = card.querySelector('[data-unit-label="quantity"]');
  const unitPrice = card.querySelector('[data-unit-label="unit_price"]');
  const knownUnits = {
    'ساعة': ['بالساعة', 'سعر الساعة'],
    'يوم': ['باليوم', 'سعر اليوم'],
    'أسبوع': ['بالأسبوع', 'سعر الأسبوع'],
    'شهر': ['بالشهر', 'سعر الشهر'],
    'كم': ['بالكيلومتر', 'سعر الكيلومتر'],
    'كيلومتر': ['بالكيلومتر', 'سعر الكيلومتر'],
    'م': ['بالمتر', 'سعر المتر'],
    'متر': ['بالمتر', 'سعر المتر'],
    'م²': ['بالمتر المربع', 'سعر المتر المربع'],
    'م³': ['بالمتر المكعب', 'سعر المتر المكعب'],
    'كجم': ['بالكيلوغرام', 'سعر الكيلوغرام'],
    'كغ': ['بالكيلوغرام', 'سعر الكيلوغرام'],
    'قطعة': ['بالقطعة', 'سعر القطعة'],
  };
  const labels = knownUnits[unit];
  if (quantity) quantity.textContent = labels
    ? `الكمية المطلوبة ${labels[0]}`
    : unit ? `الكمية المطلوبة بوحدة ${unit}` : 'الكمية المطلوبة';
  if (unitPrice) unitPrice.textContent = labels
    ? labels[1]
    : unit ? `سعر الوحدة (${unit})` : 'سعر الوحدة';
}

function renumberRequirementCards(cards) {
  cards.querySelectorAll('[data-requirement-card] header span').forEach((label, index) => {
    label.textContent = `الاحتياج ${index + 1}`;
  });
}

function clearFxPreview(panel) {
  const summary = panel?.querySelector('[data-fx-summary]');
  if (summary) summary.hidden = true;
  const output = panel?.querySelector('[data-fx-result]');
  if (output) output.textContent = 'تغيّرت بيانات التسعير؛ أعد الحساب لمراجعة المبلغ المتوقع حفظه.';
}

function addDecimalAmounts(amounts) {
  const decimals = amounts.map(value => {
    const [whole, fraction = ''] = String(value).split('.');
    return {whole: whole || '0', fraction};
  });
  const scale = Math.max(0, ...decimals.map(value => value.fraction.length));
  const total = decimals.reduce((sum, value) => {
    const digits = `${value.whole}${value.fraction.padEnd(scale, '0')}`;
    return sum + BigInt(digits || '0');
  }, 0n).toString().padStart(scale + 1, '0');
  if (!scale) return total;
  const normalized = `${total.slice(0, -scale)}.${total.slice(-scale)}`.replace(/0+$/, '').replace(/\.$/, '');
  return normalized;
}

document.addEventListener('click', async event => {
  const addRequirement = event.target.closest('[data-requirement-add]');
  if (addRequirement) {
    const form = addRequirement.closest('form');
    const cards = form.querySelector('[data-requirement-cards]');
    const source = cards.querySelector('[data-requirement-card]');
    const card = source.cloneNode(true);
    const index = cards.querySelectorAll('[data-requirement-card]').length + 1;
    card.querySelectorAll('input, select, textarea').forEach(field => {
      if (field.name === 'currency' || field.name === 'rate_date') return;
      field.value = '';
    });
    card.querySelectorAll('[id]').forEach(field => { field.id = `${field.id}-${index}`; });
    card.querySelectorAll('label[for]').forEach(label => { label.htmlFor = `${label.htmlFor}-${index}`; });
    card.querySelector('header span').textContent = `الاحتياج ${index}`;
    card.querySelector('[data-requirement-remove]').hidden = false;
    cards.append(card);
    updateRequirementUnitLabels(card);
    card.querySelector('[name="name"]')?.focus();
    clearFxPreview(form.querySelector('[data-fx-panel]'));
    return;
  }

  const removeRequirement = event.target.closest('[data-requirement-remove]');
  if (removeRequirement) {
    const cards = removeRequirement.closest('[data-requirement-cards]');
    if (cards.querySelectorAll('[data-requirement-card]').length > 1) {
      removeRequirement.closest('[data-requirement-card]').remove();
      renumberRequirementCards(cards);
      clearFxPreview(cards.closest('form').querySelector('[data-fx-panel]'));
    }
    return;
  }

  const button = event.target.closest('[data-fx-preview]');
  if (!button) return;
  const panel = button.closest('.pm-fx-panel');
  const form = panel.closest('form');
  const cards = [...form.querySelectorAll('[data-requirement-card]')];
  if (!cards.length) cards.push(form);
  const output = panel.querySelector('[data-fx-result]');
  const summary = panel.querySelector('[data-fx-summary]');
  const entries = cards.map((card, index) => ({
    card,
    index,
    name: card.querySelector('[name="name"]')?.value.trim() || `الاحتياج ${index + 1}`,
    source: card.querySelector('[name="currency"]')?.value,
    date: card.querySelector('[name="rate_date"]')?.value,
    quantity: card.querySelector('[name="quantity"]')?.value,
    unitPrice: card.querySelector('[name="unit_price"]')?.value,
  }));
  if (entries.some(entry => !entry.source || !entry.date || !entry.quantity || !entry.unitPrice)) {
    output.textContent = 'أكمل الكمية وسعر الوحدة والعملة وتاريخ الصرف لكل الاحتياجات أولاً.';
    if (summary) summary.hidden = true;
    return;
  }
  button.disabled = true;
  output.textContent = `جارٍ حساب تكلفة ${entries.length} ${entries.length === 1 ? 'احتياج' : 'احتياجات'} حسب أسعار الصرف المعتمدة…`;
  try {
    const quotes = await Promise.all(entries.map(async entry => {
      const url = new URL(form.action || location.href, location.href);
      url.searchParams.set('fx', '1');
      url.searchParams.set('currency', entry.source);
      url.searchParams.set('rate_date', entry.date);
      url.searchParams.set('quantity', entry.quantity);
      url.searchParams.set('unit_price', entry.unitPrice);
      const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('quote-failed');
      return {entry, quote: await response.json()};
    }));
    if (quotes.some(({quote}) => !quote.available)) {
      output.textContent = 'لا يتوفر سعر صرف معتمد لهذه العملة والتاريخ.';
      if (summary) summary.hidden = true;
    } else {
      const targetCurrency = quotes[0].quote.cost_currency || quotes[0].quote.to;
      if (quotes.some(({quote}) => (quote.cost_currency || quote.to) !== targetCurrency)) {
        throw new Error('mixed-target-currencies');
      }
      output.textContent = `احتُسبت تكلفة ${quotes.length} ${quotes.length === 1 ? 'احتياج' : 'احتياجات'} حسب سعر الصرف المعتمد.`;
      if (summary) {
        summary.querySelector('[data-fx-source-amount]').textContent = quotes.map(({entry}) =>
          `${entry.name}: ${entry.quantity} × ${entry.unitPrice} ${entry.source}`).join(' · ');
        summary.querySelector('[data-fx-rate]').textContent = quotes.map(({entry, quote}) =>
          `${entry.name}: 1 ${quote.from} = ${quote.rate} ${quote.to} (${quote.date})`).join(' · ');
        summary.querySelector('[data-fx-planned-cost]').textContent =
          `${addDecimalAmounts(quotes.map(({quote}) => quote.planned_cost ?? '0'))} ${targetCurrency}`;
        summary.hidden = false;
      }
    }
  } catch {
    output.textContent = 'تعذر جلب سعر الصرف. تحقق من الاتصال والصلاحيات والتاريخ ثم أعد المحاولة.';
  } finally {
    button.disabled = false;
  }
});

document.addEventListener('input', event => {
  const card = event.target.closest('[data-requirement-card]') || event.target.closest('.pm-requirements-form');
  if (!card) return;
  if (event.target.matches('[name="unit"]')) updateRequirementUnitLabels(card);
  if (event.target.matches('[name="currency"], [name="rate_date"], [name="quantity"], [name="unit_price"]')) {
    clearFxPreview(card.closest('form').querySelector('[data-fx-panel]'));
  }
});

document.addEventListener('change', event => {
  if (event.target.matches('[name="currency"], [name="rate_date"], [name="quantity"], [name="unit_price"]')) {
    clearFxPreview(event.target.closest('form')?.querySelector('[data-fx-panel]'));
  }
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-requirement-card]').forEach(updateRequirementUnitLabels);
  document.querySelectorAll('.pm-requirements-form').forEach(updateRequirementUnitLabels);
});

new MutationObserver(records => {
  records.flatMap(record => [...record.addedNodes]).forEach(node => {
    if (!(node instanceof Element)) return;
    if (node.matches('[data-requirement-card], .pm-requirements-form')) updateRequirementUnitLabels(node);
    node.querySelectorAll?.('[data-requirement-card], .pm-requirements-form').forEach(updateRequirementUnitLabels);
  });
}).observe(document.documentElement, {childList: true, subtree: true});

document.addEventListener('submit', async event => {
  const form = event.target.closest('form[data-multi-requirements]');
  if (!form || form.querySelectorAll('[data-requirement-card]').length < 2) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const submitter = event.submitter;
  if (submitter) submitter.disabled = true;
  const feedback = form.querySelector('[data-multi-feedback]') || Object.assign(document.createElement('p'), {textContent: 'جارٍ حفظ الاحتياجات…'});
  feedback.dataset.multiFeedback = '';
  feedback.setAttribute('role', 'status');
  form.prepend(feedback);
  try {
    const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    for (const card of form.querySelectorAll('[data-requirement-card]')) {
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrf);
      card.querySelectorAll('[name]').forEach(field => {
        if (!field.disabled) data.append(field.name, field.value);
      });
      const response = await fetch(form.action || location.href, {method: 'POST', body: data, credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (!response.redirected) throw new Error('save-failed');
    }
    document.querySelector('#pm-reference-dialog')?.close();
    window.dispatchEvent(new CustomEvent('pm:planning-saved'));
  } catch {
    feedback.textContent = 'تعذر حفظ جميع الاحتياجات. راجع البيانات ثم أعد المحاولة.';
    feedback.setAttribute('role', 'alert');
  } finally {
    if (submitter) submitter.disabled = false;
  }
}, true);
