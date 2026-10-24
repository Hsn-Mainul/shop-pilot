from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"

# Using bcrypt directly rather than through passlib: passlib 1.7.4 (its last
# release) detects the bcrypt backend via an `__about__` attribute that was
# removed in bcrypt>=4.1, so passlib+modern bcrypt raises a spurious
# "password cannot be longer than 72 bytes" error on every hash/verify call.
# bcrypt's own 72-byte input limit is still enforced below, explicitly.


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


def create_token(subject: str, extra_claims: dict[str, Any], expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": subject, "exp": expire, **extra_claims}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: str, shop_id: str, role: str) -> str:
    return create_token(
        subject=user_id,
        extra_claims={"shop_id": shop_id, "role": role, "type": "access"},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    return create_token(
        subject=user_id,
        extra_claims={"type": "refresh"},
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
