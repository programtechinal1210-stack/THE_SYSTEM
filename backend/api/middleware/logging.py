from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid4().hex
        logger.info(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(f"Response: {request.method} {request.url.path} - {response.status_code}")
        return response
