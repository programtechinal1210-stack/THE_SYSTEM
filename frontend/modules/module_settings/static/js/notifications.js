/* ═══════════════════════════════════════════════════════════════
   🔔 GOMS Settings - Notifications Tab
   ═══════════════════════════════════════════════════════════════ */

var allNotifs = [];
var currentFilter = 'all';

// تحميل قائمة الإشعارات
async function loadNotifList() {
    try {
        var r = await fetch('/settings/api/notifications/?limit=100');
        var d = await r.json();
        allNotifs = d.notifications || [];
        renderNotifList();
        updateNotifStats();
    } catch(e) {
        document.getElementById('notifListContainer').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted);">❌ فشل تحميل الإشعارات</div>';
    }
}

// عرض قائمة الإشعارات
function renderNotifList() {
    var container = document.getElementById('notifListContainer');
    var filtered = currentFilter === 'all' ? allNotifs :
                   currentFilter === 'unread' ? allNotifs.filter(function(n) { return !n.is_read; }) :
                   allNotifs.filter(function(n) { return n.type === currentFilter; });

    if (filtered.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted);">🎉 لا توجد إشعارات</div>';
        return;
    }

    var icons = { task_assigned:'🆕', task_completed:'🎉', task_overdue:'⚠️', case_referred:'📨', directive_issued:'📢', response_added:'💬', action_assigned:'⚡' };

    container.innerHTML = filtered.map(function(n) {
        var time = new Date(n.created_at).toLocaleString('ar-SA');
        return '<div class="notif-row ' + (n.is_read ? '' : 'unread') + '">' +
            '<div class="n-icon">' + (icons[n.type] || '🔔') + '</div>' +
            '<div class="n-content" onclick="readNotif(\'' + n.id + '\')">' +
                '<div class="n-title">' + (n.title || '') + '</div>' +
                '<div class="n-text">' + (n.content || '') + '</div>' +
                '<div class="n-time">' + time + '</div>' +
            '</div>' +
            '<div class="n-actions">' +
                (!n.is_read ? '<button class="n-btn" onclick="event.stopPropagation();readNotif(\'' + n.id + '\')" title="تحديد كمقروء">✓</button>' : '') +
                '<button class="n-btn" onclick="event.stopPropagation();deleteNotif(\'' + n.id + '\')" title="حذف" style="color:#ef4444;">🗑</button>' +
            '</div>' +
        '</div>';
    }).join('');
}

// فلترة الإشعارات
function filterNotifs(filter, el) {
    currentFilter = filter;
    document.querySelectorAll('.filter-chip').forEach(function(c) { c.classList.remove('active'); });
    if (el) el.classList.add('active');
    renderNotifList();
}

// تحديد كمقروء
async function readNotif(id) {
    try { 
        await fetch('/settings/api/notifications/read/' + id + '/'); 
        loadNotifList(); 
        if (typeof updateNotificationBadge === 'function') updateNotificationBadge(); 
    } catch(e) {}
}

// حذف إشعار
async function deleteNotif(id) {
    if (!confirm('🗑️ حذف هذا الإشعار؟')) return;
    try { 
        await fetch('/settings/api/notifications/read/' + id + '/'); 
        loadNotifList(); 
    } catch(e) {}
}

// تحديد الكل كمقروء
async function markAllRead() {
    try { await fetch('/settings/api/notifications/read-all/'); loadNotifList(); } catch(e) {}
}

// تحديث الإحصائيات
function updateNotifStats() {
    var total = document.getElementById('statTotalNotifs');
    var unread = document.getElementById('statUnreadNotifs');
    if (total) total.textContent = allNotifs.length;
    if (unread) unread.textContent = allNotifs.filter(function(n) { return !n.is_read; }).length;
}

// تهيئة
(function() {
    loadNotifList();
})();
