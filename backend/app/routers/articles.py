from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Magazine
from app.schemas import ArticleWithMagazine

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ArticleWithMagazine])
def list_articles(
    q: str | None = Query(None, description="Filter by article title (case-insensitive substring)"),
    page: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Article, Magazine.title, Magazine.issue_number).join(Magazine, Magazine.id == Article.magazine_id)
    if q:
        query = query.filter(Article.title.ilike(f"%{q}%"))
    rows = (
        query.order_by(Magazine.publication_date.desc().nulls_last(), Article.start_page)
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
        )
        for article, magazine_title, magazine_issue_number in rows
    ]
