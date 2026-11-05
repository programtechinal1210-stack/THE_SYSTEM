from django.shortcuts import render

def _ude_palette_enabled():
    import json
    from pathlib import Path
    from django.conf import settings
    try:
        flag_path = Path(settings.BASE_DIR) / 'shared' / 'static' / 'ude' / 'ude-color-palettes-v1.0-feature-flags.json'
        flag = json.loads(flag_path.read_text(encoding='utf-8'))
        return bool(flag.get('default_enabled') is True and flag.get('production_load') is False)
    except (OSError, ValueError, TypeError):
        return False


def settings_index(request):
    """الصفحة الرئيسية للإعدادات"""
    context = {
        'page_title': 'الإعدادات',
        'active': 'settings',
        'ude_color_palettes_enabled': _ude_palette_enabled(),
    }
    return render(request, 'settings/index.html', context)
