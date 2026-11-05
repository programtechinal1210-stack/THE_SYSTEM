import base64
import hashlib
import hmac
import secrets


class PasswordHasher:
    """
    Password hashing based entirely on Python's standard library.

    Format:
        pbkdf2_sha256$<iterations>$<salt_b64>$<digest_b64>

    This removes the historical passlib/bcrypt runtime dependency and is
    suitable for the fresh Core database, which has no legacy user hashes.
    """

    ALGORITHM = "sha256"
    ITERATIONS = 310_000
    SALT_BYTES = 16
    PREFIX = "pbkdf2_sha256"

    def needs_rehash(self, encoded: str) -> bool:
        try:
            prefix, iterations, *_ = encoded.split("$")
            return prefix != self.PREFIX or int(iterations) < self.ITERATIONS
        except (ValueError, TypeError, AttributeError):
            return True

    def hash(self, password: str) -> str:
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string")

        salt = secrets.token_bytes(self.SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            self.ALGORITHM,
            password.encode("utf-8"),
            salt,
            self.ITERATIONS,
        )

        salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
        digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

        return (
            f"{self.PREFIX}${self.ITERATIONS}$"
            f"{salt_b64}${digest_b64}"
        )

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        try:
            prefix, iterations_text, salt_b64, digest_b64 = hashed_password.split("$", 3)

            if prefix != self.PREFIX:
                return False

            iterations = int(iterations_text)

            def decode_unpadded(value: str) -> bytes:
                padding = "=" * (-len(value) % 4)
                return base64.urlsafe_b64decode(value + padding)

            salt = decode_unpadded(salt_b64)
            expected = decode_unpadded(digest_b64)

            actual = hashlib.pbkdf2_hmac(
                self.ALGORITHM,
                plain_password.encode("utf-8"),
                salt,
                iterations,
            )

            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError, base64.binascii.Error):
            return False
