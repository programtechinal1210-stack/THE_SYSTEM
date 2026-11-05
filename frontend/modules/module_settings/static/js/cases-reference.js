/* ═══════════════════════════════════════════════════════════════
   📋 GOMS Cases - Reference Data (Shared)
   ═══════════════════════════════════════════════════════════════ */

var API_BASE = '/settings/api/cases';

// تبديل التبويبات الفرعية
function switchCaseTab(tab, el) {
    document.querySelectorAll('.case-tab-content').forEach(function(c) { c.classList.remove('active'); });
    document.querySelectorAll('.cases-subtabs .subtab').forEach(function(s) { s.classList.remove('active'); });
    document.getElementById('case-tab-' + tab).classList.add('active');
    if (el) el.classList.add('active');
    loadRefData(tab);
}

// جلب البيانات
async function loadRefData(type) {
    if (type === 'priorities' || type === 'settings' || type === 'storage') return;
    var tbody = document.getElementById('tbody-' + type);
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">⏳ جاري التحميل...</td></tr>';
    try {
        var r = await fetch(API_BASE + '/' + type);
        var data = await r.json();
        renderRefTable(type, data);
        updateStats(type, data.length);
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#ef4444;">❌ فشل التحميل</td></tr>';
    }
}

// عرض الجدول
function renderRefTable(type, data) {
    var tbody = document.getElementById('tbody-' + type);
    if (!tbody) return;
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">لا توجد بيانات</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(function(item, i) {
        var statusBadge = item.is_active 
            ? '<span class="badge-sm" style="background:#10b981;color:white;">✅ نشط</span>'
            : '<span class="badge-sm" style="background:#ef4444;color:white;">❌ معطل</span>';
        var actions = '<button class="btn btn-secondary btn-sm" onclick="openRefModal(\'' + type + '\', \'edit\', ' + item.id + ')" title="تعديل">✏️</button>' +
            '<button class="btn btn-warning btn-sm" onclick="toggleRefItem(\'' + type + '\', ' + item.id + ')" title="تبديل" style="margin:0 3px;">🔄</button>' +
            '<button class="btn btn-danger btn-sm" onclick="deleteRefItem(\'' + type + '\', ' + item.id + ')" title="حذف">🗑️</button>';
        var row = '<tr><td>' + (i+1) + '</td><td>' + (item.code || '-') + '</td><td>' + (item.name || '-') + '</td><td>' + (item.name_english || '-') + '</td>';
        if (type === 'classifications') row += '<td>' + (item.level || '-') + '</td>';
        row += '<td>' + statusBadge + '</td><td style="white-space:nowrap;">' + actions + '</td></tr>';
        return row;
    }).join('');
}

// تحديث الإحصائيات
function updateStats(type, count) {
    if (type === 'transaction-types') document.getElementById('statTransTypes').textContent = count;
    if (type === 'classifications') document.getElementById('statClassifications').textContent = count;
    if (type === 'archive-status') document.getElementById('statArchiveStatus').textContent = count;
}

// فتح المودال
async function openRefModal(type, mode, id) {
    var modal = document.getElementById('refModal');
    document.getElementById('refType').value = type;
    document.getElementById('refMode').value = mode;
    document.getElementById('refLevelGroup').style.display = (type === 'classifications') ? 'block' : 'none';
    
    if (mode === 'create') {
        document.getElementById('refModalTitle').textContent = '➕ إضافة عنصر جديد';
        document.getElementById('refId').value = '';
        document.getElementById('refCode').value = '';
        document.getElementById('refName').value = '';
        document.getElementById('refNameEn').value = '';
        document.getElementById('refLevel').value = '1';
        document.getElementById('refDescription').value = '';
    } else if (mode === 'edit' && id) {
        document.getElementById('refModalTitle').textContent = '✏️ تعديل العنصر';
        document.getElementById('refId').value = id;
        try {
            var r = await fetch(API_BASE + '/' + type + '/' + id);
            var item = await r.json();
            document.getElementById('refCode').value = item.code || '';
            document.getElementById('refName').value = item.name || '';
            document.getElementById('refNameEn').value = item.name_english || '';
            document.getElementById('refLevel').value = item.level || '1';
            document.getElementById('refDescription').value = item.description || '';
        } catch(e) { showToast('❌ فشل جلب البيانات', 'error'); return; }
    }
    modal.classList.add('active');
}

