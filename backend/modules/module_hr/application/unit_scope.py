from fastapi import HTTPException

from core.access import unit_scope


def require_unit(request, permission, unit_id, status_code=403):
    allowed_units = unit_scope(request, permission)
    if allowed_units is not None and (not allowed_units or str(unit_id) not in allowed_units):
        raise HTTPException(status_code, "Outside assigned organizational unit scope")


def unit_filter(request, permission, column, params, prefix="scope_unit"):
    allowed_units = unit_scope(request, permission)
    if allowed_units is None:
        return ""
    if not allowed_units:
        raise HTTPException(403, "Permission has no assigned organizational units")
    placeholders = []
    for index, unit_id in enumerate(sorted(allowed_units)):
        key = f"{prefix}_{index}"
        placeholders.append(f":{key}")
        params[key] = unit_id
    return f" AND {column} IN ({','.join(placeholders)})"
