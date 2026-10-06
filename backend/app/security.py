from __future__ import annotations

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

password_hasher = PasswordHasher()
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_initial_password(full_name: str, registration_number: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]", "", full_name.strip())
    registration = registration_number.strip()
    if not name or not registration:
        raise ValueError("A name and registration number are required.")
    return f"{name}{registration}"


def create_session_token(secret: str, user_id: int, role: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt="skillonex-session-v1")
    return serializer.dumps(
        {"sub": user_id, "role": role, "jti": secrets.token_urlsafe(18)}
    )


def read_session_token(secret: str, token: str) -> dict[str, int | str] | None:
    serializer = URLSafeTimedSerializer(secret, salt="skillonex-session-v1")
    try:
        payload = serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("sub"), int)
        or payload.get("role") not in {"admin", "student"}
        or not isinstance(payload.get("jti"), str)
    ):
        return None
    return {"sub": payload["sub"], "role": payload["role"]}
