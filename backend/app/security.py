import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Algorithme figé dans le code plutôt que piloté par l'environnement : une
# variable mal renseignée (ou mise à "none") affaiblirait la signature de tous
# les jetons sans que rien ne le signale au démarrage.
JWT_ALGORITHM = "HS256"

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
    maintenant = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=settings.jwt_expire_minutes),
        # Identifiant unique du jeton : sans lui, deux connexions successives
        # dans la même seconde produisent des jetons identiques, et il n'existe
        # aucune prise pour une future liste de révocation.
        "jti": uuid.uuid4().hex,
        "pwf": password_fingerprint(password_hash),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return payload
