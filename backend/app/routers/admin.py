from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Article, Magazine, OcrStatus, Page, ScanStatus, User
from app.queue import ingestion_queue
from app.schemas import (
    AdminStatsResponse,
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    GeminiSettingsResponse,
    GeminiSettingsUpdate,
    LogEntry,
    MagazineOut,
    PasswordReset,
    RetryFailedResponse,
    ScanStatusResponse,
    ScanTriggerResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import hash_password
from app.services.logs import read_logs
from app.services.scan import get_scan_job_magazine_ids, run_scan
from app.services.toc import AVAILABLE_GEMINI_MODELS, get_gemini_model, set_gemini_model
from app.worker.tasks import process_magazine, retry_toc

router = APIRouter(dependencies=[Depends(get_current_admin)])


# ---- Users ----


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_admin:
        other_admins = db.query(User).filter(User.is_admin.is_(True), User.id != user_id).count()
        if other_admins == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete the last remaining admin")
    db.delete(user)
    db.commit()


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user


# ---- Scan ----


@router.post("/scan", response_model=ScanTriggerResponse)
def trigger_scan(db: Session = Depends(get_db)):
    try:
        job_id, new_files = run_scan(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ScanTriggerResponse(job_id=job_id, new_files_detected=new_files)


@router.post("/scan/retry-failed", response_model=RetryFailedResponse)
def retry_failed(db: Session = Depends(get_db)):
    failed = db.query(Magazine).filter(Magazine.scan_status == ScanStatus.failed).all()
    for magazine in failed:
        magazine.scan_status = ScanStatus.queued
        magazine.error_message = None
        db.commit()
        ingestion_queue.enqueue(process_magazine, magazine.id, job_timeout="30m")
    return RetryFailedResponse(retried=len(failed))


@router.post("/magazines/{magazine_id}/reprocess")
def reprocess_magazine(magazine_id: int, db: Session = Depends(get_db)):
    """Force a full re-run (OCR + indexing + TOC extraction) of an already-processed
    magazine, e.g. to pick up a feature added after it was first ingested."""
    magazine = db.get(Magazine, magazine_id)
    if not magazine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    magazine.scan_status = ScanStatus.queued
    magazine.error_message = None
    db.commit()
    ingestion_queue.enqueue(process_magazine, magazine_id, job_timeout="30m")
    return {"status": "queued"}


@router.get("/scan/{job_id}/status", response_model=ScanStatusResponse)
def scan_status(job_id: str, db: Session = Depends(get_db)):
    magazine_ids = get_scan_job_magazine_ids(job_id)
    if magazine_ids is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown scan job")

    counts = {status_value: 0 for status_value in ("detected", "processing", "done", "failed")}
    if magazine_ids:
        magazines = db.query(Magazine.scan_status).filter(Magazine.id.in_(magazine_ids)).all()
        for (magazine_status,) in magazines:
            if magazine_status in (ScanStatus.detected, ScanStatus.stable, ScanStatus.queued):
                counts["detected"] += 1
            elif magazine_status == ScanStatus.processing:
                counts["processing"] += 1
            elif magazine_status == ScanStatus.done:
                counts["done"] += 1
            elif magazine_status == ScanStatus.failed:
                counts["failed"] += 1

    finished = len(magazine_ids) == 0 or (counts["done"] + counts["failed"] == len(magazine_ids))

    return ScanStatusResponse(job_id=job_id, finished=finished, **counts)


# ---- Stats ----


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(db: Session = Depends(get_db)):
    counts = dict(db.query(Magazine.scan_status, func.count(Magazine.id)).group_by(Magazine.scan_status).all())

    def count_of(*statuses: ScanStatus) -> int:
        return sum(counts.get(s, 0) for s in statuses)

    recent_rows = (
        db.query(Magazine, func.count(Page.id))
        .outerjoin(Page, Page.magazine_id == Magazine.id)
        .group_by(Magazine.id)
        .order_by(Magazine.created_at.desc())
        .limit(10)
        .all()
    )
    recent = []
    for magazine, page_count in recent_rows:
        out = MagazineOut.model_validate(magazine)
        out.page_count = page_count
        recent.append(out)

    return AdminStatsResponse(
        total=sum(counts.values()),
        done=count_of(ScanStatus.done),
        processing=count_of(ScanStatus.processing),
        failed=count_of(ScanStatus.failed),
        pending=count_of(ScanStatus.detected, ScanStatus.stable, ScanStatus.queued),
        recent=recent,
    )


# ---- Logs ----


@router.get("/logs", response_model=list[LogEntry])
def get_logs(
    level: str | None = Query(None, description="Filter by log level, e.g. INFO, WARNING, ERROR"),
    component: str | None = Query(None, description="Filter by component: backend or worker"),
    limit: int = Query(200, ge=1, le=1000),
):
    return read_logs(level=level, component=component, limit=limit)


# ---- Articles (sommaires) ----


def _get_article_or_404(article_id: int, db: Session) -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


@router.post("/magazines/{magazine_id}/toc/retry")
def retry_toc_extraction(magazine_id: int, db: Session = Depends(get_db)):
    magazine = db.get(Magazine, magazine_id)
    if not magazine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    magazine.toc_status = OcrStatus.pending
    magazine.toc_error_message = None
    db.commit()
    ingestion_queue.enqueue(retry_toc, magazine_id, job_timeout="10m")
    return {"status": "queued"}


@router.post("/magazines/{magazine_id}/articles", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
def create_article(magazine_id: int, payload: ArticleCreate, db: Session = Depends(get_db)):
    magazine = db.get(Magazine, magazine_id)
    if not magazine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    article = Article(magazine_id=magazine_id, **payload.model_dump())
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.patch("/articles/{article_id}", response_model=ArticleOut)
def update_article(article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db)):
    article = _get_article_or_404(article_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    db.commit()
    db.refresh(article)
    return article


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = _get_article_or_404(article_id, db)
    db.delete(article)
    db.commit()


# ---- Settings ----


@router.get("/settings/gemini", response_model=GeminiSettingsResponse)
def get_gemini_settings(db: Session = Depends(get_db)):
    return GeminiSettingsResponse(model=get_gemini_model(db), available_models=AVAILABLE_GEMINI_MODELS)


@router.put("/settings/gemini", response_model=GeminiSettingsResponse)
def update_gemini_settings(payload: GeminiSettingsUpdate, db: Session = Depends(get_db)):
    set_gemini_model(db, payload.model)
    return GeminiSettingsResponse(model=get_gemini_model(db), available_models=AVAILABLE_GEMINI_MODELS)
