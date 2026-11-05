/**
 * audit-tabs.js - إدارة التبويبات
 * ============================================================
 */

const TabManager = {
    /**
     * تهيئة التبويبات
     */
    init() {
        document.querySelectorAll('.tabs-modern .tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = tab.dataset.tab;
                this.switchTo(tabName);
            });
        });

        // تفعيل التبويب من URL hash
        const hash = window.location.hash.replace('#tab-', '');
        if (hash && document.querySelector(.tab[data-tab=""])) {
            this.switchTo(hash);
        }

        console.log('📑 TabManager جاهز!');
    },

    /**
     * التبديل إلى تبويب
     */
    switchTo(tabName) {
        // تحديث الأزرار
        document.querySelectorAll('.tabs-modern .tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tabName);
        });

        // تحديث المحتوى
        document.querySelectorAll('.tab-content').forEach(c => {
            c.classList.toggle('active', c.id === 	ab-);
        });

        // تحديث الحالة
        AuditState.activeTab = tabName;

        // تحديث URL hash
        window.location.hash = 	ab-;

        // تحميل البيانات إذا لزم
        this.loadTabData(tabName);
    },

    /**
     * تحميل بيانات التبويب
     */
    loadTabData(tabName) {
        switch (tabName) {
            case 'dashboard':
                AuditApp.loadStats();
                AuditApp.loadRecentActivities();
                break;
            case 'logs':
                AuditApp.loadLogs();
                break;
            case 'followups':
                AuditApp.loadFollowups();
                break;
            case 'execution':
                AuditApp.loadExecution();
                break;
            case 'anomalies':
                AuditApp.loadAnomalies();
                break;
            case 'alerts':
                AuditApp.loadAlerts();
                break;
            case 'exports':
                AuditApp.loadExports();
                break;
        }
    },

    /**
     * تحديث عداد التبويب
     */
    updateBadge(tabName, count) {
        const badge = document.getElementById(${tabName}Count);
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        }
    }
};

console.log('📑 TabManager مُعرّف!');