// إغلاق المودال
function closeRefModal() { document.getElementById('refModal').classList.remove('active'); }

// حفظ العنصر
async function saveRefItem() {
    var type = document.getElementById('refType').value;
    var mode = document.getElementById('refMode').value;
    var id = document.getElementById('refId').value;
    var code = document.getElementById('refCode').value.trim();
    var name = document.getElementById('refName').value.trim();
    var nameEn = document.getElementById('refNameEn').value.trim();
    var description = document.getElementById('refDescription').value.trim();
    var level = parseInt(document.getElementById('refLevel').value) || 1;
    
    if (!code || !name) { showToast('⚠️ الرمز والاسم العربي مطلوبان', 'warning'); return; }
    var body = { code: code, name: name, name_english: nameEn, description: description };
    if (type === 'classifications') body.level = level;
    
    try {
        var url = API_BASE + '/' + type;
        var method = 'POST';
        if (mode === 'edit') { url += '/' + id; method = 'PUT'; }
        var r = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (r.ok) { showToast('✅ تم الحفظ بنجاح', 'success'); closeRefModal(); loadRefData(type); }
        else { var err = await r.json(); showToast('❌ ' + (err.detail || 'فشل الحفظ'), 'error'); }
    } catch(e) { showToast('❌ فشل الاتصال', 'error'); }
}

// تبديل الحالة
async function toggleRefItem(type, id) {
    try { await fetch(API_BASE + '/' + type + '/' + id + '/toggle', { method: 'PATCH' }); showToast('🔄 تم تبديل الحالة', 'success'); loadRefData(type); }
    catch(e) { showToast('❌ فشل', 'error'); }
}

// حذف عنصر
async function deleteRefItem(type, id) {
    if (!confirm('🗑️ هل أنت متأكد من حذف هذا العنصر؟')) return;
    try { await fetch(API_BASE + '/' + type + '/' + id, { method: 'DELETE' }); showToast('🗑️ تم الحذف', 'warning'); loadRefData(type); }
    catch(e) { showToast('❌ فشل الحذف', 'error'); }
}

// تهيئة
(function() {
    loadRefData('transaction-types');
    loadRefData('classifications');
    loadRefData('archive-status');
})();

// ═══════════════════════════════════════════════════════
// 💾 مسار التخزين
// ═══════════════════════════════════════════════════════
var SETTINGS_API = '/settings/api';

async function loadStoragePath() {
    try {
        var r = await fetch(SETTINGS_API + '/get/');
        var d = await r.json();
        if (d.system && d.system.general && d.system.general.upload_path) {
            document.getElementById('storage_path').value = d.system.general.upload_path;
        }
    } catch(e) {
        document.getElementById('storage_path').value = 'فشل التحميل';
    }
}

async function updateStoragePath() {
    var newPath = document.getElementById('storage_new_path').value.trim();
    var result = document.getElementById('storageResult');
    
    if (!newPath) {
        result.style.display = 'block';
        result.style.background = 'rgba(239,68,68,0.08)';
        result.style.color = '#ef4444';
        result.textContent = '❌ الرجاء إدخال مسار';
        return;
    }
    
    result.style.display = 'block';
    result.style.background = 'rgba(245,158,11,0.08)';
    result.style.color = '#f59e0b';
    result.textContent = '⏳ جاري تحديث المسار...';
    
    try {
        var r = await fetch(SETTINGS_API + '/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tab: 'general', settings: { upload_path: newPath } })
        });
        
        if (r.ok) {
            document.getElementById('storage_path').value = newPath;
            document.getElementById('storage_new_path').value = '';
            result.style.background = 'rgba(16,185,129,0.08)';
            result.style.color = '#10b981';
            result.textContent = '✅ تم تحديث مسار التخزين بنجاح';
            showToast('✅ تم تحديث مسار التخزين', 'success');
        } else {
            throw new Error('فشل');
        }
    } catch(e) {
        result.style.background = 'rgba(239,68,68,0.08)';
        result.style.color = '#ef4444';
        result.textContent = '❌ فشل تحديث المسار';
    }
    
    setTimeout(function() { result.style.display = 'none'; }, 3000);
}

function copyStoragePath() {
    var input = document.getElementById('storage_path');
    if (input && input.value) {
        navigator.clipboard.writeText(input.value).then(function() {
            showToast('📋 تم نسخ المسار', 'success');
        });
    }
}

