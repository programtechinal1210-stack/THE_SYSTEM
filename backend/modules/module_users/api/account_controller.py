from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from infrastructure.database.db_context import get_session
from infrastructure.authentication.password_hasher import PasswordHasher
from modules.module_users.infrastructure.models.user_model import UserModel
from modules.module_users.infrastructure.models.role_model import RoleModel
from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
from modules.module_users.infrastructure.repositories.user_repository import UserRepository
from modules.module_users.application.dtos.user_dto import UserDTO
from core.access import check_user_scope

router = APIRouter()


class RoleAssignment(BaseModel):
    role_name: str
    scope: Literal["self", "organization", "institution"] = "self"


@router.get("/api/v1/users/{uid}")
async def user_detail(uid: UUID, request: Request, session=Depends(get_session, scope="function")):
    user = await UserRepository(session).get_by_id(uid)
    if not user:
        raise HTTPException(404, "User not found")
    check_user_scope(request, user)
    return UserDTO.from_entity(user)


@router.post("/api/v1/users/{uid}/roles")
async def assign_role(uid: UUID, data: RoleAssignment, request: Request, session=Depends(get_session, scope="function")):
    if not request.state.is_admin:
        raise HTTPException(403, "Only the system administrator can assign roles")
    user = await session.get(UserModel, uid)
    role = await session.scalar(select(RoleModel).where(RoleModel.name == data.role_name))
    if not user or not role:
        raise HTTPException(404, "User or role not found")
    old_scope = await session.scalar(text("SELECT scope FROM user_roles WHERE user_id=:uid AND role_id=:rid"), {"uid": uid.hex, "rid": role.id})
    request.state.audit_details = {"entity_type": "users.user", "entity_id": str(uid),
        "old": {"role": role.name, "scope": old_scope}, "new": {"role": role.name, "scope": data.scope}}
    await session.execute(text("INSERT INTO user_roles(user_id,role_id,scope) VALUES(:uid,:rid,:scope) ON CONFLICT(user_id,role_id) DO UPDATE SET scope=excluded.scope"),
        {"uid": uid.hex, "rid": role.id, "scope": data.scope})
    return {"detail": "Role assigned"}


@router.delete("/api/v1/users/{uid}/roles/{role_id}")
async def remove_role(uid: UUID, role_id: int, request: Request, session=Depends(get_session, scope="function")):
    if not request.state.is_admin or uid == request.state.user.id:
        raise HTTPException(403, "Cannot remove own role or assign without administrator rights")
    old_scope = await session.scalar(text("SELECT scope FROM user_roles WHERE user_id=:uid AND role_id=:rid"), {"uid": uid.hex, "rid": role_id})
    request.state.audit_details = {"entity_type": "users.user", "entity_id": str(uid),
        "old": {"role_id": role_id, "scope": old_scope}, "new": None}
    result = await session.execute(text("""DELETE FROM user_roles WHERE user_id=:uid AND role_id=:rid AND (
        NOT EXISTS (SELECT 1 FROM roles WHERE id=:rid AND name='admin' AND is_system=1)
        OR (SELECT count(DISTINCT u.id) FROM users u JOIN user_roles ur ON ur.user_id=u.id
            JOIN roles r ON r.id=ur.role_id WHERE u.is_active=1 AND r.name='admin' AND r.is_system=1)>1
    )"""), {"uid": uid.hex, "rid": role_id})
    if result.rowcount != 1:
        raise HTTPException(409, "Assignment unavailable or last administrator protected")
    return {"detail": "Role removed"}


class ProfileInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)


@router.put("/api/v1/profile")
async def update_profile(data: ProfileInput, request: Request, session=Depends(get_session, scope="function")):
    user = await session.get(UserModel, request.state.user.id)
    request.state.audit_details = {"entity_type": "users.user", "entity_id": str(user.id),
        "old": {"full_name": user.full_name, "phone": user.phone}, "new": data.model_dump()}
    user.full_name, user.phone = data.full_name, data.phone
    await session.flush()
    return {"detail": "Profile updated"}


class PasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


@router.put("/api/v1/profile/password")
async def change_password(data: PasswordInput, request: Request, session=Depends(get_session, scope="function")):
    user = await session.get(UserModel, request.state.user.id)
    hasher = PasswordHasher()
    if not hasher.verify(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    from modules.module_settings.application.security_policy import validate_password
    await validate_password(session, data.new_password)
    user.password_hash = hasher.hash(data.new_password)
    await session.execute(update(UserSessionModel).where(UserSessionModel.user_id == user.id).values(is_active=False, logout_time=datetime.utcnow()))
    try:
        from infrastructure.authentication.security_events import record, alert
        ip = request.client.host if request.client else "unknown"
        await record(session, "password_changed", user.id, ip, request.headers.get("user-agent", ""))
        await alert(session, user.id, "core.security.password_changed", {"username": user.username}, f"pwd:{user.id.hex}")
    except Exception:
        pass
    return {"detail": "Password changed; sign in again"}


@router.get("/api/v1/profile/sessions")
async def sessions(request: Request, session=Depends(get_session, scope="function")):
    rows = await session.scalars(select(UserSessionModel).where(UserSessionModel.user_id == request.state.user.id, UserSessionModel.is_active.is_(True)))
    return [{"id": str(row.id), "ip_address": row.ip_address, "login_time": row.login_time,
             "expiry_time": row.expiry_time, "current": row.id == request.state.session_id} for row in rows]


@router.delete("/api/v1/profile/sessions/{sid}")
async def revoke_session(sid: UUID, request: Request, session=Depends(get_session, scope="function")):
    result = await session.execute(update(UserSessionModel).where(UserSessionModel.id == sid,
        UserSessionModel.user_id == request.state.user.id).values(is_active=False, logout_time=datetime.utcnow()))
    if not result.rowcount:
        raise HTTPException(404, "Session not found")
    return {"detail": "Session revoked"}


class ResetPasswordInput(BaseModel):
    new_password: str = Field(min_length=12, max_length=200)


@router.put("/api/v1/users/{uid}/password")
async def reset_password(uid: UUID, data: ResetPasswordInput, request: Request, session=Depends(get_session, scope="function")):
    if not request.state.is_admin:
        raise HTTPException(403, "Administrator required")
    user = await session.get(UserModel, uid)
    if not user:
        raise HTTPException(404, "User not found")
    from modules.module_settings.application.security_policy import validate_password
    await validate_password(session, data.new_password)
    user.password_hash = PasswordHasher().hash(data.new_password)
    await session.execute(update(UserSessionModel).where(UserSessionModel.user_id == uid).values(is_active=False, logout_time=datetime.utcnow()))
    return {"detail": "Password reset and sessions revoked"}


@router.get("/api/v1/users/{uid}/permissions")
async def permission_preview(uid: UUID, request: Request, session=Depends(get_session, scope="function")):
    user = await session.get(UserModel, uid)
    if not user:
        raise HTTPException(404, "User not found")
    check_user_scope(request, user)
    rows = (await session.execute(text("SELECT DISTINCT p.code,ur.scope FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=:uid"), {"uid": uid.hex})).mappings()
    return [dict(r) for r in rows]
