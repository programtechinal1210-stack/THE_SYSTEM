// ═══════════════════════════════════════════════════════════════
// 🎯 التفاعلات المتقدمة - GOMS v2.0
// ═══════════════════════════════════════════════════════════════

// تأثير Ripple على الأزرار
document.addEventListener('click', function(e) {
    const rippleElement = e.target.closest('.ripple-effect');
    if (!rippleElement) return;
    
    const ripple = document.createElement('span');
    ripple.classList.add('ripple');
    
    const rect = rippleElement.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    
    rippleElement.appendChild(ripple);
    
    ripple.addEventListener('animationend', () => {
        ripple.remove();
    });
});

// تأثيرات الظهور عند التمرير
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

// Smooth Scroll للروابط الداخلية
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// تحسين حقول البحث
document.querySelectorAll('.search-bar input').forEach(input => {
    const clearBtn = input.parentElement.querySelector('.search-clear');
    
    input.addEventListener('input', () => {
        if (clearBtn) {
            clearBtn.style.display = input.value ? 'block' : 'none';
        }
    });
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            input.value = '';
            clearBtn.style.display = 'none';
            input.focus();
            input.dispatchEvent(new Event('input'));
        });
    }
});

// تحسين النماذج
document.querySelectorAll('.form-input').forEach(input => {
    input.addEventListener('focus', () => {
        input.closest('.form-group')?.classList.add('focused');
    });
    
    input.addEventListener('blur', () => {
        input.closest('.form-group')?.classList.remove('focused');
        
        // التحقق من الصحة
        if (input.hasAttribute('required') && !input.value.trim()) {
            input.classList.add('error');
        } else {
            input.classList.remove('error');
        }
    });
});

// Modal Manager
class ModalManager {
    static open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        // تركيز أول حقل إدخال
        const firstInput = modal.querySelector('input, textarea, select');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
    
    static close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    static init() {
        // إغلاق بالنقر على الخلفية
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', function(e) {
                if (e.target === this) {
                    this.classList.remove('active');
                    document.body.style.overflow = '';
                }
            });
        });
        
        // إغلاق بزر Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const activeModal = document.querySelector('.modal-overlay.active');
                if (activeModal) {
                    activeModal.classList.remove('active');
                    document.body.style.overflow = '';
                }
            }
        });
    }
}

// تهيئة المودالات
document.addEventListener('DOMContentLoaded', () => {
    ModalManager.init();
});

// Tabs Manager
class TabsManager {
    static init(containerSelector = '.tabs-container') {
        document.querySelectorAll(containerSelector).forEach(container => {
            const tabs = container.querySelectorAll('.tab-item');
            const panes = document.querySelectorAll(
                container.getAttribute('data-tabs-target') 
                    ? # .tab-pane
                    : '.tab-pane'
            );
            
            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const target = tab.getAttribute('data-tab');
                    
                    // إزالة active من الكل
                    tabs.forEach(t => t.classList.remove('active'));
                    panes.forEach(p => p.classList.remove('active'));
                    
                    // تفعيل المحدد
                    tab.classList.add('active');
                    const targetPane = document.querySelector(target);
                    if (targetPane) {
                        targetPane.classList.add('active');
                    }
                });
            });
        });
    }
}

// تهيئة التبويبات
document.addEventListener('DOMContentLoaded', () => {
    TabsManager.init();
});

// Tooltip
document.querySelectorAll('[data-tooltip]').forEach(element => {
    element.addEventListener('mouseenter', function(e) {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
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

// تحسين الجداول - تحديد الصف
document.querySelectorAll('.data-table tbody tr').forEach(row => {
    row.addEventListener('click', function() {
        const table = this.closest('.data-table');
        table.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));
        this.classList.add('selected');
    });
});

console.log('✨ GOMS Interactions Ready');
