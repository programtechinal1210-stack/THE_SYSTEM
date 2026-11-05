/* UDE-05 pilot-only shell adapter; no alternate navigation or business calls. */
(function () {
  'use strict';
  function boot() {
    var root = document.querySelector('[data-ude-pilot="core-home"]');
    if (!root || root.dataset.udeBooted === 'true') return;
    root.dataset.udeBooted = 'true';
    document.body.classList.add('ude-05-pilot-shell');
    var html = document.documentElement;
    var coreTheme = html.getAttribute('data-core-theme') || html.getAttribute('data-theme') || 'light';
    var bootstrap = {};
    var bootstrapNode = document.getElementById('ude-theme-bootstrap');
    try { bootstrap = bootstrapNode ? JSON.parse(bootstrapNode.textContent || '{}') : {}; } catch (_) { bootstrap = {}; }
    bootstrap.settings = bootstrap.settings || {};
    if (!bootstrap.settings.theme) bootstrap.settings.theme = coreTheme;
    var profile = coreTheme === 'dark' ? 'ude-dark-default' : coreTheme === 'high-contrast' ? 'ude-high-contrast' : 'ude-light-default';
    if (window.UDEThemeResolver) {
      var result = window.UDEThemeResolver.resolve(bootstrap, {matchMedia: window.matchMedia.bind(window)});
      profile = result.profile;
      window.UDEThemeResolver.apply(result, document, html);
      root.setAttribute('data-ude-theme', result.profile);
      root.setAttribute('data-ude-density', result.settings.density);
    } else {
      root.setAttribute('data-ude-theme', profile);
    }
    if (window.UDEComponents) window.UDEComponents.init(root);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
  window.addEventListener('load', boot, {once: true});
}());
