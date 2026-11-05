// ═══════════════════════════════════════════════════════════════
// 📊 سكربتات لوحة التحكم
// ═══════════════════════════════════════════════════════════════

(function() {
    'use strict';
    
    document.addEventListener('DOMContentLoaded', function() {
        
        // ═══════════════════════════════════════════════════
        // زر الرجوع للأعلى
        // ═══════════════════════════════════════════════════
        const backToTop = document.getElementById('backToTop');
        
        if (backToTop) {
            window.addEventListener('scroll', function() {
                if (window.scrollY > 300) {
                    backToTop.classList.add('visible');
                } else {
                    backToTop.classList.remove('visible');
                }
            });
            
            backToTop.addEventListener('click', function() {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
        
        // ═══════════════════════════════════════════════════
        // تأثير Ripple على الأزرار
        // ═══════════════════════════════════════════════════
        document.querySelectorAll('.btn, .btn-icon, .header-icon-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                ripple.classList.add('ripple');
                
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
                ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
                
                this.appendChild(ripple);
                
                ripple.addEventListener('animationend', function() {
                    ripple.remove();
                });
            });
        });
        
        // ═══════════════════════════════════════════════════
        // تأثير الظهور التدريجي
        // ═══════════════════════════════════════════════════
        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, { threshold: 0.1 });
        
        document.querySelectorAll('.fade-in').forEach(function(el) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'all 0.6s ease';
            observer.observe(el);
        });
        
    });
    
    // ═══════════════════════════════════════════════════════
    // تبديل حالة المهمة
    // ═══════════════════════════════════════════════════════
    window.toggleTask = function(checkbox) {
        checkbox.classList.toggle('checked');
        const taskText = checkbox.nextElementSibling;
        if (taskText) {
            taskText.classList.toggle('done');
        }
    };
    
})();

console.log('📊 Dashboard Ready');
