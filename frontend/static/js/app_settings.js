// ═══════════════════════════════════════════════════════════════
// 🎨 AppSettings - نظام المظهر والخطوط
// ═══════════════════════════════════════════════════════════════

const AppSettings = {
    defaults: { 
        theme: 'dark', 
        colorPackage: 'ocean', 
        fontSize: 'medium', 
        fontFamily: 'tajawal', 
        density: 'comfortable' 
    },

    // 🎨 الألوان الأساسية
    baseColors: [
        { name: '🌊 المحيط الأزرق', type: 'رسمية', hue: 210, lightBg: '#f0f4ff', darkBg: '#0f172a' },
        { name: '💚 الزمرد الأخضر', type: 'طبيعية', hue: 160, lightBg: '#f0fdf4', darkBg: '#0a1a0a' },
        { name: '👑 البنفسج الملكي', type: 'فاخرة', hue: 270, lightBg: '#faf5ff', darkBg: '#0f0b1a' },
        { name: '❤️ الياقوت الأحمر', type: 'جريئة', hue: 0, lightBg: '#fef2f2', darkBg: '#1a0a0a' },
        { name: '✨ الكهرمان الذهبي', type: 'دافئة', hue: 40, lightBg: '#fffbeb', darkBg: '#1a1005' },
        { name: '🪸 المرجان الوردي', type: 'عصرية', hue: 330, lightBg: '#fdf2f8', darkBg: '#1a0a12' },
        { name: '🪽 الفيروز السماوي', type: 'هادئة', hue: 175, lightBg: '#f0fdfa', darkBg: '#0a1a18' },
        { name: '🏺 النحاسي البرونزي', type: 'أصيلة', hue: 25, lightBg: '#fff7ed', darkBg: '#1a0e05' },
        { name: '💎 الياقوت الداكن', type: 'ليلية', hue: 225, lightBg: '#eff6ff', darkBg: '#0a0f1e' },
        { name: '🖤 الأونيكس الأسود', type: 'أنيقة', hue: 215, lightBg: '#f8fafc', darkBg: '#020617' },
        { name: '☕ الموكا البنية', type: 'غنية', hue: 30, lightBg: '#fef3e4', darkBg: '#1a0e03' },
        { name: '🌸 الأوركيد الحالم', type: 'ناعمة', hue: 285, lightBg: '#faf5ff', darkBg: '#0f0a1a' },
        { name: '☁️ السماء الصافية', type: 'مريحة', hue: 200, lightBg: '#f0f9ff', darkBg: '#0c1929' },
        { name: '🍃 النعناع المنعش', type: 'منعشة', hue: 155, lightBg: '#f0fdf4', darkBg: '#0a1a10' },
        { name: '🫐 البرقوق الغامق', type: 'غامقة', hue: 300, lightBg: '#fdf4ff', darkBg: '#1a0a18' },
        { name: '🫒 الزيتون العسكري', type: 'عسكرية', hue: 80, lightBg: '#f7fee7', darkBg: '#0a1005' },
        { name: '🍒 الكرز الناضج', type: 'جذابة', hue: 350, lightBg: '#fff1f2', darkBg: '#1a0a0e' },
        { name: '💜 الخزامى الهادئ', type: 'مهدئة', hue: 245, lightBg: '#f5f3ff', darkBg: '#0a0820' },
        { name: '⬛ الفحم الرمادي', type: 'احترافية', hue: 220, lightBg: '#f9fafb', darkBg: '#030712' },
        { name: '🍂 أوراق الخريف', type: 'خريفية', hue: 35, lightBg: '#fef7ed', darkBg: '#1a0c02' },
        { name: '🪨 الأردواز الرمادي', type: 'متوازنة', hue: 215, lightBg: '#f8fafc', darkBg: '#0f172a' },
        { name: '💙 النيلي العميق', type: 'عميقة', hue: 240, lightBg: '#eef2ff', darkBg: '#0a0830' },
        { name: '🌹 الورد الجوري', type: 'رومانسية', hue: 345, lightBg: '#fff1f2', darkBg: '#1a0510' },
        { name: '🍊 البرتقالي الناري', type: 'نارية', hue: 15, lightBg: '#fff7ed', darkBg: '#1a0c02' }
    ],

    // 📐 الخطوط
    fonts: [
        { key: 'tajawal', name: 'Tajawal', nameAr: 'تجوال', type: 'حديث', css: "'Tajawal', sans-serif" },
        { key: 'cairo', name: 'Cairo', nameAr: 'القاهرة', type: 'عصري', css: "'Cairo', sans-serif" },
        { key: 'noto', name: 'Noto Sans Arabic', nameAr: 'نوتو', type: 'كلاسيكي', css: "'Noto Sans Arabic', sans-serif" },
        { key: 'ibm', name: 'IBM Plex Sans Arabic', nameAr: 'آي بي إم', type: 'احترافي', css: "'IBM Plex Sans Arabic', sans-serif" },
        { key: 'almarai', name: 'Almarai', nameAr: 'المراعي', type: 'رسمي', css: "'Almarai', sans-serif" }
    ],

    // 🏭 توليد باقة
    generatePackage(base) {
        var h = base.hue;
        return {
            name: base.name, type: base.type,
            light: {
                '--bg-primary': base.lightBg,
                '--bg-secondary': '#ffffff',
                '--bg-glass': 'rgba(255,255,255,0.95)',
                '--text-primary': 'hsl(' + h + ', 80%, 15%)',
                '--text-secondary': 'hsl(' + h + ', 20%, 25%)',
                '--text-muted': 'hsl(' + h + ', 10%, 40%)',
                '--border-color': 'hsla(' + h + ', 70%, 50%, 0.2)',
                '--border-light': 'hsla(' + h + ', 70%, 50%, 0.1)',
                '--gradient-1': 'hsl(' + h + ', 80%, 35%)',
                '--gradient-2': 'hsl(' + h + ', 70%, 50%)',
                '--icon-color': 'hsl(' + h + ', 70%, 45%)',
                '--header-bg': 'linear-gradient(135deg, hsl(' + h + ', 70%, 25%), hsl(' + h + ', 80%, 35%))'
            },
            dark: {
                '--bg-primary': base.darkBg,
                '--bg-secondary': 'hsl(' + h + ', 30%, 12%)',
                '--bg-glass': 'hsla(' + h + ', 30%, 15%, 0.95)',
                '--text-primary': 'hsl(' + h + ', 30%, 90%)',
                '--text-secondary': 'hsl(' + h + ', 25%, 80%)',
                '--text-muted': 'hsl(' + h + ', 40%, 65%)',
                '--border-color': 'hsla(' + h + ', 50%, 50%, 0.25)',
                '--border-light': 'hsla(' + h + ', 50%, 50%, 0.12)',
                '--gradient-1': 'hsl(' + h + ', 60%, 50%)',
                '--gradient-2': 'hsl(' + h + ', 70%, 60%)',
                '--icon-color': 'hsl(' + h + ', 70%, 60%)',
                '--header-bg': 'linear-gradient(135deg, hsl(' + h + ', 40%, 10%), hsl(' + h + ', 50%, 20%))'
            }
        };
    },

    // الباقات
    get colorPackages() {
        if (this._packages) return this._packages;
        this._packages = {};
        var self = this;
        this.baseColors.forEach(function(b) {
            var key = b.name.replace(/[^a-zA-Z]/g, '').toLowerCase().substring(0, 10) + '_' + b.hue;
            self._packages[key] = self.generatePackage(b);
        });
        return this._packages;
    },

    init() {
        var root = document.documentElement;
        var hasCoreSettings = root.hasAttribute('data-core-theme');
        var serverTheme = root.getAttribute('data-core-theme') || root.getAttribute('data-theme');
        // Core's scoped value wins over the legacy browser cache on every page load.
        if (hasCoreSettings && ['light', 'dark', 'system'].includes(serverTheme)) {
            localStorage.setItem('goms_theme', serverTheme);
        } else if (!localStorage.getItem('goms_theme') && ['light', 'dark', 'system'].includes(serverTheme)) {
            localStorage.setItem('goms_theme', serverTheme);
        } else if (!localStorage.getItem('goms_theme')) {
            localStorage.setItem('goms_theme', this.defaults.theme);
        }
        if (!hasCoreSettings && !localStorage.getItem('goms_color_package')) localStorage.setItem('goms_color_package', Object.keys(this.colorPackages)[0]);
        this.applyAll();
        console.log('✅ ' + Object.keys(this.colorPackages).length + ' باقة مولوّدة تلقائياً');
    },

    applyAll() {
        this.applyTheme();
        this.applyColorPackage();
        this.applyFontFamily();
        this.applyFontSize();
    },

    // اللون
    getColorPackage() { return localStorage.getItem('goms_color_package') || Object.keys(this.colorPackages)[0]; },
    setColorPackage(pkg) { localStorage.setItem('goms_color_package', pkg); this.applyColorPackage(); },
    applyColorPackage() {
        // Scoped Core branding/theme tokens are server-rendered; an old browser
        // palette must not overwrite institutional or personal saved settings.
        if (document.documentElement.hasAttribute('data-core-theme')) return;
        var pkg = this.colorPackages[this.getColorPackage()] || Object.values(this.colorPackages)[0];
        var root = document.documentElement;
        var t = this.getTheme();
        var isDark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
        var colors = isDark ? pkg.dark : pkg.light;
        Object.keys(colors).forEach(function(k) { root.style.setProperty(k, colors[k]); });
    },

    // السمة
    getTheme() { return localStorage.getItem('goms_theme') || this.defaults.theme; },
    setTheme(t) { localStorage.setItem('goms_theme', t); this.applyAll(); },
    async persistTheme(t) {
        var csrf = document.querySelector('meta[name="csrf-token"]');
        var response = await fetch('/settings/api/user/save/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf ? csrf.content : ''
            },
            body: JSON.stringify({ settings: { theme: t } })
        });
        var result = await response.json();
        if (!response.ok || !result.success) throw new Error('تعذر حفظ تفضيل المظهر');
        document.documentElement.setAttribute('data-core-theme', t);
        sessionStorage.setItem('core_theme_last_saved', t);
        return result;
    },
    applyTheme() {
        var t = this.getTheme();
        if (t === 'system') t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
        this.updateThemeToggle(t);
    },
    updateThemeToggle(theme) {
        var isLight = theme === 'light';
        document.querySelectorAll('.theme-toggle').forEach(function (button) {
            var icon = button.querySelector('i');
            if (icon) icon.className = isLight ? 'fas fa-moon' : 'fas fa-sun';
            var label = isLight ? 'تفعيل الوضع الداكن' : 'تفعيل الوضع الفاتح';
            button.title = label;
            button.setAttribute('aria-label', label);
        });
    },

    // الخط
    getFontFamily() { return localStorage.getItem('goms_font_family') || this.defaults.fontFamily; },
    setFontFamily(f) { localStorage.setItem('goms_font_family', f); this.applyFontFamily(); },
    applyFontFamily() {
        var root = document.documentElement;
        if (root.hasAttribute('data-core-font-family')) {
            root.style.setProperty('--font-family', '"' + root.getAttribute('data-core-font-family') + '", sans-serif');
            return;
        }
        var self = this;
        var f = this.fonts.find(function(x) { return x.key === self.getFontFamily(); }) || this.fonts[0];
        document.documentElement.style.setProperty('--font-family', f.css);
        document.body.style.fontFamily = f.css;
    },

    // الحجم
    getFontSize() { return localStorage.getItem('goms_font_size') || this.defaults.fontSize; },
    setFontSize(s) { localStorage.setItem('goms_font_size', s); this.applyFontSize(); },
    applyFontSize() {
        var root = document.documentElement;
        var coreSize = Number(root.getAttribute('data-core-font-size'));
        if (Number.isInteger(coreSize) && coreSize >= 12 && coreSize <= 24) {
            root.style.fontSize = coreSize + 'px';
            return;
        }
        var sizes = { small: '0.8rem', medium: '0.9rem', large: '1.05rem', xlarge: '1.2rem' };
        document.documentElement.style.fontSize = sizes[this.getFontSize()] || '0.9rem';
    },

    // الكثافة
    getDensity() { return localStorage.getItem('goms_density') || this.defaults.density; },
    setDensity(d) { localStorage.setItem('goms_density', d); },

    getAll() { return { theme: this.getTheme(), colorPackage: this.getColorPackage(), fontSize: this.getFontSize(), fontFamily: this.getFontFamily(), density: this.getDensity() }; },
    resetAll() { ['goms_theme','goms_color_package','goms_font_size','goms_font_family','goms_density'].forEach(function(k) { localStorage.removeItem(k); }); this._packages = null; this.init(); }
};

