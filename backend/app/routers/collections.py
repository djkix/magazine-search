from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Collection, Magazine, Theme
from app.schemas import CollectionSummary, LibraryOverview, MagazineThemeOut, TagOut

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


@router.get("/{collection_id}/themes", response_model=list[MagazineThemeOut])
def get_collection_themes(collection_id: int, db: Session = Depends(get_db)):
    """Themes assigned (at indexing time) to any magazine in this
    collection, each with how many of the collection's magazines carry it."""
    rows = (
        db.query(Theme.id, Theme.name, func.count(Magazine.id.distinct()))
        .join(Theme.magazines)
        .filter(Magazine.collection_id == collection_id)
        .group_by(Theme.id, Theme.name)
        .order_by(func.count(Magazine.id.distinct()).desc(), Theme.name)
        .all()
    )
    return [MagazineThemeOut(id=theme_id, name=name, magazine_count=count) for theme_id, name, count in rows]
