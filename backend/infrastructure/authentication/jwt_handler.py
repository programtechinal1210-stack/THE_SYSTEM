# infrastructure/authentication/jwt_handler.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import secrets
from uuid import uuid4
from core.config import settings


class JWTHandler:
    # Process-wide kid -> secret cache, refreshed lazily from jwt_keys.
    _key_cache: dict[str, str] = {}

    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.JWT_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.JWT_REFRESH_EXPIRE_DAYS

    @classmethod
    async def refresh_key_cache(cls, session) -> None:
        from sqlalchemy import text
        try:
            rows = (await session.execute(
                text("SELECT kid,secret FROM jwt_keys WHERE retired_at IS NULL"))).all()
            for kid, secret in rows:
                cls._key_cache[kid] = secret
        except Exception:
            pass

    @classmethod
    def secret_for_kid(cls, kid: str | None) -> str | None:
        if not kid or kid == "legacy":
            return None
        return cls._key_cache.get(kid)

    # ---- key rotation (kid) ----
    @staticmethod
    def _active_kid(session) -> str:
        """Current signing key id; lazily creates the first key. Sync helper for session access."""
        return "legacy"

    async def signing_secret(self, session, kid: str) -> str:
        if session is None or kid in (None, "legacy"):
            return self.secret_key
        from sqlalchemy import text
        row = await session.scalar(text("SELECT secret FROM jwt_keys WHERE kid=:k AND retired_at IS NULL"), {"k": kid})
        return row or self.secret_key

    @staticmethod
    async def ensure_active_key(session) -> str:
        """Create the first jwt_keys row on demand; returns its kid."""
        from sqlalchemy import text
        kid = await session.scalar(text("SELECT kid FROM jwt_keys WHERE retired_at IS NULL ORDER BY created_at DESC LIMIT 1"))
        if kid:
            return kid
        kid = "k-" + secrets.token_hex(4)
        await session.execute(text("INSERT INTO jwt_keys(kid,secret) VALUES(:kid,:secret)"),
                              {"kid": kid, "secret": secrets.token_urlsafe(48)})
        return kid

    def _encode(self, payload: Dict[str, Any], secret: str) -> str:
        headers = {"kid": payload.get("kid", "legacy")}
        return jwt.encode(payload, secret, algorithm=self.algorithm, headers=headers)

    def create_access_token(self, data: Dict[str, Any], secret: Optional[str] = None, kid: str = "legacy") -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access", "jti": str(uuid4()), "kid": kid})
        return self._encode(to_encode, secret or self.secret_key)

    def create_refresh_token(self, data: Dict[str, Any], secret: Optional[str] = None, kid: str = "legacy") -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid4()), "kid": kid})
        return self._encode(to_encode, secret or self.secret_key)

    @staticmethod
    def token_fingerprint(token: str) -> str:
        """SHA-256 of the raw token: what is stored in DB instead of the token itself."""
        import hashlib
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify_token(self, token: str, secret: Optional[str] = None) -> Dict[str, Any]:
        if secret is not None:
            try:
                return jwt.decode(token, secret, algorithms=[self.algorithm],
                                  options={"require": ["exp"]}, leeway=30)
            except jwt.ExpiredSignatureError:
                raise ValueError("Token has expired")
            except jwt.InvalidTokenError:
                raise ValueError("Invalid token")
        # kid-aware: try the key id from the unverified header first, then legacy + active keys.
        candidates: list[str] = []
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            if kid:
                candidates.append(kid)
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
        candidates += [k for k in ("legacy",) if k not in candidates]
        last_error: Exception | None = None
        for kid in candidates:
            try:
                sec = self._key_cache.get(kid) if hasattr(self, "_key_cache") else None
                return jwt.decode(token, sec or self.secret_key, algorithms=[self.algorithm],
                                  options={"require": ["exp"]}, leeway=30)
            except jwt.ExpiredSignatureError:
                raise ValueError("Token has expired")
            except jwt.InvalidTokenError as exc:
                last_error = exc
        raise ValueError("Invalid token")

    def verify_with_session(self, token: str, session_secret: Optional[str], token_kid: Optional[str]) -> Dict[str, Any]:
        """Verify using the session's key when available (rotation-aware), else legacy secret."""
        if session_secret:
            return self.verify_token(token, session_secret)
        if token_kid and token_kid != "legacy" and hasattr(self, "_key_cache"):
            cached = self._key_cache.get(token_kid)
            if cached:
                return self.verify_token(token, cached)
        return self.verify_token(token)
