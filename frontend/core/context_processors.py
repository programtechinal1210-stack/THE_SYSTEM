from .navigation import navigation_context
from shared.services.api_client import ApiClient, ApiException
from .ude_v2_flags import use_shared_shell
from .ude_v2_components import use_shared_components


def platform_context(request):
    try:
        branding = ApiClient().get('/settings-center/branding')
    except ApiException:
        branding = {}
    if not request.session.get("access_token"):
        return {**navigation_context(request, []), "core_branding": branding,
                "ude_v2_shared_shell_enabled": False}
    if not hasattr(request, "core_modules"):
        try:
            client = ApiClient(token=request.session["access_token"])
            request.core_modules = client.get("/modules")
            request.core_identity = client.get("/auth/me")
        except ApiException:
            request.core_modules, request.core_identity = [], {}
    modules = [dict(m, active=request.path == m["href"] or (m["code"] == "users" and request.path.startswith("/users/") and request.path != "/users/profile/")) for m in request.core_modules]
    # Effective preferences are user-scoped Core data.  Keep the authenticated
    # client here so every page receives the same identity values as the
    # settings center instead of falling back to the light defaults.
    core_client = ApiClient(token=request.session["access_token"])
    try:
        preferences = {item["setting_key"]: item["value"] for item in core_client.get("/user-settings/effective")}
    except ApiException:
        preferences = {}
    # Read the existing scoped Core settings contract as well: the compact
    # user-settings endpoint intentionally exposes only a subset of settings.
    try:
        scoped_settings = core_client.get('/settings-center', {'scope': 'user'}).get('items', [])
    except ApiException:
        scoped_settings = []
    scoped_values = {item.get('key'): item.get('value') for item in scoped_settings}
    scoped_sources = {item.get('key'): item.get('source') for item in scoped_settings}
    theme = preferences.get("theme", "light")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from django.utils import timezone
    try: timezone.activate(ZoneInfo(preferences.get('timezone','Asia/Riyadh')))
    except (ZoneInfoNotFoundError, ValueError): timezone.deactivate()
    core_theme = theme if theme in ("light", "dark", "system") else "light"
    font_family = scoped_values.get('core.ude.font_family', 'Tajawal')
    if font_family not in ('Tajawal', 'Almarai', 'IBM Plex Sans Arabic'):
        font_family = 'Tajawal'
    custom_colors = scoped_values.get('core.ude.custom_colors', {})
    if not isinstance(custom_colors, dict):
        custom_colors = {}
    import re
    custom_colors = {key: value for key, value in custom_colors.items()
                     if key in ('primary', 'secondary', 'accent', 'surface', 'text')
                     and isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value)}
    if not ({'surface', 'text'} <= custom_colors.keys()):
        custom_colors.pop('surface', None)
        custom_colors.pop('text', None)
    palette = scoped_values.get('core.ude.palette', 'navy')
    if palette not in ('navy', 'royal-blue', 'emerald', 'modern-purple', 'turquoise', 'burgundy'):
        palette = 'navy'
    # A stored scoped palette is a personal/institutional identity choice.
    # When the catalog default is still in effect, preserve Core's current
    # primary-color setting as the institutional default.
    core_palette = palette if scoped_sources.get('core.ude.palette') != 'default' else ''
    font_size = preferences.get('font_size', 16)
    if not isinstance(font_size, int) or isinstance(font_size, bool) or not 12 <= font_size <= 24:
        font_size = 16
    font_weight = scoped_values.get('core.font_weight', '400')
    try:
        font_weight = str(int(font_weight))
    except (TypeError, ValueError):
        font_weight = '400'
    if font_weight not in ('400', '500', '600', '700', '800', '900'):
        font_weight = '400'
    weight_profiles = {
        '400': {'normal': '400', 'medium': '500', 'semibold': '600', 'bold': '700', 'extra': '800', 'black': '900'},
        '500': {'normal': '500', 'medium': '500', 'semibold': '600', 'bold': '700', 'extra': '800', 'black': '900'},
        '600': {'normal': '600', 'medium': '600', 'semibold': '600', 'bold': '700', 'extra': '800', 'black': '900'},
        '700': {'normal': '700', 'medium': '700', 'semibold': '700', 'bold': '800', 'extra': '900', 'black': '900'},
        '800': {'normal': '800', 'medium': '800', 'semibold': '800', 'bold': '800', 'extra': '900', 'black': '900'},
        '900': {'normal': '900', 'medium': '900', 'semibold': '900', 'bold': '900', 'extra': '900', 'black': '900'},
    }[font_weight]
    radius_profiles = {
        'compact': {'sm': '4px', 'md': '6px', 'lg': '8px'},
        'balanced': {'sm': '6px', 'md': '12px', 'lg': '16px'},
        'rounded': {'sm': '10px', 'md': '16px', 'lg': '24px'},
    }
    core_radius = radius_profiles.get(scoped_values.get('core.ude.radius'), radius_profiles['balanced'])
    card_style = scoped_values.get('core.ude.card_style', 'soft')
    if card_style not in ('flat', 'soft', 'raised'):
        card_style = 'soft'
    card_border = scoped_values.get('core.ude.card_border', '1px')
    if card_border not in ('none', '1px', '2px'):
        card_border = '1px'
    card_shadow = scoped_values.get('core.ude.card_shadow', 'light')
    if card_shadow not in ('none', 'light', 'medium'):
        card_shadow = 'light'
    card_interaction = scoped_values.get('core.ude.card_interaction', 'highlight')
    if card_interaction not in ('none', 'highlight', 'lift'):
        card_interaction = 'highlight'
    contrast = preferences.get("contrast", "normal")
    profile = "ude-high-contrast" if contrast == "high" else "ude-dark-default" if core_theme == "dark" else "ude-light-default"
    ude_v2_enabled = use_shared_shell(request, request.core_identity)
    ude_v2_components_enabled = use_shared_components(request, request.core_identity, ude_v2_enabled)
    ude_v2_bootstrap = {"settings": {
        "theme": core_theme,
        "palette": palette,
        "density": preferences.get("density", "comfortable"),
        "fontSize": font_size,
        "fontFamily": font_family,
        "fontWeight": int(font_weight),
        "radius": scoped_values.get('core.ude.radius', 'balanced'),
        "cardStyle": card_style,
        "cardBorder": card_border,
        "cardShadow": card_shadow,
        "cardInteraction": card_interaction,
        "customColors": custom_colors,
        "contrast": contrast,
    }}
    return {**navigation_context(request, modules), "core_identity": request.core_identity, "core_branding":branding,
            "work_context": preferences.get('current_organization', {}),
            "core_theme": core_theme,
            "core_density":preferences.get('density','comfortable'),
            "core_sound":preferences.get('notifications.sound',False),"core_quiet":preferences.get('notifications.quiet',False),
            "core_font_size": font_size,
            "core_font_family": font_family,
            "core_font_weight": font_weight,
            "core_font_weight_profile": weight_profiles,
            "core_palette": core_palette,
            "core_brand_color": custom_colors.get('primary') or ('' if core_palette else branding.get('primary_color', '#2766e9')),
            "core_accent_color": custom_colors.get('accent') or custom_colors.get('secondary'),
            "core_custom_colors": custom_colors,
            "core_radius": core_radius,
            "core_card_style": card_style,
            "core_card_border": card_border,
            "core_card_shadow": card_shadow,
            "core_card_interaction": card_interaction,
            "ude_v2_shared_shell_enabled": ude_v2_enabled,
            "ude_v2_shared_components_enabled": ude_v2_components_enabled,
            "ude_v2_theme_profile": profile,
            "ude_v2_theme_bootstrap": ude_v2_bootstrap}