document.addEventListener('DOMContentLoaded', function() {
    AppSettings.init();
    document.querySelectorAll('.theme-toggle').forEach(function (button) {
        button.addEventListener('click', async function () {
            if (button.dataset.themeSaving === 'true') return;
            var previous = AppSettings.getTheme();
            var next = previous === 'light' ? 'dark' : 'light';
            button.dataset.themeSaving = 'true';
            button.disabled = true;
            AppSettings.setTheme(next);
            try {
                await AppSettings.persistTheme(next);
            } catch (error) {
                AppSettings.setTheme(previous);
                console.error('Core theme preference was not saved:', error);
            } finally {
                button.disabled = false;
                delete button.dataset.themeSaving;
            }
        });
    });
});
window.AppSettings = AppSettings;

// A history traversal may restore an older DOM snapshot from the back/forward
// cache. Keep that snapshot aligned with the last Core preference saved by
// this tab; ordinary page loads still take their value from server-rendered
// data-core-theme in init().
window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    var saved = sessionStorage.getItem('core_theme_last_saved') || localStorage.getItem('goms_theme');
    if (!['light', 'dark', 'system'].includes(saved)) return;
    localStorage.setItem('goms_theme', saved);
    document.documentElement.setAttribute('data-core-theme', saved);
    AppSettings.applyAll();
});
