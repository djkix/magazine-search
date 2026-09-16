from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, Magazine, Subtheme, subtheme_articles
from app.schemas import CollectionSummary, LibraryOverview, SubthemeOut, TagOut

router = APIRouter(dependencies=[Depends(get_current_user)])


def _summarize(magazines: list[Magazine]) -> tuple[int, int | None]:
    cover = next((m.id for m in magazines if m.cover_thumbnail_path), None)
    return len(magazines), cover


@router.get("", response_model=LibraryOverview)
def library_overview(db: Session = Depends(get_db)):
    """Level-1 view of the library: every collection with its magazine count
    and a representative cover, plus a bucket for magazines not yet assigned
    to any collection."""
    collections = db.query(Collection).order_by(Collection.name).all()
    magazines = (
        db.query(Magazine)
        .order_by(Magazine.publication_date.desc().nulls_last(), Magazine.created_at.desc())
        .all()
    )

    by_collection: dict[int | None, list[Magazine]] = {}
    for magazine in magazines:
        by_collection.setdefault(magazine.collection_id, []).append(magazine)

    summaries = []
    for collection in collections:
        count, cover_id = _summarize(by_collection.get(collection.id, []))
        summaries.append(
            CollectionSummary(
                id=collection.id,
                name=collection.name,
                tags=[TagOut(id=t.id, name=t.name) for t in collection.tags],
                magazine_count=count,
                cover_magazine_id=cover_id,
            )
        )

    unassigned_count, unassigned_cover = _summarize(by_collection.get(None, []))

    return LibraryOverview(
        collections=summaries,
        unassigned_count=unassigned_count,
        unassigned_cover_magazine_id=unassigned_cover,
    )


# « GET /collections/{id}/themes » a été retiré en même temps que son jumeau
# « GET /api/themes » : il comptait les NUMÉROS portant une étiquette Gemini,
# table qui n'est plus alimentée. La vue « Par thématique » d'une collection
# s'appuie désormais sur /collections/{id}/subthemes, juste en dessous.


@router.get("/{collection_id}/subthemes", response_model=list[SubthemeOut])
def get_collection_subthemes(collection_id: int, db: Session = Depends(get_db)):
    """Sous-thématiques présentes dans les articles de cette collection.

    Remplace `/{collection_id}/themes`, qui comptait les NUMÉROS portant une
    étiquette posée par Gemini. Ici on compte les ARTICLES rattachés par la
    taxonomie : ni la même granularité, ni la même source. Le thémage par
    numéro n'étant plus alimenté, l'ancien endpoint renvoyait un résultat qui
    se serait figé sur les seuls numéros déjà traités.

    Les articles sont comptés DISTINCTS : un même article peut relever de
    plusieurs sous-thématiques, mais il ne doit peser qu'une fois dans
    chacune.
    """
    rows = (
        db.query(Subtheme.id, Subtheme.name, func.count(Article.id.distinct()))
        .join(subtheme_articles, subtheme_articles.c.subtheme_id == Subtheme.id)
        .join(Article, Article.id == subtheme_articles.c.article_id)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .filter(Magazine.collection_id == collection_id)
        .group_by(Subtheme.id, Subtheme.name)
        .order_by(func.count(Article.id.distinct()).desc(), Subtheme.name)
        .all()
    )
    return [SubthemeOut(id=sid, name=name, article_count=count) for sid, name, count in rows]