// تحميل مسار التخزين عند فتح التبويب
var origSwitchCaseTab = switchCaseTab;
switchCaseTab = function(tab, el) {
    origSwitchCaseTab(tab, el);
    if (tab === 'storage') loadStoragePath();
};

// ═══════════════════════════════════════════════════════
// 🗂️ File Explorer
// ═══════════════════════════════════════════════════════

function browseFolder() {
    var explorer = document.getElementById('fileExplorer');
    explorer.style.display = 'block';
    var currentPath = document.getElementById('storage_path').value || 'C:/';
    document.getElementById('explorerCurrentPath').value = currentPath;
    loadFolders(currentPath);
}

function closeFileExplorer() {
    document.getElementById('fileExplorer').style.display = 'none';
}

async function loadFolders(path) {
    var list = document.getElementById('explorerFolderList');
    list.innerHTML = '<div style="text-align:center;padding:1rem;color:var(--text-muted);">⏳ جاري التحميل...</div>';
    
    try {
        var r = await fetch('/settings/api/browse-folders/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        var data = await r.json();
        
        if (data.error) {
            list.innerHTML = '<div style="text-align:center;padding:1rem;color:#ef4444;">❌ ' + data.error + '</div>';
            return;
        }
        
        if (!data.folders || data.folders.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:1rem;color:var(--text-muted);">📭 لا توجد مجلدات فرعية</div>';
            return;
        }
        
        list.innerHTML = data.folders.map(function(f) {
            return '<div onclick="enterFolder(\'' + f.path.replace(/\\/g, '\\\\') + '\')" style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0.8rem;border-radius:0.4rem;cursor:pointer;transition:all 0.15s;font-size:0.8rem;" onmouseover="this.style.background=\'var(--bg-card-hover)\'" onmouseout="this.style.background=\'transparent\'">' +
                '<span>📁</span><span style="color:var(--text-primary);">' + f.name + '</span>' +
                '<span style="color:var(--text-muted);font-size:0.7rem;margin-right:auto;">' + (f.item_count || '') + '</span>' +
            '</div>';
        }).join('');
        
        document.getElementById('explorerCurrentPath').value = data.current_path || path;
    } catch(e) {
        list.innerHTML = '<div style="text-align:center;padding:1rem;color:#ef4444;">❌ فشل تحميل المجلدات</div>';
    }
}

function enterFolder(path) {
    document.getElementById('storage_new_path').value = path;
    loadFolders(path);
}

function navigateUp() {
    var currentPath = document.getElementById('explorerCurrentPath').value;
    var parts = currentPath.replace(/\\/g, '/').replace(/\/$/, '').split('/');
    if (parts.length > 1) {
        parts.pop();
        var parentPath = parts.join('/').replace(/^([A-Z]):$/, '$1:/');
        if (parentPath.length < 3) parentPath = parentPath + '/';
        document.getElementById('explorerCurrentPath').value = parentPath;
        loadFolders(parentPath);
    }
}

function selectCurrentFolder() {
    var path = document.getElementById('explorerCurrentPath').value;
    document.getElementById('storage_new_path').value = path;
    closeFileExplorer();
    showToast('📁 تم تحديد: ' + path, 'success');
}

async function createNewFolder() {
    var name = document.getElementById('newFolderName').value.trim();
    if (!name) { showToast('⚠️ أدخل اسم المجلد', 'warning'); return; }
    var currentPath = document.getElementById('explorerCurrentPath').value;
    
    try {
        var r = await fetch('/settings/api/create-folder/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentPath, folder_name: name })
        });
        var data = await r.json();
        if (data.success) {
            showToast('✅ تم إنشاء المجلد', 'success');
            document.getElementById('newFolderName').value = '';
            loadFolders(currentPath);
        } else {
            showToast('❌ ' + (data.error || 'فشل الإنشاء'), 'error');
        }
    } catch(e) {
        showToast('❌ فشل الاتصال', 'error');
    }
    
}
function handleFolderPick(input) {
    if (input.files.length > 0) {
        var fullPath = input.files[0].webkitRelativePath || input.files[0].name;
        var folderName = fullPath.split('/')[0];
        document.getElementById('storage_new_path').value = folderName;
        showToast('📁 تم اختيار المجلد: ' + folderName, 'info');
    }
}