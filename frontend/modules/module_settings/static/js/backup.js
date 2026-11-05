// ═══════════════════════════════════════════════════════════════
// 💾 النسخ الاحتياطي - settings/backup.js
// ═══════════════════════════════════════════════════════════════

var BACKUP_KEY = 'goms_backups';

function getBackups() {
    try { return JSON.parse(localStorage.getItem(BACKUP_KEY)) || []; }
    catch (e) { return []; }
}

function setBackups(list) {
    try { localStorage.setItem(BACKUP_KEY, JSON.stringify(list)); } catch (e) {}
    renderBackupHistory();
}

function collectData() {
    var keys = ['goms_theme', 'goms_color_package', 'goms_font_size', 'goms_font_family', 'goms_density'];
    var settings = {};
    keys.forEach(function (k) {
        var v = localStorage.getItem(k);
        if (v !== null) settings[k] = v;
    });
    return {
        version: 1,
        created_at: new Date().toISOString(),
        system: 'GOMS',
        settings: settings
    };
}

function renderBackupHistory() {
    var box = document.getElementById('backupHistory');
    var count = document.getElementById('backupCount');
    var last = document.getElementById('lastBackup');
    if (!box) return;
    var list = getBackups();

    if (count) count.textContent = list.length;
    if (last) last.textContent = list.length ? new Date(list[0].created_at).toLocaleString('ar-SA') : '—';

    if (!list.length) {
        box.innerHTML = '<div style="text-align:center;padding:1.4rem;color:var(--text-muted);font-size:0.82rem;">لا توجد نسخ محفوظة بعد</div>';
        return;
    }
    box.innerHTML = list.map(function (b, i) {
        var d = new Date(b.created_at).toLocaleString('ar-SA');
        return '<div style="display:flex;justify-content:space-between;align-items:center;padding:0.6rem 0.8rem;background:rgba(99,102,241,0.06);border-radius:0.5rem;font-size:0.8rem;">' +
            '<div><span style="color:var(--icon-color);font-weight:600;">💾</span> ' +
            '<span style="color:var(--text-primary);">نسخة #' + (list.length - i) + '</span>' +
            '<span style="color:var(--text-muted);margin-right:0.5rem;">' + d + '</span></div>' +
            '<div style="display:flex;gap:0.3rem;">' +
            '<button class="btn btn-sm btn-secondary" onclick="downloadBackup(' + i + ')">⬇️ تنزيل</button>' +
            '<button class="btn btn-sm btn-danger" onclick="deleteBackup(' + i + ')">🗑️</button>' +
            '</div></div>';
    }).join('');
}

function download(filename, text) {
    var blob = new Blob([text], { type: 'application/json;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function stamp() {
    var d = new Date();
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + '_' + p(d.getHours()) + p(d.getMinutes());
}

function createBackup() {
    var data = collectData();
    var list = getBackups();
    list.unshift(data);
    if (list.length > 20) list = list.slice(0, 20);
    setBackups(list);
    download('GOMS-backup-' + stamp() + '.json', JSON.stringify(data, null, 2));
    showToast('تم إنشاء نسخة احتياطية وتنزيلها', 'success');
}

function exportJson() {
    download('GOMS-settings-' + stamp() + '.json', JSON.stringify(collectData(), null, 2));
    showToast('تم تصدير الإعدادات', 'success');
}

function downloadTemplate() {
    download('GOMS-backup-template.json', JSON.stringify(collectData(), null, 2));
    showToast('تم تنزيل القالب', 'info');
}

function downloadBackup(index) {
    var list = getBackups();
    if (!list[index]) return;
    download('GOMS-backup-' + index + '.json', JSON.stringify(list[index], null, 2));
    showToast('تم تنزيل النسخة', 'success');
}

function deleteBackup(index) {
    if (!confirm('حذف هذه النسخة؟')) return;
    var list = getBackups();
    list.splice(index, 1);
    setBackups(list);
    showToast('تم حذف النسخة', 'warning');
}

function restoreBackup(input) {
    var result = document.getElementById('backupRestoreResult');
    var show = function (ok, msg) {
        if (!result) return;
        result.style.display = 'block';
        result.style.background = ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)';
        result.style.color = ok ? '#10b981' : '#ef4444';
        result.textContent = msg;
    };
    if (!input.files || !input.files[0]) return;

    var reader = new FileReader();
    reader.onload = function (e) {
        try {
            var data = JSON.parse(e.target.result);
            if (!data || !data.settings) throw new Error('bad');
            Object.keys(data.settings).forEach(function (k) {
                localStorage.setItem(k, data.settings[k]);
            });
            if (window.AppSettings) AppSettings.applyAll();
            show(true, '✅ تمت استعادة الإعدادات بنجاح وإعادة تطبيقها.');
            showToast('تمت استعادة النسخة الاحتياطية', 'success');
        } catch (err) {
            show(false, '❌ ملف غير صالح — تأكد أنه ملف نسخة GOMS.');
        }
        input.value = '';
    };
    reader.readAsText(input.files[0]);
}

function saveBackupSettings() {
    var interval = document.getElementById('backupInterval');
    var keep = document.getElementById('backupKeep');
    try {
        localStorage.setItem('goms_backup_interval', interval ? interval.value : 'off');
        localStorage.setItem('goms_backup_keep', keep ? keep.value : '10');
    } catch (e) {}
    renderBackupSettingsState();
    showToast('تم حفظ إعدادات النسخ الاحتياطي', 'success');
}

function renderBackupSettingsState() {
    var state = document.getElementById('autoBackupState');
    if (!state) return;
    var v = 'معطّل';
    try { v = localStorage.getItem('goms_backup_interval') || 'off'; } catch (e) {}
    var labels = { off: 'معطّل', daily: 'يومي', weekly: 'أسبوعي', monthly: 'شهري' };
    state.textContent = labels[v] || v;
}

document.addEventListener('DOMContentLoaded', function () {
    var interval = document.getElementById('backupInterval');
    if (interval) {
        try { interval.value = localStorage.getItem('goms_backup_interval') || 'off'; } catch (e) {}
    }
    renderBackupSettingsState();
    renderBackupHistory();
});
