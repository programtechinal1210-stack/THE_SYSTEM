/* ═══════════════════════════════════════════════════════════════
   📐 GOMS Settings - Fonts
   ═══════════════════════════════════════════════════════════════ */

function buildFontCards() {
    var grid = document.getElementById('fontFamilyGrid');
    if (!grid || typeof AppSettings === 'undefined' || !AppSettings.fonts) return;

    var html = '';
    AppSettings.fonts.forEach(function(f) {
        var isActive = AppSettings.getFontFamily() === f.key;
        html += '<div class="font-card" data-font="' + f.key + '" onclick="setFontFamily(\'' + f.key + '\', this)" style="background:' + (isActive ? 'rgba(168,85,247,0.08)' : 'rgba(255,255,255,0.03)') + ';border:2px solid ' + (isActive ? '#a855f7' : 'var(--border-color)') + ';border-radius:0.8rem;padding:0.8rem;cursor:pointer;transition:all 0.3s;">';
        html += '<div style="font-family:' + f.css + ';font-size:1.1rem;font-weight:700;color:var(--text-primary);">' + f.nameAr + '</div>';
        html += '<div style="font-family:' + f.css + ';font-size:0.75rem;color:var(--text-muted);">' + f.name + '</div>';
        html += '<div style="font-size:0.65rem;color:var(--icon-color);">' + f.type + '</div>';
        if (isActive) html += '<div style="margin-top:0.3rem;padding:0.15rem 0.5rem;border-radius:2rem;font-size:0.6rem;background:rgba(168,85,247,0.2);color:#a855f7;display:inline-block;">مفعل ✓</div>';
        html += '</div>';
    });
    grid.innerHTML = html;
    updateFontPreview();
    updateFontSizeSlider();
}

function setFontFamily(fontKey, el) {
    if (typeof AppSettings !== 'undefined') AppSettings.setFontFamily(fontKey);
    document.querySelectorAll('.font-card').forEach(function(c) {
        c.style.border = '2px solid var(--border-color)'; c.style.background = 'rgba(255,255,255,0.03)';
        var badge = c.querySelector('div:last-child'); if (badge && badge.textContent.includes('مفعل')) badge.remove();
    });
    if (el) {
        el.style.border = '2px solid #a855f7'; el.style.background = 'rgba(168,85,247,0.08)';
        var newBadge = document.createElement('div');
        newBadge.style.cssText = 'margin-top:0.3rem;padding:0.15rem 0.5rem;border-radius:2rem;font-size:0.6rem;background:rgba(168,85,247,0.2);color:#a855f7;display:inline-block;';
        newBadge.textContent = 'مفعل ✓'; el.appendChild(newBadge);
    }
    updateFontPreview();
}

function setFontSizeSlider(value) {
    var v = parseInt(value), size, label;
    if (v <= 25) { size = 'small'; label = 'صغير'; }
    else if (v <= 50) { size = 'medium'; label = 'متوسط'; }
    else if (v <= 75) { size = 'large'; label = 'كبير'; }
    else { size = 'xlarge'; label = 'كبير جداً'; }
    if (typeof AppSettings !== 'undefined') AppSettings.setFontSize(size);
    var labelEl = document.getElementById('fontSizeLabel');
    if (labelEl) labelEl.textContent = label;
    updateFontPreview();
}

function updateFontSizeSlider() {
    if (typeof AppSettings === 'undefined') return;
    var current = AppSettings.getFontSize();
    var map = { small: 15, medium: 50, large: 75, xlarge: 95 };
    var labels = { small: 'صغير', medium: 'متوسط', large: 'كبير', xlarge: 'كبير جداً' };
    var slider = document.getElementById('fontSizeSlider');
    var label = document.getElementById('fontSizeLabel');
    if (slider) slider.value = map[current] || 50;
    if (label) label.textContent = labels[current] || 'متوسط';
}

function updateFontPreview() {
    if (typeof AppSettings === 'undefined' || !AppSettings.fonts) return;
    var f = AppSettings.fonts.find(function(x) { return x.key === AppSettings.getFontFamily(); }) || AppSettings.fonts[0];
    var sizes = { small: '0.8rem', medium: '0.9rem', large: '1.05rem', xlarge: '1.2rem' };
    var base = sizes[AppSettings.getFontSize()] || '0.9rem';
    var preview = document.getElementById('fontPreview');
    if (preview) { preview.style.fontFamily = f.css; preview.style.fontSize = base; }
    ['previewHeading','previewSubtext','previewSample'].forEach(function(id) {
        var el = document.getElementById(id); if (el) el.style.fontFamily = f.css;
    });
}

var fontCheck = setInterval(function() {
    if (typeof AppSettings !== 'undefined' && AppSettings.fonts) {
        clearInterval(fontCheck);
        buildFontCards();
    }
}, 200);
