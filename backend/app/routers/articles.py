from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, Magazine, User
from app.schemas import ArticleWithMagazine, ShareCreate, ShareOut
from app.services.partage import (
    duree_demandee,
    obtenir_ou_creer_token_partage,
    peut_revoquer,
    revoquer_partage,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def echapper_like(terme: str) -> str:
    """Neutralise les jokers LIKE fournis par l'utilisateur.

    Sans cela, « % » et « _ » saisis dans le champ de recherche sont
    interprétés par PostgreSQL : « % » seul renvoie toute la table, et un
    terme truffé de jokers force un balayage complet.
    L'antislash est échappé en premier, sinon il neutraliserait les
    échappements ajoutés ensuite.
    """
    return terme.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[ArticleWithMagazine])
def list_articles(
    q: str | None = Query(
        None,
        max_length=200,
        description="Filter by article title (case-insensitive substring)",
    ),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    unassigned: bool = Query(False, description="Restrict to magazines with no collection assigned"),
    page: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            Article,
            Magazine.title,
            Magazine.issue_number,
            Magazine.issue_month_label,
            Magazine.publication_date,
            Collection.name,
        )
        .join(Magazine, Magazine.id == Article.magazine_id)
        .outerjoin(Collection, Collection.id == Magazine.collection_id)
    )
    if q:
        query = query.filter(Article.title.ilike(f"%{echapper_like(q)}%", escape="\\"))
    if unassigned:
        query = query.filter(Magazine.collection_id.is_(None))
    elif collection_id is not None:
        query = query.filter(Magazine.collection_id == collection_id)
    rows = (
        query.order_by(Magazine.title, Magazine.publication_date.desc().nulls_last(), Article.start_page)
        .offset(page * limit)
        .limit(limit)
        .all()
    )
    return [
        ArticleWithMagazine(
            id=article.id,
            magazine_id=article.magazine_id,
            title=article.title,
            start_page=article.start_page,
            end_page=article.end_page,
            magazine_title=magazine_title,
            magazine_issue_number=magazine_issue_number,
            magazine_issue_month=magazine_issue_month,
            magazine_publication_date=magazine_publication_date,
            magazine_collection_name=magazine_collection_name,
        )
        for (
            article,
            magazine_title,
            magazine_issue_number,
            magazine_issue_month,
            magazine_publication_date,
            magazine_collection_name,
        ) in rows
    ]


@router.post("/{article_id}/share", response_model=ShareOut)
def share_article(
    article_id: int,
    payload: ShareCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cree ou retrouve le lien de partage public d'un article.

    Idempotent : rejouer l'appel sur un article deja partage renvoie le
    meme token tant qu'il n'a pas expire ni ete revoque — un seul lien
    valide par article, jamais une liste qui grossit a chaque clic.
    """
    article = _get_article_or_404(article_id, db)
    token = obtenir_ou_creer_token_partage(db, Article, article, user.id, duree_demandee(payload))
    return ShareOut(token=token, expires_at=article.share_expires_at)


@router.delete("/{article_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def revoke_article_share(article_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revoque le lien de partage de l'article : auteur du lien ou admin."""
    article = _get_article_or_404(article_id, db)
    if not article.share_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active share link")
    if not peut_revoquer(user, article):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to revoke this link")
    revoquer_partage(db, article)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_article_or_404(article_id: int, db: Session) -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article
