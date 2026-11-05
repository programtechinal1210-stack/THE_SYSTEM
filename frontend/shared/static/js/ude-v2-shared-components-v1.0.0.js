/* UDE V2 Stage 03: idempotent marker only; existing component behavior remains authoritative. */
(function () {
  'use strict';
  function boot() {
    var body = document.body;
    if (!body || body.dataset.udeV2ComponentsBooted === 'true') return;
    body.dataset.udeV2ComponentsBooted = 'true';
    document.documentElement.setAttribute('data-ude-v2-components', 'ready');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
}());
