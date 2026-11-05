// ═══════════════════════════════════════════════════════════════
// 🔐 سكربتات المصادقة - GOMS v2.0
// ═══════════════════════════════════════════════════════════════

// إظهار/إخفاء كلمة المرور
function togglePassword(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    
    if (!input || !icon) return;
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// التحقق من تطابق كلمة المرور (لصفحة التسجيل)
function validatePasswordMatch(passwordId, confirmId, errorId) {
    const password = document.getElementById(passwordId);
    const confirm = document.getElementById(confirmId);
    const error = document.getElementById(errorId);
    
    if (!password || !confirm || !error) return;
    
    confirm.addEventListener('input', function() {
        if (this.value !== password.value) {
            error.textContent = 'كلمة المرور غير متطابقة';
            error.style.display = 'flex';
        } else {
            error.textContent = '';
            error.style.display = 'none';
        }
    });
}

// إزالة الـ loading عند الرجوع للصفحة
window.addEventListener('pageshow', function() {
    const submitBtn = document.querySelector('.login-btn');
    if (submitBtn && submitBtn.classList.contains('loading')) {
        submitBtn.classList.remove('loading');
        submitBtn.innerHTML = '<i class="fas fa-arrow-left btn-arrow"></i> تسجيل الدخول';
        submitBtn.disabled = false;
    }
});

console.log('🔐 GOMS Auth Ready - Glass Morphism Design');
