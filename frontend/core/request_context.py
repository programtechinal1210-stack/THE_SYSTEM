"""Request-local credentials for legacy services, never process-wide cache."""
from contextvars import ContextVar

current_request = ContextVar("core_current_request", default=None)


def current_session():
    request = current_request.get()
    return request.session if request is not None else None
