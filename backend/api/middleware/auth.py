from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select, text, update
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from infrastructure.database.db_context import AsyncSessionLocal
from infrastructure.authentication.jwt_handler import JWTHandler
from modules.module_users.infrastructure.repositories.user_repository import UserRepository
from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
from core.access import route_permission, allowed
from infrastructure.audit.services.denial_writer import write_denial_event, ensure_request_id


class AuthMiddleware(BaseHTTPMiddleware):
    PUBLIC = {"/api/v1/settings-center/branding", "/api/v1/auth/login", "/api/v1/auth/refresh", "/health",
              "/api/docs", "/api/redoc", "/api/openapi.json"}

    async def dispatch(self, request, call_next):
        # Every request gets a correlation id before any gate can reject it, so a
        # denial can be traced in the audit trail even though the inner logging
        # middleware never runs for it.
        request_id = ensure_request_id(request)

        async def deny(status_code: int, detail: str, reason: str):
            await write_denial_event(request, status_code, reason)
            return JSONResponse({"detail": detail}, status_code=status_code,
                                headers={"X-Request-ID": request_id})

        if request.method == "OPTIONS" or request.url.path in self.PUBLIC:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return await deny(401, "Authentication required", "missing_bearer_token")
        token = header[7:]
        async with AsyncSessionLocal() as session:
            # Rotation-aware lookup: find the session first (token or fingerprint),
            # then verify the signature with that session's key.
            from infrastructure.authentication.jwt_handler import JWTHandler as _JH
            fingerprint = _JH.token_fingerprint(token)
            row = await session.execute(select(
                    UserSessionModel.id, UserSessionModel.last_activity,
                    UserSessionModel.mfa_verified, UserSessionModel.token_kid,
                    UserSessionModel.session_token).where(
                UserSessionModel.is_active.is_(True),
                UserSessionModel.expiry_time > datetime.utcnow(),
                ((UserSessionModel.session_token == token)
                 | (UserSessionModel.refresh_token_hash == fingerprint)
                 | (UserSessionModel.session_token == fingerprint))))
            found = row.one_or_none()
            if not found:
                return await deny(401, "Session revoked or expired", "session_not_active")
            active, last_activity, mfa_verified, token_kid, stored_token = found
            if stored_token != token and stored_token != fingerprint:
                # Matched on refresh fingerprint: this is not an access token.
                return await deny(401, "Not an access token", "wrong_token_type")
            await JWTHandler.refresh_key_cache(session)
            try:
                payload = JWTHandler().verify_with_session(
                    token, JWTHandler.secret_for_kid(token_kid), token_kid)
                if payload.get("type") != "access":
                    raise ValueError("Not an access token")
                uid = UUID(payload["sub"])
            except (ValueError, KeyError, TypeError):
                return await deny(401, "Invalid or expired session", "invalid_access_token")
            from modules.module_users.infrastructure.models.user_session_model import UserSessionModel as _SMCheck
            owner = await session.scalar(select(_SMCheck.user_id).where(_SMCheck.id == active))
            if owner is None or owner != uid:
                return await deny(401, "Session revoked or expired", "session_owner_mismatch")
            # MFA gate: sessions pending second-factor verification can only reach
            # the MFA endpoints themselves and read-only identity.
            from modules.module_settings.application.center_service import system_value as _mv
            if not mfa_verified:
                from modules.module_users.infrastructure.models.user_model import UserModel as _UMV
                _u = await session.get(_UMV, uid)
                # The pending gate always applies, but it must still let the user
                # through to the MFA flow itself: /mfa/challenge (verify an
                # already-enrolled device) AND /mfa/enroll (bootstrap TOTP when the
                # org-wide policy mfa_required is on and the user never enrolled).
                if _u is not None and (_u.mfa_enabled or await _mv(session, 'core.security.mfa_required')):
                    path = request.url.path
                    if path not in ("/api/v1/auth/mfa/challenge", "/api/v1/auth/logout", "/api/v1/auth/me"):
                        return JSONResponse({"detail": "التحقق بخطوتين مطلوب؛ أكمل التحقق أولاً", "code": "mfa_required"}, status_code=403)
            # Auto-logout after 10 minutes without server contact (sliding window).
            from modules.module_settings.application.center_service import system_value
            idle_minutes = await system_value(session, 'core.security.idle_minutes')
            try:
                idle_minutes = int(idle_minutes)
            except (TypeError, ValueError):
                idle_minutes = 10
            if last_activity is not None and datetime.utcnow() - last_activity > timedelta(minutes=idle_minutes):
                await session.execute(update(UserSessionModel).where(UserSessionModel.id == active).values(
                    is_active=False, logout_time=datetime.utcnow()))
                await session.commit()
                return JSONResponse({"detail": "انتهت الجلسة بسبب الخمول لمدة 10 دقائق؛ سجّل الدخول مجددًا", "code": "idle_timeout"}, status_code=401)
            # Any authenticated contact counts as activity and renews the window.
            await session.execute(update(UserSessionModel).where(UserSessionModel.id == active).values(
                last_activity=datetime.utcnow()))
            await session.commit()
            user = await UserRepository(session).get_by_id(uid)
            if not user or not user.is_active:
                return await deny(403, "Account unavailable", "account_unavailable")
            roles = (await session.execute(text("SELECT r.name, r.is_system FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=:uid"), {"uid": uid.hex})).all()
            permissions = (await session.execute(text(
                "SELECT p.code,ur.scope,rp.id AS role_permission_id,rpus.unit_id "
                "FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id "
                "JOIN user_roles ur ON ur.role_id=rp.role_id "
                "LEFT JOIN role_permission_unit_scopes rpus ON rpus.role_permission_id=rp.id "
                "WHERE ur.user_id=:uid"
            ), {"uid": uid.hex})).mappings().all()
            request.state.user = user
            request.state.user_id = uid
            request.state.username = user.username
            request.state.session_id = active
            request.state.permissions = {grant["code"] for grant in permissions}
            request.state.permission_scopes = {}
            request.state.permission_global_scopes = {}
            request.state.permission_unit_scopes = {}
            for grant in permissions:
                code, scope, unit_id = grant["code"], grant["scope"], grant["unit_id"]
                request.state.permission_scopes.setdefault(code, set()).add(scope)
                if unit_id is None:
                    request.state.permission_global_scopes.setdefault(code, set()).add(scope)
                else:
                    request.state.permission_unit_scopes.setdefault(code, set()).add(unit_id)
            request.state.is_admin = any(name == "admin" and system in (1, True) for name, system in roles)
            request.state.scopes = set((await session.execute(text("SELECT scope FROM user_roles WHERE user_id=:uid"), {"uid": uid.hex})).scalars()) or {"self"}
            from modules.module_settings.application.center_service import system_value
            if not request.state.is_admin and await system_value(session, 'core.maintenance'):
                return JSONResponse({'detail':'النظام في وضع الصيانة؛ حاول لاحقًا'}, status_code=503)
            from modules.module_settings.application.module_policy import enabled_modules
            enabled=await enabled_modules(session)
        from core.module_registry import registry
        for module in registry.modules.values():
            if not enabled[module.code] and any(request.url.path == p or request.url.path.startswith(p + "/") for p in module.api_prefixes):
                return JSONResponse({"detail": "Module disabled"}, status_code=404)
            if module.permission and any(request.url.path == p or request.url.path.startswith(p + "/") for p in module.api_prefixes) and not allowed(request, module.permission):
                return await deny(403, "Module access denied", "module_permission_denied")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith(("/api/v1/roles", "/api/v1/permissions")) and not request.state.is_admin:
            return await deny(403, "Administrator required for access policy changes", "administrator_required")
        if request.url.path.startswith("/api/v1/audit/") and not request.url.path.startswith(("/api/v1/audit/logs", "/api/v1/audit/export")) and not request.state.is_admin:
            return await deny(403, "Administrator required for legacy audit endpoints", "administrator_required")
        permission = route_permission(request.url.path.rstrip("/"), request.method)
        request.state.scopes = request.state.permission_scopes.get(permission, {"self"})
        if permission and not allowed(request, permission):
            return await deny(403, "Permission denied", "route_permission_denied")
        return await call_next(request)
