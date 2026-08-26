import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def password_fingerprint(password_hash: str) -> str:
    """Derive a short, non-reversible fingerprint of a password hash to embed in JWTs.

    Changing a user's password changes password_hash, which changes this
    fingerprint, which invalidates every token issued before the change.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_access_token(subject: str, password_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire, "pwf": password_fingerprint(password_hash)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return payload
