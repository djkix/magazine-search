from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Category, Collection, Magazine
from app.schemas import ArticleWithMagazine

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ArticleWithMagazine])
def list_articles(
    q: str | None = Query(None, description="Filter by article title (case-insensitive substring)"),
    category_id: int | None = Query(None, description="Restrict to magazines in this category"),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    page: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Article, Magazine.title, Magazine.issue_number, Category.id, Category.name)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .outerjoin(Collection, Collection.id == Magazine.collection_id)
        .outerjoin(Category, Category.id == Collection.category_id)
    )
    if q:
        query = query.filter(Article.title.ilike(f"%{q}%"))
    if category_id is not None:
        query = query.filter(Collection.category_id == category_id)
    if collection_id is not None:
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
            category_id=cat_id,
            category_name=cat_name,
        )
        for article, magazine_title, magazine_issue_number, cat_id, cat_name in rows
    ]
