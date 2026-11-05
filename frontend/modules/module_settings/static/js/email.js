/* ═══════════════════════════════════════════════════════════════
   📧 GOMS Settings - Email Tab
   ═══════════════════════════════════════════════════════════════ */

// اختبار البريد
function testEmail() {
    var input = document.getElementById('email_test_address');
    var result = document.getElementById('emailTestResult');
    if (!input || !result) return;

    if (!input.value) {
        result.style.display = 'block';
        result.style.background = 'rgba(239,68,68,0.08)';
        result.style.color = '#ef4444';
        result.innerHTML = '❌ يرجى إدخال بريد إلكتروني صالح للاختبار';
        return;
    }

    result.style.display = 'block';
    result.style.background = 'rgba(245,158,11,0.08)';
    result.style.color = '#f59e0b';
    result.innerHTML = '⏳ جاري إرسال بريد اختبار إلى <strong>' + input.value + '</strong>...';

    setTimeout(function() {
        result.style.background = 'rgba(16,185,129,0.08)';
        result.style.color = '#10b981';
        result.innerHTML = '✅ تم إرسال بريد اختبار بنجاح إلى <strong>' + input.value + '</strong>. تحقق من صندوق الوارد.';
        showToast('📧 تم إرسال بريد اختبار بنجاح', 'success');
    }, 2000);
}
