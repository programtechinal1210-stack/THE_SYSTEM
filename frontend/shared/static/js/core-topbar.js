(function () {
  'use strict';

  const search = document.querySelector('[data-topbar-search]');
  const input = search && search.querySelector('input[type="search"]');
  const trigger = search && search.querySelector('[data-search-trigger]');
  const menus = document.querySelectorAll('[data-topbar-menu]');

  function openSearch() {
    if (!search || !input) return;
    search.classList.add('is-open');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    input.focus();
  }

  function closeSearch() {
    if (!search) return;
    search.classList.remove('is-open');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  }

  if (trigger) {
    trigger.addEventListener('click', function () {
      if (search.classList.contains('is-open')) {
        closeSearch();
      } else {
        openSearch();
      }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.ctrlKey && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openSearch();
      return;
    }

    if (event.key === 'Escape') {
      closeSearch();
      menus.forEach(function (menu) { menu.open = false; });
    }
  });

  document.addEventListener('click', function (event) {
    if (search && !search.contains(event.target)) closeSearch();
    menus.forEach(function (menu) {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
})();
