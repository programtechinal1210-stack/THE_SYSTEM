(function () {
  'use strict';
  document.querySelectorAll('form[data-confirm-save="true"]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm('هذا التغيير مؤثر على الترحيل أو إقفال الفترة. هل تريد المتابعة؟')) event.preventDefault();
    });
  });
})();
