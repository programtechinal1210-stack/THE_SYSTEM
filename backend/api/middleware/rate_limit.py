"""In-process token-bucket rate limiting + security headers (no new dependency).

Buckets are per (client IP, route-class); state lives in the rate_limits table
so limits survive restarts. Limits:
  login:    5 req / 60s per IP
  refresh:  30 req / 60s per IP
  default:  300 req / 60s per IP
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

LIMITS = (
    ("/api/v1/auth/login", 5, 60),
    ("/api/v1/auth/refresh", 30, 60),
    ("", 300, 60),
)


def _bucket(path: str) -> tuple[str, float, float]:
    for prefix, capacity, window in LIMITS:
        if path.startswith(prefix):
            return prefix or "default", float(capacity), float(window)
    return "default", 300.0, 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS" or request.url.path in ("/health",):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        prefix, capacity, window = _bucket(request.url.path)
        key = f"{ip}:{prefix or 'default'}"
        now = time.time()
        try:
            from infrastructure.database.db_context import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                row = (await session.execute(
                    text("SELECT bucket,tokens,updated_at FROM rate_limits WHERE bucket=:b"), {"b": key})).mappings().one_or_none()
                tokens = float(row["tokens"]) if row else capacity
                stamp = row["updated_at"] if row else None
                try:
                    from datetime import datetime
                    last = datetime.fromisoformat(stamp).timestamp() if stamp else now
                except (ValueError, TypeError):
                    last = now
                tokens = min(capacity, tokens + (now - last) * (capacity / window))
                if tokens < 1.0:
                    retry = max(1, int(window / capacity))
                    return JSONResponse({"detail": "طلبات كثيرة؛ حاول بعد قليل"}, status_code=429,
                                        headers={"Retry-After": str(retry)})
                tokens -= 1.0
                await session.execute(text(
                    "INSERT INTO rate_limits(bucket,tokens,updated_at) VALUES(:b,:t,CURRENT_TIMESTAMP) "
                    "ON CONFLICT(bucket) DO UPDATE SET tokens=excluded.tokens,updated_at=CURRENT_TIMESTAMP"),
                    {"b": key, "t": tokens})
                await session.commit()
        except Exception:
            pass  # rate limiting is best-effort; never block legitimate traffic on DB errors
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
