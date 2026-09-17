import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Article, Collection, Magazine, OcrStatus, Page, ScanStatus, Tag, User, subtheme_articles
from app.queue import ingestion_queue
from app.schemas import (
    AdminStatsResponse,
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    CollectionOut,
    CollectionTagsUpdate,
    CollectionUpdate,
    GeminiSettingsResponse,
    GeminiSettingsUpdate,
    LogEntry,
    MagazineOut,
    MagazineProgressResponse,
    OrphansExportOut,
    OrphansOut,
    PasswordReset,
    RetryFailedResponse,
    ScanStatusResponse,
    ScanTriggerResponse,
    TagCreate,
    TagOut,
    TagUpdate,
    CorpusExportOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import hash_password
from app.services.export_orphelins import charge_utile as charge_utile_orphelins
from app.services.export_orphelins import nom_de_fichier as nom_de_fichier_orphelins
from app.services.export_orphelins import resume as resume_orphelins
from app.services.export_thematiques import charge_utile, nom_de_fichier, resume
from app.services.import_sous_thematiques import (
    ImportInvalide,
    articles_orphelins,
    importer,
    recalculer_tout,
)
from app.services.themes_des_tags import propager
from app.services.logs import read_logs
from app.services.progress import get_magazine_progress
from app.services.gemini_quota import (
    get_gemini_daily_limit,
    get_gemini_rpm_limit,
    get_gemini_usage_today,
    set_gemini_daily_limit,
    set_gemini_rpm_limit,
)
from app.services.scan import get_latest_scan_job_id, get_scan_job_magazine_ids, run_collections_backfill, run_scan
from app.services.toc import AVAILABLE_GEMINI_MODELS, get_gemini_model, set_gemini_model
from app.worker.tasks import (
    handle_process_magazine_failure,
    process_magazine,
    process_pending_theme_batch,
    reindex_magazine,
    retry_toc,
)

logger = logging.getLogger("app")

router = APIRouter(dependencies=[Depends(get_current_admin)])


# ---- Users ----


@router.get("/users", response_model=list[UserOut])
def list_users(
    page: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    # Borne haute volontairement généreuse : sur une instance auto-hébergée le
    # nombre de comptes se compte en dizaines, la pagination ne change donc
    # rien en pratique — elle supprime seulement le cas où une table anormale
    # serait renvoyée d'un bloc.
    return db.query(User).order_by(User.created_at).offset(page * limit).limit(limit).all()


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
        # Le détail (chemin absolu du montage NAS) part dans les logs, pas
        # dans la réponse HTTP : il renseignerait l'arborescence du serveur.
        logger.error("Scan impossible, montage NAS introuvable : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Le montage NAS est introuvable. Voir les logs applicatifs.",
        ) from exc
    return ScanTriggerResponse(job_id=job_id, new_files_detected=new_files)


@router.post("/scan/retry-failed", response_model=RetryFailedResponse)
def retry_failed(db: Session = Depends(get_db)):
    failed = db.query(Magazine).filter(Magazine.scan_status == ScanStatus.failed).all()
    for magazine in failed:
        magazine.scan_status = ScanStatus.queued
        magazine.error_message = None
    # Un seul commit pour tout le lot, AVANT d'enfiler : un commit par
    # itération multiplie les allers-retours, et enfiler avant d'avoir
    # committé laisse le worker lire une ligne encore en statut « failed ».
    db.commit()
    for magazine in failed:
        ingestion_queue.enqueue(
            process_magazine, magazine.id, job_timeout="30m", on_failure=handle_process_magazine_failure
        )
    return RetryFailedResponse(retried=len(failed))


def _magazines_sans_sommaire(db: Session) -> list[Magazine]:
    """Numéros traités dont aucun article n'a pu être extrait."""
    return (
        db.query(Magazine)
        .filter(
            Magazine.scan_status == ScanStatus.done,
            ~Magazine.id.in_(db.query(Article.magazine_id).distinct()),
        )
        .all()
    )


@router.post("/magazines/reprocess-no-sommaire")
def reextract_sommaires(db: Session = Depends(get_db)):
    """Rejoue UNIQUEMENT l'extraction du sommaire, à partir du texte déjà
    en base. Ni OCR, ni appel Gemini : quelques minutes pour toute la
    bibliothèque, contre plusieurs heures pour un retraitement complet.

    C'est l'action attendue dans l'immense majorité des cas — après une
    amélioration du parseur, pour rattraper les numéros existants. Le texte
    OCR, lui, ne change pas : le refaire produirait exactement le même
    résultat pour un coût sans commune mesure.

    `scan_status` n'est volontairement PAS modifié : ces numéros restent
    « terminés », seule leur table d'articles est reconstruite. Les faire
    repasser en « en attente » brouillait le tableau de bord et laissait
    croire à une régression de l'OCR.

    Pour réellement refaire l'OCR, voir /magazines/reocr-no-sommaire.
    """
    magazines = _magazines_sans_sommaire(db)
    for magazine in magazines:
        ingestion_queue.enqueue(retry_toc, magazine.id, job_timeout="10m")
    logger.info("Réextraction des sommaires demandée pour %d numéro(s)", len(magazines))
    return {"reprocessed": len(magazines), "mode": "sommaire"}


@router.post("/magazines/reocr-no-sommaire")
def reocr_magazines_without_sommaire(db: Session = Depends(get_db)):
    """Relance le traitement COMPLET — OCR compris — des numéros sans
    sommaire. Opération longue : de l'ordre d'une minute par numéro.

    Utile dans un seul cas : la logique de décision OCR a changé (détection
    du texte natif, du texte illisible…) et il faut réellement reproduire
    le texte source. Si seul le parseur du sommaire a évolué,
    /magazines/reprocess-no-sommaire suffit et coûte cent fois moins.

    Endpoint distinct, et non un paramètre du précédent : la différence de
    coût est telle qu'elle mérite un appel explicite plutôt qu'un drapeau
    qu'on oublie de renseigner.
    """
    magazines = _magazines_sans_sommaire(db)
    for magazine in magazines:
        magazine.scan_status = ScanStatus.queued
        magazine.error_message = None
    # Même logique que retry_failed : un commit pour le lot, puis l'enfilement.
    db.commit()
    for magazine in magazines:
        ingestion_queue.enqueue(
            process_magazine, magazine.id, job_timeout="30m", on_failure=handle_process_magazine_failure
        )
    logger.warning("OCR complet relancé pour %d numéro(s) sans sommaire", len(magazines))
    return {"reprocessed": len(magazines), "mode": "ocr"}


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
    ingestion_queue.enqueue(
        process_magazine, magazine_id, job_timeout="30m", on_failure=handle_process_magazine_failure
    )
    return {"status": "queued"}


@router.get("/scan/current")
def current_scan():
    """The most recently triggered scan's job id, if any, so the dashboard can
    resume showing its progress after a page reload."""
    return {"job_id": get_latest_scan_job_id()}


@router.get("/magazines/{magazine_id}/progress", response_model=MagazineProgressResponse | None)
def get_magazine_progress_endpoint(magazine_id: int, db: Session = Depends(get_db)):
    """Live page-processing progress for a magazine currently being OCR'd
    and indexed (see app.services.progress) - null once it's done, failed,
    or was never started, since the underlying Redis key is cleared then."""
    # Un identifiant inexistant renvoyait 200 avec un corps null, exactement
    # comme un numéro déjà traité : le client ne pouvait pas distinguer les
    # deux cas.
    if not db.get(Magazine, magazine_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Magazine not found")
    return get_magazine_progress(magazine_id)


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

    # Deux jointures sortantes dans la même requête produisent un produit
    # cartésien : sans « distinct », un numéro de 80 pages et 12 articles
    # compterait 960 pages et 960 articles. article_count restait par ailleurs
    # à 0 côté tableau de bord, faute d'être calculé.
    recent_rows = (
        db.query(
            Magazine,
            func.count(distinct(Page.id)),
            func.count(distinct(Article.id)),
        )
        .outerjoin(Page, Page.magazine_id == Magazine.id)
        .outerjoin(Article, Article.magazine_id == Magazine.id)
        .group_by(Magazine.id)
        .order_by(Magazine.updated_at.desc())
        .limit(10)
        .all()
    )
    recent = []
    for magazine, page_count, article_count in recent_rows:
        out = MagazineOut.model_validate(magazine)
        out.page_count = page_count
        out.article_count = article_count
        recent.append(out)

    # Couverture de la taxonomie, mesurée au niveau de l'ARTICLE.
    #
    # Les compteurs précédents s'appuyaient sur `Magazine.themed_at`, qui est
    # posé sur tout numéro parcouru par le lot Gemini, y compris quand le
    # modèle ne lui a attribué aucune thématique : ils surestimaient donc la
    # couverture. Et depuis que la navigation par sujet passe par la taxonomie
    # par article, ils ne mesuraient plus ce qui intéresse.
    #
    # `articles_rattaches` compte les articles DISTINCTS : un article peut
    # relever de plusieurs sous-thématiques, le compter une fois par
    # rattachement gonflerait artificiellement le total.
    articles_total = db.query(Article).count()
    articles_rattaches = db.query(subtheme_articles.c.article_id).distinct().count()

    return AdminStatsResponse(
        total=sum(counts.values()),
        done=count_of(ScanStatus.done),
        processing=count_of(ScanStatus.processing),
        failed=count_of(ScanStatus.failed),
        pending=count_of(ScanStatus.detected, ScanStatus.stable, ScanStatus.queued),
        articles_total=articles_total,
        articles_rattaches=articles_rattaches,
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


@router.post("/articles/deduplicate")
def deduplicate_articles(
    dry_run: bool = Query(
        True,
        description="Compter sans supprimer. Passer explicitement false pour appliquer.",
    ),
    db: Session = Depends(get_db),
):
    """One-off cleanup for exact-duplicate Article rows: a race between two
    concurrent extraction runs for the same magazine (e.g. a full reprocess
    and a TOC-only retry overlapping, or the same action double-clicked)
    could each delete only what the other hadn't committed yet, so both
    runs' rows ended up side by side - see extract_and_store_articles's
    row lock, which now prevents this from recurring. Keeps the oldest row
    per (magazine_id, title, start_page)."""
    # NOTE : le regroupement ignore end_page. Deux articles de même titre et
    # même page de début mais de pages de fin différentes sont donc traités
    # comme des doublons, et le plus récent est supprimé. Vérifier le compte
    # en dry-run avant d'appliquer.
    keep_ids = (
        db.query(func.min(Article.id).label("id"))
        .group_by(Article.magazine_id, Article.title, Article.start_page)
        .subquery()
    )
    doublons = db.query(Article).filter(~Article.id.in_(db.query(keep_ids.c.id)))

    if dry_run:
        # Aucune écriture : on renvoie ce qui SERAIT supprimé.
        return {"deleted": 0, "would_delete": doublons.count(), "dry_run": True}

    deleted = doublons.delete(synchronize_session=False)
    db.commit()
    logger.warning("Déduplication des articles : %d ligne(s) supprimée(s)", deleted)
    return {"deleted": deleted, "would_delete": deleted, "dry_run": False}


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
    model = get_gemini_model(db)
    return GeminiSettingsResponse(
        model=model,
        available_models=AVAILABLE_GEMINI_MODELS,
        daily_request_limit=get_gemini_daily_limit(db),
        rpm_limit=get_gemini_rpm_limit(db),
        requests_used_today=get_gemini_usage_today(model),
    )


@router.put("/settings/gemini", response_model=GeminiSettingsResponse)
def update_gemini_settings(payload: GeminiSettingsUpdate, db: Session = Depends(get_db)):
    set_gemini_model(db, payload.model)
    set_gemini_daily_limit(db, payload.daily_request_limit)
    set_gemini_rpm_limit(db, payload.rpm_limit)
    model = get_gemini_model(db)
    return GeminiSettingsResponse(
        model=model,
        available_models=AVAILABLE_GEMINI_MODELS,
        daily_request_limit=get_gemini_daily_limit(db),
        rpm_limit=get_gemini_rpm_limit(db),
        requests_used_today=get_gemini_usage_today(model),
    )


# ---- Tags ----


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    page: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return db.query(Tag).order_by(Tag.name).offset(page * limit).limit(limit).all()


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    if db.query(Tag).filter(Tag.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")
    tag = Tag(name=payload.name, is_subject=payload.is_subject)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    tag.name = payload.name
    # None signifie « ne pas toucher » : les appels existants n'envoient que
    # le nom et ne doivent pas remettre la nature du tag à faux au passage.
    if payload.is_subject is not None:
        tag.is_subject = payload.is_subject
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    db.delete(tag)
    db.commit()


# ---- Collections ----


def _to_collection_out(collection: Collection) -> CollectionOut:
    return CollectionOut(
        id=collection.id,
        name=collection.name,
        tags=[TagOut(id=t.id, name=t.name) for t in collection.tags],
    )


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(
    page: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    collections = db.query(Collection).order_by(Collection.name).offset(page * limit).limit(limit).all()
    return [_to_collection_out(c) for c in collections]


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: int, payload: CollectionUpdate, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    collection.name = payload.name
    db.commit()
    db.refresh(collection)
    return _to_collection_out(collection)


@router.put("/collections/{collection_id}/tags", response_model=CollectionOut)
def set_collection_tags(collection_id: int, payload: CollectionTagsUpdate, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()
    if len(tags) != len(set(payload.tag_ids)):
        # 422 et non 404 : la ressource visée par l'URL (la collection) existe
        # bien, c'est le corps de la requête qui référence des tags absents.
        # Un 404 laissait croire que la collection elle-même était introuvable.
        connus = {t.id for t in tags}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tags inconnus : {sorted(set(payload.tag_ids) - connus)}",
        )

    collection.tags = tags
    db.commit()
    db.refresh(collection)

    magazine_ids = [m.id for m in db.query(Magazine.id).filter(Magazine.collection_id == collection_id).all()]
    for magazine_id in magazine_ids:
        ingestion_queue.enqueue(reindex_magazine, magazine_id, job_timeout="10m")

    return _to_collection_out(collection)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    magazine_ids = [m.id for m in db.query(Magazine.id).filter(Magazine.collection_id == collection_id).all()]
    db.delete(collection)
    db.commit()
    for magazine_id in magazine_ids:
        ingestion_queue.enqueue(reindex_magazine, magazine_id, job_timeout="10m")




@router.post("/search-index/reindex-all")
def reindex_all(db: Session = Depends(get_db)):
    """Re-push every processed magazine's pages to Meilisearch. Needed once
    after adding a new filterable field (e.g. tag_ids) so already-indexed
    documents pick it up - going forward, changes reindex automatically."""
    magazine_ids = [m.id for m in db.query(Magazine.id).filter(Magazine.scan_status == ScanStatus.done).all()]
    for magazine_id in magazine_ids:
        ingestion_queue.enqueue(reindex_magazine, magazine_id, job_timeout="10m")
    return {"enqueued": len(magazine_ids)}


@router.get("/themes/export", response_model=CorpusExportOut)
def corpus_export_summary(db: Session = Depends(get_db)):
    """Volumétrie du corpus, sans charger les titres.

    Sert à afficher ce que pèse l'export avant de le télécharger : au-delà
    d'environ 150 000 caractères, le corpus ne tiendra pas dans une seule
    invite et il faudra le soumettre en plusieurs fois.
    """
    return CorpusExportOut(**resume(db))


@router.get("/themes/export/file")
def download_corpus_export(db: Session = Depends(get_db)):
    """Le corpus complet, groupé par collection, prêt pour un modèle externe.

    Un seul fichier : un découpage par collection ferait diverger la taxonomie
    d'une revue à l'autre, sans rien pour les réconcilier ensuite. La consigne
    est incluse — rien à retenir au moment de solliciter le modèle.
    """
    charge = charge_utile(db)
    return Response(
        content=json.dumps(charge, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nom_de_fichier()},
    )


@router.get("/themes/orphans/export", response_model=OrphansExportOut)
def orphans_export_summary(db: Session = Depends(get_db)):
    """Volumétrie des orphelins, sans charger les titres.

    Distincte de celle du corpus complet : c'est le volume À CLASSER qui
    décide s'il faudra plusieurs envois, pas celui de la bibliothèque.
    """
    return OrphansExportOut(**resume_orphelins(db))


@router.get("/themes/orphans/export/file")
def download_orphans_export(db: Session = Depends(get_db)):
    """Les articles non rattachés, avec la taxonomie déjà en place.

    Le corpus complet sert à bâtir une taxonomie de zéro ; celui-ci sert à
    l'étendre. Soumettre les 13 500 titres pour n'obtenir que des ajouts noie
    le signal et consomme du contexte pour rien.

    La taxonomie existante accompagne les orphelins : sans elle, le modèle
    recrée sous un nom voisin ce qui existe déjà. La consigne est incluse,
    avec les trois contraintes réelles du code d'import.
    """
    charge = charge_utile_orphelins(db)
    return Response(
        content=json.dumps(charge, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nom_de_fichier_orphelins()},
    )


# Un fichier de sous-thématiques pèse quelques kilo-octets. Le plafond écarte
# un dépôt manifestement erroné avant de charger quoi que ce soit en mémoire.
TAILLE_MAX_IMPORT_OCTETS = 2 * 1024 * 1024


@router.post("/themes/import")
async def import_subthemes(
    fichier: UploadFile = File(...),
    appliquer: bool = Query(False, description="Écrire réellement ; simulation sinon"),
    db: Session = Depends(get_db),
):
    """Injecte la réponse d'un modèle de langage et rend le compte rendu.

    SIMULATION PAR DÉFAUT : sans `appliquer=true`, la transaction est annulée
    et rien n'est écrit. L'appelant voit ce qui se produirait — numéros
    rattachés, mots-clés sans correspondance, numéros laissés de côté — avant
    de décider.
    """
    contenu = await fichier.read(TAILLE_MAX_IMPORT_OCTETS + 1)
    if len(contenu) > TAILLE_MAX_IMPORT_OCTETS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux (%d Ko maximum)." % (TAILLE_MAX_IMPORT_OCTETS // 1024),
        )

    try:
        charge = json.loads(contenu.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # Le cas le plus fréquent : la réponse du modèle a été copiée avec son
        # habillage (```json ...```), ou tronquée. Le dire plutôt que de
        # renvoyer une erreur de bas niveau.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON illisible : %s. Vérifiez que le fichier ne contient que le JSON, sans texte autour." % exc,
        ) from exc

    try:
        return importer(db, charge, appliquer)
    except ImportInvalide as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/themes/subthemes/orphans", response_model=OrphansOut)
def subtheme_orphans(db: Session = Depends(get_db)):
    """Articles rattachés à aucune sous-thématique, et mots qui y dominent.

    Gratuit et instantané : aucun modèle n'intervient. Un terme qui revient
    cinquante fois parmi les orphelins et qu'aucun mot-clé ne couvre se voit
    à l'œil — il suffit alors de compléter la taxonomie.
    """
    return OrphansOut(**articles_orphelins(db))


@router.post("/themes/subthemes/recompute")
def recompute_subthemes(
    appliquer: bool = Query(False, description="Écrire réellement ; simulation sinon"),
    db: Session = Depends(get_db),
):
    """Rejoue le rattachement de toutes les sous-thématiques existantes.

    Sans appel à un modèle : les mots-clés sont conservés en base. À lancer
    après l'arrivée de nouveaux numéros, pour qu'ils rejoignent les
    regroupements déjà définis.
    """
    return recalculer_tout(db, appliquer)


@router.post("/tags/propagate")
def propagate_subject_tags(
    appliquer: bool = Query(False, description="Écrire réellement ; simulation sinon"),
    db: Session = Depends(get_db),
):
    """Attache aux numéros les thématiques héritées des tags de sujet.

    SIMULATION PAR DÉFAUT. Gratuit et instantané : aucun appel à un modèle,
    le tag de collection est une donnée déjà curée par l'administrateur.

    `themed_at` n'est pas renseigné : les numéros restent dans la file de
    thématisation, et le modèle viendra affiner. Le tag fournit le socle, le
    modèle l'enrichit.
    """
    return propager(db, appliquer)


@router.post("/themes/regenerate-all")
def regenerate_all_themes(db: Session = Depends(get_db)):
    """Force-regenerate themes for every processed magazine, even ones that
    already have some - unlike reindexing the search index, theme
    assignment is otherwise only ever computed once per magazine, so a
    magazine left at 0 themes by a past transient Gemini failure has no
    other way to retry.

    Resets themed_at (and clears any existing themes) so every magazine
    looks "pending" again, then hands off to the same batched pipeline
    used after ordinary OCR completion (process_pending_theme_batch,
    THEME_BATCH_SIZE magazines per Gemini request) - not one job per
    magazine, which would burn one full Gemini request per magazine and
    could exhaust the whole day's quota from a single click on any
    library past a couple of dozen magazines.
    """
    # Seul themed_at est remis à zéro : les thèmes existants sont CONSERVÉS
    # jusqu'à ce qu'un lot les remplace effectivement.
    #
    # Auparavant, `magazine.themes = []` vidait toute la bibliothèque d'un
    # coup, avant le moindre appel à Gemini. Un dépassement de quota en cours
    # de série — inévitable au-delà de quelques dizaines de numéros — laissait
    # donc la bibliothèque amputée, sans reprise automatique, et recliquer
    # re-purgeait ce qui venait d'être régénéré.
    #
    # Désormais l'opération est idempotente et sans perte : chaque numéro
    # garde ses thèmes actuels jusqu'à son remplacement, et une chaîne
    # interrompue se reprend simplement en recliquant — themed_at marquant
    # déjà ce qui a été traité.
    magazines = db.query(Magazine).filter(Magazine.scan_status == ScanStatus.done).all()
    for magazine in magazines:
        magazine.themed_at = None
    db.commit()
    ingestion_queue.enqueue(process_pending_theme_batch, job_timeout="15m")
    return {"enqueued": len(magazines)}


@router.post("/collections/backfill")
def backfill_collections_endpoint():
    """Recompute every magazine's collection, issue_type, issue_number,
    publication_date and month label from its stored file path/title,
    fixing magazines scanned before this metadata was derived automatically
    as well as ones mis-assigned by an older heuristic. Runs in the
    background (see run_collections_backfill) - at hundreds of magazines
    the full loop can comfortably exceed a typical reverse-proxy timeout
    if run synchronously inside this request."""
    ingestion_queue.enqueue(run_collections_backfill, job_timeout="30m")
    return {"status": "queued"}
