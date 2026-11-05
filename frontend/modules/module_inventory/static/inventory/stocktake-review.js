(function () {
  'use strict';
  document.querySelectorAll('.result-table tbody tr').forEach(function (row) {
    row.addEventListener('click', function (event) {
      if (event.target.closest('a,button')) return;
      var link = row.querySelector('.item-link');
      if (link) window.location.href = link.href;
    });
  });
}());
