/**
 * audit-filters.js - إدارة الفلاتر
 * ============================================================
 */

const FilterManager = {
    /**
     * تهيئة الفلاتر
     */
    init() {
        console.log('🔍 FilterManager جاهز!');
    },

    /**
     * جمع قيم الفلاتر من شريط فلتر
     */
    collectFilters(filterBarId) {
        const filterBar = document.getElementById(filterBarId);
        if (!filterBar) return {};

        const filters = {};
        filterBar.querySelectorAll('input, select').forEach(el => {
            if (el.name && el.value) {
                if (el.type === 'checkbox') {
                    if (el.checked) filters[el.name] = el.value;
                } else {
                    filters[el.name] = el.value;
                }
            }
        });
        return filters;
    },

    /**
     * إعادة تعيين الفلاتر
     */
    resetFilters(filterBarId, section) {
        const filterBar = document.getElementById(filterBarId);
        if (!filterBar) return;

        filterBar.querySelectorAll('input, select').forEach(el => {
            if (el.type === 'checkbox') {
                el.checked = false;
            } else {
                el.value = '';
            }
        });

        AuditState.resetFilters(section);
    }
};

// دوال إعادة التعيين لكل قسم
function resetAuditFilters() {
    FilterManager.resetFilters('auditFilterBar', 'logs');
    AuditApp.loadLogs();
}

function resetFollowupFilters() {
    FilterManager.resetFilters('followupFilterBar', 'followups');
    AuditApp.loadFollowups();
}

function resetExecutionFilters() {
    FilterManager.resetFilters('executionFilterBar', 'execution');
    AuditApp.loadExecution();
}

function resetAnomalyFilters() {
    FilterManager.resetFilters('anomalyFilterBar', 'anomalies');
    AuditApp.loadAnomalies();
}

function resetAlertFilters() {
    FilterManager.resetFilters('alertFilterBar', 'alerts');
    AuditApp.loadAlerts();
}

function resetExportFilters() {
    FilterManager.resetFilters('exportFilterBar', 'exports');
    AuditApp.loadExports();
}

console.log('🔍 FilterManager مُعرّف!');
