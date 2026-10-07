import secrets

from sqlalchemy.orm import Session

# 32 octets -> 43 caracteres en base64 URL-safe : largement hors de portee
# d'une attaque par force brute sur l'URL.
TAILLE_TOKEN_OCTETS = 32


def obtenir_ou_creer_token_partage(db: Session, model, instance) -> str:
    """Assure que `instance.share_token` est renseigné, et renvoie sa valeur.

    Partagé par le partage d'article et de numéro entier (Article et
    Magazine ont chacun leur propre colonne share_token). Idempotent et
    protégé d'une course entre deux clics presque simultanés : la mise à
    jour est conditionnée à WHERE share_token IS NULL, un seul des deux
    UPDATE concurrents peut matcher la ligne — l'autre la trouve déjà
    renseignée. On relit ensuite la valeur réellement persistée, jamais
    celle générée localement, pour que les deux appels renvoient le même
    lien plutôt que l'un des deux ne pointe vers un jeton immédiatement
    écrasé.
    """
    if not instance.share_token:
        db.query(model).filter(model.id == instance.id, model.share_token.is_(None)).update(
            {"share_token": secrets.token_urlsafe(TAILLE_TOKEN_OCTETS)}
        )
        db.commit()
        db.refresh(instance)
    return instance.share_token
