from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except __import__("sqlalchemy").exc.IntegrityError:
            return JSONResponse(status_code=409, content={"detail": "Data conflicts with an existing record or relationship"})
        except __import__("sqlalchemy").exc.StatementError as e:
            logger.error("SQL statement error: %s", e)
            return JSONResponse(status_code=500, content={"detail": "Database statement error"})
        except Exception as e:
            logger.error("Unhandled exception type: %s", type(e).__name__)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
