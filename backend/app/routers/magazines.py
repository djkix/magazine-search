from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, IssueType, Magazine, Page, ScanStatus, collection_tags, theme_magazines
from app.schemas import ArticleOut, MagazineOut, PageOut, TagOut

router = APIRouter(dependencies=[Depends(get_current_user)])
settings = get_settings()


def _get_magazine_or_404(magazine_id: int, db: Session) -> Magazine:
    magazine = db.get(Magazine, magazine_id)
    if not magazine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    return magazine


def _to_magazine_out(magazine: Magazine, page_count: int, article_count: int = 0) -> MagazineOut:
    out = MagazineOut.model_validate(magazine)
    out.page_count = page_count
    out.article_count = article_count
    out.collection_name = magazine.collection.name if magazine.collection else None
    out.tags = [TagOut(id=t.id, name=t.name) for t in magazine.collection.tags] if magazine.collection else []
    out.issue_month = magazine.issue_month_label
    return out


def _resolve_pdf_path(magazine: Magazine) -> Path:
    processed_path = Path(settings.processed_dir) / f"{magazine.id}.pdf"
    if processed_path.exists():
        return processed_path
    return Path(settings.nas_mount_path) / magazine.file_path


def _apply_magazine_filters(
    query,
    tag_id: int | None,
    collection_id: int | None,
    theme_id: int | None,
    unassigned: bool,
    year: int | None,
    issue_type: IssueType | None = None,
    scan_status: list[ScanStatus] | None = None,
    has_sommaire: bool | None = None,
):
    if unassigned:
        query = query.filter(Magazine.collection_id.is_(None))
    elif collection_id is not None:
        query = query.filter(Magazine.collection_id == collection_id)
    elif tag_id is not None:
        query = (
            query.join(Collection, Collection.id == Magazine.collection_id)
            .join(collection_tags, collection_tags.c.collection_id == Collection.id)
            .filter(collection_tags.c.tag_id == tag_id)
        )
    if theme_id is not None:
        query = query.join(theme_magazines, theme_magazines.c.magazine_id == Magazine.id).filter(
            theme_magazines.c.theme_id == theme_id
        )
    if year is not None:
        query = query.filter(func.extract("year", Magazine.publication_date) == year)
    if issue_type is not None:
        query = query.filter(Magazine.issue_type == issue_type)
    if scan_status:
        query = query.filter(Magazine.scan_status.in_(scan_status))
    if has_sommaire is not None:
        magazine_ids_with_sommaire = query.session.query(Article.magazine_id).distinct()
        if has_sommaire:
            query = query.filter(Magazine.id.in_(magazine_ids_with_sommaire))
        else:
            query = query.filter(~Magazine.id.in_(magazine_ids_with_sommaire))
    return query


@router.get("/count")
def count_magazines(
    tag_id: int | None = Query(None, description="Restrict to magazines whose collection carries this tag"),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    theme_id: int | None = Query(None, description="Restrict to magazines assigned this theme"),
    unassigned: bool = Query(False, description="Restrict to magazines with no collection assigned"),
    year: int | None = Query(None, description="Restrict to magazines published in this year"),
    issue_type: IssueType | None = Query(None, description="Restrict to magazines of this issue type"),
    scan_status: list[ScanStatus] | None = Query(None, description="Restrict to magazines with one of these scan statuses (repeat the param for several)"),
    has_sommaire: bool | None = Query(None, description="Restrict to magazines with (true) or without (false) at least one article"),
    db: Session = Depends(get_db),
):
    query = _apply_magazine_filters(
        db.query(Magazine.id), tag_id, collection_id, theme_id, unassigned, year, issue_type, scan_status, has_sommaire
    )
    return {"total": query.distinct().count()}


@router.get("/facets")
def get_magazine_facets(
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    unassigned: bool = Query(False, description="Restrict to magazines with no collection assigned"),
    db: Session = Depends(get_db),
):
    """Distinct publication years (with counts) and HS/SP counts among the
    matching magazines - used to build a year/type filter sidebar."""
    query = _apply_magazine_filters(
        db.query(Magazine.publication_date, Magazine.issue_type), None, collection_id, None, unassigned, None
    )
    years: dict[int, int] = {}
    hs_count = 0
    sp_count = 0
    for publication_date, issue_type in query.all():
        if publication_date:
            years[publication_date.year] = years.get(publication_date.year, 0) + 1
        if issue_type == IssueType.hs:
            hs_count += 1
        elif issue_type == IssueType.sp:
            sp_count += 1

    return {
        "years": [{"year": year, "count": count} for year, count in sorted(years.items(), reverse=True)],
        "hs_count": hs_count,
        "sp_count": sp_count,
    }


@router.get("", response_model=list[MagazineOut])
def list_magazines(
    page: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    sort: str = Query("date", pattern="^(date|added|updated)$"),
    tag_id: int | None = Query(None, description="Restrict to magazines whose collection carries this tag"),
    collection_id: int | None = Query(None, description="Restrict to magazines in this collection"),
    theme_id: int | None = Query(None, description="Restrict to magazines assigned this theme"),
    unassigned: bool = Query(False, description="Restrict to magazines with no collection assigned"),
    year: int | None = Query(None, description="Restrict to magazines published in this year"),
    issue_type: IssueType | None = Query(None, description="Restrict to magazines of this issue type"),
    scan_status: list[ScanStatus] | None = Query(None, description="Restrict to magazines with one of these scan statuses (repeat the param for several)"),
    has_sommaire: bool | None = Query(None, description="Restrict to magazines with (true) or without (false) at least one article"),
    db: Session = Depends(get_db),
):
    if sort == "added":
        order = Magazine.created_at.desc()
    elif sort == "updated":
        order = Magazine.updated_at.desc()
    else:
        order = Magazine.publication_date.desc().nulls_last()
    query = db.query(Magazine, func.count(Page.id)).outerjoin(Page, Page.magazine_id == Magazine.id)
    query = _apply_magazine_filters(
        query, tag_id, collection_id, theme_id, unassigned, year, issue_type, scan_status, has_sommaire
    )
    rows = query.group_by(Magazine.id).order_by(order, Magazine.title).offset(page * limit).limit(limit).all()

    magazine_ids = [magazine.id for magazine, _page_count in rows]
    article_counts = dict(
        db.query(Article.magazine_id, func.count(Article.id))
        .filter(Article.magazine_id.in_(magazine_ids))
        .group_by(Article.magazine_id)
        .all()
    )
    return [
        _to_magazine_out(magazine, page_count, article_counts.get(magazine.id, 0)) for magazine, page_count in rows
    ]


@router.get("/{magazine_id}", response_model=MagazineOut)
def get_magazine(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    return _to_magazine_out(magazine, len(magazine.pages), len(magazine.articles))


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
