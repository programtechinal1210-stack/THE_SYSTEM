/* UDE palette settings surface. Loaded only while its feature flag is enabled. */
(function (root) {
  'use strict';
  function init() {
    var host = document.querySelector('[data-ude-palette-picker]');
    if (!host || !root.UDEColorPalettes) return;
    var grid = host.querySelector('[data-ude-palette-grid]');
    var preview = host.querySelector('[data-ude-palette-preview]');
    var status = host.querySelector('[data-ude-palette-status]');
    var current = root.UDEColorPalettes.DEFAULT;
    var mode = 'light';
    function setStatus(text) { if (status) status.textContent = text || ''; }
    function apply() {
      root.UDEColorPalettes.apply(current, mode, preview);
      var item = root.UDEColorPalettes.get(current);
      var name = host.querySelector('[data-ude-palette-preview-name]');
      if (name) name.textContent = item.nameAr;
      host.querySelectorAll('[data-ude-palette-card]').forEach(function (card) {
        card.setAttribute('aria-pressed', card.getAttribute('data-palette') === current ? 'true' : 'false');
      });
      host.querySelectorAll('[data-ude-palette-mode]').forEach(function (button) {
        button.setAttribute('aria-pressed', button.getAttribute('data-ude-palette-mode') === mode ? 'true' : 'false');
      });
    }
    Object.keys(root.UDEColorPalettes.REGISTRY).forEach(function (id) {
      var item = root.UDEColorPalettes.get(id);
      var card = document.createElement('button');
      var colors = root.UDEColorPalettes.vars(id, 'light');
      card.type = 'button';
      card.setAttribute('data-ude-palette-card', '');
      card.setAttribute('data-palette', id);
      card.setAttribute('aria-pressed', 'false');
      card.setAttribute('aria-label', '\u0627\u062e\u062a\u064a\u0627\u0631 ' + item.nameAr);
      card.innerHTML = '<span data-ude-palette-swatches aria-hidden="true"><i data-ude-palette-swatch style="background:' + colors['--ude-color-brand'] + '"></i><i data-ude-palette-swatch style="background:' + colors['--ude-color-accent'] + '"></i><i data-ude-palette-swatch style="background:' + colors['--ude-color-border'] + '"></i></span><strong></strong>';
      card.querySelector('strong').textContent = item.nameAr;
      card.addEventListener('click', function () { current = id; apply(); });
      grid.appendChild(card);
    });
    host.querySelectorAll('[data-ude-palette-mode]').forEach(function (button) {
      button.addEventListener('click', function () { mode = button.getAttribute('data-ude-palette-mode'); apply(); });
    });
    host.querySelector('[data-ude-palette-reset]').addEventListener('click', function () {
      current = root.UDEColorPalettes.DEFAULT;
      apply();
      setStatus('\u062a\u0645\u062a \u0627\u0633\u062a\u0639\u0627\u062f\u0629 \u0627\u0644\u0628\u0627\u0642\u0629 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u0629 \u0645\u062d\u0644\u064a\u0627\u064b. \u0627\u0636\u063a\u0637 \u062d\u0641\u0638 \u0644\u0644\u062a\u062b\u0628\u064a\u062a.');
    });
    host.querySelector('[data-ude-palette-save]').addEventListener('click', async function () {
      setStatus('\u062c\u0627\u0631\u064d \u0627\u0644\u062d\u0641\u0638...');
      try {
        var csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        var response = await fetch('/settings/api/user/save/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ settings: { 'ude.palette': current } })
        });
        var result = await response.json();
        if (!response.ok || !result.success) throw new Error('save');
        setStatus('\u062a\u0645 \u062d\u0641\u0638 \u0627\u0644\u0628\u0627\u0642\u0629 \u0644\u062d\u0633\u0627\u0628\u0643.');
      } catch (_) {
        setStatus('\u062a\u0639\u0630\u0631 \u0627\u0644\u062d\u0641\u0638\u061b \u0644\u0645 \u062a\u062a\u063a\u064a\u0631 \u0628\u064a\u0627\u0646\u0627\u062a Core.');
      }
    });
    fetch('/settings/api/get/', { credentials: 'same-origin' })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) {
        var rows = payload && Array.isArray(payload.user) ? payload.user : [];
        var row = rows.find(function (item) { return item.setting_key === 'ude.palette' || item.setting_key === 'palette' || item.setting_key === 'core.ude.palette'; });
        if (row && root.UDEColorPalettes.valid(row.value)) current = row.value;
        apply();
      })
      .catch(function () { apply(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
}(window));
