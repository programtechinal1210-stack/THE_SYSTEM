(function () {
  'use strict';
  var search = document.querySelector('[data-line-search]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('[data-line]'));
  if (search) search.addEventListener('input', function () {
    var term = search.value.trim().toLowerCase();
    rows.forEach(function (row) { row.hidden = term && !(row.dataset.search || '').toLowerCase().includes(term); });
  });
  var quantity = document.querySelector('#counted-quantity');
  var workspace = document.querySelector('.stocktake-execution');
  if (workspace && workspace.dataset.countEnabled === 'false') {
    var lockedForm = document.querySelector('[data-count-form]');
    if (lockedForm) lockedForm.hidden = true;
    var lockedNote = document.querySelector('.blind-note');
    if (lockedNote) lockedNote.textContent = 'هذه العملية ليست مفتوحة للعد حالياً. يمكنك مراجعة النتائج وفق صلاحيتك.';
  }
  document.querySelectorAll('[data-step]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!quantity) return;
      var current = Number(quantity.value || 0) + Number(button.dataset.step || 0);
      quantity.value = Math.max(0, current);
      quantity.focus();
    });
  });
  var zero = document.querySelector('.count-button.zero');
  if (zero && quantity) zero.addEventListener('click', function () { quantity.value = '0'; });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && document.activeElement === quantity) {
      event.preventDefault();
      var next = document.querySelector('.count-button.primary');
      if (next) next.click();
    }
  });
  var submit = document.querySelector('[data-submit-form]');
  if (submit) submit.addEventListener('submit', function (event) {
    if (!window.confirm('سيتم تقديم نتائج العد للمراجعة دون تعديل الأرصدة. هل تريد المتابعة؟')) event.preventDefault();
  });
})();
