/* ═══════════════════════════════════════════════════════════════
   ⚙️ GOMS Settings - Shared Functions
   ═══════════════════════════════════════════════════════════════ */

// إخفاء التبويبات عند التحميل
(function() {
    var all = document.querySelectorAll('.settings-content');
    for (var i = 0; i < all.length; i++) all[i].style.display = 'none';
    if (all.length > 0) { all[0].style.display = 'block'; all[0].classList.add('active'); }
})();

// تبديل التبويبات
function switchTab(tab, el) {
    var all = document.querySelectorAll('.settings-content');
    for (var i = 0; i < all.length; i++) { all[i].style.display = 'none'; all[i].classList.remove('active'); }
    var target = document.getElementById('tab-' + tab);
    if (target) { target.style.display = 'block'; target.classList.add('active'); }
    var tabs = document.querySelectorAll('.settings-tabs .tab');
    for (var j = 0; j < tabs.length; j++) tabs[j].classList.remove('active');
    if (el) el.classList.add('active');
}

// حفظ / إعادة تعيين
function saveSettings(tab) { showToast('✅ تم حفظ إعدادات ' + (tab || ''), 'success'); }
function resetTab(tab) { if (confirm('⚠️ إعادة تعيين إعدادات ' + (tab || '') + '؟')) showToast('↺ تم إعادة التعيين', 'warning'); }

// المظهر
function setThemeLive(theme, el) { if (typeof AppSettings !== 'undefined') AppSettings.setTheme(theme); highlightCard('theme-card', theme, 'data-theme'); }
function setPackageLive(pkg, el) { if (typeof AppSettings !== 'undefined') AppSettings.setColorPackage(pkg); highlightCard('pkg-card', pkg, 'data-pkg'); }
function setFontLive(size, el) { if (typeof AppSettings !== 'undefined') AppSettings.setFontSize(size); highlightBtn('size-btn', size); }
function setDensityLive(d, el) { if (typeof AppSettings !== 'undefined') AppSettings.setDensity(d); highlightBtn('density-btn', d); }
function saveAppearance() { showToast('✅ تم حفظ المظهر', 'success'); }
function resetAppearance() { if (confirm('⚠️ إعادة تعيين المظهر؟')) { if (typeof AppSettings !== 'undefined') AppSettings.resetAll(); showToast('↺ تم', 'warning'); } }

// مساعدة
function testEmail() { var i = document.getElementById('email_test_address'); if (i && i.value) showToast('📧 تم الإرسال', 'success'); }
function selectColor(el) { var d = el.parentElement.querySelectorAll('.color-dot'); for (var i = 0; i < d.length; i++) d[i].classList.remove('selected'); el.classList.add('selected'); }
function selectBg(el) { var d = el.parentElement.querySelectorAll('.bg-thumb'); for (var i = 0; i < d.length; i++) d[i].classList.remove('selected'); el.classList.add('selected'); }
function toggleBadge(el) { el.classList.toggle('disabled'); }

// تمييز البطاقات
function highlightCard(cls, val, attr) {
    document.querySelectorAll('.' + cls).forEach(function(c) {
        c.style.border = '2px solid var(--border-color)'; c.style.background = 'rgba(255,255,255,0.03)';
        var b = c.querySelector('.tbadge, .pbadge'); if (b) { b.textContent = 'اختيار'; b.style.background = 'rgba(255,255,255,0.05)'; b.style.color = 'var(--text-muted)'; }
    });
    var el = document.querySelector('.' + cls + '[' + attr + '="' + val + '"]');
    if (el) { el.style.border = '2px solid #a855f7'; el.style.background = 'rgba(168,85,247,0.08)'; var b = el.querySelector('.tbadge, .pbadge'); if (b) { b.textContent = 'مفعل ✓'; b.style.background = 'rgba(168,85,247,0.2)'; b.style.color = '#a855f7'; } }
}

function highlightBtn(cls, val) {
    document.querySelectorAll('.' + cls).forEach(function(b) { b.style.border = '2px solid var(--border-color)'; b.style.background = 'transparent'; b.style.color = 'var(--text-muted)'; });
    var el = document.querySelector('.' + cls + '[data-size="' + val + '"], .' + cls + '[data-density="' + val + '"]');
    if (el) { el.style.border = '2px solid #a855f7'; el.style.background = 'rgba(168,85,247,0.08)'; el.style.color = 'var(--text-primary)'; }
}

// Toast
function showToast(m, t) {
    t = t || 'info';
    var old = document.querySelector('.toast'); if (old) old.remove();
    var colors = { success: '#10b981', error: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;bottom:2rem;left:2rem;z-index:9999;padding:0.8rem 1.2rem;border-radius:0.8rem;color:white;font-weight:600;font-family:Tajawal;background:' + (colors[t] || colors.info) + ';transition:all 0.3s;';
    d.textContent = m; document.body.appendChild(d);
    setTimeout(function() { d.style.opacity = '0'; d.style.transform = 'translateX(-20px)'; setTimeout(function() { d.remove(); }, 300); }, 3500);
}

// Modal
function openModal(id) { var m = document.getElementById(id); if (m) m.classList.add('active'); }
function closeModal(id) { var m = document.getElementById(id); if (m) m.classList.remove('active'); }
