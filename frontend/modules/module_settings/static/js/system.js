/* ═══════════════════════════════════════════════════════════════
   🖥️ GOMS Settings - System Tab
   ═══════════════════════════════════════════════════════════════ */

// إعادة تشغيل النظام
function restartSystem() {
    if (confirm('⚠️ تحذير: إعادة تشغيل النظام ستؤدي إلى إيقاف جميع الخدمات مؤقتاً.\n\nالمدة المتوقعة: 30-60 ثانية.\n\nهل تريد المتابعة؟')) {
        showToast('🔄 جاري إعادة تشغيل النظام... سيتم إعادة الاتصال تلقائياً', 'warning');
        var countdown = 5;
        var interval = setInterval(function() {
            if (countdown <= 0) {
                clearInterval(interval);
                location.reload();
            }
            countdown--;
        }, 1000);
    }
}

// مسح الكاش
function clearCache() {
    if (confirm('🧹 هل تريد مسح الكاش؟\n\nسيؤدي ذلك إلى إعادة تحميل جميع البيانات من قاعدة البيانات.')) {
        showToast('🧹 جاري مسح الكاش...', 'warning');
        setTimeout(function() {
            showToast('✅ تم مسح الكاش بنجاح', 'success');
        }, 1500);
    }
}

// مسح السجلات
function clearLogs() {
    if (confirm('🗑️ هل تريد مسح سجل النظام؟\n\nلا يمكن استعادة السجلات بعد المسح.')) {
        document.getElementById('systemLogs').innerHTML = '<div class="log-line log-info">[2026-01-20 14:35:00] ℹ️ SYSTEM | تم مسح السجل بواسطة المسؤول</div>';
        showToast('🗑️ تم مسح سجل النظام', 'warning');
    }
}

// فلترة السجلات
function filterLogs() {
    var filter = document.getElementById('logFilter').value;
    var logs = document.querySelectorAll('#systemLogs .log-line');
    logs.forEach(function(log) {
        if (filter === 'all') {
            log.style.display = '';
        } else if (filter === 'success' && log.classList.contains('log-success')) {
            log.style.display = '';
        } else if (filter === 'info' && log.classList.contains('log-info')) {
            log.style.display = '';
        } else if (filter === 'warning' && log.classList.contains('log-warning')) {
            log.style.display = '';
        } else if (filter === 'error' && log.classList.contains('log-error')) {
            log.style.display = '';
        } else {
            log.style.display = 'none';
        }
    });
}
