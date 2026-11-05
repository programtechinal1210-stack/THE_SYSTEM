# modules/module_users/api/users_controller.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..application.commands.create_user import CreateUserCommand
from ..application.handlers.create_user_handler import CreateUserHandler
from ..application.commands.login_user import LoginUserCommand
from ..application.handlers.login_user_handler import LoginUserHandler
from ..application.dtos.user_dto import CreateUserDTO, LoginDTO, TokenDTO, UserDTO, UpdateUserDTO
from infrastructure.database.db_context import get_session  # <-- تغيير هنا
from modules.module_users.infrastructure.repositories.user_repository import UserRepository
from modules.module_users.infrastructure.repositories.role_repository import RoleRepository
from modules.module_users.infrastructure.repositories.user_session_repository import UserSessionRepository
from infrastructure.authentication.password_hasher import PasswordHasher
from infrastructure.authentication.jwt_handler import JWTHandler
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from uuid import UUID

auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])

async def get_user_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return UserRepository(session)

async def get_role_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return RoleRepository(session)

async def get_session_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return UserSessionRepository(session)

async def get_create_user_handler(
    user_repo: UserRepository = Depends(get_user_repository),
    role_repo: RoleRepository = Depends(get_role_repository),
):
    return CreateUserHandler(user_repo, role_repo, PasswordHasher())

async def get_login_handler(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: UserSessionRepository = Depends(get_session_repository),
):
    return LoginUserHandler(
        user_repository=user_repo,
        password_hasher=PasswordHasher(),
        jwt_handler=JWTHandler(),
        session_repository=session_repo
    )

@auth_router.post("/register", response_model=UserDTO, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    user_data: CreateUserDTO,
    handler: CreateUserHandler = Depends(get_create_user_handler)
):
    if not request.state.is_admin:
        raise HTTPException(403, "Only administrator can create accounts")
    if not user_data.organization_id:
        raise HTTPException(422, "Organization is required")
    from modules.module_settings.application.security_policy import validate_password
    await validate_password(handler.user_repository._session, user_data.password)
    command = CreateUserCommand(
        username=user_data.username,
        password=user_data.password,
        full_name=user_data.full_name,
        email=user_data.email,
        organization_id=user_data.organization_id,
        phone=user_data.phone,
        position=user_data.position,
        role_names=user_data.role_names
    )
    
    result = await handler.handle(command)
    
    if not result.is_success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )
    
    from modules.module_notifications.application.notification_service import NotificationService
    from sqlalchemy import select
    from modules.module_notifications.infrastructure.models.notification_template_model import NotificationTemplateModel
    db = handler.user_repository._session
    if await db.scalar(select(NotificationTemplateModel.id).where(NotificationTemplateModel.type == "core.user.created")):
        await NotificationService(db).emit("core.user.created", result.value.id,
            {"username": result.value.username}, "user-created:" + str(result.value.id))
    return UserDTO.from_entity(result.value)

