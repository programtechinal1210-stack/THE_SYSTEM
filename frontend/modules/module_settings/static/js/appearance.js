/* ═══════════════════════════════════════════════════════════════
   🎨 GOMS Settings - Appearance Tab
   ═══════════════════════════════════════════════════════════════ */

var packageKeys = [];
var currentPackageIndex = 0;

// بناء جميع الباقات
function buildAllPackages() {
    var grid = document.getElementById('packageGrid');
    if (!grid || !AppSettings.colorPackages) return;

    packageKeys = Object.keys(AppSettings.colorPackages);
    var html = '';

    for (var i = 0; i < packageKeys.length; i++) {
        var key = packageKeys[i];
        var pkg = AppSettings.colorPackages[key];
        var c = pkg.light;
        var c1 = c['--gradient-1'] || '#888';
        var c2 = c['--gradient-2'] || '#aaa';
        var c3 = c['--icon-color'] || '#aaa';
        var searchText = (pkg.name + ' ' + pkg.type + ' ' + key).toLowerCase();

        html += '<div class="pkg-card" data-pkg="' + key + '" data-search="' + searchText + '" onclick="setPackageLive(\'' + key + '\', this)" style="background:' + c1 + '10;border:2px solid var(--border-color);border-radius:0.8rem;padding:0.7rem;text-align:center;cursor:pointer;transition:all 0.3s;">';
        html += '<div style="display:flex;gap:2px;justify-content:center;margin-bottom:0.3rem;"><span style="width:12px;height:12px;border-radius:2px;background:' + c1 + ';"></span><span style="width:12px;height:12px;border-radius:2px;background:' + c2 + ';"></span><span style="width:12px;height:12px;border-radius:2px;background:' + c3 + ';"></span></div>';
        html += '<div style="font-weight:700;color:var(--text-primary);font-size:0.78rem;line-height:1.2;">' + (pkg.name || key) + '</div>';
        html += '<div style="font-size:0.65rem;color:var(--text-muted);">' + (pkg.type || '') + '</div>';
        html += '<div class="pbadge" style="margin-top:0.3rem;padding:0.15rem 0.5rem;border-radius:2rem;font-size:0.6rem;background:rgba(255,255,255,0.05);color:var(--text-muted);display:inline-block;">اختيار</div>';
        html += '</div>';
    }
    grid.innerHTML = html;

    var countEl = document.getElementById('packageCount');
    if (countEl) countEl.textContent = '(' + packageKeys.length + ' باقة)';

    var current = AppSettings.getColorPackage();
    currentPackageIndex = packageKeys.indexOf(current);
    if (currentPackageIndex < 0) currentPackageIndex = 0;
    updatePackageIndex();
}

