from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _b64decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw.encode("utf-8"))


def hash_password(password: str, iterations: int = 390_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, raw_iterations, salt_raw, digest_raw = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(raw_iterations)
        salt = _b64decode(salt_raw)
        expected = _b64decode(digest_raw)
    except ValueError:
        # Covers a malformed field count, a non-integer iteration count, and
        # binascii.Error (a ValueError subclass) from a corrupt base64 field.
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


# Verified against when a login names a user that does not exist, so the
# response time does not reveal which usernames are real.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def verify_password_or_dummy(password: str, encoded: str | None) -> bool:
    """Verify *password*, spending the same work when the user is unknown."""
    if encoded is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return False
    return verify_password(password, encoded)


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class SecretCipher:
    key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "_fernet", Fernet(self.key.encode("utf-8")))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        try:
            raw = self._fernet.decrypt(encrypted.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("Secret decryption failed; invalid key or ciphertext.") from exc
        return raw.decode("utf-8")
