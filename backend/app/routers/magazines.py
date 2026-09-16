import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, IssueType, Magazine, Page, ScanStatus, collection_tags
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
    unassigned: bool = Query(False, description="Restrict to magazines with no collection assigned"),
    year: int | None = Query(None, description="Restrict to magazines published in this year"),
    issue_type: IssueType | None = Query(None, description="Restrict to magazines of this issue type"),
    scan_status: list[ScanStatus] | None = Query(None, description="Restrict to magazines with one of these scan statuses (repeat the param for several)"),
    has_sommaire: bool | None = Query(None, description="Restrict to magazines with (true) or without (false) at least one article"),
    db: Session = Depends(get_db),
):
    query = _apply_magazine_filters(
        db.query(Magazine.id), tag_id, collection_id, unassigned, year, issue_type, scan_status, has_sommaire
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
        query, tag_id, collection_id, unassigned, year, issue_type, scan_status, has_sommaire
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


# La couverture est reecrite au meme emplacement a chaque retraitement OCR
# (tasks.py reaffecte cover_thumbnail_path) : pas d'immutable, sinon une
# vignette perimee resterait affichee indefiniment. Un jour de cache, puis
# revalidation via le ETag/Last-Modified que FileResponse pose deja.
CACHE_COUVERTURE = "private, max-age=86400"

# Le PDF est lourd et relu page apres page : le garder une heure evite de le
# retelecharger a chaque reouverture du lecteur. Duree courte car un
# retraitement OCR le remplace au meme emplacement.
CACHE_PDF = "private, max-age=3600"

# Starlette 0.38 ne gere pas l'en-tete Range sur FileResponse (verifie sur
# l'image deployee). Consequence : chaque ouverture du lecteur telechargeait
# le PDF entier — 36 Mo pour un Computer Music — pour afficher une seule page,
# et arriver page 87 depuis un resultat de recherche imposait de rapatrier
# tout le reste. pdf.js sait ne demander que les octets utiles, mais seulement
# si le serveur annonce « Accept-Ranges ».
#
# On ne traite qu'UNE plage par requete. C'est ce qu'emet pdf.js, et repondre
# au cas general (plages multiples en multipart/byteranges) couterait bien
# plus a ecrire et a maintenir que ce que ca rapporterait ici.
_PLAGE_RE = re.compile(r"^bytes=(?P<debut>\d*)-(?P<fin>\d*)$")

# 64 Kio : assez grand pour ne pas multiplier les allers-retours disque, assez
# petit pour ne pas charger une plage entiere en memoire quand pdf.js en
# demande une grosse.
TAILLE_MORCEAU = 64 * 1024


def _lire_plage(chemin: Path, debut: int, longueur: int) -> Iterator[bytes]:
    """Rend le contenu du fichier par morceaux, sans le charger en entier."""
    with chemin.open("rb") as fichier:
        fichier.seek(debut)
        restant = longueur
        while restant > 0:
            morceau = fichier.read(min(TAILLE_MORCEAU, restant))
            if not morceau:
                break
            restant -= len(morceau)
            yield morceau


def _servir_pdf(chemin: Path, nom: str, disposition: str, requete: Request, cache: str | None):
    """Sert un PDF en honorant l'en-tete Range quand le client en envoie un.

    Sans en-tete Range, ou avec un en-tete qu'on ne sait pas lire, on retombe
    sur la reponse complete habituelle — mais en annoncant « Accept-Ranges »,
    sans quoi le client ne tenterait jamais de requete partielle.
    """
    taille = chemin.stat().st_size
    entetes = {"Accept-Ranges": "bytes"}
    if cache:
        entetes["Cache-Control"] = cache

    brut = requete.headers.get("range")
    correspondance = _PLAGE_RE.match(brut.strip()) if brut else None
    if correspondance is None:
        return FileResponse(
            chemin,
            media_type="application/pdf",
            filename=nom,
            content_disposition_type=disposition,
            headers=entetes,
        )

    debut_txt, fin_txt = correspondance.group("debut"), correspondance.group("fin")
    if not debut_txt and not fin_txt:
        # « bytes=- » ne designe rien : on sert tout plutot que d'echouer.
        return FileResponse(
            chemin,
            media_type="application/pdf",
            filename=nom,
            content_disposition_type=disposition,
            headers=entetes,
        )

    if not debut_txt:
        # Forme suffixe « bytes=-500 » : les 500 derniers octets.
        longueur = min(int(fin_txt), taille)
        debut, fin = taille - longueur, taille - 1
    else:
        debut = int(debut_txt)
        fin = min(int(fin_txt), taille - 1) if fin_txt else taille - 1

    if debut >= taille or debut > fin:
        # 416 obligatoire : renvoyer 200 ferait croire au client que sa plage
        # a ete servie, et pdf.js interpreterait le fichier de travers.
        return Response(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={**entetes, "Content-Range": f"bytes */{taille}"},
        )

    longueur = fin - debut + 1
    return StreamingResponse(
        _lire_plage(chemin, debut, longueur),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type="application/pdf",
        headers={
            **entetes,
            "Content-Range": f"bytes {debut}-{fin}/{taille}",
            "Content-Length": str(longueur),
            "Content-Disposition": f'{disposition}; filename="{nom}"',
        },
    )


@router.get("/{magazine_id}/cover")
def get_cover(magazine_id: int, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    if not magazine.cover_thumbnail_path or not Path(magazine.cover_thumbnail_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover not available")
    # Le type MIME suit l'extension reelle du fichier : les vignettes produites
    # avant la bascule vers WebP sont encore en PNG sur le disque, et les
    # annoncer en image/webp les rendrait indechiffrables pour le navigateur.
    chemin = Path(magazine.cover_thumbnail_path)
    return FileResponse(
        chemin,
        media_type="image/webp" if chemin.suffix.lower() == ".webp" else "image/png",
        headers={"Cache-Control": CACHE_COUVERTURE},
    )


@router.get("/{magazine_id}/file")
def view_file(magazine_id: int, requete: Request, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    pdf_path = _resolve_pdf_path(magazine)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not available")
    return _servir_pdf(pdf_path, magazine.filename, "inline", requete, CACHE_PDF)


@router.get("/{magazine_id}/download")
def download_file(magazine_id: int, requete: Request, db: Session = Depends(get_db)):
    magazine = _get_magazine_or_404(magazine_id, db)
    pdf_path = _resolve_pdf_path(magazine)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not available")
    # Pas de Cache-Control ici : un telechargement est un geste ponctuel. En
    # revanche il beneficie aussi des plages, donc il devient reprenable apres
    # une coupure.
    return _servir_pdf(pdf_path, magazine.filename, "attachment", requete, None)
