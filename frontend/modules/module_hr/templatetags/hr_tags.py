from django import template

register = template.Library()


@register.filter
def get_item(value, key):
    return value.get(key, "")


@register.filter
def lookup(value, key):
    if not isinstance(value, dict):
        return ""
    normalized = key.isoformat() if hasattr(key, "isoformat") else key
    return value.get(normalized, value.get(key, ""))
