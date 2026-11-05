"""Atomic protections for privileged accounts on SQLite."""
from fastapi import HTTPException
from sqlalchemy import text


async def protect_privileged_target(session, request, uid):
    privileged = await session.scalar(text("SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=:uid AND r.name='admin' AND r.is_system=1"), {"uid": uid.hex})
    if privileged and not request.state.is_admin:
        raise HTTPException(403, "System administrator accounts require administrator authority")


async def deactivate(session, uid):
    # Check and change within one write statement, so competing administrators
    # cannot both observe two administrators and deactivate each other.
    result = await session.execute(text("""
        UPDATE users SET is_active=0 WHERE id=:uid AND (
          NOT EXISTS (SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                      WHERE ur.user_id=:uid AND r.name='admin' AND r.is_system=1)
          OR (SELECT count(DISTINCT u.id) FROM users u JOIN user_roles ur ON ur.user_id=u.id
              JOIN roles r ON r.id=ur.role_id WHERE u.is_active=1 AND r.name='admin' AND r.is_system=1)>1
        )
    """), {"uid": uid.hex})
    if result.rowcount != 1:
        raise HTTPException(409, "Cannot deactivate the last active administrator")