@auth_router.post("/login", response_model=TokenDTO)
async def login(
    request: Request,
    login_data: LoginDTO,
    handler: LoginUserHandler = Depends(get_login_handler),
    session: AsyncSession = Depends(get_session, scope="function")
):
    handler.request = request
    from sqlalchemy import text
    from datetime import datetime, timedelta
    from hashlib import sha256
    from modules.module_settings.application.center_service import system_value
    identity = sha256(login_data.username.strip().casefold().encode()).hexdigest()
    locked = await session.scalar(text('SELECT locked_until FROM login_attempts WHERE identity=:i'), {'i':identity})
    if locked and datetime.fromisoformat(locked) > datetime.utcnow():
        raise HTTPException(429, 'محاولات متكررة؛ انتظر انتهاء مدة القفل ثم حاول مجددًا')

    command = LoginUserCommand(
        username=login_data.username,
        password=login_data.password
    )

    result = await handler.handle(command)

    if not result.is_success:
        attempts = await system_value(session, 'core.security.login_attempts')
        minutes = await system_value(session, 'core.security.lock_minutes')
        until = (datetime.utcnow()+timedelta(minutes=minutes)).isoformat()
        await session.execute(text('''INSERT INTO login_attempts(identity,attempts) VALUES(:i,1)
            ON CONFLICT(identity) DO UPDATE SET attempts=CASE WHEN locked_until IS NOT NULL THEN 1 ELSE attempts+1 END,locked_until=NULL'''), {'i':identity})
        await session.execute(text('UPDATE login_attempts SET locked_until=:until WHERE identity=:i AND attempts>=:n'), {'i':identity,'until':until,'n':attempts})
        await session.commit()  # Failed-attempt counters survive the rejected authentication transaction.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error
        )

    await session.execute(text('DELETE FROM login_attempts WHERE identity=:i'), {'i':identity})
    request.state.user_id = result.value["user_id"]
    try:
        from infrastructure.authentication.security_events import record, alert
        ip = request.client.host if request.client else "unknown"
        agent = request.headers.get("user-agent", "")
        await record(session, "login", result.value["user_id"], ip, agent)
        if await system_value(session, 'core.security.alert_new_ip'):
            from sqlalchemy import text as _t
            older = await session.scalar(_t(
                "SELECT ip_address FROM security_events WHERE user_id=:u AND kind='login' ORDER BY id DESC LIMIT 1 OFFSET 1"),
                {"u": result.value["user_id"].hex})
            if older is not None and older != ip:
                await alert(session, result.value["user_id"], "core.security.new_login",
                            {"username": login_data.username, "ip_address": ip},
                            f"new-ip:{result.value['user_id']}:{ip}")
        await session.commit()
    except Exception:
        pass
    from modules.module_users.infrastructure.models.user_model import UserModel as _UM
    _user = await session.get(_UM, result.value["user_id"])
    _mfa_required = await system_value(session, 'core.security.mfa_required')
    if _user is not None and (_user.mfa_enabled or _mfa_required):
        from sqlalchemy import update as _up
        from modules.module_users.infrastructure.models.user_session_model import UserSessionModel as _SM
        await session.execute(_up(_SM).where(
            _SM.session_token == result.value["access_token"]).values(mfa_verified=False))
        await session.commit()
        payload = dict(TokenDTO(**result.value).model_dump(mode="json"))
        payload["mfa_required"] = True
        return payload
    return TokenDTO(**result.value)


class MFAVerifyInput(BaseModel):
    code: str


