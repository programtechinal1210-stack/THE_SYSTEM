"""Time-based one-time passwords (RFC 6238) on the standard library only.

No new dependency: HMAC-SHA1 + base32 secrets, 30s step, 6 digits,
±1 step acceptance window for clock skew.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


STEP = 30
DIGITS = 6
WINDOW = 1


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def provisioning_uri(secret: str, username: str, issuer: str = "THE_SYSTEM") -> str:
    return (f"otpauth://totp/{quote(issuer)}:{quote(username)}"
            f"?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** DIGITS)).zfill(DIGITS)


def verify(secret: str, code: str, at: float | None = None) -> bool:
    code = (code or "").strip()
    if not code.isdigit() or len(code) != DIGITS:
        return False
    counter = int((time.time() if at is None else at) // STEP)
    for delta in range(-WINDOW, WINDOW + 1):
        if hmac.compare_digest(_code(secret, counter + delta), code):
            return True
    return False
