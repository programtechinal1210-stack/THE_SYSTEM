// إعادة ضبط localStorage
localStorage.removeItem('goms_theme');
localStorage.removeItem('goms_color_package');
localStorage.removeItem('goms_font_size');
localStorage.removeItem('goms_density');
localStorage.removeItem('goms_bg');
localStorage.removeItem('goms_primary_color');
document.documentElement.removeAttribute('data-theme');
document.documentElement.setAttribute('data-theme', 'light');
location.reload();
