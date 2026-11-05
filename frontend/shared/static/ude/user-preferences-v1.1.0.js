/* UDE-03 preference persistence helpers. No credentials or network calls. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.UDEUserPreferences = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var KEYS = Object.freeze([
    'core.ude.theme','core.ude.palette','core.ude.custom_colors',
    'core.ude.luminance_adjustment','core.ude.font_family','core.ude.font_scale',
    'core.ude.density','core.ude.contrast','core.ude.motion','core.ude.sidebar'
  ]);
  function isObject(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function onlyUde(values) {
    var out = {};
    if (!isObject(values)) return out;
    KEYS.forEach(function (key) { if (Object.prototype.hasOwnProperty.call(values, key)) out[key] = values[key]; });
    return out;
  }
  function mergeConflict(base, current, desired) {
    var merged = {}, conflicts = [];
    base = onlyUde(base); current = onlyUde(current); desired = onlyUde(desired);
    KEYS.forEach(function (key) {
      var changedByMe = Object.prototype.hasOwnProperty.call(desired, key) && desired[key] !== base[key];
      var changedOnServer = current[key] !== base[key];
      if (changedByMe && changedOnServer && current[key] !== desired[key]) conflicts.push(key);
      else if (changedByMe) merged[key] = desired[key];
    });
    return { values: merged, conflicts: conflicts };
  }
  function readCache(storage, key) {
    try {
      var raw = storage && storage.getItem(key || 'ude.user.preferences.v1');
      var value = raw ? JSON.parse(raw) : null;
      return isObject(value) && typeof value.server_token === 'string' ? value : null;
    } catch (_) { return null; }
  }
  function writeCache(storage, profile, key) {
    if (!storage || !profile || typeof profile.server_token !== 'string') return;
    storage.setItem(key || 'ude.user.preferences.v1', JSON.stringify({
      server_token: profile.server_token, values: onlyUde(profile.values), cached_at: Date.now()
    }));
  }
  return Object.freeze({ KEYS: KEYS, onlyUde: onlyUde, mergeConflict: mergeConflict, readCache: readCache, writeCache: writeCache });
}));
