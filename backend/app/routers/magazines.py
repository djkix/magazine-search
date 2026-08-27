from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, Magazine, Page
from app.schemas import ArticleOut, MagazineOut, PageOut

router = APIRouter(dependencies=[Depends(get_current_user)])
settings = get_settings()


def _get_magazine_or_404(magazine_id: int, db: Session) -> Magazine:
    magazine = db.get(Magazine, magazine_id)
    if not magazine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    return magazine


def _to_magazine_out(magazine: Magazine, page_count: int) -> MagazineOut:
    out = MagazineOut.model_validate(magazine)
    out.page_count = page_count
    out.collection_name = magazine.collection.name if magazine.collection else None
    out.category_id = magazine.collection.category_id if magazine.collection else None
    out.category_name = (
        magazine.collection.category.name if magazine.collection and magazine.collection.category else None
    )
    return out


def _resolve_pdf_path(magazine: Magazine) -> Path:
    processed_path = Path(settings.processed_dir) / f"{magazine.id}.pdf"
    if processed_path.exists():
        return processed_path
    return Path(settings.nas_mount_path) / magazine.file_path


@router.get("", response_model=list[MagazineOut])
def list_magazines(
    page: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    sort: str = Query("date", pattern="^(date|added)$"),
    category_id: int | None = Query(None, description="Restrict to magazines in this category"),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    db: Session = Depends(get_db),
):
    order = Magazine.created_at.desc() if sort == "added" else Magazine.publication_date.desc().nulls_last()
    query = db.query(Magazine, func.count(Page.id)).outerjoin(Page, Page.magazine_id == Magazine.id)
    if category_id is not None:
        query = query.join(Collection, Collection.id == Magazine.collection_id).filter(
            Collection.category_id == category_id
        )
    if collection_id is not None:
        query = query.filter(Magazine.collection_id == collection_id)
    rows = query.group_by(Magazine.id).order_by(order, Magazine.title).offset(page * limit).limit(limit).all()
    return [_to_magazine_out(magazine, page_count) for magazine, page_count in rows]


@router.get("/{magazine_id}", response_model=MagazineOut)
def get_magazine(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    return _to_magazine_out(magazine, len(magazine.pages))


@router.get("/{magazine_id}/articles", response_model=list[ArticleOut])
def list_magazine_articles(magazine_id: int, db: Session = Depends(get_db)):
    _get_magazine_or_404(magazine_id, db)
    return db.query(Article).filter(Article.magazine_id == magazine_id).order_by(Article.start_page).all()


@router.get("/{magazine_id}/pages/{page_number}", response_model=PageOut)
def get_page(magazine_id: int, page_number: int, db: Session = Depends(get_db)):
    page = (
        db.query(Page)
        .filter(Page.magazine_id == magazine_id, Page.page_number == page_number)
        .first()
    )
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


@router.get("/{magazine_id}/cover")
def get_cover(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    if not magazine.cover_thumbnail_path or not Path(magazine.cover_thumbnail_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover not available")
    return FileResponse(magazine.cover_thumbnail_path, media_type="image/png")


@router.get("/{magazine_id}/file")
def view_file(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    pdf_path = _resolve_pdf_path(magazine)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not available")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=magazine.filename,
        content_disposition_type="inline",
    )


@router.get("/{magazine_id}/download")
def download_file(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    pdf_path = _resolve_pdf_path(magazine)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not available")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=magazine.filename,
        content_disposition_type="attachment",
    )
