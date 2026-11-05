// ═══════════════════════════════════════════════════════════════
// 🌓 Theme Manager - Light/Dark Mode
// ═══════════════════════════════════════════════════════════════

(function() {
    'use strict';
    
    const THEME_KEY = 'goms_theme';
    
    const ThemeManager = {
        
        // الحصول على السمة المحفوظة
        getSavedTheme: function() {
            return localStorage.getItem(THEME_KEY) || 'dark';
        },
        
        // حفظ السمة
        saveTheme: function(theme) {
            localStorage.setItem(THEME_KEY, theme);
        },
        
        // تطبيق السمة
        applyTheme: function(theme) {
            const html = document.documentElement;
            
            if (theme === 'light') {
                html.setAttribute('data-theme', 'light');
            } else {
                html.removeAttribute('data-theme');
            }
            
            this.updateIcons(theme);
        },
        
        // تحديث أيقونات أزرار التبديل
        updateIcons: function(theme) {
            const isLight = theme === 'light';
            
            document.querySelectorAll('.theme-toggle').forEach(function(btn) {
                const icon = btn.querySelector('i');
                if (!icon) return;
                
                if (isLight) {
                    // الوضع الفاتح - إظهار أيقونة القمر
                    icon.className = icon.className.replace(/fa-sun/g, 'fa-moon');
                    btn.setAttribute('title', 'تفعيل الوضع الداكن');
                    btn.setAttribute('aria-label', 'تفعيل الوضع الداكن');
                } else {
                    // الوضع الداكن - إظهار أيقونة الشمس
                    icon.className = icon.className.replace(/fa-moon/g, 'fa-sun');
                    btn.setAttribute('title', 'تفعيل الوضع الفاتح');
                    btn.setAttribute('aria-label', 'تفعيل الوضع الفاتح');
                }
            });
        },
        
        // تبديل السمة
        toggle: function() {
            const currentTheme = this.getCurrentTheme();
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            this.saveTheme(newTheme);
            this.applyTheme(newTheme);
            return newTheme;
        },
        
        // الحصول على السمة الحالية
        getCurrentTheme: function() {
            return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        },
        
        // تهيئة
        init: function() {
            const savedTheme = this.getSavedTheme();
            this.applyTheme(savedTheme);
            
            // ربط أزرار التبديل
            document.addEventListener('DOMContentLoaded', function() {
                document.querySelectorAll('.theme-toggle').forEach(function(btn) {
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        ThemeManager.toggle();
                    });
                });
            });
            
            // اختصار Ctrl+Shift+D
            document.addEventListener('keydown', function(e) {
                if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                    e.preventDefault();
                    ThemeManager.toggle();
                }
            });
            
            console.log('🌓 Theme Manager Ready - Current: ' + savedTheme);
        }
    };
    
    // تهيئة فورية
    ThemeManager.init();
    
    // تصدير للاستخدام العام
    window.ThemeManager = ThemeManager;
    
})();