@auth_router.post("/mfa/enroll")
async def mfa_enroll(request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    from infrastructure.authentication.totp import generate_secret, provisioning_uri
    from modules.module_users.infrastructure.models.user_model import UserModel
    # Deliberately NOT gated on mfa_required here: NIST AAL2 requires that a
    # pending (not-yet-verified) session MUST be able to reach /mfa/enroll to
    # bootstrap TOTP for the org-wide policy. The AuthMiddleware's mfa_required
    # gate must exempt this route too.
    user = await session.get(UserModel, request.state.user.id)
    secret = generate_secret()
    user.mfa_secret = secret
    await session.flush()
    request.state.audit_details = {"entity_type": "users.mfa", "entity_id": str(user.id), "new": {"enrolled": True}}
    return {"secret": secret, "uri": provisioning_uri(secret, user.username)}


@auth_router.post("/mfa/verify")
async def mfa_verify(data: MFAVerifyInput, request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    from infrastructure.authentication.totp import verify
    from sqlalchemy import update
    from modules.module_users.infrastructure.models.user_model import UserModel
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
    user = await session.get(UserModel, request.state.user.id)
    if not user or not user.mfa_secret or not verify(user.mfa_secret, data.code):
        raise HTTPException(401, "رمز التحقق غير صحيح")
    user.mfa_enabled = True
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel as _SMAll
    # Only this pending session is marked verified; sibling sessions must still
    # complete their own challenge at next use (no MFA bypass via old sessions).
    await session.execute(update(_SMAll).where(
        _SMAll.id == request.state.session_id).values(mfa_verified=True))
    try:
        from infrastructure.authentication.security_events import record, alert
        ip = request.client.host if request.client else "unknown"
        await record(session, "mfa_enabled", user.id, ip, request.headers.get("user-agent", ""))
        await alert(session, user.id, "core.security.mfa_enabled", {"username": user.username}, f"mfa:{user.id.hex}")
    except Exception:
        pass
    request.state.audit_details = {"entity_type": "users.mfa", "entity_id": str(user.id), "new": {"enabled": True}}
    return {"detail": "تم تفعيل التحقق بخطوتين"}


@auth_router.post("/mfa/challenge")
async def mfa_challenge(data: MFAVerifyInput, request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    from infrastructure.authentication.totp import verify
    from sqlalchemy import update
    from modules.module_users.infrastructure.models.user_model import UserModel
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
    user = await session.get(UserModel, request.state.user.id)
    # An org-wide mfa_required policy also locks users who never enrolled: they
    # must first enroll via /mfa/enroll (which is exempt from the pending gate).
    if not user or not user.mfa_secret or not verify(user.mfa_secret, data.code):
        raise HTTPException(401, "رمز التحقق غير صحيح")
    await session.execute(update(UserSessionModel).where(
        UserSessionModel.id == request.state.session_id).values(mfa_verified=True))
    from modules.module_settings.application.center_service import system_value
    if user.organization_id is not None and await system_value(session, 'core.security.mfa_required'):
        user.mfa_enabled = True
    return {"detail": "تم التحقق؛ الجلسة مفعلة الآن"}


@auth_router.delete("/mfa")
async def mfa_disable(request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    from modules.module_users.infrastructure.models.user_model import UserModel
    user = await session.get(UserModel, request.state.user.id)
    user.mfa_secret = None
    user.mfa_enabled = False
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel as _SMOff
    from sqlalchemy import update as _up_off
    # Recovery path: the verified owner (current session) or an administrator
    # (via /mfa/admin-disable) may switch MFA off; this un-gates every session.
    await session.execute(
        _up_off(_SMOff).where(_SMOff.user_id == user.id).values(mfa_verified=False))
    request.state.audit_details = {"entity_type": "users.mfa", "entity_id": str(user.id), "new": {"enabled": False}}
    return {"detail": "تم إيقاف التحقق بخطوتين"}


@auth_router.post("/mfa/admin-disable")
async def mfa_admin_disable(uid: UUID, request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    """Administrator-triggered recovery for a user who lost their authenticator device."""
    from modules.module_users.infrastructure.models.user_model import UserModel
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel as _SMOff
    from sqlalchemy import update as _up_off
    if not request.state.is_admin:
        raise HTTPException(403, "Administrator required")
    user = await session.get(UserModel, uid)
    if not user:
        raise HTTPException(404, "User not found")
    user.mfa_secret = None
    user.mfa_enabled = False
    await session.execute(
        _up_off(_SMOff).where(_SMOff.user_id == user.id).values(mfa_verified=False))
    request.state.audit_details = {"entity_type": "users.mfa", "entity_id": str(user.id), "new": {"enabled": False, "by": "admin"}}
    return {"detail": "تم إيقاف التحقق بخطوتين للمستخدم"}


@auth_router.post("/keys/rotate")
async def rotate_keys(request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    """Create a new signing key; old keys stay valid for in-flight tokens until retired."""
    from core.access import require
    require(request, "core.settings.security.manage")
    import secrets as _secrets
    from sqlalchemy import text as _t
    from infrastructure.authentication.jwt_handler import JWTHandler as _JH
    kid = "k-" + _secrets.token_hex(4)
    await session.execute(_t("INSERT INTO jwt_keys(kid,secret) VALUES(:kid,:secret)"),
                          {"kid": kid, "secret": _secrets.token_urlsafe(48)})
    await _JH.refresh_key_cache(session)
    request.state.audit_details = {"entity_type": "auth.key", "entity_id": kid, "new": {"rotated": True}}
    return {"kid": kid}


@auth_router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session, scope="function")
):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    await UserSessionRepository(session).revoke_session(token)
    return {"detail": "Logged out"}

@users_router.get("/", response_model=list[UserDTO])
async def list_users(
    request: Request,
    search: str = "",
    organization_id: UUID | None = None,
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    from ..application.user_queries import scoped_users
    from modules.module_users.infrastructure.models.user_model import UserModel
    query = scoped_users(request, search, organization_id, is_active).with_only_columns(UserModel.id)
    ids = (await user_repo._session.execute(query.order_by(UserModel.username).offset(max(skip, 0)).limit(min(max(limit, 1), 100)))).scalars()
    users = [await user_repo.get_by_id(uid) for uid in ids]
    return [UserDTO.from_entity(user) for user in users]


@users_router.get("/summary")
async def user_summary(request: Request, search: str = "", organization_id: UUID | None = None,
                       is_active: bool | None = None, session=Depends(get_session, scope="function")):
    from sqlalchemy import select, func
    from ..application.user_queries import scoped_users
    query = scoped_users(request, search, organization_id, is_active)
    return {"total": await session.scalar(select(func.count()).select_from(query.subquery()))}


@users_router.get("/export")
async def export_users(request: Request, search: str = "", organization_id: UUID | None = None,
                       is_active: bool | None = None, session=Depends(get_session, scope="function")):
    import csv, io
    from fastapi.responses import Response
    from sqlalchemy import select, func
    from core.access import require
    from ..application.user_queries import scoped_users
    from ..infrastructure.models.user_model import UserModel
    require(request, "core.users.export")
    request.state.scopes = request.state.permission_scopes.get("core.users.export", {"self"})
    query = scoped_users(request, search, organization_id, is_active)
    if await session.scalar(select(func.count()).select_from(query.subquery())) > 10000:
        raise HTTPException(422, "Narrow export to at most 10000 users")
    rows = await session.scalars(query.order_by(UserModel.username))
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "username", "full_name", "email", "organization_id", "is_active"])
    for row in rows:
        values = [str(value) for value in (row.id, row.username, row.full_name, row.email, row.organization_id, row.is_active)]
        writer.writerow(["'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
    request.state.audit_export = True
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users.csv"'})

@users_router.put("/{user_id}", response_model=UserDTO)
async def update_user(
    request: Request,
    user_id: UUID,
    user_data: UpdateUserDTO,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_data = user_data.model_dump(exclude_unset=True, exclude_none=True)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    from core.access import check_user_scope
    check_user_scope(request, user)
    from ..application.account_policy import protect_privileged_target, deactivate
    await protect_privileged_target(user_repo._session, request, user_id)
    if user.id == current_user.id and user_data.get("is_active") is False:
        raise HTTPException(400, "Cannot deactivate your own account")
    if user_data.get("is_active") is False:
        await deactivate(user_repo._session, user_id)
    if "organization_id" in user_data and user_data["organization_id"] != user.organization_id:
        if not request.state.is_admin:
            raise HTTPException(403, "Only administrator can transfer user membership")
        from infrastructure.database.models.organization_model import OrganizationModel
        destination = await user_repo._session.get(OrganizationModel, user_data["organization_id"])
        if not destination or not destination.is_active:
            raise HTTPException(422, "Destination must be an active organizational unit")
    request.state.audit_details = {"entity_type": "core.user", "entity_id": str(user_id), "old": {k: getattr(user,k,None) for k in user_data}, "new": user_data}
    if "full_name" in user_data:
        user.full_name = user_data["full_name"]
    if "position" in user_data:
        user.position = user_data["position"]
    if "phone" in user_data:
        user.phone = user_data["phone"]
    if "is_active" in user_data:
        user.is_active = user_data["is_active"]
    if "email" in user_data:
        user.email = user_data["email"]
    if "organization_id" in user_data:
        user.organization_id = user_data["organization_id"]
    
    updated_user = await user_repo.save(user)
    return UserDTO.from_entity(updated_user)

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    from core.access import check_user_scope
    target = await user_repo.get_by_id(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    check_user_scope(request, target)
    from ..application.account_policy import protect_privileged_target, deactivate
    await protect_privileged_target(user_repo._session, request, user_id)
    await deactivate(user_repo._session, user_id)
    target.is_active = False
    await user_repo.save(target)
    deleted = True
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return None


@auth_router.get("/me")
async def me(request: Request, user: User = Depends(get_current_user)):
    data = UserDTO.from_entity(user).model_dump(mode="json")
    data.update(permissions=sorted(request.state.permissions), is_admin=request.state.is_admin)
    return data


class RefreshRequest(BaseModel):
    refresh_token: str


@auth_router.post("/refresh", response_model=TokenDTO)
async def refresh(data: RefreshRequest, request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    from sqlalchemy import update
    from datetime import datetime
    from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
    jwt = JWTHandler()
    from modules.module_settings.application.security_policy import configure_tokens
    await configure_tokens(session, jwt)
    await JWTHandler.refresh_key_cache(session)
    # Rotation-aware: verify with the session's key (fingerprint lookup), not the legacy secret.
    fp = JWTHandler.token_fingerprint(data.refresh_token)
    from sqlalchemy import select as _sel
    kid_row = await session.execute(
        _sel(UserSessionModel.token_kid).where(
            ((UserSessionModel.refresh_token == data.refresh_token)
             | (UserSessionModel.refresh_token_hash == fp)),
            UserSessionModel.is_active.is_(True)))
    kid = kid_row.scalar_one_or_none()
    try:
        payload = jwt.verify_with_session(data.refresh_token, JWTHandler.secret_for_kid(kid), kid)
        if payload.get("type") != "refresh":
            raise ValueError()
        uid = UUID(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid refresh token")
    # Idle timeout also blocks silent renewal: a refresh with no server contact
    # for longer than core.security.idle_minutes is rejected like any other call.
    from modules.module_settings.application.center_service import system_value as _idle_value
    from sqlalchemy import select as _select
    from datetime import timedelta as _td
    _idle = await _idle_value(session, 'core.security.idle_minutes')
    try:
        _idle = int(_idle)
    except (TypeError, ValueError):
        _idle = 10
    _row = await session.execute(
        _select(UserSessionModel.last_activity).where(
            ((UserSessionModel.refresh_token == data.refresh_token)
             | (UserSessionModel.refresh_token_hash == fp)),
            UserSessionModel.user_id == uid, UserSessionModel.is_active.is_(True)))
    _last = _row.scalar_one_or_none()
    if _last is not None and datetime.utcnow() - _last > _td(minutes=_idle):
        await session.execute(update(UserSessionModel).where(
            ((UserSessionModel.refresh_token == data.refresh_token)
             | (UserSessionModel.refresh_token_hash == fp)),
            UserSessionModel.user_id == uid, UserSessionModel.is_active.is_(True),
        ).values(is_active=False, logout_time=datetime.utcnow()))
        await session.commit()
        raise HTTPException(401, "انتهت الجلسة بسبب الخمول لمدة 10 دقائق؛ سجّل الدخول مجددًا")
    # Atomic consume: a refresh token can create a replacement session only once.
    consumed = await session.execute(update(UserSessionModel).where(
        ((UserSessionModel.refresh_token == data.refresh_token)
         | (UserSessionModel.refresh_token_hash == fp)),
        UserSessionModel.user_id == uid, UserSessionModel.is_active.is_(True),
    ).values(is_active=False, logout_time=datetime.utcnow()))
    if consumed.rowcount != 1:
        raise HTTPException(401, "Session revoked")
    user = await UserRepository(session).get_by_id(uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Account unavailable")
    kid = await JWTHandler.ensure_active_key(session)
    secret = await jwt.signing_secret(session, kid)
    access = jwt.create_access_token({"sub": str(uid)}, secret=secret, kid=kid)
    renewed = jwt.create_refresh_token({"sub": str(uid)}, secret=secret, kid=kid)
    # MFA state carries over: a verified session stays verified after rotation.
    from sqlalchemy import select as _s2
    _was = await session.scalar(_s2(UserSessionModel.mfa_verified).where(
        ((UserSessionModel.refresh_token == data.refresh_token)
         | (UserSessionModel.refresh_token_hash == fp)), UserSessionModel.user_id == uid))
    await UserSessionRepository(session).create_session(uid, access, renewed,
        request.client.host if request.client else "unknown", expiry_minutes=jwt.access_token_expire_minutes,
        mfa_verified=bool(_was), token_kid=kid)
    request.state.user_id = uid
    return TokenDTO(access_token=access, refresh_token=renewed, user_id=uid,
                    username=user.username, full_name=user.full_name)



