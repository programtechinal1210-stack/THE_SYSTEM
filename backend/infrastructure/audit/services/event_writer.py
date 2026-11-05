"""Persist bounded, redacted business events in the caller's transaction."""
import json
from uuid import UUID, uuid4
from sqlalchemy import text

SENSITIVE = ("password", "token", "secret", "authorization", "cookie")


def redact(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if any(s in str(k).lower() for s in SENSITIVE) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def write_event(session, request, action, status_code):
    actor = getattr(request.state, "user_id", None)
    path = request.url.path
    details = getattr(request.state, "audit_details", {})
    route_id = next((str(v) for v in request.path_params.values() if isinstance(v, UUID)), None)
    entity_id = details.get("entity_id", route_id)
    entity_id = UUID(str(entity_id)).hex if entity_id else None
    module = path.split("/")[3] if len(path.split("/")) > 3 else "core"
    values = dict(uid=actor.hex if actor else None, action=action, module=module,
        entity_type=details.get("entity_type", module), entity_id=entity_id,
        old=json.dumps(redact(details.get("old")), default=str),
        new=json.dumps(redact(details.get("new")), default=str),
        code=status_code, ip=request.client.host if request.client else None,
        summary=details.get("summary", action + " " + module),
        severity="warning" if status_code >= 400 else "info")
    values["metadata"] = json.dumps({"request_id": getattr(request.state, "request_id", None),
                                     "reference": redact(details.get("reference"))})
    # The increment is part of the INSERT statement under SQLite's writer lock.
    await session.execute(text("INSERT INTO audit_logs(id,user_id,action,module,entity_type,entity_id,old_value,new_value,status_code,ip_address,changes_summary,severity,metadata) VALUES((SELECT COALESCE(MAX(id),0)+1 FROM audit_logs),:uid,:action,:module,:entity_type,:entity_id,:old,:new,:code,:ip,:summary,:severity,:metadata)"), values)
    if status_code < 400:
        await session.execute(text("INSERT INTO activity_stream(id,source_type,actor_id,verb,description_ar) VALUES(:id,'core',:uid,:verb,:description)"),
            dict(id=uuid4().hex, uid=values["uid"], verb=action, description=values["summary"]))
