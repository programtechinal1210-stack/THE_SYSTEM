/* UDE V2 Stage 02: apply the already server-provided Core appearance to Shared Shell. */
(function () {
  'use strict';
  function boot() {
    var body = document.body;
    var node = document.getElementById('ude-v2-theme-bootstrap');
    if (!body || !node || body.dataset.udeV2Booted === 'true') return;
    body.dataset.udeV2Booted = 'true';
    var payload = {};
    try { payload = JSON.parse(node.textContent || '{}'); } catch (_) { payload = {}; }
    if (!window.UDEThemeResolver) return;
    var result = window.UDEThemeResolver.resolve(payload, {matchMedia: window.matchMedia.bind(window)});
    if (window.UDEColorPalettes && typeof window.UDEColorPalettes.apply === 'function') {
      window.UDEThemeResolver.apply(result, document, document.documentElement);
    }
    // High Contrast owns the complete semantic palette.  The V1 resolver may
    // also apply the selected aesthetic palette inline; remove those inline
    // overrides so the high-contrast token layer remains authoritative.
    if (result.theme === 'high-contrast') {
      [
        '--ude-color-canvas', '--ude-color-surface', '--ude-color-surface-raised',
        '--ude-color-surface-sunken', '--ude-color-text', '--ude-color-text-muted',
        '--ude-color-border', '--ude-color-divider', '--ude-color-brand',
        '--ude-color-brand-strong', '--ude-color-brand-soft', '--ude-color-focus'
      ].forEach(function (property) {
        document.documentElement.style.removeProperty(property);
      });
    }
    body.setAttribute('data-ude-v2-shell', 'ready');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
}());
