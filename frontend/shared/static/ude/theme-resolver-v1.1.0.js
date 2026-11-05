/* UDE-02 V1.1.0 — read-only Theme Resolver.
 * This file is intentionally not referenced by production templates.
 * It reads Core's effective settings and uses localStorage only as a fallback cache.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.UDEThemeResolver = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DEFAULTS = Object.freeze({
    theme: 'light',
    palette: 'navy',
    density: 'comfortable',
    fontSize: 16,
    fontFamily: 'Tajawal',
    contrast: 'normal'
  });
  var THEMES = Object.freeze({
    light: 'ude-light-default',
    dark: 'ude-dark-default',
    'high-contrast': 'ude-high-contrast'
  });
  var SOURCES = Object.freeze(['system', 'institution', 'organization', 'user']);
  var FONTS = Object.freeze(['Tajawal', 'Almarai', 'IBM Plex Sans Arabic']);
  var PALETTES = Object.freeze(['navy', 'royal-blue', 'emerald', 'modern-purple', 'turquoise', 'burgundy']);

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function validTheme(value) {
    return value === 'light' || value === 'dark' || value === 'system' || value === 'high-contrast';
  }

  function validFont(value) { return FONTS.indexOf(value) !== -1; }
  function validPalette(value) { return PALETTES.indexOf(value) !== -1; }

  function validate(settings) {
    var input = isObject(settings) ? settings : {};
    var result = Object.assign({}, DEFAULTS);
    var rejected = [];
    if (validTheme(input.theme)) result.theme = input.theme;
    else if (input.theme !== undefined) rejected.push('theme');
    if (validPalette(input.palette)) result.palette = input.palette;
    else if (input.palette !== undefined) rejected.push('palette');
    if (input.density === 'compact' || input.density === 'comfortable') result.density = input.density;
    else if (input.density !== undefined) rejected.push('density');
    if (Number.isInteger(input.fontSize) && input.fontSize >= 12 && input.fontSize <= 24) result.fontSize = input.fontSize;
    else if (input.fontSize !== undefined) rejected.push('fontSize');
    if (validFont(input.fontFamily)) result.fontFamily = input.fontFamily;
    else if (input.fontFamily !== undefined) rejected.push('fontFamily');
    if (input.contrast === 'normal' || input.contrast === 'high') result.contrast = input.contrast;
    else if (input.contrast !== undefined) rejected.push('contrast');
    if (result.contrast === 'high') result.theme = 'high-contrast';
    return { settings: result, rejected: rejected };
  }

  function toSettings(row) {
    if (!isObject(row)) return {};
    var key = row.setting_key || row.key || '';
    var value = row.value;
    var map = {
      'theme': 'theme', 'core.theme': 'theme',
      'density': 'density', 'core.density': 'density',
      'font_size': 'fontSize', 'core.font_size': 'fontSize',
      'font_family': 'fontFamily', 'core.font_family': 'fontFamily',
      'contrast': 'contrast', 'core.contrast': 'contrast'
      ,'palette': 'palette', 'ude.palette': 'palette', 'core.palette': 'palette', 'core.ude.palette': 'palette'
    };
    if (!map[key]) return {};
    var out = {}; out[map[key]] = value; return out;
  }

  function mergeLayers(layers) {
    var merged = {};
    SOURCES.forEach(function (source) {
      var rows = Array.isArray(layers && layers[source]) ? layers[source] : [];
      rows.forEach(function (row) { Object.assign(merged, toSettings(row)); });
      if (isObject(layers && layers[source])) Object.assign(merged, layers[source]);
    });
    return merged;
  }

  function effectivePayload(payload) {
    if (Array.isArray(payload)) return mergeLayers({ system: payload });
    if (!isObject(payload)) return {};
    if (Array.isArray(payload.effective)) return mergeLayers({ system: payload.effective });
    if (isObject(payload.layers)) return mergeLayers(payload.layers);
    return payload.settings || payload;
  }

  function resolve(input, options) {
    options = options || {};
    var fromCore = effectivePayload(input);
    var checked = validate(fromCore);
    var settings = checked.settings;
    var resolvedTheme = settings.theme;
    if (resolvedTheme === 'system') {
      var matches = options.matchMedia && options.matchMedia('(prefers-color-scheme: dark)');
      resolvedTheme = matches && matches.matches ? 'dark' : 'light';
    }
    if (settings.contrast === 'high') resolvedTheme = 'high-contrast';
    return {
      settings: settings,
      theme: resolvedTheme,
      profile: THEMES[resolvedTheme] || THEMES.light,
      rejected: checked.rejected,
      source: options.source || 'core'
    };
  }

  function readCache(storage, key) {
    key = key || 'ude.theme.resolver.v1';
    try {
      if (!storage || typeof storage.getItem !== 'function') return null;
      var raw = storage.getItem(key);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      return isObject(parsed) && isObject(parsed.settings) ? parsed : null;
    } catch (_) { return null; }
  }

  function readFromCore(fetcher, endpoint) {
    if (typeof fetcher !== 'function') return Promise.reject(new Error('Core reader is required'));
    endpoint = endpoint || '/api/v1/user-settings/effective';
    return Promise.resolve(fetcher(endpoint)).then(function (response) {
      if (!response || (response.ok === false)) throw new Error('Core settings read failed');
      return typeof response.json === 'function' ? response.json() : response;
    }).then(function (payload) { return resolve(payload, { source: 'core' }); });
  }

  function resolveWithCache(coreReader, storage, options) {
    options = options || {};
    return readFromCore(coreReader, options.endpoint).catch(function () {
      var cached = readCache(storage, options.cacheKey);
      if (!cached) return resolve({}, { source: 'safe-default' });
      return resolve(cached.settings, { source: 'cache-fallback' });
    });
  }

  function apply(result, documentRef, root) {
    if (!result || !documentRef) throw new Error('Resolver result and document are required');
    root = root || documentRef.documentElement;
    root.setAttribute('data-ude-theme', result.profile);
    root.setAttribute('data-ude-density', result.settings.density);
    root.style.setProperty('--ude-font-size-md', result.settings.fontSize + 'px');
    root.style.setProperty('--ude-font-family-sans', '"' + result.settings.fontFamily + '"');
    if (typeof root.UDEColorPalettes === 'object' && typeof root.UDEColorPalettes.apply === 'function') {
      root.UDEColorPalettes.apply(result.settings.palette, result.theme === 'dark' ? 'dark' : 'light', root);
    } else if (typeof documentRef.defaultView !== 'undefined' && documentRef.defaultView.UDEColorPalettes) {
      documentRef.defaultView.UDEColorPalettes.apply(result.settings.palette, result.theme === 'dark' ? 'dark' : 'light', root);
    }
    return result;
  }

  return Object.freeze({
    DEFAULTS: DEFAULTS,
    THEMES: THEMES,
    PALETTES: PALETTES,
    validate: validate,
    resolve: resolve,
    readCache: readCache,
    readFromCore: readFromCore,
    resolveWithCache: resolveWithCache,
    apply: apply
  });
}));
