/* ═══════════════════════════════════════════════════════════════
   📋 GOMS Settings - Cases Tab
   ═══════════════════════════════════════════════════════════════ */

// تصنيفات المعاملات
var caseCategories = [
    { key:'request',  name:'طلبية',  icon:'📝', color:'#3b82f6', active:true },
    { key:'memo',     name:'مذكرة',  icon:'📄', color:'#64748b', active:true },
    { key:'report',   name:'تقرير',  icon:'📊', color:'#8b5cf6', active:true },
    { key:'letter',   name:'خطاب',   icon:'✉️', color:'#10b981', active:true },
    { key:'decision', name:'قرار',   icon:'⚖️', color:'#ef4444', active:true },
    { key:'contract', name:'عقد',    icon:'📑', color:'#14b8a6', active:true },
    { key:'meeting',  name:'اجتماع', icon:'🤝', color:'#ec4899', active:true },
    { key:'general',  name:'عام',    icon:'📌', color:'#f59e0b', active:true }
];

// بناء شبكة التصنيفات
function buildCategoryGrid() {
    var g = document.getElementById('categoryGrid');
    if(!g) return;
    g.innerHTML = caseCategories.map(function(c){
        return '<div class="cat-card" onclick="toggleCat(\''+c.key+'\',this)" style="background:'+(c.active?c.color+'10':'rgba(255,255,255,0.02)')+';border-color:'+(c.active?c.color+'40':'var(--border-color)')+';opacity:'+(c.active?'1':'0.5')+';">'+
            '<div class="cat-icon">'+c.icon+'</div>'+
            '<div class="cat-name">'+c.name+'</div>'+
            '<div class="cat-badge" style="'+(c.active?'background:'+c.color+'30;color:'+c.color:'')+'">'+(c.active?'مفعل ✓':'معطل ✕')+'</div>'+
        '</div>';
    }).join('');
    updateCatCount();
}

// تبديل تصنيف
function toggleCat(key, el) {
    var cat = caseCategories.find(function(c){return c.key===key;});
    if(!cat) return;
    cat.active = !cat.active;
    el.style.background = cat.active ? cat.color+'10' : 'rgba(255,255,255,0.02)';
    el.style.borderColor = cat.active ? cat.color+'40' : 'var(--border-color)';
    el.style.opacity = cat.active ? '1' : '0.5';
    var badge = el.querySelector('.cat-badge');
    badge.textContent = cat.active ? 'مفعل ✓' : 'معطل ✕';
    badge.style.background = cat.active ? cat.color+'30' : 'rgba(255,255,255,0.05)';
    badge.style.color = cat.active ? cat.color : 'var(--text-muted)';
    updateCatCount();
}

// تحديد/إلغاء الكل
function toggleAllCats(state) { 
    caseCategories.forEach(function(c){c.active = state;}); 
    buildCategoryGrid(); 
}

// تحديث العداد
function updateCatCount() {
    var count = caseCategories.filter(function(c){return c.active;}).length;
    var el = document.getElementById('activeCatCount');
    if (el) el.textContent = count;
}

// تحديث المعاينة
function updateCasePreview() {
    var pfx = (document.getElementById('cases_prefix').value || 'و').split('/')[0];
    var preview = document.getElementById('previewCaseNumber');
    if (preview) preview.textContent = pfx + '-001-' + new Date().getFullYear();
}

// حفظ الإعدادات
function saveCasesSettings() {
    var s = {
        number_format: document.getElementById('cases_number_format').value,
        prefix: document.getElementById('cases_prefix').value,
        default_status: document.getElementById('cases_default_status').value,
        default_days: document.getElementById('cases_default_days').value,
        default_classification: document.getElementById('cases_default_classification').value,
        archive_days: document.getElementById('cases_archive_days').value,
        auto_archive: document.getElementById('cases_auto_archive').checked,
        max_file_size: document.getElementById('cases_max_file_size').value,
        allowed_types: document.getElementById('cases_allowed_types').value,
        categories: caseCategories.filter(function(c){return c.active;}).map(function(c){return c.key;})
    };
    localStorage.setItem('goms_cases_settings', JSON.stringify(s));
    showToast('✅ تم حفظ إعدادات المعاملات', 'success');
}

// إعادة تعيين
function resetCasesSettings() {
    if(!confirm('⚠️ إعادة تعيين جميع إعدادات المعاملات؟')) return;
    document.getElementById('cases_number_format').value = 'type-seq-year';
    document.getElementById('cases_prefix').value = 'و/ص/د';
    document.getElementById('cases_default_status').value = 'reviewed';
    document.getElementById('cases_default_days').value = '14';
    document.getElementById('cases_default_classification').value = 'public';
    document.getElementById('cases_archive_days').value = '90';
    document.getElementById('cases_auto_archive').checked = true;
    document.getElementById('cases_max_file_size').value = '10';
    document.getElementById('cases_allowed_types').value = 'pdf,doc,docx,xlsx,jpg,png';
    caseCategories.forEach(function(c){c.active = true;});
    buildCategoryGrid(); 
    updateCasePreview();
    localStorage.removeItem('goms_cases_settings');
    showToast('↺ تم إعادة التعيين', 'warning');
}

// تحميل الإعدادات المحفوظة
function loadCasesSettings() {
    var saved = localStorage.getItem('goms_cases_settings');
    if(!saved) return;
    try {
        var d = JSON.parse(saved);
        if(d.number_format) document.getElementById('cases_number_format').value = d.number_format;
        if(d.prefix) document.getElementById('cases_prefix').value = d.prefix;
        if(d.default_status) document.getElementById('cases_default_status').value = d.default_status;
        if(d.default_days) document.getElementById('cases_default_days').value = d.default_days;
        if(d.default_classification) document.getElementById('cases_default_classification').value = d.default_classification;
        if(d.archive_days) document.getElementById('cases_archive_days').value = d.archive_days;
        if(d.auto_archive !== undefined) document.getElementById('cases_auto_archive').checked = d.auto_archive;
        if(d.max_file_size) document.getElementById('cases_max_file_size').value = d.max_file_size;
        if(d.allowed_types) document.getElementById('cases_allowed_types').value = d.allowed_types;
        if(d.categories) caseCategories.forEach(function(c){c.active = d.categories.indexOf(c.key) > -1;});
    } catch(e) {}
}

// تهيئة
(function() {
    loadCasesSettings();
    buildCategoryGrid();
    updateCasePreview();
})();
