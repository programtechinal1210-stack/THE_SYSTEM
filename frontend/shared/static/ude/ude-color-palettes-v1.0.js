/* UDE Color Palettes V1.0 — local, dependency-free, UDE-scoped only. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.UDEColorPalettes = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var SEMANTIC = Object.freeze(['--ude-color-success','--ude-color-warning','--ude-color-danger']);
  var REGISTRY = Object.freeze({
    navy: {nameAr:'الكحلي المؤسسي', light:{brand:'#1d4ed8',strong:'#1e3a8a',accent:'#115e59',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#111827',secondary:'#374151',muted:'#4b5563',border:'#cbd5e1',focus:'#1d4ed8',onBrand:'#ffffff'}, dark:{brand:'#93c5fd',strong:'#bfdbfe',accent:'#5eead4',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#f9fafb',secondary:'#e5e7eb',muted:'#d1d5db',border:'#475569',focus:'#bfdbfe',onBrand:'#172554'}},
    'royal-blue': {nameAr:'الأزرق الملكي', light:{brand:'#1e40af',strong:'#1e3a8a',accent:'#2563eb',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#111827',secondary:'#1e3a8a',muted:'#374151',border:'#cbd5e1',focus:'#1d4ed8',onBrand:'#ffffff'}, dark:{brand:'#93c5fd',strong:'#bfdbfe',accent:'#60a5fa',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#f8fafc',secondary:'#dbeafe',muted:'#bfdbfe',border:'#475569',focus:'#dbeafe',onBrand:'#172554'}},
    emerald: {nameAr:'الأخضر الزمردي', light:{brand:'#047857',strong:'#065f46',accent:'#059669',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#102a22',secondary:'#064e3b',muted:'#365b50',border:'#cbd5e1',focus:'#047857',onBrand:'#ffffff'}, dark:{brand:'#6ee7b7',strong:'#a7f3d0',accent:'#5eead4',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#f0fdf4',secondary:'#d1fae5',muted:'#a7f3d0',border:'#475569',focus:'#a7f3d0',onBrand:'#064e3b'}},
    'modern-purple': {nameAr:'البنفسجي العصري', light:{brand:'#6d28d9',strong:'#4c1d95',accent:'#7c3aed',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#21152f',secondary:'#4c1d95',muted:'#5b4b6b',border:'#cbd5e1',focus:'#6d28d9',onBrand:'#ffffff'}, dark:{brand:'#c4b5fd',strong:'#ddd6fe',accent:'#c084fc',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#faf5ff',secondary:'#ede9fe',muted:'#ddd6fe',border:'#475569',focus:'#ede9fe',onBrand:'#4c1d95'}},
    turquoise: {nameAr:'الفيروزي', light:{brand:'#0f766e',strong:'#134e4a',accent:'#0891b2',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#12303a',secondary:'#164e63',muted:'#3f6370',border:'#cbd5e1',focus:'#0e7490',onBrand:'#ffffff'}, dark:{brand:'#5eead4',strong:'#99f6e4',accent:'#67e8f9',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#ecfeff',secondary:'#cffafe',muted:'#a5f3fc',border:'#475569',focus:'#cffafe',onBrand:'#134e4a'}},
    burgundy: {nameAr:'العنابي', light:{brand:'#9f1239',strong:'#881337',accent:'#be123c',canvas:'#f8fafc',surface:'#ffffff',raised:'#ffffff',text:'#2d1118',secondary:'#881337',muted:'#69434c',border:'#cbd5e1',focus:'#9f1239',onBrand:'#ffffff'}, dark:{brand:'#fda4af',strong:'#fecdd3',accent:'#fb7185',canvas:'#0f172a',surface:'#1e293b',raised:'#273449',text:'#fff1f2',secondary:'#ffe4e6',muted:'#fecdd3',border:'#475569',focus:'#ffe4e6',onBrand:'#881337'}}
  });
  var TOKENS = Object.freeze({canvas:'--ude-color-canvas',surface:'--ude-color-surface',raised:'--ude-color-surface-raised',text:'--ude-color-text',secondary:'--ude-color-text-secondary',muted:'--ude-color-text-muted',border:'--ude-color-border',brand:'--ude-color-brand',strong:'--ude-color-brand-strong',accent:'--ude-color-accent',focus:'--ude-color-focus',onBrand:'--ude-color-on-brand'});
  /* Core is the source of truth for the rest of the application. Keep the
     UDE names above for the preview, but also project the same palette into
     the legacy aliases consumed by shared and module CSS. */
  var CORE_TOKENS = Object.freeze({canvas:'--bg-primary',surface:'--bg-secondary',raised:'--bg-elevated',text:'--text-primary',secondary:'--text-secondary',muted:'--text-muted',border:'--border-color',brand:'--brand-color',strong:'--primary-700',accent:'--accent',focus:'--info'});
  function valid(id) { return Object.prototype.hasOwnProperty.call(REGISTRY, id); }
  function get(id) { return REGISTRY[valid(id) ? id : 'navy']; }
  function vars(id, mode) { var p=get(id), c=p[mode === 'dark' ? 'dark' : 'light'], out={}; Object.keys(TOKENS).forEach(function(k){out[TOKENS[k]]=c[k];}); return out; }
  function apply(id, mode, target) {
    target=target||document.documentElement;
    var paletteId=valid(id)?id:'navy';
    var values=vars(paletteId,mode);
    var palette=get(paletteId), colors=palette[mode === 'dark' ? 'dark' : 'light'];
    Object.keys(values).forEach(function(k){target.style.setProperty(k,values[k]);});
    Object.keys(CORE_TOKENS).forEach(function(k){target.style.setProperty(CORE_TOKENS[k],colors[k]);});
    target.style.setProperty('--core-palette-canvas',colors.canvas);
    target.style.setProperty('--core-palette-surface',colors.surface);
    target.style.setProperty('--core-palette-raised',colors.raised);
    target.style.setProperty('--core-palette-text',colors.text);
    target.style.setProperty('--core-palette-secondary',colors.secondary);
    target.style.setProperty('--core-palette-muted',colors.muted);
    target.style.setProperty('--core-palette-border',colors.border);
    target.style.setProperty('--core-palette-brand',colors.brand);
    target.style.setProperty('--core-palette-strong',colors.strong);
    target.style.setProperty('--core-palette-accent',colors.accent);
    target.style.setProperty('--core-palette-focus',colors.focus);
    target.style.setProperty('--primary-500',colors.brand);
    target.style.setProperty('--primary-600',colors.brand);
    target.style.setProperty('--bg-card',colors.raised);
    target.style.setProperty('--bg-input',colors.raised);
    target.style.setProperty('--bg-tertiary',colors.surface);
    target.style.setProperty('--border-light',colors.border);
    target.style.setProperty('--text-inverse',colors.onBrand);
    target.setAttribute('data-core-palette',paletteId);
    return paletteId;
  }
  return Object.freeze({DEFAULT:'navy', REGISTRY:REGISTRY, SEMANTIC_TOKENS:SEMANTIC, valid:valid, get:get, vars:vars, apply:apply});
}));
