/**
 * audit-render.js - دوال عرض البيانات
 * ============================================================
 */

const AuditRenderer = {
    /**
     * عرض بطاقات الإحصائيات
     */
    renderStats(stats) {
        if (!stats) return;
        document.getElementById('statTotalActions').textContent = stats.total_actions || 0;
        document.getElementById('statUniqueUsers').textContent = stats.unique_users || 0;
        document.getElementById('statPendingFollowups').textContent = stats.pending_followups || 0;
        document.getElementById('statOpenAnomalies').textContent = stats.open_anomalies || 0;
        document.getElementById('statAvgDuration').textContent = AuditUtils.formatDurationMs(stats.avg_duration_ms);
        document.getElementById('statTotalExports').textContent = stats.total_exports || 0;

        // تحديث العدادات في التبويبات
        TabManager.updateBadge('logs', stats.total_actions || 0);
        TabManager.updateBadge('followups', stats.pending_followups || 0);
        TabManager.updateBadge('anomalies', stats.open_anomalies || 0);
    },

    /**
     * عرض سجل التدقيق
     */
    renderLogs(data) {
        const tbody = document.querySelector('#auditTable tbody');
        if (!tbody) return;

        if (!data || !data.results || data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9"><div class="empty-state">' +
                '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">' +
                '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>' +
                '</svg><p>لا توجد سجلات تدقيق</p></div></td></tr>';
            return;
        }

        let html = '';
        data.results.forEach((log, i) => {
            const severityBadge = log.severity === 'critical' ? 'badge-danger' : log.severity === 'warning' ? 'badge-warning' : 'badge-info';
            const actionBadge = log.action_type === 'CREATE' ? 'badge-success' : log.action_type === 'DELETE' ? 'badge-danger' : log.action_type === 'UPDATE' ? 'badge-info' : 'badge-secondary';
            const initials = AuditUtils.getInitials(log.actor_name);
            const color = AuditUtils.stringToColor(log.actor_name);
            const rowClass = log.severity === 'critical' ? 'critical' : '';
            const rowNum = (data.page_start || 1) + i;
            const actorName = AuditUtils.escapeHtml(log.actor_name || 'النظام');
            const summary = AuditUtils.truncate(log.changes_summary || log.action, 60);
            const dateStr = AuditUtils.formatDate(log.created_at, 'datetime');

            html += '<tr class="' + rowClass + '">' +
                '<td>' + rowNum + '</td>' +
                '<td><div class="user-cell"><span class="user-avatar" style="background:' + color + '">' + initials + '</span><span class="user-name">' + actorName + '</span></div></td>' +
                '<td><span class="badge ' + actionBadge + '">' + log.action_type + '</span></td>' +
                '<td><span class="badge badge-secondary">' + log.entity_type + '</span></td>' +
                '<td><span class="badge badge-secondary">' + (log.module || '--') + '</span></td>' +
                '<td><span class="badge ' + severityBadge + '">' + log.severity + '</span></td>' +
                '<td>' + summary + '</td>' +
                '<td><span class="datetime">' + dateStr + '</span></td>' +
                '<td><button class="btn-icon" onclick="AuditApp.viewLogDetail(' + log.id + ')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></td>' +
                '</tr>';
        });
        tbody.innerHTML = html;

        // تحديث العدد الإجمالي
        const totalEl = document.getElementById('auditTotal');
        if (totalEl) totalEl.textContent = 'إجمالي: ' + (data.total_count || 0) + ' سجل';

        // تحديث الترقيم
        TableManager.updatePagination('auditPagination', data, 'logs');
    },

    /**
     * عرض المتابعات
     */
    renderFollowups(data) {
        const tbody = document.querySelector('#followupTable tbody');
        if (!tbody) return;

        if (!data || !data.results || data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state">' +
                '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">' +
                '<polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>' +
                '</svg><p>لا توجد متابعات</p></div></td></tr>';
            return;
        }

        let html = '';
        data.results.forEach((f, i) => {
            const catBadge = f.category === 'URGENT' ? 'badge-danger' : f.category === 'REVIEW' ? 'badge-warning' : f.category === 'APPROVAL' ? 'badge-success' : 'badge-secondary';
            const statusBadge = f.resolved_at ? 'badge-success' : f.is_escalated ? 'badge-danger' : 'badge-warning';
            const statusText = f.resolved_at ? 'مكتملة' : f.is_escalated ? 'مصعّدة' : 'قيد التنفيذ';
            const progressColor = f.progress_percentage >= 80 ? 'green' : f.progress_percentage >= 50 ? 'orange' : 'red';
            const rowNum = (data.page_start || 1) + i;
            const notes = AuditUtils.truncate(f.notes, 60);
            const dateStr = AuditUtils.formatDate(f.due_date, 'short');

            let actionsHtml = '<div class="action-buttons">';
            actionsHtml += '<button class="btn-icon" onclick="AuditApp.viewFollowupDetail(\'' + f.id + '\')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>';
            if (!f.resolved_at) {
                actionsHtml += '<button class="btn-icon success" onclick="AuditApp.resolveFollowup(\'' + f.id + '\')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></button>';
            }
            actionsHtml += '<button class="btn-icon danger" onclick="openDeleteModal(\'' + f.id + '\', \'/audit/api/followups/' + f.id + '/delete/\')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></button>';
            actionsHtml += '</div>';

            html += '<tr>' +
                '<td>' + rowNum + '</td>' +
                '<td><span class="badge badge-info">' + f.entity_type + '</span> <small>' + (f.entity_id || '') + '</small></td>' +
                '<td>' + notes + '</td>' +
                '<td><span class="badge ' + catBadge + '">' + f.category + '</span></td>' +
                '<td><div class="progress-cell"><div class="progress-bar"><div class="progress-fill ' + progressColor + '" style="width:' + f.progress_percentage + '%"></div></div><span class="progress-text">' + f.progress_percentage + '%</span></div></td>' +
                '<td><span class="badge ' + statusBadge + '">' + statusText + '</span></td>' +
                '<td><span class="datetime">' + dateStr + '</span></td>' +
                '<td>' + actionsHtml + '</td>' +
                '</tr>';
        });
        tbody.innerHTML = html;

        TableManager.updatePagination('followupPagination', data, 'followups');
    },

    /**
     * عرض سجل التنفيذ
     */
    renderExecution(data) {
        const tbody = document.querySelector('#executionTable tbody');
        if (!tbody) return;

        if (!data || !data.results || data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9"><div class="empty-state">' +
                '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">' +
                '<polygon points="5 3 19 12 5 21 5 3"/>' +
                '</svg><p>لا توجد سجلات تنفيذ</p></div></td></tr>';
            return;
        }

        let html = '';
        data.results.forEach((e, i) => {
            const actionBadge = e.action === 'CREATED' ? 'badge-success' : e.action === 'COMPLETED' ? 'badge-info' : e.action === 'REJECTED' ? 'badge-danger' : 'badge-secondary';
            const initials = AuditUtils.getInitials(e.actor_name);
            const color = AuditUtils.stringToColor(e.actor_name);
            const rowClass = e.is_delayed ? 'delayed' : '';
            const rowNum = (data.page_start || 1) + i;
            const actorName = AuditUtils.escapeHtml(e.actor_name || '--');
            const notes = AuditUtils.truncate(e.notes, 60);
            const duration = AuditUtils.formatDuration(e.duration_seconds);
            const delayBadge = e.is_delayed ? '<span class="badge badge-danger">⚠️ نعم</span>' : '<span class="badge badge-success">✅ لا</span>';
            const dateStr = AuditUtils.formatDate(e.created_at, 'datetime');

            html += '<tr class="' + rowClass + '">' +
                '<td>' + rowNum + '</td>' +
                '<td><span class="badge badge-info">' + e.entity_type + '</span> <small>' + (e.entity_id || '') + '</small></td>' +
                '<td><span class="badge ' + actionBadge + '">' + e.action + '</span></td>' +
                '<td><div class="user-cell"><span class="user-avatar" style="background:' + color + '">' + initials + '</span><span class="user-name">' + actorName + '</span></div></td>' +
                '<td>' + notes + '</td>' +
                '<td>' + duration + '</td>' +
                '<td>' + delayBadge + '</td>' +
                '<td><span class="datetime">' + dateStr + '</span></td>' +
                '<td><button class="btn-icon" onclick="AuditApp.viewExecutionDetail(\'' + e.id + '\')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></td>' +
                '</tr>';
        });
        tbody.innerHTML = html;

        TableManager.updatePagination('executionPagination', data, 'execution');
    }
};

console.log('🎨 AuditRenderer جاهز!');
