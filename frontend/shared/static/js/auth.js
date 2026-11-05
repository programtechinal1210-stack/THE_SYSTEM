// ═══════════════════════════════════════════════════════════════
// 🔐 سكربتات صفحات المصادقة المشتركة
// ═══════════════════════════════════════════════════════════════

(function() {
    'use strict';
    
    document.addEventListener('DOMContentLoaded', function() {
        
        // ═══════════════════════════════════════════════════
        // إظهار/إخفاء كلمة المرور
        // ═══════════════════════════════════════════════════
        document.querySelectorAll('.toggle-password').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const wrapper = this.closest('.password-wrapper');
                const input = wrapper ? wrapper.querySelector('input') : null;
                const icon = this.querySelector('i');
                
                if (!input || !icon) return;
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                    this.setAttribute('aria-label', 'إخفاء كلمة المرور');
                } else {
                    input.type = 'password';
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                    this.setAttribute('aria-label', 'إظهار كلمة المرور');
                }
            });
        });
        
        // ═══════════════════════════════════════════════════
        // تأثير تحميل على زر الإرسال
        // ═══════════════════════════════════════════════════
        document.querySelectorAll('.auth-form').forEach(function(form) {
            form.addEventListener('submit', function() {
                const submitBtn = this.querySelector('.btn-auth');
                if (submitBtn && !submitBtn.classList.contains('loading')) {
                    submitBtn.classList.add('loading');
                    submitBtn.innerHTML = '<span class="spinner"></span> جاري المعالجة...';
                    submitBtn.disabled = true;
                }
            });
        });
        
        // ═══════════════════════════════════════════════════
        // إزالة التحميل عند الرجوع للصفحة
        // ═══════════════════════════════════════════════════
        window.addEventListener('pageshow', function() {
            document.querySelectorAll('.btn-auth.loading').forEach(function(btn) {
                btn.classList.remove('loading');
                btn.innerHTML = '<i class="fas fa-arrow-left btn-arrow"></i> تسجيل الدخول';
                btn.disabled = false;
            });
        });
        
        // ═══════════════════════════════════════════════════
        // إزالة كلاس الخطأ عند الكتابة
        // ═══════════════════════════════════════════════════
        document.querySelectorAll('.input-wrapper input').forEach(function(input) {
            input.addEventListener('input', function() {
                if (this.value.trim()) {
                    this.style.borderColor = '';
                }
            });
        });
        
    });
    
})();

// Spinner animation style
// Spinner animation style
var spinnerStyle = document.createElement('style');
spinnerStyle.textContent = `
    .spinner {
        width: 22px;
        height: 22px;
        border: 2.5px solid rgba(255, 255, 255, 0.3);
        border-top-color: #ffffff;
        border-radius: 50%;
        animation: authSpinner 0.7s linear infinite;
    }
    @keyframes authSpinner {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(spinnerStyle);

console.log('🔐 Auth scripts ready');