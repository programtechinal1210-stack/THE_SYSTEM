/**
 * audit-utils.js - دوال مساعدة عامة
 * ============================================================
 */

const AuditUtils = {
    /**
     * تنسيق التاريخ بالعربية
     */
    formatDate(dateStr, format = 'full') {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;

        const options = {
            full: { year: 'numeric', month: 'long', day: 'numeric' },
            short: { year: 'numeric', month: '2-digit', day: '2-digit' },
            time: { hour: '2-digit', minute: '2-digit' },
            datetime: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }
        };

        return date.toLocaleDateString('ar-SA', options[format] || options.full);
    },

    /**
     * حساب الوقت النسبي (منذ 5 دقائق، منذ ساعة...)
     */
    timeAgo(dateStr) {
        if (!dateStr) return '';
        const now = new Date();
        const date = new Date(dateStr);
        const seconds = Math.floor((now - date) / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 30) return this.formatDate(dateStr, 'short');
        if (days > 0) return منذ  يوم;
        if (hours > 0) return منذ  ساعة;
        if (minutes > 0) return منذ  دقيقة;
        return 'الآن';
    },

    /**
     * تنسيق حجم الملف
     */
    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },

    /**
     * تنسيق المدة
     */
    formatDuration(seconds) {
        if (!seconds) return '--';
        if (seconds < 60) return seconds + 's';
        if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + (seconds % 60) + 's';
        return Math.floor(seconds / 3600) + 'h ' + Math.floor((seconds % 3600) / 60) + 'm';
    },

    /**
     * تنسيق المدة بالمللي ثانية
     */
    formatDurationMs(ms) {
        if (!ms) return '--';
        if (ms < 1000) return ms + 'ms';
        return this.formatDuration(Math.floor(ms / 1000));
    },

    /**
     * truncate نص
     */
    truncate(text, length = 50) {
        if (!text) return '';
        return text.length > length ? text.substring(0, length) + '...' : text;
    },

    /**
     * الحصول على الأحرف الأولى من الاسم
     */
    getInitials(name) {
        if (!name) return '?';
        const parts = name.trim().split(' ');
        if (parts.length >= 2) {
            return parts[0][0] + parts[parts.length - 1][0];
        }
        return parts[0].substring(0, 2).toUpperCase();
    },

    /**
     * إنشاء لون من نص (للأفاتار)
     */
    stringToColor(str) {
        if (!str) return '#3b82f6';
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        const colors = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899', '#6366f1'];
        return colors[Math.abs(hash) % colors.length];
    },

    /**
     * الهروب من HTML
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * بناء query string من كائن
     */
    buildQueryString(params) {
        const query = Object.entries(params)
            .filter(([_, v]) => v !== null && v !== undefined && v !== '')
            .map(([k, v]) => ${encodeURIComponent(k)}=)
            .join('&');
        return query ? '?' + query : '';
    },

    /**
     * تحديث عنوان URL بدون إعادة تحميل
     */
    updateURL(params) {
        const url = new URL(window.location);
        Object.entries(params).forEach(([key, value]) => {
            if (value) url.searchParams.set(key, value);
            else url.searchParams.delete(key);
        });
        window.history.replaceState({}, '', url);
    },

    /**
     * الحصول على CSRF Token
     */
    getCSRFToken() {
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    },

    /**
     * نسخ إلى الحافظة
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            showToast('📋 تم النسخ إلى الحافظة', 'success');
        } catch (err) {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showToast('📋 تم النسخ إلى الحافظة', 'success');
        }
    }
};

console.log('🔧 AuditUtils جاهز!');
