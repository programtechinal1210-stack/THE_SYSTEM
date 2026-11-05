document.addEventListener('DOMContentLoaded', function () {
  var sidebar = document.getElementById('sidebar');
  var main = document.getElementById('mainContent');
  if (window.matchMedia('(min-width: 900px)').matches && sidebar) {
    sidebar.classList.remove('collapsed');
    if (main) main.classList.remove('expanded');
    try { localStorage.setItem('goms_sidebar', 'open'); } catch (error) { /* storage may be disabled */ }
  }
});
