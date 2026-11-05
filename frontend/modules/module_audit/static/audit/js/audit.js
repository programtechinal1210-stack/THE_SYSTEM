/**
 * audit.js - التطبيق الرئيسي لوحدة التدقيق
 * ============================================================
 */

const AuditApp = {
    /**
     * تهيئة التطبيق
     */
    init() {
        Toast.init();
        TabManager.init();
        FilterManager.init();
        ModalManager.init();

        // تحميل الإحصائيات عند التحميل
        this.loadStats();

        // تحديث التاريخ
        this.updateDate();

        console.log('🔍 AuditApp جاهز!');
    },

    /**
     * تحديث التاريخ في رأس الصفحة
     */
    updateDate() {
        const el = document.getElementById('currentDate');
        if (el) {
            el.textContent = new Date().toLocaleDateString('ar-SA', {
                year: 'numeric', month: 'long', day: 'numeric'
            });
        }
    },

    /**
     * تحميل الإحصائيات
     */
    async loadStats() {
        try {
            // محاولة API أولاً
            const stats = await AuditAPI.getStats();
            AuditState.stats = stats;
            AuditRenderer.renderStats(stats);
        } catch (error) {
            // استخدام بيانات وهمية عند الفشل
            console.warn('استخدام بيانات إحصائية وهمية');
            AuditRenderer.renderStats({
                total_actions: 1284,
                unique_users: 18,
                pending_followups: 7,
                open_anomalies: 2,
                avg_duration_ms: 45,
                total_exports: 34
            });
        }
    },

    /**
     * تحميل آخر النشاطات
     */
    async loadRecentActivities() {
        try {
            const data = await AuditAPI.getLogs({ page_size: 10 });
            // عرض في التايملاين
            const container = document.getElementById('recentActivities');
            if (container && data.results) {
                container.innerHTML = data.results.map(a => 
                    <div class="timeline-item">
                        <div class="timeline-dot "></div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <span class="user-name"></span>
                                <span class="time-badge"></span>
                            </div>
                            <div class="action-text"></div>
                        </div>
                    </div>
                ).join('');
            }
        } catch (error) {
            console.warn('استخدام بيانات نشاطات وهمية');
        }
    },

    /**
     * تحميل سجل التدقيق
     */
    async loadLogs() {
        const params = AuditState.getQueryParams('logs');
        TableManager.showLoading('auditTable');
        try {
            const data = await AuditAPI.getLogs(params);
            AuditState.pagination.logs = data;
            AuditRenderer.renderLogs(data);
        } catch (error) {
            // بيانات وهمية
            AuditRenderer.renderLogs({
                results: MockData.logs,
                total_count: MockData.logs.length,
                current_page: 1,
                total_pages: 1
            });
        }
    },

    /**
     * تحميل المتابعات
     */
    async loadFollowups() {
        const params = AuditState.getQueryParams('followups');
        TableManager.showLoading('followupTable');
        try {
            const data = await AuditAPI.getFollowups(params);
            AuditState.pagination.followups = data;
            AuditRenderer.renderFollowups(data);
        } catch (error) {
            AuditRenderer.renderFollowups({
                results: MockData.followups,
                total_count: MockData.followups.length,
                current_page: 1,
                total_pages: 1
            });
        }
    },

    /**
     * تحميل سجل التنفيذ
     */
    async loadExecution() {
        const params = AuditState.getQueryParams('execution');
        TableManager.showLoading('executionTable');
        try {
            const data = await AuditAPI.getExecution(params);
            AuditState.pagination.execution = data;
            AuditRenderer.renderExecution(data);
        } catch (error) {
            AuditRenderer.renderExecution({
                results: MockData.execution,
                total_count: MockData.execution.length,
                current_page: 1,
                total_pages: 1
            });
        }
    },

    /**
     * تحميل الحالات الشاذة
     */
    async loadAnomalies() {
        try {
            const data = await AuditAPI.getAnomalies(AuditState.getQueryParams('anomalies'));
            AuditState.pagination.anomalies = data;
            const container = document.getElementById('anomaliesContainer');
            if (container && data.results) {
                container.innerHTML = data.results.map(a => 
                    <div class="anomaly-card ">
                        <div class="anomaly-header">
                            <span class="badge "></span>
                            <span class="anomaly-date"></span>
                        </div>
                        <h4 class="anomaly-title"></h4>
                        <p class="anomaly-description"></p>
                        <div class="anomaly-actions">
                            <button class="btn btn-sm btn-primary" onclick="AuditAPI.investigateAnomaly('').then(() => AuditApp.loadAnomalies())">تحقيق</button>
                            <button class="btn btn-sm btn-success" onclick="AuditAPI.resolveAnomaly('').then(() => AuditApp.loadAnomalies())">حل</button>
                        </div>
                    </div>
                ).join('');
            }
        } catch (error) {
            console.warn('لا توجد حالات شاذة');
        }
    },

    /**
     * تحميل التنبيهات
     */
    async loadAlerts() {
        try {
            const data = await AuditAPI.getAlerts(AuditState.getQueryParams('alerts'));
            AuditState.pagination.alerts = data;
        } catch (error) {
            console.warn('استخدام بيانات تنبيهات وهمية');
        }
    },

    /**
     * تحميل التصدير
     */
    async loadExports() {
        try {
            const data = await AuditAPI.getExports(AuditState.getQueryParams('exports'));
            AuditState.pagination.exports = data;
        } catch (error) {
            console.warn('استخدام بيانات تصدير وهمية');
        }
    },

    /**
     * الانتقال إلى صفحة
     */
    goToPage(section, page) {
        AuditState.setPage(section, page);
        switch (section) {
            case 'logs': this.loadLogs(); break;
            case 'followups': this.loadFollowups(); break;
            case 'execution': this.loadExecution(); break;
            case 'anomalies': this.loadAnomalies(); break;
            case 'alerts': this.loadAlerts(); break;
            case 'exports': this.loadExports(); break;
        }
    },

    /**
     * عرض تفاصيل سجل التدقيق
     */
    async viewLogDetail(logId) {
        try {
            const log = await AuditAPI.getLogDetail(logId);
            // يمكن فتح مودال أو الانتقال لصفحة التفاصيل
            showInfoToast(سجل #);
        } catch (error) {
            showErrorToast('فشل تحميل التفاصيل');
        }
    },

    /**
     * عرض تفاصيل متابعة
     */
    viewFollowupDetail(id) {
        openModal('followupDetailModal');
    },

    /**
     * إكمال متابعة
     */
    async resolveFollowup(id) {
        try {
            await AuditAPI.resolveFollowup(id);
            showSuccessToast('تم إكمال المتابعة بنجاح');
            this.loadFollowups();
        } catch (error) {
            showErrorToast('فشل إكمال المتابعة');
        }
    },

    /**
     * عرض تفاصيل تنفيذ
     */
    viewExecutionDetail(id) {
        showInfoToast(تنفيذ #);
    }
};

// التهيئة عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
    AuditApp.init();
});

console.log('🚀 نظام التدقيق والمتابعة جاهز!');
