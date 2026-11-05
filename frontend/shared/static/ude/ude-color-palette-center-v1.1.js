/* UDE palette cards for the Core settings-center adapter. Core form remains the save owner. */
(function () {
  'use strict';
  var host = document.querySelector('[data-ude-palette-center]');
  if (!host || !window.UDEColorPalettes) return;
  var field = document.querySelector('[data-setting="core.ude.palette"] [data-value]');
  var grid = host.querySelector('[data-ude-palette-center-grid]');
  var preview = host.querySelector('[data-ude-palette-center-preview]');
  var mode = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  if (!field || !grid || !preview) return;
  function apply(id) {
    var vars = window.UDEColorPalettes.vars(id, mode);
    Object.keys(vars).forEach(function (key) { preview.style.setProperty(key, vars[key]); });
    preview.setAttribute('data-palette', id);
    /* Keep the live shell in sync before save. The Core settings form still
       owns persistence; this only updates the document preview and central
       tokens for the current page. */
    window.UDEColorPalettes.apply(id, mode, document.documentElement);
    grid.querySelectorAll('[data-palette]').forEach(function (card) {
      card.setAttribute('aria-pressed', card.getAttribute('data-palette') === id ? 'true' : 'false');
    });
  }
  Object.keys(window.UDEColorPalettes.REGISTRY).forEach(function (id) {
    var item = window.UDEColorPalettes.get(id);
    var card = document.createElement('button');
    var colors = window.UDEColorPalettes.vars(id, 'light');
    card.type = 'button';
    card.setAttribute('data-palette', id);
    card.setAttribute('data-ude-palette-card', '');
    card.setAttribute('aria-pressed', 'false');
    card.setAttribute('aria-label', '\u0627\u062e\u062a\u064a\u0627\u0631 ' + item.nameAr);
    card.innerHTML = '<span data-ude-palette-swatches aria-hidden="true"><i data-ude-palette-swatch style="background:' + colors['--ude-color-brand'] + '"></i><i data-ude-palette-swatch style="background:' + colors['--ude-color-accent'] + '"></i><i data-ude-palette-swatch style="background:' + colors['--ude-color-border'] + '"></i></span><strong></strong>';
    card.querySelector('strong').textContent = item.nameAr;
    card.addEventListener('click', function () {
      field.value = id;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      apply(id);
    });
    grid.appendChild(card);
  });
  host.querySelectorAll('[data-palette-center-mode]').forEach(function (button) {
    button.addEventListener('click', function () { mode = button.getAttribute('data-palette-center-mode'); apply(field.value); });
  });
  apply(window.UDEColorPalettes.valid(field.value) ? field.value : window.UDEColorPalettes.DEFAULT);
}());
