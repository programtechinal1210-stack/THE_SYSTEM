/**
 * audit-api.js - استدعاءات API
 * ============================================================
 */

const AuditAPI = {
    baseURL: '/audit/api',

    /**
     * استدعاء عام
     */
    async request(endpoint, options = {}) {
        const url = ${this.baseURL};
        const config = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': AuditUtils.getCSRFToken(),
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                throw new Error(HTTP : );
            }
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            showToast('❌ فشل الاتصال بالخادم', 'error');
            throw error;
        }
    },

    /**
     * سجل التدقيق
     */
    async getLogs(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/logs/);
    },

    async getLogDetail(logId) {
        return this.request(/logs//);
    },

    /**
     * المتابعات
     */
    async getFollowups(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/followups/);
    },

    async getFollowupDetail(id) {
        return this.request(/followups//);
    },

    async createFollowup(data) {
        return this.request('/followups/create/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async updateFollowup(id, data) {
        return this.request(/followups//update/, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async resolveFollowup(id) {
        return this.request(/followups//resolve/, {
            method: 'POST'
        });
    },

    async escalateFollowup(id, escalateTo) {
        return this.request(/followups//escalate/, {
            method: 'POST',
            body: JSON.stringify({ escalated_to: escalateTo })
        });
    },

    async deleteFollowup(id) {
        return this.request(/followups//delete/, {
            method: 'DELETE'
        });
    },

    /**
     * سجل التنفيذ
     */
    async getExecution(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/execution/);
    },

    async getExecutionDetail(id) {
        return this.request(/execution//);
    },

    /**
     * الحالات الشاذة
     */
    async getAnomalies(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/anomalies/);
    },

    async getAnomalyDetail(id) {
        return this.request(/anomalies//);
    },

    async investigateAnomaly(id) {
        return this.request(/anomalies//investigate/, {
            method: 'POST'
        });
    },

    async resolveAnomaly(id) {
        return this.request(/anomalies//resolve/, {
            method: 'POST'
        });
    },

    async detectAnomalies() {
        return this.request('/anomalies/detect/', {
            method: 'POST'
        });
    },

    /**
     * التنبيهات
     */
    async getAlerts(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/alerts/);
    },

    async createAlert(data) {
        return this.request('/alerts/create/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async updateAlert(id, data) {
        return this.request(/alerts//update/, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async toggleAlert(id) {
        return this.request(/alerts//toggle/, {
            method: 'POST'
        });
    },

    async deleteAlert(id) {
        return this.request(/alerts//delete/, {
            method: 'DELETE'
        });
    },

    /**
     * التصدير
     */
    async getExports(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/exports/);
    },

    async createExport(data) {
        return this.request('/exports/create/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async downloadExport(id) {
        window.open(${this.baseURL}/exports//download/, '_blank');
    },

    async deleteExport(id) {
        return this.request(/exports//delete/, {
            method: 'DELETE'
        });
    },

    /**
     * الإحصائيات
     */
    async getStats() {
        return this.request('/stats/');
    },

    async getDailyStats(params = {}) {
        const query = AuditUtils.buildQueryString(params);
        return this.request(/stats/daily/);
    }
};

console.log('🔌 AuditAPI جاهز!');
