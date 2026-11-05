// ═══════════════════════════════════════════════════════════════
// 🚀 السكربتات الرئيسية - GOMS v2.0
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    console.log('🏛️ GOMS v2.0 - Initialized');

    // ═══════════════════════════════════════════════════
    // تهيئة المكونات
    // ═══════════════════════════════════════════════════

    initTooltips();
    initDropdowns();
    initScrollAnimations();
    handleHTMXEvents();
});

// ═══════════════════════════════════════════════════════════════
// Tooltips
// ═══════════════════════════════════════════════════════════════

function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', function(e) {
            const tooltip = document.createElement('div');
            tooltip.className = 'fixed bg-gray-900 text-white text-xs px-3 py-1.5 rounded-lg shadow-lg z-[9999] pointer-events-none animate-fade-in';
            tooltip.textContent = this.getAttribute('data-tooltip');

            document.body.appendChild(tooltip);

            const rect = this.getBoundingClientRect();
            tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';
            tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';

            this.addEventListener('mouseleave', () => {
                tooltip.remove();
            }, { once: true });
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// Dropdowns - إغلاق عند النقر خارجها
// ═══════════════════════════════════════════════════════════════

function initDropdowns() {
    document.addEventListener('click', function(e) {
        const isDropdown = e.target.closest('[data-dropdown]');
        const isDropdownContent = e.target.closest('.dropdown-content');

        if (!isDropdown && !isDropdownContent) {
            document.querySelectorAll('.dropdown-content.show').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// حركات الظهور عند التمرير
// ═══════════════════════════════════════════════════════════════

function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

// ═══════════════════════════════════════════════════════════════
// HTMX Events
// ═══════════════════════════════════════════════════════════════

function handleHTMXEvents() {
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        showLoader();
    });

    document.body.addEventListener('htmx:afterRequest', function(evt) {
        hideLoader();
    });

    document.body.addEventListener('htmx:responseError', function(evt) {
        hideLoader();
        if (typeof showToast === 'function') showToast('حدث خطأ في الاتصال بالخادم', 'error');
    });
}

// ═══════════════════════════════════════════════════════════════
// أدوات مساعدة
// ═══════════════════════════════════════════════════════════════

// تنسيق التاريخ
function formatDate(dateString, format = 'ar-SA') {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString(format, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// تنسيق الوقت النسبي
function timeAgo(dateString) {
    const now = new Date();
    const date = new Date(dateString);
    const seconds = Math.floor((now - date) / 1000);

    const intervals = [
        { label: 'سنة', seconds: 31536000 },
        { label: 'شهر', seconds: 2592000 },
        { label: 'أسبوع', seconds: 604800 },
        { label: 'يوم', seconds: 86400 },
        { label: 'ساعة', seconds: 3600 },
        { label: 'دقيقة', seconds: 60 }
    ];

    for (const interval of intervals) {
        const count = Math.floor(seconds / interval.seconds);
        if (count >= 1) {
            return 'منذ ' + count + ' ' + interval.label;
        }
    }

    return 'الآن';
}

// تحويل النص إلى slug
function slugify(text) {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, '-')
        .replace(/[^\w\-]+/g, '')
        .replace(/\-\-+/g, '-');
}

// تأخير التنفيذ
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

console.log('✨ GOMS v2.0 Ready');
