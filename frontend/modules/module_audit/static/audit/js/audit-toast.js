/**
 * audit-toast.js - نظام الإشعارات (مستقل عن _toast.html)
 * ============================================================
 */

const Toast = {
    container: null,
    defaultDuration: 5000,

    init() {
        this.container = document.getElementById('toastContainer');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toastContainer';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', options = {}) {
        if (!this.container) this.init();

        const { duration = this.defaultDuration, title = '' } = options;

        const icons = {
            success: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
            error: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
            warning: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
            info: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        };

        const titles = {
            success: title || '✅ تم بنجاح',
            error: title || '❌ خطأ',
            warning: title || '⚠️ تنبيه',
            info: title || 'ℹ️ معلومات'
        };

        const toast = document.createElement('div');
        toast.className = 	oast toast-;
        toast.innerHTML = 
            <div class="toast-icon"></div>
            <div class="toast-body">
                <div class="toast-title"></div>
                <div class="toast-message"></div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        ;

        this.container.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);

        return toast;
    },

    success(message, title = '') { return this.show(message, 'success', { title }); },
    error(message, title = '') { return this.show(message, 'error', { title, duration: 7000 }); },
    warning(message, title = '') { return this.show(message, 'warning', { title }); },
    info(message, title = '') { return this.show(message, 'info', { title }); }
};

// دوال عامة
function showToast(message, type = 'info', title = '') {
    Toast.show(message, type, { title });
}

function showSuccessToast(message, title = '') { Toast.success(message, title); }
function showErrorToast(message, title = '') { Toast.error(message, title); }
function showWarningToast(message, title = '') { Toast.warning(message, title); }
function showInfoToast(message, title = '') { Toast.info(message, title); }

console.log('🍞 Toast جاهز!');
