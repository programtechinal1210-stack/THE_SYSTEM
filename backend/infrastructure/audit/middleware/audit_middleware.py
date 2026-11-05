from starlette.middleware.base import BaseHTTPMiddleware
from infrastructure.audit.services.denial_writer import write_denial_event

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Success audit persistence belongs exclusively to get_session(), which
        # owns the endpoint transaction.  Authorization middleware can reject a
        # request before a dependency/session exists, so record only those
        # rejected write outcomes here in a separate completed audit transaction.
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and response.status_code >= 400
            and not getattr(request.state, "request_denied_audited", False)
        ):
            await write_denial_event(request, response.status_code, "rejected_after_endpoint_entry")
        return response
