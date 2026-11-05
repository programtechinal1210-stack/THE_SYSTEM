"""Best-effort persistence for authorization rejections outside endpoint transactions."""
import logging
from uuid import uuid4

from infrastructure.audit.services.event_writer import write_event
from infrastructure.database.db_context import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Only authorization outcomes are recorded as REQUEST_DENIED. Business conflicts
# (409), validation failures (422) and server faults (5xx) are not security
# denials and must never be labelled as such in the audit trail.
DENIAL_STATUS_CODES = frozenset({401, 403})


def ensure_request_id(request) -> str:
    """Guarantee a correlation id even when the request is rejected before logging."""
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = uuid4().hex
        request.state.request_id = request_id
    return request_id


async def write_denial_event(request, status_code: int, reason: str) -> None:
    """Record one rejected write without ever changing the original denial response."""
    if status_code not in DENIAL_STATUS_CODES:
        return
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if getattr(request.state, "request_denied_audited", False):
        return

    request.state.request_denied_audited = True
    request.state.audit_details = {
        "entity_type": "request",
        "summary": "Authorization denied",
        "reference": {"reason": reason},
    }
    ensure_request_id(request)
    try:
        async with AsyncSessionLocal() as session:
            await write_event(session, request, "REQUEST_DENIED", status_code)
            await session.commit()
    except Exception:
        logger.exception(
            "Security audit persistence failed for denied %s %s (status=%s)",
            request.method,
            request.url.path,
            status_code,
        )