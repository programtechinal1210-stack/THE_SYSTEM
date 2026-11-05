import csv
import io
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func
from infrastructure.database.db_context import get_session
from infrastructure.audit.models.audit_log_model import AuditLogModel
from modules.module_users.infrastructure.models.user_model import UserModel
from core.access import require

router = APIRouter()


def scoped_query(request, module=None, action=None, search=None, date_from=None, date_to=None,
                 user_id=None, severity=None, status_code=None):
    start = date_from.replace(tzinfo=timezone.utc) if date_from and date_from.tzinfo is None else date_from
    end = date_to.replace(tzinfo=timezone.utc) if date_to and date_to.tzinfo is None else date_to
    if start and end and start > end:
        raise HTTPException(422, "Start date must not be after end date")
    query = select(AuditLogModel)
    if not request.state.is_admin and "institution" not in request.state.scopes:
        if "organization" in request.state.scopes:
            query = query.where(AuditLogModel.user_id.in_(select(UserModel.id).where(UserModel.organization_id == request.state.user.organization_id)))
        else:
            query = query.where(AuditLogModel.user_id == request.state.user.id)
    if module: query = query.where(AuditLogModel.module == module)
    if action: query = query.where(AuditLogModel.action == action)
    if search: query = query.where(AuditLogModel.changes_summary.contains(search))
    if date_from: query = query.where(AuditLogModel.created_at >= date_from)
    if date_to: query = query.where(AuditLogModel.created_at <= date_to)
    if user_id: query = query.where(AuditLogModel.user_id == user_id)
    if severity: query = query.where(AuditLogModel.severity == severity)
    if status_code: query = query.where(AuditLogModel.status_code == status_code)
    return query


def item(row):
    return {"id": row.id, "user_id": str(row.user_id) if row.user_id else None,
            "action": row.action, "module": row.module, "entity_type": row.entity_type,
            "changes_summary": row.changes_summary, "created_at": row.created_at,
            "status_code": row.status_code, "severity": row.severity}


@router.get("/api/v1/audit/logs")
async def logs(request: Request, module: str | None = None, action: str | None = None,
               search: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
               user_id: UUID | None = None, severity: str | None = None, status_code: int | None = Query(None, ge=100, le=599),
               skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
               session=Depends(get_session, scope="function")):
    query = scoped_query(request, module, action, search, date_from, date_to, user_id, severity, status_code)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(query.order_by(AuditLogModel.id.desc()).offset(skip).limit(limit))
    return {"items": [item(r) for r in rows], "total": total, "skip": skip, "limit": limit}


@router.get("/api/v1/audit/logs/summary")
async def summary(request: Request, module: str | None = None, action: str | None = None,
                  search: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                  user_id: UUID | None = None, severity: str | None = None, status_code: int | None = Query(None, ge=100, le=599),
                  session=Depends(get_session, scope="function")):
    query = scoped_query(request, module, action, search, date_from, date_to, user_id, severity, status_code)
    return {"total_actions": await session.scalar(select(func.count()).select_from(query.subquery()))}


@router.get("/api/v1/audit/export")
async def export(request: Request, module: str | None = None, action: str | None = None,
                 search: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                 user_id: UUID | None = None, severity: str | None = None, status_code: int | None = Query(None, ge=100, le=599),
                 session=Depends(get_session, scope="function")):
    require(request, "core.audit.export")
    request.state.audit_export = True
    request.state.scopes = request.state.permission_scopes.get("core.audit.export", {"self"})
    query = scoped_query(request, module, action, search, date_from, date_to, user_id, severity, status_code)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    if total > 10000:
        raise HTTPException(422, "Narrow the export filters to at most 10000 records")
    rows = await session.scalars(query.order_by(AuditLogModel.id.desc()))
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "action", "module", "created_at", "description"])
    for row in rows:
        description = row.changes_summary or ""
        if description.startswith(("=", "+", "-", "@")): description = "'" + description
        writer.writerow([row.id, row.action, row.module, row.created_at, description])
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit.csv"'})


@router.get("/api/v1/audit/logs/{log_id}")
async def detail(log_id: int, request: Request, session=Depends(get_session, scope="function")):
    from infrastructure.audit.services.event_writer import redact
    row = await session.scalar(scoped_query(request).where(AuditLogModel.id == log_id))
    if row is None:
        raise HTTPException(404, "Audit event not found")
    return {**item(row), "entity_id": str(row.entity_id) if row.entity_id else None,
            "old": redact(row.old_value), "new": redact(row.new_value), "ip_address": row.ip_address,
            "metadata": redact(row.metadata_json)}


@router.get("/api/v1/profile/activity")
async def activity(request: Request, session=Depends(get_session, scope="function")):
    # Personal stream is always restricted to its actor, regardless of administrator role.
    from sqlalchemy import text
    rows = (await session.execute(text("SELECT id,verb,description_ar,created_at FROM activity_stream WHERE actor_id=:uid ORDER BY created_at DESC LIMIT 20"), {"uid": request.state.user.id.hex})).mappings()
    return [dict(row) for row in rows]
