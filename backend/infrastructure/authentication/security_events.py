"""Security events + in-app alerts for suspicious authentication activity."""
from uuid import UUID


async def record(session, kind: str, user_id: UUID | None, ip: str, agent: str, detail: str = ""):
    from sqlalchemy import text
    await session.execute(text(
        "INSERT INTO security_events(user_id,kind,ip_address,user_agent,detail) VALUES(:u,:k,:ip,:ag,:d)"),
        {"u": user_id.hex if user_id else None, "k": kind, "ip": ip[:45], "ag": (agent or "")[:255], "d": detail[:500]})


async def last_ip(session, user_id: UUID) -> str | None:
    from sqlalchemy import text
    return await session.scalar(text(
        "SELECT ip_address FROM security_events WHERE user_id=:u AND kind='login' ORDER BY id DESC LIMIT 1"),
        {"u": user_id.hex})


async def alert(session, recipient: UUID, code: str, variables: dict, event_key: str):
    try:
        from modules.module_notifications.application.notification_service import NotificationService
        await NotificationService(session).emit(code, recipient, variables, event_key)
    except Exception:
        pass  # alerts are best-effort; a missing template must not break login
