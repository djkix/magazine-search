import secrets

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.config import get_settings
from app.models import User
from app.security import hash_password

settings = get_settings()


class GoogleAuthInvalide(Exception):
    """Jeton Google invalide, ou compte qui ne peut pas se connecter ainsi."""


def verifier_id_token(credential: str) -> dict:
    """Vérifie la signature, l'audience et l'expiration du jeton d'identité
    Google. Lève GoogleAuthInvalide pour toute défaillance : jeton expiré,
    signature invalide, destiné à un autre client, etc. — verify_oauth2_token
    fait déjà tout ce travail, on ne fait que traduire son exception."""
    try:
        return google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), audience=settings.google_client_id
        )
    except ValueError as exc:
        raise GoogleAuthInvalide(f"Jeton Google invalide : {exc}") from exc


def authentifier_ou_creer(db: Session, credential: str) -> User:
    """Vérifie le jeton Google puis retrouve ou crée l'utilisateur
    correspondant, par EMAIL (pas par google_sub) : un compte créé à la
    main par mot de passe et un login Google ultérieur avec le même email
    doivent fusionner sur la même ligne, pas créer un doublon."""
    claims = verifier_id_token(credential)

    if not claims.get("email_verified"):
        # Google autorise des comptes à email non vérifié : les accepter
        # reviendrait à authentifier quelqu'un sur une adresse qu'il ne
        # contrôle pas forcément.
        raise GoogleAuthInvalide("Adresse Google non vérifiée.")

    email = claims["email"]
    sub = claims["sub"]

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            display_name=claims.get("name") or email.split("@")[0],
            # Mot de passe aléatoire, jamais révélé : ce compte ne se
            # connecte que via Google, sauf si un admin lui fixe un mot de
            # passe plus tard depuis le panneau d'administration existant.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            google_sub=sub,
            is_admin=False,
            is_active=True,
        )
        db.add(user)
    else:
        if not user.is_active:
            # Une désactivation manuelle par l'admin reste la plus forte
            # autorité : Google ne doit pas pouvoir la contourner.
            raise GoogleAuthInvalide("Compte désactivé.")
        if user.google_sub is None:
            user.google_sub = sub

    user.last_login = func.now()
    db.commit()
    return user
