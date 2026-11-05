from datetime import date, datetime
from fastapi import HTTPException

USER_SETTINGS = {
    "theme": ("select", "light", ["light", "dark", "system"]),
    "ude.palette": ("select", "navy", ["navy", "royal-blue", "emerald", "modern-purple", "turquoise", "burgundy"]),
    "palette": ("select", "navy", ["navy", "royal-blue", "emerald", "modern-purple", "turquoise", "burgundy"]),
    "language": ("select", "ar", ["ar", "en"]),
    "font_size": ("integer", 16, None),
}


def validate_value(kind, value, options=None, rules=None):
    valid = {"string": lambda: isinstance(value, str),
             "integer": lambda: type(value) is int,
             "decimal": lambda: type(value) in (int, float),
             "boolean": lambda: type(value) is bool,
             "json": lambda: isinstance(value, (dict, list)),
             "select": lambda: value in (options or []),
             "multi-select": lambda: isinstance(value, list) and all(v in (options or []) for v in value),
             "date": lambda: isinstance(value, str) and bool(date.fromisoformat(value)),
             "datetime": lambda: isinstance(value, str) and bool(datetime.fromisoformat(value))}
    try:
        if kind not in valid or not valid[kind]():
            raise ValueError()
        rules = rules or {}
        if "min" in rules and value < rules["min"]:
            raise ValueError()
        if "max" in rules and value > rules["max"]:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, "Setting value does not match its definition")
    return value


def validate_user_setting(key, value):
    if key not in USER_SETTINGS:
        raise HTTPException(403, "This setting cannot be overridden by the user")
    kind, default, options = USER_SETTINGS[key]
    return validate_value(kind, value, options, {"min": 12, "max": 24} if key == "font_size" else {})
