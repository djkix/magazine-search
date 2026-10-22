import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings

# 32 octets -> 43 caracteres en base64 URL-safe : largement hors de portee
# d'une attaque par force brute sur l'URL.
TAILLE_TOKEN_OCTETS = 32


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def filtre_lien_valide(model, token: str, instant: datetime | None = None):
    """Conditions SQL d'un lien servable : bon jeton ET non expiré. Un lien
    sans date d'expiration n'est jamais servi (échec fermé)."""
    instant = instant or maintenant()
    return (
        model.share_token == token,
        model.share_expires_at.is_not(None),
        model.share_expires_at > instant,
    )


def obtenir_ou_creer_token_partage(
    db: Session, model, instance, createur_id: int | None = None, duree_jours: int | None = None
) -> str:
    """Assure que `instance` porte un lien de partage valide, et renvoie son jeton.

    Partagé par le partage d'article et de numéro entier (Article et
    Magazine ont chacun leurs propres colonnes share_*). Un lien encore
    valide est renvoyé tel quel, sans prolonger son expiration ni changer
    son auteur : un seul lien actif par ressource, jamais une liste qui
    grossit à chaque clic. Un lien absent, révoqué ou expiré est remplacé
    par un nouveau jeton — l'ancien ne redevient jamais valide.

    Protégé d'une course entre deux clics presque simultanés : la mise à
    jour est conditionnée à l'absence de lien valide, un seul des deux
    UPDATE concurrents peut matcher la ligne — l'autre la trouve déjà
    renseignée. On relit ensuite la valeur réellement persistée, jamais
    celle générée localement, pour que les deux appels renvoient le même
    lien.
    """
    settings = get_settings()
    instant = maintenant()
    duree = duree_jours or settings.share_link_default_days
    db.query(model).filter(
        model.id == instance.id,
        or_(
            model.share_token.is_(None),
            model.share_expires_at.is_(None),
            model.share_expires_at <= instant,
        ),
    ).update(
        {
            "share_token": secrets.token_urlsafe(TAILLE_TOKEN_OCTETS),
            "share_expires_at": instant + timedelta(days=duree),
            "share_created_by_id": createur_id,
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(instance)
    return instance.share_token


def peut_revoquer(user, instance) -> bool:
    """L'auteur du lien, ou un administrateur. Les liens émis avant le suivi
    de l'auteur (share_created_by_id nul) ne sont révocables que par un
    administrateur."""
    return bool(user.is_admin) or (
        instance.share_created_by_id is not None and instance.share_created_by_id == user.id
    )


def revoquer_partage(db: Session, instance) -> None:
    """Coupe le lien immédiatement. Un partage ultérieur générera un jeton
    différent : l'URL révoquée ne redevient jamais valide."""
    instance.share_token = None
    instance.share_expires_at = None
    instance.share_created_by_id = None
    db.commit()


def duree_demandee(payload) -> int | None:
    """Durée demandée à la création, bornée par SHARE_LINK_MAX_DAYS."""
    if payload is None or payload.days is None:
        return None
    plafond = get_settings().share_link_max_days
    if payload.days > plafond:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Durée maximale : {plafond} jours",
        )
    return payload.days
