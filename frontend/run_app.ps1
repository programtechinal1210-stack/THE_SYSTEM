# ============================================================
# تشغيل GOMS.exe من مجلد dist
# ============================================================

 = "dist\GOMS.exe"

if (Test-Path ) {
    Write-Host "🏛️ تشغيل نظام إدارة المكتب الحكومي" -ForegroundColor Cyan
    Write-Host "🚀 جاري تشغيل GOMS.exe..." -ForegroundColor Green
    Start-Process -FilePath 
    Write-Host "✅ تم تشغيل التطبيق!" -ForegroundColor Green
    Write-Host "🌐 الخادم يعمل على: http://127.0.0.1:8000" -ForegroundColor Cyan
} else {
    Write-Host "❌ الملف غير موجود!" -ForegroundColor Red
}