// التنقل بين الباقات
function nextPackage() {
    if (packageKeys.length === 0) return;
    currentPackageIndex = (currentPackageIndex + 1) % packageKeys.length;
    var key = packageKeys[currentPackageIndex];
    AppSettings.setColorPackage(key);
    highlightCard('pkg-card', key, 'data-pkg');
    updateLivePreview();
    updatePackageIndex();
    var el = document.querySelector('.pkg-card[data-pkg="' + key + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function prevPackage() {
    if (packageKeys.length === 0) return;
    currentPackageIndex = (currentPackageIndex - 1 + packageKeys.length) % packageKeys.length;
    var key = packageKeys[currentPackageIndex];
    AppSettings.setColorPackage(key);
    highlightCard('pkg-card', key, 'data-pkg');
    updateLivePreview();
    updatePackageIndex();
    var el = document.querySelector('.pkg-card[data-pkg="' + key + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function updatePackageIndex() {
    var el = document.getElementById('packageIndex');
    if (el) el.textContent = (currentPackageIndex + 1) + ' / ' + packageKeys.length;
}

// توليد باقة عشوائية
function generateNewPackage() {
    var hue = Math.floor(Math.random() * 360);
    var names = ['✨', '🌟', '💫', '🔥', '💎', '🎯', '🌈', '🦋', '🌺', '🍀', '🎪', '🌴', '🪐', '🌸', '💜', '🧡', '💙', '🤍'];
    var types = ['مولدة', 'عشوائية', 'جديدة', 'مميزة', 'فريدة'];
    var name = names[Math.floor(Math.random() * names.length)] + ' لون ' + hue + '°';
    var type = types[Math.floor(Math.random() * types.length)];

    var key = 'gen_' + Date.now();
    AppSettings.colorPackages[key] = AppSettings.generatePackage({
        name: name, type: type, hue: hue,
        lightBg: 'hsl(' + hue + ', 30%, 95%)',
        darkBg: 'hsl(' + hue + ', 30%, 8%)'
    });

    buildAllPackages();
    AppSettings.setColorPackage(key);
    currentPackageIndex = packageKeys.indexOf(key);
    highlightCard('pkg-card', key, 'data-pkg');
    updateLivePreview();
    updatePackageIndex();
    var countEl = document.getElementById('packageCount');
    if (countEl) countEl.textContent = '(' + packageKeys.length + ' باقة)';
    showToast('🎲 تم توليد باقة جديدة: ' + name, 'success');
}

// بحث عن الباقات
function filterPackages() {
    var q = (document.getElementById('packageSearch').value || '').toLowerCase();
    document.querySelectorAll('.pkg-card').forEach(function(c) {
        c.style.display = q === '' || c.getAttribute('data-search').indexOf(q) > -1 ? '' : 'none';
    });
}

// تحديث المعاينة المباشرة
function updateLivePreview() {
    var t = AppSettings.getTheme();
    var p = AppSettings.getColorPackage();
    var pkg = AppSettings.colorPackages[p];
    
    var liveTheme = document.getElementById('liveTheme');
    var livePackage = document.getElementById('livePackage');
    var liveFont = document.getElementById('liveFont');
    var liveDensity = document.getElementById('liveDensity');
    
    if (liveTheme) liveTheme.textContent = t === 'dark' ? '🌙 داكن' : (t === 'light' ? '☀️ فاتح' : '🔄 تلقائي');
    if (livePackage) livePackage.textContent = pkg ? pkg.name + ' (' + pkg.type + ')' : p;
    if (liveFont) liveFont.textContent = AppSettings.getFontSize();
    if (liveDensity) liveDensity.textContent = AppSettings.getDensity();
}

// تعيين المظهر مباشرة
function setThemeLive(theme, el) { 
    AppSettings.setTheme(theme); 
    highlightCard('theme-card', theme, 'data-theme'); 
    updateLivePreview(); 
}

function setPackageLive(pkg, el) { 
    AppSettings.setColorPackage(pkg); 
    currentPackageIndex = packageKeys.indexOf(pkg); 
    highlightCard('pkg-card', pkg, 'data-pkg'); 
    updateLivePreview(); 
    updatePackageIndex(); 
}

function setFontLive(size, el) { 
    AppSettings.setFontSize(size); 
    highlightBtn('size-btn', size); 
    updateLivePreview(); 
}

function setDensityLive(d, el) { 
    AppSettings.setDensity(d); 
    highlightBtn('density-btn', d); 
    updateLivePreview(); 
}

// حفظ وإعادة تعيين
async function saveAppearance() {
    var csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
        var response = await fetch('/settings/api/user/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ settings: { theme: AppSettings.getTheme() } })
        });
        var result = await response.json();
        if (!response.ok || !result.success) throw new Error('تعذر حفظ تفضيل المظهر');
        showToast('✅ تم حفظ إعدادات المظهر لجميع أجهزتك', 'success');
    } catch (error) {
        showToast('تعذر حفظ المظهر على الحساب. حاول مجددًا.', 'error');
    }
}

function resetAppearance() { 
    if (confirm('⚠️ إعادة تعيين؟')) { 
        AppSettings.resetAll(); 
        updateLivePreview(); 
        showToast('↺ تم', 'warning'); 
    } 
}

// تهيئة
(function() {
    buildAllPackages();
    updateLivePreview();
    highlightCard('pkg-card', AppSettings.getColorPackage(), 'data-pkg');
    highlightCard('theme-card', AppSettings.getTheme(), 'data-theme');
})();
